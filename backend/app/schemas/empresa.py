import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Annotated

from pydantic import BaseModel, Field

from app.schemas.comun import ORMModel

Clabe = Annotated[str, Field(pattern=r"^\d{18}$", description="CLABE de 18 dígitos")]


class EmpresaCrear(BaseModel):
    nombre: str = Field(min_length=1, max_length=200)
    csf: str = Field(min_length=1, max_length=100)
    banco: str = Field(min_length=1, max_length=100)
    numero_cuenta: str = Field(min_length=1, max_length=30)
    clabe: Clabe | None = None
    usuario_id: uuid.UUID | None = Field(
        default=None, description="Solo admin: registrar la empresa a nombre de un contador"
    )


class EmpresaActualizar(BaseModel):
    nombre: str | None = Field(default=None, min_length=1, max_length=200)
    csf: str | None = Field(default=None, min_length=1, max_length=100)
    banco: str | None = Field(default=None, min_length=1, max_length=100)
    numero_cuenta: str | None = Field(default=None, min_length=1, max_length=30)
    clabe: Clabe | None = None


class Reasignar(BaseModel):
    usuario_id: uuid.UUID


class ArchivosEmpresa(BaseModel):
    pdf1: str | None = None
    pdf2: str | None = None
    logo: str | None = None


class EmpresaOut(ORMModel):
    id: uuid.UUID
    usuario_id: uuid.UUID
    nombre: str
    csf: str
    banco: str
    numero_cuenta: str
    clabe: str | None
    fecha_registro: datetime
    archivos: ArchivosEmpresa


class SaldoOut(BaseModel):
    empresa_id: uuid.UUID
    al_dia: date
    ingresos_netos: Decimal
    salidas: Decimal
    saldo: Decimal
