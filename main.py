import os
from typing import List
from dotenv import load_dotenv

from fastapi import FastAPI, HTTPException, Depends, status, BackgroundTasks
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from proxmoxer import ProxmoxAPI

import database
import models
import schemas
import scheduler
import vmware
import ansible_runner

# Cargar variables de entorno desde el archivo .env
load_dotenv()

# Configuración de Proxmox en VMware NAT (IP 192.168.8.50)
PROXMOX_HOST = os.getenv("PROXMOX_HOST", "192.168.8.50")
PROXMOX_USER = os.getenv("PROXMOX_USER", "root@pam")
PROXMOX_PASSWORD = os.getenv("PROXMOX_PASSWORD", "123456789")
PROXMOX_NODE = os.getenv("PROXMOX_NODE", "pve")

# Inicialización de la aplicación FastAPI
app = FastAPI(title="Orion Cloud API - Control Plane")

# 1. Montar carpeta para la interfaz estática si existe
if os.path.exists("static"):
    app.mount("/static", StaticFiles(directory="static"), name="static")

# 2. Inicializar Base de Datos SQLite y el sistema de Auto-Healing
database.init_db()
scheduler.iniciar_auto_healing()


def get_proxmox_client() -> ProxmoxAPI:
    """Crea y retorna un cliente de conexión a la API de Proxmox VE."""
    try:
        return ProxmoxAPI(
            PROXMOX_HOST,
            user=PROXMOX_USER,
            password=PROXMOX_PASSWORD,
            verify_ssl=False
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error de conexión a Proxmox ({PROXMOX_HOST}): {str(e)}"
        )


# --- RUTAS DE LA INTERFAZ WEB Y ESTADO ---

@app.get("/dashboard")
def ver_dashboard():
    """Sirve la interfaz web visual desde static/index.html"""
    if os.path.exists("static/index.html"):
        return FileResponse("static/index.html")
    return {"message": "Interfaz gráfica no encontrada en static/index.html"}


@app.get("/")
def read_root():
    return {"message": "Bienvenido a Orion Cloud API"}


@app.get("/status")
def get_status():
    return {"status": "ok", "service": "Orion Cloud Backend"}


@app.get("/proxmox/status")
def get_proxmox_status():
    """Verifica si FastAPI puede comunicarse con Proxmox en 192.168.8.50"""
    try:
        proxmox = get_proxmox_client()
        version_info = proxmox.version.get()
        return {
            "status": "connected",
            "proxmox_version": version_info.get("version"),
            "host": PROXMOX_HOST
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"No se pudo consultar Proxmox ({PROXMOX_HOST}): {str(e)}"
        )


# --- RUTAS DE ADMINISTRACIÓN DE SERVIDORES ---

@app.post("/crear-servidor", response_model=schemas.ServidorResponse, status_code=status.HTTP_201_CREATED)
def crear_servidor(
    data: schemas.ServidorCreate, 
    background_tasks: BackgroundTasks, 
    db: Session = Depends(database.get_db)
):
    # 1. Validar si el VMID ya existe en la base de datos local
    servidor_existente = db.query(models.Inventario).filter(models.Inventario.vmid == data.vmid).first()
    if servidor_existente:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"El servidor con VMID {data.vmid} ya existe en el inventario local."
        )

    # 2. Intentar la creación real en Proxmox VE
    try:
        proxmox = get_proxmox_client()
        if data.tipo == "lxc":
            proxmox.nodes(PROXMOX_NODE).lxc.create(
                vmid=data.vmid,
                hostname=data.nombre,
                ostemplate="local:vztmpl/ubuntu-22.04-standard_22.04-1_amd64.tar.zst",
                storage="local-lvm",
                rootfs="local-lvm:8",
                memory=1024,
                cores=1,
                password="PasswordSeguro123!",
                net0="name=eth0,bridge=vmbr0,ip=dhcp",
                start=1
            )
        elif data.tipo == "vm":
            proxmox.nodes(PROXMOX_NODE).qemu.create(
                vmid=data.vmid,
                name=data.nombre,
                memory=2048,
                cores=2,
                scsihw="virtio-scsi-pci",
                scsi0="local-lvm:16",
                net0="virtio,bridge=vmbr0",
                start=0
            )
    except Exception as e:
        print(f"[Warning/Error Proxmox] Fallo al crear en hipervisor: {e}")
        # Descomenta la siguiente línea si deseas bloquear el guardado local en caso de error en Proxmox:
        # raise HTTPException(status_code=500, detail=f"Error en Proxmox: {str(e)}")

    # 3. Guardar en Base de Datos SQLite
    nuevo_recurso = models.Inventario(
        vmid=data.vmid,
        nombre=data.nombre,
        tipo=data.tipo,
        estado="running" if data.tipo == "lxc" else "stopped"
    )
    db.add(nuevo_recurso)
    db.commit()
    db.refresh(nuevo_recurso)

    # 4. Programar ejecución de Ansible en SEGUNDO PLANO
    ip_asignada = f"192.168.8.{data.vmid}" 
    rol_ansible = data.rol if data.rol else "web"

    background_tasks.add_task(
        ansible_runner.actualizar_inventario_y_ejecutar, 
        rol=rol_ansible, 
        ip_servidor=ip_asignada
    )

    return nuevo_recurso


