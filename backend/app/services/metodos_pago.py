import uuid

from sqlalchemy.orm import Session

from app.core.errors import ReglaNegocio
from app.models import MetodoPago


def validar_metodo_pago(db: Session, metodo_pago_id: uuid.UUID) -> MetodoPago:
    """El método de pago debe existir y estar activo para usarse en registros nuevos o corregidos."""
    metodo = db.get(MetodoPago, metodo_pago_id)
    if metodo is None or not metodo.activo:
        raise ReglaNegocio("El método de pago no existe o está inactivo")
    return metodo
