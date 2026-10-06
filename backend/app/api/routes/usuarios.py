import uuid
from typing import Annotated

from fastapi import APIRouter, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import DB, Admin, PaginacionDep
from app.api.utils import cambios_no_nulos, paginar
from app.core.errors import Conflicto, NoEncontrado, ReglaNegocio
from app.core.security import hash_password
from app.models import AccionBitacora, Rol, Usuario
from app.schemas.comun import Pagina
from app.schemas.usuario import RestablecerPassword, UsuarioActualizar, UsuarioCrear, UsuarioOut
from app.services.bitacora import instantanea, registrar

router = APIRouter(prefix="/usuarios", tags=["Usuarios (admin)"])

CAMPOS = ("nombre", "apellidos", "correo", "rol", "activo")


def _obtener(db: Session, usuario_id: uuid.UUID) -> Usuario:
    usuario = db.get(Usuario, usuario_id)
    if usuario is None:
        raise NoEncontrado("Usuario no encontrado")
    return usuario


def _correo_libre(db: Session, correo: str, excepto: uuid.UUID | None = None) -> None:
    stmt = select(Usuario.id).where(Usuario.correo == correo)
    if excepto:
        stmt = stmt.where(Usuario.id != excepto)
    if db.scalar(stmt):
        raise Conflicto("Ya existe un usuario con ese correo")


def _no_dejar_sin_admins(db: Session, usuario: Usuario) -> None:
    if not usuario.es_admin or not usuario.activo:
        return
    admins_activos = db.scalar(
        select(func.count()).where(Usuario.rol == Rol.ADMIN, Usuario.activo.is_(True))
    )
    if admins_activos <= 1:
        raise ReglaNegocio("No se puede dejar el sistema sin administradores activos")


@router.get("", response_model=Pagina[UsuarioOut])
def listar(db: DB, _: Admin, pag: PaginacionDep, rol: Rol | None = None,
           activo: Annotated[bool | None, Query()] = None):
    stmt = select(Usuario).order_by(Usuario.nombre, Usuario.apellidos)
    if rol:
        stmt = stmt.where(Usuario.rol == rol)
    if activo is not None:
        stmt = stmt.where(Usuario.activo.is_(activo))
    return paginar(db, stmt, pag.limit, pag.offset)


@router.post("", response_model=UsuarioOut, status_code=status.HTTP_201_CREATED)
def crear(datos: UsuarioCrear, db: DB, admin: Admin):
    _correo_libre(db, datos.correo)
    usuario = Usuario(**datos.model_dump(exclude={"password"}), password_hash=hash_password(datos.password))
    db.add(usuario)
    db.flush()
    registrar(db, usuario_id=admin.id, entidad="Usuario", entidad_id=usuario.id,
              accion=AccionBitacora.CREAR_USUARIO, detalle={"correo": usuario.correo, "rol": usuario.rol})
    db.commit()
    return usuario


@router.get("/{usuario_id}", response_model=UsuarioOut)
def obtener(usuario_id: uuid.UUID, db: DB, _: Admin):
    return _obtener(db, usuario_id)


@router.patch("/{usuario_id}", response_model=UsuarioOut)
def actualizar(usuario_id: uuid.UUID, datos: UsuarioActualizar, db: DB, admin: Admin):
    usuario = _obtener(db, usuario_id)
    cambios = cambios_no_nulos(datos.model_dump(exclude_unset=True), {"nombre", "apellidos", "correo", "rol"})
    if "correo" in cambios:
        _correo_libre(db, cambios["correo"], excepto=usuario.id)
    if cambios.get("rol") == Rol.CONTADOR:
        _no_dejar_sin_admins(db, usuario)
    antes = instantanea(usuario, CAMPOS)
    for campo, valor in cambios.items():
        setattr(usuario, campo, valor)
    registrar(db, usuario_id=admin.id, entidad="Usuario", entidad_id=usuario.id,
              accion=AccionBitacora.EDITAR_USUARIO, detalle={"antes": antes, "despues": instantanea(usuario, CAMPOS)})
    db.commit()
    return usuario


@router.post("/{usuario_id}/activar", response_model=UsuarioOut)
def activar(usuario_id: uuid.UUID, db: DB, admin: Admin):
    usuario = _obtener(db, usuario_id)
    if not usuario.activo:
        usuario.activo = True
        registrar(db, usuario_id=admin.id, entidad="Usuario", entidad_id=usuario.id, accion=AccionBitacora.ACTIVAR)
        db.commit()
    return usuario


@router.post("/{usuario_id}/desactivar", response_model=UsuarioOut)
def desactivar(usuario_id: uuid.UUID, db: DB, admin: Admin):
    """El usuario pierde el acceso de inmediato. Sus empresas se conservan y un admin puede reasignarlas."""
    usuario = _obtener(db, usuario_id)
    if usuario.id == admin.id:
        raise ReglaNegocio("No puedes desactivar tu propia cuenta")
    if usuario.activo:
        _no_dejar_sin_admins(db, usuario)
        usuario.activo = False
        registrar(db, usuario_id=admin.id, entidad="Usuario", entidad_id=usuario.id, accion=AccionBitacora.DESACTIVAR)
        db.commit()
    return usuario


@router.post("/{usuario_id}/restablecer-password", status_code=status.HTTP_204_NO_CONTENT)
def restablecer_password(usuario_id: uuid.UUID, datos: RestablecerPassword, db: DB, admin: Admin):
    usuario = _obtener(db, usuario_id)
    usuario.password_hash = hash_password(datos.nueva)
    registrar(db, usuario_id=admin.id, entidad="Usuario", entidad_id=usuario.id,
              accion=AccionBitacora.CAMBIO_PASSWORD, detalle={"por": "administrador"})
    db.commit()