@app.get("/inventario", response_model=List[schemas.ServidorResponse])
def obtener_inventario(db: Session = Depends(database.get_db)):
    return db.query(models.Inventario).all()


# --- RUTAS DE ACCIÓN SOBRE SERVIDORES ---

@app.post("/servidor/{vmid}/iniciar")
def iniciar_servidor(vmid: int, db: Session = Depends(database.get_db)):
    srv = db.query(models.Inventario).filter(models.Inventario.vmid == vmid).first()
    if not srv:
        raise HTTPException(status_code=404, detail="Servidor no encontrado")

    try:
        proxmox = get_proxmox_client()
        if srv.tipo == "lxc":
            proxmox.nodes(PROXMOX_NODE).lxc(vmid).status.start.post()
        else:
            proxmox.nodes(PROXMOX_NODE).qemu(vmid).status.start.post()
    except Exception as e:
        print(f"[Aviso Proxmox] Inicio para VMID {vmid}: {e}")

    srv.estado = "running"
    db.commit()
    return {"mensaje": f"Servidor {vmid} iniciado"}


@app.post("/servidor/{vmid}/detener")
def detener_servidor(vmid: int, db: Session = Depends(database.get_db)):
    srv = db.query(models.Inventario).filter(models.Inventario.vmid == vmid).first()
    if not srv:
        raise HTTPException(status_code=404, detail="Servidor no encontrado")

    try:
        proxmox = get_proxmox_client()
        if srv.tipo == "lxc":
            proxmox.nodes(PROXMOX_NODE).lxc(vmid).status.stop.post()
        else:
            proxmox.nodes(PROXMOX_NODE).qemu(vmid).status.stop.post()
    except Exception as e:
        print(f"[Aviso Proxmox] Paro para VMID {vmid}: {e}")

    srv.estado = "stopped"
    db.commit()
    return {"mensaje": f"Servidor {vmid} detenido"}


@app.delete("/servidor/{vmid}")
def eliminar_servidor(vmid: int, db: Session = Depends(database.get_db)):
    srv = db.query(models.Inventario).filter(models.Inventario.vmid == vmid).first()
    if not srv:
        raise HTTPException(status_code=404, detail="Servidor no encontrado")

    try:
        proxmox = get_proxmox_client()
        if srv.tipo == "lxc":
            proxmox.nodes(PROXMOX_NODE).lxc(vmid).delete()
        else:
            proxmox.nodes(PROXMOX_NODE).qemu(vmid).delete()
    except Exception as e:
        print(f"[Aviso Proxmox] Eliminación para VMID {vmid}: {e}")

    db.delete(srv)
    db.commit()
    return {"mensaje": f"Servidor {vmid} eliminado"}


@app.post("/crear-nodo-proxmox")
def desplegar_nodo_proxmox(nombre_nodo: str):
    """Endpoint para crear un nuevo hipervisor Proxmox VE sobre VMware"""
    resultado = vmware.crear_nodo_proxmox_en_vmware(
        nombre_nodo=nombre_nodo,
        esxi_host=os.getenv("ESXI_HOST", "192.168.8.100"),
        esxi_user=os.getenv("ESXI_USER", "root"),
        esxi_pass=os.getenv("ESXI_PASS", "123456789")
    )
    return resultado