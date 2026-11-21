from apscheduler.schedulers.background import BackgroundScheduler
from proxmoxer import ProxmoxAPI
import database
import models

PROXMOX_HOST = "192.168.8.50"
PROXMOX_USER = "root@pam"
PROXMOX_PASSWORD = "123456789"
PROXMOX_NODE = "pve"

def revisar_y_recuperar():
    db = database.SessionLocal()
    try:
        servidores = db.query(models.Inventario).all()
        if not servidores:
            return

        proxmox = ProxmoxAPI(
            PROXMOX_HOST, 
            user=PROXMOX_USER, 
            password=PROXMOX_PASSWORD, 
            verify_ssl=False,
            timeout=5
        )

        for srv in servidores:
            # Solo intentamos recuperar si en la BD el servidor debería estar "running"
            if srv.estado in ["running", "recovering"]:
                try:
                    if srv.tipo == "lxc":
                        status_info = proxmox.nodes(PROXMOX_NODE).lxc(srv.vmid).status.current.get()
                    else:
                        status_info = proxmox.nodes(PROXMOX_NODE).qemu(srv.vmid).status.current.get()

                    estado_real = status_info.get("status")

                    if estado_real != "running":
                        print(f"[Auto-Healing] ⚠️ Restableciendo VMID {srv.vmid} ({srv.nombre})...")
                        if srv.tipo == "lxc":
                            proxmox.nodes(PROXMOX_NODE).lxc(srv.vmid).status.start.post()
                        else:
                            proxmox.nodes(PROXMOX_NODE).qemu(srv.vmid).status.start.post()
                        srv.estado = "recovering"
                    else:
                        srv.estado = "running"
                except Exception as e:
                    print(f"[Auto-Healing Error] Fallo al consultar VMID {srv.vmid}: {e}")
                    srv.estado = "error"

        db.commit()
    except Exception as general_err:
        print(f"[Auto-Healing Log Error]: {general_err}")
    finally:
        db.close()

def iniciar_auto_healing():
    sched = BackgroundScheduler()
    # Ejecutar cada 15 segundos en lugar de 5 minutos
    sched.add_job(revisar_y_recuperar, 'interval', seconds=15)
    sched.start()
    print("[Scheduler] 🚀 APScheduler de Auto-Healing activo (intervalo: 15 segundos).")