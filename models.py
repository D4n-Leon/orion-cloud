from sqlalchemy import Column, Integer, String
from database import Base

class Inventario(Base):
    __tablename__ = "inventario"

    id = Column(Integer, primary_key=True, index=True)
    vmid = Column(Integer, unique=True, index=True, nullable=False)
    nombre = Column(String, nullable=False)
    tipo = Column(String, nullable=False)
    estado = Column(String, nullable=False)