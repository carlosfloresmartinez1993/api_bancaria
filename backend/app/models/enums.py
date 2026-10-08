from enum import StrEnum

from sqlalchemy import Enum as SAEnum


class Rol(StrEnum):
    ADMIN = "admin"
    CONTADOR = "contador"


class AccionBitacora(StrEnum):
    """Catálogo cerrado de acciones de la bitácora."""

    CREAR_USUARIO = "CREAR_USUARIO"
    EDITAR_USUARIO = "EDITAR_USUARIO"
    CAMBIO_PASSWORD = "CAMBIO_PASSWORD"
    ACTIVAR = "ACTIVAR"
    DESACTIVAR = "DESACTIVAR"
    REASIGNAR_EMPRESA = "REASIGNAR_EMPRESA"
    MOVER_CLIENTE = "MOVER_CLIENTE"  # asociar un cliente a una empresa, quitárselo o revertirlo
    REASIGNAR_CLIENTE = "REASIGNAR_CLIENTE"  # cambiar el responsable de un cliente sin empresa
    CAMBIO_PORCENTAJE = "CAMBIO_PORCENTAJE"
    EDITAR_MOVIMIENTO = "EDITAR_MOVIMIENTO"
    ELIMINAR_MOVIMIENTO = "ELIMINAR_MOVIMIENTO"
    EDITAR_SALIDA = "EDITAR_SALIDA"
    ELIMINAR_SALIDA = "ELIMINAR_SALIDA"
    CIERRE_ENVIADO = "CIERRE_ENVIADO"
    CIERRE_ERROR = "CIERRE_ERROR"


def enum_columna(enum_cls: type[StrEnum], nombre: str, largo: int) -> SAEnum:
    """Enum guardado como varchar + CHECK (evita ALTER TYPE al agregar valores)."""
    return SAEnum(
        enum_cls,
        name=nombre,
        native_enum=False,
        create_constraint=True,
        length=largo,
        values_callable=lambda e: [m.value for m in e],
        validate_strings=True,
    )
