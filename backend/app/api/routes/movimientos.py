import uuid
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Query, status
from sqlalchemy import select
from sqlalchemy.orm import joinedload

from app.api.deps import DB, PaginacionDep, UsuarioActual
from app.api.utils import cambios_no_nulos, paginar, validar_no_futura
from app.core.errors import ReglaNegocio
from app.models import AccionBitacora, Empresa, Movimiento, Proyecto, TerminalBancaria
from app.schemas.comun import Pagina
from app.schemas.movimiento import MovimientoActualizar, MovimientoCrear, MovimientoOut
from app.services.acceso import obtener_movimiento, obtener_proyecto, solo_propias, unir_jerarquia
from app.services.bitacora import instantanea, registrar
from app.services.metodos_pago import validar_metodo_pago
from app.services.porcentajes import porcentaje_vigente
from app.services.reportes import validar_rango

router = APIRouter(prefix="/movimientos", tags=["Movimientos (entradas)"])

CAMPOS = ("proyecto_id", "fecha_movimiento", "monto_bruto", "porcentaje_aplicado", "monto_neto",
          "metodo_pago_id", "requiere_factura", "observaciones")


def _validar_proyecto_activo(proyecto: Proyecto) -> None:
    if not proyecto.activo:
        raise ReglaNegocio("El proyecto está inactivo; no acepta capturas nuevas")
    if not proyecto.terminal.activa:
        raise ReglaNegocio("El cliente (terminal) está inactivo; no acepta capturas nuevas")


@router.get("", response_model=Pagina[MovimientoOut])
def listar(
    db: DB,
    usuario: UsuarioActual,
    pag: PaginacionDep,
    empresa_id: uuid.UUID | None = None,
    terminal_id: uuid.UUID | None = None,
    proyecto_id: uuid.UUID | None = None,
    metodo_pago_id: uuid.UUID | None = None,
    requiere_factura: bool | None = None,
    capturo_id: Annotated[uuid.UUID | None, Query(description="Filtrar por quién capturó")] = None,
    desde: date | None = None,
    hasta: date | None = None,
):
    validar_rango(desde, hasta)
    stmt = solo_propias(
        unir_jerarquia(select(Movimiento), Movimiento.proyecto_id).options(
            joinedload(Movimiento.proyecto).joinedload(Proyecto.terminal)
        ),
        usuario,
    ).order_by(Movimiento.fecha_movimiento.desc(), Movimiento.fecha_captura.desc())
    if empresa_id:
        stmt = stmt.where(Empresa.id == empresa_id)
    if terminal_id:
        stmt = stmt.where(TerminalBancaria.id == terminal_id)
    if proyecto_id:
        stmt = stmt.where(Movimiento.proyecto_id == proyecto_id)
    if metodo_pago_id:
        stmt = stmt.where(Movimiento.metodo_pago_id == metodo_pago_id)
    if requiere_factura is not None:
        stmt = stmt.where(Movimiento.requiere_factura.is_(requiere_factura))
    if capturo_id:
        stmt = stmt.where(Movimiento.usuario_id == capturo_id)
    if desde:
        stmt = stmt.where(Movimiento.fecha_movimiento >= desde)
    if hasta:
        stmt = stmt.where(Movimiento.fecha_movimiento <= hasta)
    return paginar(db, stmt, pag.limit, pag.offset)


@router.post("", response_model=MovimientoOut, status_code=status.HTTP_201_CREATED)
def capturar(datos: MovimientoCrear, db: DB, usuario: UsuarioActual):
    """Registra una entrada. El % se toma del historial del proyecto para la fecha del movimiento."""
    proyecto = obtener_proyecto(db, usuario, datos.proyecto_id)
    _validar_proyecto_activo(proyecto)
    validar_no_futura(datos.fecha_movimiento, "fecha del movimiento")
    validar_metodo_pago(db, datos.metodo_pago_id)
    movimiento = Movimiento(
        proyecto_id=proyecto.id,
        usuario_id=usuario.id,
        metodo_pago_id=datos.metodo_pago_id,
        fecha_movimiento=datos.fecha_movimiento,
        monto_bruto=datos.monto_bruto,
        porcentaje_aplicado=porcentaje_vigente(db, proyecto.id, datos.fecha_movimiento),
        requiere_factura=datos.requiere_factura,
        observaciones=datos.observaciones,
    )
    db.add(movimiento)
    db.commit()
    db.refresh(movimiento)  # trae el monto_neto que calculó PostgreSQL
    return movimiento


