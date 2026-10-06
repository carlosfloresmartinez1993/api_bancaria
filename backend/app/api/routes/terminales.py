import uuid

from fastapi import APIRouter, status
from datetime import date

from sqlalchemy import and_, func, select
from sqlalchemy.orm import Session

from app.api.deps import DB, PaginacionDep, UsuarioActual
from app.api.utils import cambios_no_nulos, validar_no_futura
from app.core.errors import Conflicto
from app.core.tiempo import hoy
from app.models import AccionBitacora, Empresa, HistorialPorcentajeTerminal as Historial, TerminalBancaria
from app.schemas.comun import Pagina
from app.schemas.terminal import (
    CambioPorcentaje,
    CambioPorcentajeOut,
    HistorialOut,
    TerminalActualizar,
    TerminalCrear,
    TerminalOut,
)
from app.services.acceso import obtener_empresa, obtener_terminal, solo_propias
from app.services.bitacora import registrar
from app.services.porcentajes import cambiar_porcentaje, condicion_vigente, crear_porcentaje_inicial, porcentaje_vigente

router = APIRouter(prefix="/terminales", tags=["Terminales"])


def _identificador_libre(db: Session, empresa_id: uuid.UUID, identificador: str, excepto: uuid.UUID | None = None):
    stmt = select(TerminalBancaria.id).where(
        TerminalBancaria.empresa_id == empresa_id, TerminalBancaria.identificador_terminal == identificador
    )
    if excepto:
        stmt = stmt.where(TerminalBancaria.id != excepto)
    if db.scalar(stmt):
        raise Conflicto("La empresa ya tiene una terminal con ese identificador")


def _salida(db: Session, terminal: TerminalBancaria) -> TerminalOut:
    salida = TerminalOut.model_validate(terminal)
    salida.porcentaje_vigente = db.scalar(
        select(Historial.porcentaje).where(Historial.terminal_id == terminal.id, *condicion_vigente(hoy()))
    )
    return salida


@router.get("", response_model=Pagina[TerminalOut])
def listar(db: DB, usuario: UsuarioActual, pag: PaginacionDep, empresa_id: uuid.UUID | None = None,
           activa: bool | None = None):
    stmt = solo_propias(
        select(TerminalBancaria, Historial.porcentaje)
        .join(Empresa, TerminalBancaria.empresa_id == Empresa.id)
        .outerjoin(Historial, and_(Historial.terminal_id == TerminalBancaria.id, *condicion_vigente(hoy()))),
        usuario,
    ).order_by(Empresa.nombre, TerminalBancaria.identificador_terminal)
    if empresa_id:
        stmt = stmt.where(TerminalBancaria.empresa_id == empresa_id)
    if activa is not None:
        stmt = stmt.where(TerminalBancaria.activa.is_(activa))
    total = db.scalar(select(func.count()).select_from(stmt.order_by(None).subquery()))
    items = []
    for terminal, porcentaje in db.execute(stmt.limit(pag.limit).offset(pag.offset)):
        salida = TerminalOut.model_validate(terminal)
        salida.porcentaje_vigente = porcentaje
        items.append(salida)
    return {"items": items, "total": total, "limit": pag.limit, "offset": pag.offset}


@router.post("", response_model=TerminalOut, status_code=status.HTTP_201_CREATED)
def crear(datos: TerminalCrear, db: DB, usuario: UsuarioActual):
    empresa = obtener_empresa(db, usuario, datos.empresa_id)
    desde = datos.vigente_desde or hoy()
    validar_no_futura(desde, "fecha de vigencia inicial")
    _identificador_libre(db, empresa.id, datos.identificador_terminal)
    terminal = TerminalBancaria(
        empresa_id=empresa.id, identificador_terminal=datos.identificador_terminal, datos_extra=datos.datos_extra
    )
    db.add(terminal)
    db.flush()
    crear_porcentaje_inicial(db, terminal, datos.porcentaje_inicial, desde)
    db.commit()
    db.refresh(terminal)
    return _salida(db, terminal)


