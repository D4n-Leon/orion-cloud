import os
from proxmoxer import ProxmoxAPI
from dotenv import load_dotenv

# Cargar las variables definidas en el archivo .env
load_dotenv()

PROXMOX_HOST = os.getenv("PROXMOX_HOST", "192.168.8.50")
PROXMOX_USER = os.getenv("PROXMOX_USER", "root@pam")
PROXMOX_PASSWORD = os.getenv("PROXMOX_PASSWORD", "123456789")

def get_proxmox_client() -> ProxmoxAPI:
    """
    Crea y retorna una sesión autenticada con la API de Proxmox VE.
    """
    try:
        return ProxmoxAPI(
            PROXMOX_HOST,
            user=PROXMOX_USER,
            password=PROXMOX_PASSWORD,
            verify_ssl=False
        )
    except Exception as e:
        raise Exception(f"Error al inicializar cliente Proxmox: {str(e)}")