"""Comandos de administración.

    python -m app.cli crear-admin --correo admin@empresa.com --nombre Ana --apellidos "López Pérez"
    python -m app.cli cierre [--fecha 2026-09-29] [--forzar]
"""

import argparse
import getpass
import os
import sys
from datetime import date

from pydantic import TypeAdapter, ValidationError
from sqlalchemy import select

from app.core.security import hash_password
from app.db.session import SessionLocal
from app.models import AccionBitacora, Rol, Usuario
from app.schemas.comun import Password
from app.services.bitacora import registrar


def crear_admin(args: argparse.Namespace) -> int:
    password = os.environ.get("ADMIN_PASSWORD") or getpass.getpass("Contraseña del administrador: ")
    try:
        TypeAdapter(Password).validate_python(password)
    except ValidationError as exc:
        print(f"Contraseña inválida: {exc.errors()[0]['msg']}", file=sys.stderr)
        return 1
    correo = args.correo.strip().lower()
    with SessionLocal() as db:
        if db.scalar(select(Usuario.id).where(Usuario.correo == correo)):
            print(f"Ya existe un usuario con el correo {correo}", file=sys.stderr)
            return 1
        admin = Usuario(nombre=args.nombre, apellidos=args.apellidos, correo=correo,
                        password_hash=hash_password(password), rol=Rol.ADMIN)
        db.add(admin)
        db.flush()
        registrar(db, usuario_id=None, entidad="Usuario", entidad_id=admin.id, accion=AccionBitacora.CREAR_USUARIO,
                  detalle={"correo": correo, "rol": Rol.ADMIN, "origen": "cli"})
        db.commit()
        print(f"Administrador creado: {correo} ({admin.id})")
    return 0


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

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
