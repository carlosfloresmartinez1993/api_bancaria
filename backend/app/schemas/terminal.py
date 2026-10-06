import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.comun import ORMModel


class TerminalCrear(BaseModel):
    empresa_id: uuid.UUID
    identificador_terminal: str = Field(min_length=1, max_length=100)


class TerminalActualizar(BaseModel):
    identificador_terminal: str | None = Field(default=None, min_length=1, max_length=100)


class TerminalOut(ORMModel):
    id: uuid.UUID
    empresa_id: uuid.UUID
    identificador_terminal: str
    activa: bool
    fecha_registro: datetime
    num_proyectos: int = 0
