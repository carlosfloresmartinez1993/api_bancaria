import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, Field

from app.schemas.comun import Dinero, ORMModel, TextoCorto


class SalidaCrear(BaseModel):
    proyecto_id: uuid.UUID
    monto: Dinero
    destino: TextoCorto
    metodo_pago_id: uuid.UUID
    fecha: date | None = Field(default=None, description="Por defecto, hoy")
    observaciones: str | None = Field(default=None, max_length=2000)


class SalidaActualizar(BaseModel):
    proyecto_id: uuid.UUID | None = None
    monto: Dinero | None = None
    destino: TextoCorto | None = None
    metodo_pago_id: uuid.UUID | None = None
    fecha: date | None = None
    observaciones: str | None = Field(default=None, max_length=2000)
    motivo: str | None = Field(default=None, max_length=500, description="Se guarda en la bitácora")


class SalidaOut(ORMModel):
    id: uuid.UUID
    proyecto_id: uuid.UUID
    terminal_id: uuid.UUID
    empresa_id: uuid.UUID | None
    usuario_id: uuid.UUID
    metodo_pago_id: uuid.UUID
    monto: Decimal
    destino: str
    fecha: date
    observaciones: str | None
    fecha_registro: datetime


class SalidaRegistrada(BaseModel):
    salida: SalidaOut
    saldo_proyecto: Decimal
    saldo_empresa: Decimal | None = None  # nulo si el cliente no tiene empresa
    advertencia: str | None = None
