import os
import subprocess

ANSIBLE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ansible")

def actualizar_inventario_y_ejecutar(rol: str, ip_servidor: str):
    inventory_path = os.path.join(ANSIBLE_DIR, "inventory.ini")
    playbook_path = os.path.join(ANSIBLE_DIR, "playbooks", f"{rol}.yml")

    # 1. Actualizar la IP dentro de inventory.ini bajo el grupo [rol]
    if os.path.exists(inventory_path):
        with open(inventory_path, "r") as f:
            lineas = f.readlines()

        nuevo_contenido = []
        for linea in lineas:
            nuevo_contenido.append(linea)
            if linea.strip() == f"[{rol}]":
                nuevo_contenido.append(f"{ip_servidor} ansible_user=root\n")

        with open(inventory_path, "w") as f:
            f.writelines(nuevo_contenido)

    # 2. Invocación de Ansible
    if os.path.exists(playbook_path):
        print(f"[Ansible] Ejecutando playbook '{rol}.yml' para el host {ip_servidor}...")
        try:
            cmd = ["ansible-playbook", "-i", f"{ip_servidor},", playbook_path]
            resultado = subprocess.run(cmd, capture_output=True, text=True)
            print(f"[Ansible Log]:\n{resultado.stdout}")
        except Exception as e:
            print(f"[Ansible Aviso] No se pudo ejecutar el binario de Ansible en este sistema: {e}")
    else:
        print(f"[Ansible] No se encontró la ruta del playbook: {playbook_path}")