@router.get("/{terminal_id}", response_model=TerminalOut)
def obtener(terminal_id: uuid.UUID, db: DB, usuario: UsuarioActual):
    return _salida(db, obtener_terminal(db, usuario, terminal_id))


@router.patch("/{terminal_id}", response_model=TerminalOut)
def actualizar(terminal_id: uuid.UUID, datos: TerminalActualizar, db: DB, usuario: UsuarioActual):
    terminal = obtener_terminal(db, usuario, terminal_id)
    cambios = cambios_no_nulos(datos.model_dump(exclude_unset=True), {"identificador_terminal", "datos_extra"})
    if "identificador_terminal" in cambios:
        _identificador_libre(db, terminal.empresa_id, cambios["identificador_terminal"], excepto=terminal.id)
    for campo, valor in cambios.items():
        setattr(terminal, campo, valor)
    db.commit()
    return _salida(db, terminal)


def _cambiar_estado(db: Session, usuario, terminal_id: uuid.UUID, activa: bool) -> TerminalOut:
    terminal = obtener_terminal(db, usuario, terminal_id)
    if terminal.activa != activa:
        terminal.activa = activa
        registrar(db, usuario_id=usuario.id, entidad="TerminalBancaria", entidad_id=terminal.id,
                  accion=AccionBitacora.ACTIVAR if activa else AccionBitacora.DESACTIVAR)
        db.commit()
    return _salida(db, terminal)


@router.post("/{terminal_id}/activar", response_model=TerminalOut)
def activar(terminal_id: uuid.UUID, db: DB, usuario: UsuarioActual):
    return _cambiar_estado(db, usuario, terminal_id, True)


@router.post("/{terminal_id}/desactivar", response_model=TerminalOut)
def desactivar(terminal_id: uuid.UUID, db: DB, usuario: UsuarioActual):
    """Una terminal inactiva no acepta capturas nuevas; sus movimientos se conservan y se pueden corregir."""
    return _cambiar_estado(db, usuario, terminal_id, False)


@router.get("/{terminal_id}/porcentajes", response_model=list[HistorialOut])
def historial_porcentajes(terminal_id: uuid.UUID, db: DB, usuario: UsuarioActual):
    terminal = obtener_terminal(db, usuario, terminal_id)
    return db.scalars(
        select(Historial).where(Historial.terminal_id == terminal.id).order_by(Historial.fecha_inicio_vigencia)
    ).all()


@router.post("/{terminal_id}/porcentajes", response_model=CambioPorcentajeOut, status_code=status.HTTP_201_CREATED)
def nuevo_porcentaje(terminal_id: uuid.UUID, datos: CambioPorcentaje, db: DB, usuario: UsuarioActual):
    terminal = obtener_terminal(db, usuario, terminal_id)
    registro, recalculados = cambiar_porcentaje(
        db, terminal=terminal, nuevo=datos.porcentaje, desde=datos.vigente_desde,
        usuario_id=usuario.id, motivo=datos.motivo,
    )
    db.commit()
    return CambioPorcentajeOut(historial=HistorialOut.model_validate(registro), movimientos_recalculados=recalculados)


@router.get("/{terminal_id}/porcentaje-vigente", response_model=HistorialOut,
            summary="Porcentaje que rige un día dado (por defecto, hoy)")
def porcentaje_en_fecha(terminal_id: uuid.UUID, db: DB, usuario: UsuarioActual, dia: date | None = None):
    terminal = obtener_terminal(db, usuario, terminal_id)
    fecha = dia or hoy()
    porcentaje_vigente(db, terminal.id, fecha)  # lanza 422 si no hay
    return db.scalar(select(Historial).where(Historial.terminal_id == terminal.id, *condicion_vigente(fecha)))
