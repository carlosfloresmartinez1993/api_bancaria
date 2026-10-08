import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, Field

from app.schemas.comun import ORMModel, Porcentaje


class ProyectoCrear(BaseModel):
    terminal_id: uuid.UUID
    nombre: str = Field(min_length=1, max_length=100)
    porcentaje_inicial: Porcentaje
    vigente_desde: date | None = Field(
        default=None, description="Desde qué día rige el porcentaje inicial (por defecto, hoy)"
    )


class ProyectoActualizar(BaseModel):
    nombre: str | None = Field(default=None, min_length=1, max_length=100)


class ProyectoOut(ORMModel):
    id: uuid.UUID
    terminal_id: uuid.UUID
    empresa_id: uuid.UUID | None
    nombre: str
    activo: bool
    fecha_registro: datetime
    porcentaje_vigente: Decimal | None = None


class CambioPorcentaje(BaseModel):
    porcentaje: Porcentaje
    vigente_desde: date | None = Field(
        default=None,
        description=(
            "Día desde el que rige (por defecto, hoy). Puede ser una fecha pasada: "
            "los movimientos desde esa fecha se recalculan con el nuevo porcentaje."
        ),
    )
    motivo: str | None = Field(default=None, max_length=500)


class HistorialOut(ORMModel):
    id: uuid.UUID
    proyecto_id: uuid.UUID
    porcentaje: Decimal
    fecha_inicio_vigencia: date
    fecha_fin_vigencia: date | None


class CambioPorcentajeOut(BaseModel):
    historial: HistorialOut
    movimientos_recalculados: int
