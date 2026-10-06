import uuid
from datetime import datetime
from typing import Annotated

from pydantic import AfterValidator, BaseModel, EmailStr, Field

from app.models.enums import Rol
from app.schemas.comun import ORMModel, Password

Correo = Annotated[EmailStr, AfterValidator(lambda v: v.strip().lower())]
Nombre = Annotated[str, Field(min_length=1, max_length=100)]
Apellidos = Annotated[str, Field(min_length=1, max_length=150)]


class UsuarioCrear(BaseModel):
    nombre: Nombre
    apellidos: Apellidos
    correo: Correo
    password: Password
    rol: Rol = Rol.CONTADOR


class UsuarioActualizar(BaseModel):
    nombre: Nombre | None = None
    apellidos: Apellidos | None = None
    correo: Correo | None = None
    rol: Rol | None = None


class RestablecerPassword(BaseModel):
    nueva: Password


class UsuarioOut(ORMModel):
    id: uuid.UUID
    nombre: str
    apellidos: str
    correo: str
    rol: Rol
    activo: bool
    fecha_creacion: datetime
