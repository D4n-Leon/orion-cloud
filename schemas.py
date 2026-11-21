from pydantic import BaseModel, Field

from pydantic import BaseModel, Field
from typing import Optional

class ServidorCreate(BaseModel):
    vmid: int = Field(..., gt=100)
    nombre: str
    tipo: str = Field(..., pattern="^(vm|lxc)$")
    rol: Optional[str] = Field("web", description="Rol de Ansible: web, database, dns, firewall, monitoring")

class ServidorResponse(BaseModel):
    id: int
    vmid: int
    nombre: str
    tipo: str
    estado: str

    class Config:
        from_attributes = True