@router.get("/{movimiento_id}", response_model=MovimientoOut)
def obtener(movimiento_id: uuid.UUID, db: DB, usuario: UsuarioActual):
    return obtener_movimiento(db, usuario, movimiento_id)


@router.patch("/{movimiento_id}", response_model=MovimientoOut)
def corregir(movimiento_id: uuid.UUID, datos: MovimientoActualizar, db: DB, usuario: UsuarioActual):
    """Corrige una entrada (dueño de la empresa o admin, sin límite de tiempo). Queda en la bitácora."""
    movimiento = obtener_movimiento(db, usuario, movimiento_id)
    motivo = datos.motivo
    cambios = cambios_no_nulos(
        datos.model_dump(exclude_unset=True, exclude={"motivo"}),
        {"proyecto_id", "fecha_movimiento", "monto_bruto", "metodo_pago_id", "requiere_factura"},
    )
    antes = instantanea(movimiento, CAMPOS)

    nuevo_proyecto = cambios.get("proyecto_id", movimiento.proyecto_id)
    if nuevo_proyecto != movimiento.proyecto_id:
        destino = obtener_proyecto(db, usuario, nuevo_proyecto)
        if destino.terminal.empresa_id != movimiento.empresa_id:
            raise ReglaNegocio("Solo se puede mover el registro a otro proyecto de la misma empresa")
        _validar_proyecto_activo(destino)
    if "fecha_movimiento" in cambios:
        validar_no_futura(cambios["fecha_movimiento"], "fecha del movimiento")
    if "metodo_pago_id" in cambios and cambios["metodo_pago_id"] != movimiento.metodo_pago_id:
        validar_metodo_pago(db, cambios["metodo_pago_id"])

    recalcular = (nuevo_proyecto != movimiento.proyecto_id
                  or cambios.get("fecha_movimiento", movimiento.fecha_movimiento) != movimiento.fecha_movimiento)
    for campo, valor in cambios.items():
        setattr(movimiento, campo, valor)
    if recalcular:
        movimiento.porcentaje_aplicado = porcentaje_vigente(db, movimiento.proyecto_id, movimiento.fecha_movimiento)

    db.flush()
    db.refresh(movimiento)  # trae el monto_neto que recalculó PostgreSQL
    despues = instantanea(movimiento, CAMPOS)
    if antes == despues:
        db.rollback()
        return obtener_movimiento(db, usuario, movimiento_id)
    registrar(db, usuario_id=usuario.id, entidad="Movimiento", entidad_id=movimiento.id,
              accion=AccionBitacora.EDITAR_MOVIMIENTO, detalle={"antes": antes, "despues": despues, "motivo": motivo})
    db.commit()
    return obtener_movimiento(db, usuario, movimiento_id)


@router.delete("/{movimiento_id}", status_code=status.HTTP_204_NO_CONTENT)
def eliminar(movimiento_id: uuid.UUID, db: DB, usuario: UsuarioActual,
             motivo: Annotated[str | None, Query(max_length=500)] = None):
    """Elimina una captura duplicada o errónea. El registro completo queda en la bitácora."""
    movimiento = obtener_movimiento(db, usuario, movimiento_id)
    antes = instantanea(movimiento, CAMPOS)
    registrar(db, usuario_id=usuario.id, entidad="Movimiento", entidad_id=movimiento.id,
              accion=AccionBitacora.ELIMINAR_MOVIMIENTO, detalle={"antes": antes, "motivo": motivo})
    db.delete(movimiento)
    db.commit()
