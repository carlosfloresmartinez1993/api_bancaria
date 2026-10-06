import uuid
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Query, status
from sqlalchemy import select
from sqlalchemy.orm import joinedload

from app.api.deps import DB, PaginacionDep, UsuarioActual
from app.api.utils import cambios_no_nulos, paginar, validar_no_futura
from app.core.errors import ReglaNegocio
from app.models import AccionBitacora, Empresa, MovimientoTerminal, TerminalBancaria
from app.schemas.comun import Pagina
from app.schemas.movimiento import MovimientoActualizar, MovimientoCrear, MovimientoOut
from app.services.acceso import obtener_movimiento, obtener_terminal, solo_propias
from app.services.bitacora import instantanea, registrar
from app.services.porcentajes import porcentaje_vigente
from app.services.reportes import validar_rango

router = APIRouter(prefix="/movimientos", tags=["Movimientos de terminal"])

CAMPOS = ("terminal_id", "fecha_movimiento", "monto_bruto", "porcentaje_aplicado", "monto_neto", "observaciones")


@router.get("", response_model=Pagina[MovimientoOut])
def listar(
    db: DB,
    usuario: UsuarioActual,
    pag: PaginacionDep,
    empresa_id: uuid.UUID | None = None,
    terminal_id: uuid.UUID | None = None,
    capturo_id: Annotated[uuid.UUID | None, Query(description="Filtrar por quién capturó")] = None,
    desde: date | None = None,
    hasta: date | None = None,
):
    validar_rango(desde, hasta)
    stmt = solo_propias(
        select(MovimientoTerminal)
        .join(MovimientoTerminal.terminal)
        .join(Empresa, TerminalBancaria.empresa_id == Empresa.id)
        .options(joinedload(MovimientoTerminal.terminal)),
        usuario,
    ).order_by(MovimientoTerminal.fecha_movimiento.desc(), MovimientoTerminal.fecha_captura.desc())
    if empresa_id:
        stmt = stmt.where(Empresa.id == empresa_id)
    if terminal_id:
        stmt = stmt.where(MovimientoTerminal.terminal_id == terminal_id)
    if capturo_id:
        stmt = stmt.where(MovimientoTerminal.usuario_id == capturo_id)
    if desde:
        stmt = stmt.where(MovimientoTerminal.fecha_movimiento >= desde)
    if hasta:
        stmt = stmt.where(MovimientoTerminal.fecha_movimiento <= hasta)
    return paginar(db, stmt, pag.limit, pag.offset)


@router.post("", response_model=MovimientoOut, status_code=status.HTTP_201_CREATED)
def capturar(datos: MovimientoCrear, db: DB, usuario: UsuarioActual):
    """Registra un ingreso. El % se toma del historial para la fecha del movimiento y el neto lo calcula la BD."""
    terminal = obtener_terminal(db, usuario, datos.terminal_id)
    if not terminal.activa:
        raise ReglaNegocio("La terminal está inactiva; no acepta capturas nuevas")
    validar_no_futura(datos.fecha_movimiento, "fecha del movimiento")
    movimiento = MovimientoTerminal(
        terminal_id=terminal.id,
        usuario_id=usuario.id,
        fecha_movimiento=datos.fecha_movimiento,
        monto_bruto=datos.monto_bruto,
        porcentaje_aplicado=porcentaje_vigente(db, terminal.id, datos.fecha_movimiento),
        observaciones=datos.observaciones,
    )
    db.add(movimiento)
    db.commit()
    db.refresh(movimiento)
    return movimiento


@router.get("/{movimiento_id}", response_model=MovimientoOut)
def obtener(movimiento_id: uuid.UUID, db: DB, usuario: UsuarioActual):
    return obtener_movimiento(db, usuario, movimiento_id)


@router.patch("/{movimiento_id}", response_model=MovimientoOut)
def corregir(movimiento_id: uuid.UUID, datos: MovimientoActualizar, db: DB, usuario: UsuarioActual):
    """Corrige un movimiento (dueño de la empresa o admin, sin límite de tiempo). Queda en la bitácora."""
    movimiento = obtener_movimiento(db, usuario, movimiento_id)
    motivo = datos.motivo
    cambios = cambios_no_nulos(
        datos.model_dump(exclude_unset=True, exclude={"motivo"}), {"terminal_id", "fecha_movimiento", "monto_bruto"}
    )
    antes = instantanea(movimiento, CAMPOS)

    nueva_terminal = cambios.get("terminal_id", movimiento.terminal_id)
    if nueva_terminal != movimiento.terminal_id:
        destino = obtener_terminal(db, usuario, nueva_terminal)
        if destino.empresa_id != movimiento.terminal.empresa_id:
            raise ReglaNegocio("Solo se puede mover el registro a otra terminal de la misma empresa")
        if not destino.activa:
            raise ReglaNegocio("La terminal destino está inactiva")
    if "fecha_movimiento" in cambios:
        validar_no_futura(cambios["fecha_movimiento"], "fecha del movimiento")

    recalcular = (nueva_terminal != movimiento.terminal_id
                  or cambios.get("fecha_movimiento", movimiento.fecha_movimiento) != movimiento.fecha_movimiento)
    for campo, valor in cambios.items():
        setattr(movimiento, campo, valor)
    if recalcular:
        movimiento.porcentaje_aplicado = porcentaje_vigente(db, movimiento.terminal_id, movimiento.fecha_movimiento)

    db.flush()
    db.refresh(movimiento)  # trae el monto_neto que recalculó PostgreSQL
    despues = instantanea(movimiento, CAMPOS)
    if antes == despues:
        db.rollback()
        return movimiento
    registrar(db, usuario_id=usuario.id, entidad="MovimientoTerminal", entidad_id=movimiento.id,
              accion=AccionBitacora.EDITAR_MOVIMIENTO, detalle={"antes": antes, "despues": despues, "motivo": motivo})
    db.commit()
    return movimiento


@router.delete("/{movimiento_id}", status_code=status.HTTP_204_NO_CONTENT)
def eliminar(movimiento_id: uuid.UUID, db: DB, usuario: UsuarioActual,
             motivo: Annotated[str | None, Query(max_length=500)] = None):
    """Elimina una captura duplicada o errónea. El registro completo queda en la bitácora."""
    movimiento = obtener_movimiento(db, usuario, movimiento_id)
    antes = instantanea(movimiento, CAMPOS)
    registrar(db, usuario_id=usuario.id, entidad="MovimientoTerminal", entidad_id=movimiento.id,
              accion=AccionBitacora.ELIMINAR_MOVIMIENTO, detalle={"antes": antes, "motivo": motivo})
    db.delete(movimiento)
    db.commit()
