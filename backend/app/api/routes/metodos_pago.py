import uuid

from fastapi import APIRouter, status
from sqlalchemy import func, select

from app.api.deps import DB, Admin, UsuarioActual
from app.api.utils import cambios_no_nulos
from app.core.errors import Conflicto, NoEncontrado
from app.models import MetodoPago
from app.schemas.metodo_pago import MetodoPagoActualizar, MetodoPagoCrear, MetodoPagoOut

router = APIRouter(prefix="/metodos-pago", tags=["Métodos de pago"])


def _nombre_libre(db, nombre: str, excepto: uuid.UUID | None = None) -> None:
    stmt = select(MetodoPago.id).where(func.lower(MetodoPago.nombre) == nombre.lower())
    if excepto:
        stmt = stmt.where(MetodoPago.id != excepto)
    if db.scalar(stmt):
        raise Conflicto("Ya existe un método de pago con ese nombre")


@router.get("", response_model=list[MetodoPagoOut])
def listar(db: DB, _: UsuarioActual, incluir_inactivos: bool = False):
    stmt = select(MetodoPago).order_by(MetodoPago.nombre)
    if not incluir_inactivos:
        stmt = stmt.where(MetodoPago.activo.is_(True))
    return db.scalars(stmt).all()


@router.post("", response_model=MetodoPagoOut, status_code=status.HTTP_201_CREATED)
def crear(datos: MetodoPagoCrear, db: DB, _: Admin):
    nombre = datos.nombre.strip()
    _nombre_libre(db, nombre)
    metodo = MetodoPago(nombre=nombre)
    db.add(metodo)
    db.commit()
    db.refresh(metodo)
    return metodo


@router.patch("/{metodo_id}", response_model=MetodoPagoOut)
def actualizar(metodo_id: uuid.UUID, datos: MetodoPagoActualizar, db: DB, _: Admin):
    """Renombrar o activar/desactivar. No se borran: los registros existentes los siguen usando."""
    metodo = db.get(MetodoPago, metodo_id)
    if metodo is None:
        raise NoEncontrado("Método de pago no encontrado")
    cambios = cambios_no_nulos(datos.model_dump(exclude_unset=True), {"nombre", "activo"})
    if "nombre" in cambios:
        cambios["nombre"] = cambios["nombre"].strip()
        _nombre_libre(db, cambios["nombre"], excepto=metodo.id)
    for campo, valor in cambios.items():
        setattr(metodo, campo, valor)
    db.commit()
    return metodo
