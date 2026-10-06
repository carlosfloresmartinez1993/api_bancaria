"""Comandos de administración.

    python -m app.cli crear-admin --correo admin@empresa.com --nombre Ana --apellidos "López Pérez"
    python -m app.cli cierre [--fecha 2026-09-29] [--forzar]
    python -m app.cli inicializar   # crea el primer admin desde ADMIN_* si no hay usuarios
"""

import argparse
import getpass
import os
import sys
from datetime import date

from pydantic import TypeAdapter, ValidationError
from sqlalchemy import func, select

from app.core.security import hash_password
from app.db.session import SessionLocal
from app.models import AccionBitacora, Rol, Usuario
from app.schemas.comun import Password
from app.services.bitacora import registrar


def _validar_password(password: str) -> bool:
    try:
        TypeAdapter(Password).validate_python(password)
    except ValidationError as exc:
        print(f"Contraseña inválida: {exc.errors()[0]['msg']}", file=sys.stderr)
        return False
    return True


def _crear_admin(correo: str, nombre: str, apellidos: str, password: str, origen: str) -> int:
    correo = correo.strip().lower()
    with SessionLocal() as db:
        if db.scalar(select(Usuario.id).where(Usuario.correo == correo)):
            print(f"Ya existe un usuario con el correo {correo}", file=sys.stderr)
            return 1
        admin = Usuario(nombre=nombre, apellidos=apellidos, correo=correo,
                        password_hash=hash_password(password), rol=Rol.ADMIN)
        db.add(admin)
        db.flush()
        registrar(db, usuario_id=None, entidad="Usuario", entidad_id=admin.id, accion=AccionBitacora.CREAR_USUARIO,
                  detalle={"correo": correo, "rol": Rol.ADMIN, "origen": origen})
        db.commit()
        print(f"Administrador creado: {correo} ({admin.id})")
    return 0


def crear_admin(args: argparse.Namespace) -> int:
    password = os.environ.get("ADMIN_PASSWORD") or getpass.getpass("Contraseña del administrador: ")
    if not _validar_password(password):
        return 1
    return _crear_admin(args.correo, args.nombre, args.apellidos, password, origen="cli")


def _restablecer_admin(correo: str, password: str) -> int:
    """Asigna ADMIN_PASSWORD al usuario ADMIN_CORREO (y lo activa); si no existe, lo crea como admin."""
    if not _validar_password(password):
        return 1
    with SessionLocal() as db:
        usuario = db.scalar(select(Usuario).where(Usuario.correo == correo.lower()))
        if usuario is None:
            print(f"inicializar: {correo} no existe; se crea como administrador")
        else:
            usuario.password_hash = hash_password(password)
            usuario.activo = True
            registrar(db, usuario_id=None, entidad="Usuario", entidad_id=usuario.id,
                      accion=AccionBitacora.CAMBIO_PASSWORD, detalle={"por": "ADMIN_RESTABLECER", "origen": "inicializar"})
            db.commit()
            print(f"inicializar: contraseña restablecida para {usuario.correo} (rol {usuario.rol})")
            return 0
    return _crear_admin(correo, os.environ.get("ADMIN_NOMBRE", "Administrador"),
                        os.environ.get("ADMIN_APELLIDOS", "General"), password, origen="inicializar")


def inicializar(_: argparse.Namespace) -> int:
    """Crea el primer administrador desde variables de entorno, solo si la base no tiene usuarios.

    Pensado para plataformas sin consola (p. ej. Render gratuito), donde se ejecuta al arrancar.
    Usa ADMIN_CORREO y ADMIN_PASSWORD (obligatorias) y ADMIN_NOMBRE / ADMIN_APELLIDOS (opcionales).
    Si ya hay usuarios no hace nada, así que es seguro ejecutarlo en cada arranque.

    Con ADMIN_RESTABLECER=true, aunque ya haya usuarios, asigna ADMIN_PASSWORD a ADMIN_CORREO
    (o lo crea como admin). Sirve para recuperar el acceso; después hay que quitar la variable.
    """
    # strip(): los campos de Render admiten varias líneas y es fácil pegar un salto de línea o espacio al final.
    correo = os.environ.get("ADMIN_CORREO", "").strip()
    password = os.environ.get("ADMIN_PASSWORD", "").strip()
    if os.environ.get("ADMIN_RESTABLECER", "").strip().lower() == "true":
        if not correo or not password:
            print("inicializar: ADMIN_RESTABLECER requiere ADMIN_CORREO y ADMIN_PASSWORD", file=sys.stderr)
            return 1
        return _restablecer_admin(correo, password)
    with SessionLocal() as db:
        if db.scalar(select(func.count()).select_from(Usuario)):
            print("inicializar: la base ya tiene usuarios; no se hace nada")
            return 0
    if not correo or not password:
        print("inicializar: la base no tiene usuarios; define ADMIN_CORREO y ADMIN_PASSWORD para crear el administrador",
              file=sys.stderr)
        return 0
    if not _validar_password(password):
        return 1
    return _crear_admin(correo, os.environ.get("ADMIN_NOMBRE", "Administrador"),
                        os.environ.get("ADMIN_APELLIDOS", "General"), password, origen="inicializar")


def cierre(args: argparse.Namespace) -> int:
    from app.services.cierre import ejecutar_cierre

    resultado = ejecutar_cierre(date.fromisoformat(args.fecha) if args.fecha else None, forzar=args.forzar)
    print(resultado)
    return 0 if resultado["estado"] in {"enviado", "ya_enviado"} else 1


def main() -> int:
    parser = argparse.ArgumentParser(prog="python -m app.cli")
    sub = parser.add_subparsers(dest="comando", required=True)

    p_admin = sub.add_parser("crear-admin", help="Crea el primer administrador")
    p_admin.add_argument("--correo", required=True)
    p_admin.add_argument("--nombre", required=True)
    p_admin.add_argument("--apellidos", required=True)
    p_admin.set_defaults(func=crear_admin)

    p_cierre = sub.add_parser("cierre", help="Ejecuta el cierre diario (útil con cron)")
    p_cierre.add_argument("--fecha", help="AAAA-MM-DD; por defecto, hoy")
    p_cierre.add_argument("--forzar", action="store_true", help="Reenviar aunque ya se haya enviado")
    p_cierre.set_defaults(func=cierre)

    p_init = sub.add_parser("inicializar", help="Crea el primer admin desde ADMIN_* si la base no tiene usuarios")
    p_init.set_defaults(func=inicializar)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
