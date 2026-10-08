import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field

from app.schemas.comun import ORMModel


class TerminalCrear(BaseModel):
    empresa_id: uuid.UUID | None = Field(default=None, description="Vacío = cliente sin empresa")
    identificador_terminal: str = Field(min_length=1, max_length=100)
    usuario_id: uuid.UUID | None = Field(
        default=None, description="Solo admin y solo sin empresa: registrar el cliente a nombre de un contador"
    )


class TerminalActualizar(BaseModel):
    identificador_terminal: str | None = Field(default=None, min_length=1, max_length=100)


class TerminalOut(ORMModel):
    id: uuid.UUID
    empresa_id: uuid.UUID | None
    usuario_id: uuid.UUID
    identificador_terminal: str
    activa: bool
    fecha_registro: datetime
    num_proyectos: int = 0


class MoverCliente(BaseModel):
    empresa_id: uuid.UUID | None = Field(description="Empresa destino; nulo = dejar el cliente sin empresa")
    motivo: str | None = Field(default=None, max_length=500)


class RevertirMovimiento(BaseModel):
    motivo: str | None = Field(default=None, max_length=500)


class ReasignarCliente(BaseModel):
    usuario_id: uuid.UUID


class MovimientoClienteOut(BaseModel):
    """Un cambio de empresa del cliente, tomado de la bitácora."""

    id: uuid.UUID
    fecha: datetime
    realizado_por: str
    empresa_antes: str
    empresa_despues: str
    saldo_movido: Decimal | None
    motivo: str | None
    es_reversion: bool
    se_puede_revertir: bool
