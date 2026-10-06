import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, Field

from app.schemas.comun import ORMModel, Porcentaje


class TerminalCrear(BaseModel):
    empresa_id: uuid.UUID
    identificador_terminal: str = Field(min_length=1, max_length=100)
    porcentaje_inicial: Porcentaje
    vigente_desde: date | None = Field(
        default=None, description="Desde qué día rige el porcentaje inicial (por defecto, hoy)"
    )
    datos_extra: dict[str, Any] = Field(default_factory=dict)


class TerminalActualizar(BaseModel):
    identificador_terminal: str | None = Field(default=None, min_length=1, max_length=100)
    datos_extra: dict[str, Any] | None = None


class TerminalOut(ORMModel):
    id: uuid.UUID
    empresa_id: uuid.UUID
    identificador_terminal: str
    activa: bool
    datos_extra: dict[str, Any]
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
    terminal_id: uuid.UUID
    porcentaje: Decimal
    fecha_inicio_vigencia: date
    fecha_fin_vigencia: date | None


class CambioPorcentajeOut(BaseModel):
    historial: HistorialOut
    movimientos_recalculados: int
