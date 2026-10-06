import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.comun import ORMModel


class MetodoPagoCrear(BaseModel):
    nombre: str = Field(min_length=1, max_length=50)


class MetodoPagoActualizar(BaseModel):
    nombre: str | None = Field(default=None, min_length=1, max_length=50)
    activo: bool | None = None


class MetodoPagoOut(ORMModel):
    id: uuid.UUID
    nombre: str
    activo: bool
    fecha_registro: datetime
