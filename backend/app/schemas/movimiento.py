import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, Field

from app.schemas.comun import Dinero, ORMModel


class MovimientoCrear(BaseModel):
    terminal_id: uuid.UUID
    fecha_movimiento: date
    monto_bruto: Dinero
    observaciones: str | None = Field(default=None, max_length=2000)


class MovimientoActualizar(BaseModel):
    terminal_id: uuid.UUID | None = None
    fecha_movimiento: date | None = None
    monto_bruto: Dinero | None = None
    observaciones: str | None = Field(default=None, max_length=2000)
    motivo: str | None = Field(default=None, max_length=500, description="Se guarda en la bitácora")


class MovimientoOut(ORMModel):
    id: uuid.UUID
    terminal_id: uuid.UUID
    empresa_id: uuid.UUID
    usuario_id: uuid.UUID
    fecha_movimiento: date
    monto_bruto: Decimal
    porcentaje_aplicado: Decimal
    comision: Decimal
    monto_neto: Decimal
    fecha_captura: datetime
    observaciones: str | None
