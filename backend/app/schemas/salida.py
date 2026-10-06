import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, Field

from app.schemas.comun import Dinero, ORMModel, TextoCorto


class SalidaCrear(BaseModel):
    empresa_id: uuid.UUID
    monto: Dinero
    destino: TextoCorto
    fecha: date | None = Field(default=None, description="Por defecto, hoy")
    observaciones: str | None = Field(default=None, max_length=2000)


class SalidaActualizar(BaseModel):
    monto: Dinero | None = None
    destino: TextoCorto | None = None
    fecha: date | None = None
    observaciones: str | None = Field(default=None, max_length=2000)
    motivo: str | None = Field(default=None, max_length=500, description="Se guarda en la bitácora")


class SalidaOut(ORMModel):
    id: uuid.UUID
    empresa_id: uuid.UUID
    usuario_id: uuid.UUID
    monto: Decimal
    destino: str
    fecha: date
    observaciones: str | None
    fecha_registro: datetime


class SalidaRegistrada(BaseModel):
    salida: SalidaOut
    saldo_empresa: Decimal
    advertencia: str | None = None
