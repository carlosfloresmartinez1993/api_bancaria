import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, Field

from app.schemas.comun import Dinero, ORMModel


class MovimientoCrear(BaseModel):
    proyecto_id: uuid.UUID
    fecha_movimiento: date
    monto_bruto: Dinero
    metodo_pago_id: uuid.UUID
    requiere_factura: bool = False
    observaciones: str | None = Field(default=None, max_length=2000)


class MovimientoActualizar(BaseModel):
    proyecto_id: uuid.UUID | None = None
    fecha_movimiento: date | None = None
    monto_bruto: Dinero | None = None
    metodo_pago_id: uuid.UUID | None = None
    requiere_factura: bool | None = None
    observaciones: str | None = Field(default=None, max_length=2000)
    motivo: str | None = Field(default=None, max_length=500, description="Se guarda en la bitácora")


class MovimientoOut(ORMModel):
    id: uuid.UUID
    proyecto_id: uuid.UUID
    terminal_id: uuid.UUID
    empresa_id: uuid.UUID
    usuario_id: uuid.UUID
    metodo_pago_id: uuid.UUID
    fecha_movimiento: date
    monto_bruto: Decimal
    porcentaje_aplicado: Decimal
    comision: Decimal
    monto_neto: Decimal
    requiere_factura: bool
    fecha_captura: datetime
    observaciones: str | None
