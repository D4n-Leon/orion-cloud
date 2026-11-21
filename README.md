# Orion Cloud - Private Cloud Control Plane

Plataforma de orquestación y administración para la gestión de infraestructura de nube privada multinivel. Integra aprovisionamiento de máquinas virtuales/contenedores en **Proxmox VE**, configuración automatizada de servicios mediante **Ansible**, despliegue de infraestructura base sobre **VMware ESXi**, monitoreo con **Auto-Healing** y un **Dashboard Web en tiempo real**.

---

## Arquitectura del Sistema

```text
               ┌────────────────────────────────────────┐
               │    Dashboard Web (HTML5 / JS Async)    │
               └───────────────────┬────────────────────┘
                                   │
                                   ▼
               ┌────────────────────────────────────────┐
               │   Orion Cloud API (FastAPI Control)    │
               └─────────┬────────────────────┬─────────┘
                         │                    │
         (Cada 15 seg)    ▼                    ▼   (En segundo plano)
        ┌──────────────────┐        ┌───────────────────┐
        │   Auto-Healing   │        │  Ansible Runner   │
        │   (Scheduler)    │        │  (Playbooks Exec) │
        └────────┬─────────┘        └─────────┬─────────┘
                 │                            │
                 ▼                            ▼
        ┌───────────────────────────────────────────────┐
        │           Servidor Proxmox VE                 │
        │  ┌───────────────────────┬─────────────────┐  │
        │  │  Contenedores (LXC)   │  VMs (QEMU)     │  │
        │  └───────────────────────┴─────────────────┘  │
        └───────────────────────┬───────────────────────┘
                                │
                                ▼
        ┌───────────────────────────────────────────────┐
        │          Hipervisor VMware ESXi               │
        └───────────────────────────────────────────────┘
```

---

## Características Principales

* **Control Plane Unificado (FastAPI):** Endpoints RESTful para la creación, inicio, paro y eliminación de recursos en Proxmox VE y VMware ESXi.
* **Auto-Healing de Infraestructura:** Proceso en segundo plano que audita la salud de cada servidor cada 5 minutos y restaura automáticamente las máquinas caídas.
* **Orquestación de Configuración con Ansible:** Inyección automática de IPs en `inventory.ini` y ejecución asíncrona de playbooks (`web`, `database`, `dns`, `firewall`, `monitoring`).
* **Dashboard Web Interactivo:** Interfaz responsiva con acciones directas (Start, Stop, Delete) y tabla con actualización de estado en vivo.
* **Resiliencia & Modos de Prueba:** Capacidad de registrar recursos en la BD local aun en escenarios de timeout de red con los servidores físicos.

---

## Estructura del Repositorio

```text
orion_cloud/
├── ansible/
│   ├── playbooks/             # Playbooks de Ansible (web.yml, database.yml, etc.)
│   ├── roles/                 # Roles modularizados
│   ├── ansible.cfg            # Configuración por defecto de Ansible
│   └── inventory.ini          # Inventario dinámico de hosts
├── static/
│   └── index.html             # Dashboard Web de control
├── .env                       # Variables de entorno y credenciales
├── ansible_runner.py          # Integrador de Ansible con FastAPI
├── database.py                # Conexión y sesión de SQLite (SQLAlchemy)
├── main.py                    # API principal de FastAPI y endpoints
├── models.py                  # Modelo ORM de la tabla 'inventario'
├── proxmox_service.py         # Cliente de comunicación con Proxmox API
├── requirements.txt           # Lista de dependencias de Python
├── scheduler.py               # Tarea programada de Auto-Healing (APScheduler)
├── schemas.py                 # Esquemas de validación de Pydantic
└── vmware.py                  # Conector pyVmomi para VMware ESXi
```

---

## Requisitos e Instalación

### 1. Clonar el repositorio e instalar dependencias:
```bash
git clone [https://github.com/tu-usuario/orion-cloud.git](https://github.com/tu-usuario/orion-cloud.git)
cd orion-cloud
python -m pip install -r requirements.txt
```

### 2. Configurar variables de entorno (`.env`):
Crea un archivo `.env` en la raíz del proyecto:
```env
PROXMOX_HOST=192.168.100.154
PROXMOX_USER=root@pam
PROXMOX_PASSWORD=tu_contraseña_proxmox
PROXMOX_NODE=pve
ESXI_HOST=192.168.100.100
ESXI_USER=root
ESXI_PASS=tu_contraseña_esxi
DATABASE_URL=sqlite:///./orion_cloud.db
```

### 3. Iniciar el servidor backend:
```bash
python -m uvicorn main:app --reload
```

---

## Uso de la Plataforma

* **Dashboard Web:** [http://localhost:8000/dashboard](http://localhost:8000/dashboard)
* **Documentación Interactiva (Swagger UI):** [http://localhost:8000/docs](http://localhost:8000/docs)

---

## Principales Endpoints de la API

| Método | Ruta | Descripción |
| :--- | :--- | :--- |
| `GET` | `/dashboard` | Sirve la interfaz gráfica web. |
| `GET` | `/inventario` | Obtiene la lista de servidores registrados en la BD. |
| `POST` | `/crear-servidor` | Crea un LXC/VM en Proxmox y dispara el Playbook de Ansible. |
| `POST` | `/servidor/{vmid}/iniciar` | Inicia una VM o LXC en Proxmox. |
| `POST` | `/servidor/{vmid}/detener` | Detiene una VM o LXC en Proxmox. |
| `DELETE` | `/servidor/{vmid}` | Elimina el recurso en Proxmox y la BD local. |
| `POST` | `/crear-nodo-proxmox` | Despliega un nuevo nodo Proxmox en VMware ESXi. |