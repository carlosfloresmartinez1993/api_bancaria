"""Clientes (terminales). En la API se conservan las rutas /terminales."""

import uuid
from datetime import date

from fastapi import APIRouter, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import DB, PaginacionDep, UsuarioActual
from app.api.utils import cambios_no_nulos, paginar
from app.core.errors import Conflicto
from app.core.tiempo import hoy
from app.models import AccionBitacora, Empresa, Proyecto, TerminalBancaria
from app.schemas.comun import Pagina
from app.schemas.empresa import SaldoOut
from app.schemas.terminal import TerminalActualizar, TerminalCrear, TerminalOut
from app.services.acceso import obtener_empresa, obtener_terminal, solo_propias
from app.services.bitacora import registrar
from app.services.saldos import totales

router = APIRouter(prefix="/terminales", tags=["Clientes (terminales)"])


def _identificador_libre(db: Session, empresa_id: uuid.UUID, identificador: str, excepto: uuid.UUID | None = None):
    stmt = select(TerminalBancaria.id).where(
        TerminalBancaria.empresa_id == empresa_id, TerminalBancaria.identificador_terminal == identificador
    )
    if excepto:
        stmt = stmt.where(TerminalBancaria.id != excepto)
    if db.scalar(stmt):
        raise Conflicto("La empresa ya tiene un cliente con ese identificador")


def _salidas(db: Session, terminales: list[TerminalBancaria]) -> list[TerminalOut]:
    """Agrega a cada cliente cuántos proyectos tiene."""
    conteo = dict(
        db.execute(
            select(Proyecto.terminal_id, func.count())
            .where(Proyecto.terminal_id.in_([t.id for t in terminales]))
            .group_by(Proyecto.terminal_id)
        ).all()
    ) if terminales else {}
    return [TerminalOut.model_validate(t).model_copy(update={"num_proyectos": conteo.get(t.id, 0)})
            for t in terminales]


@router.get("", response_model=Pagina[TerminalOut])
def listar(db: DB, usuario: UsuarioActual, pag: PaginacionDep, empresa_id: uuid.UUID | None = None,
           activa: bool | None = None):
    stmt = solo_propias(
        select(TerminalBancaria).join(Empresa, TerminalBancaria.empresa_id == Empresa.id), usuario
    ).order_by(Empresa.nombre, TerminalBancaria.identificador_terminal)
    if empresa_id:
        stmt = stmt.where(TerminalBancaria.empresa_id == empresa_id)
    if activa is not None:
        stmt = stmt.where(TerminalBancaria.activa.is_(activa))
    pagina = paginar(db, stmt, pag.limit, pag.offset)
    pagina["items"] = _salidas(db, pagina["items"])
    return pagina


@router.post("", response_model=TerminalOut, status_code=status.HTTP_201_CREATED)
def crear(datos: TerminalCrear, db: DB, usuario: UsuarioActual):
    empresa = obtener_empresa(db, usuario, datos.empresa_id)
    identificador = datos.identificador_terminal.strip()
    _identificador_libre(db, empresa.id, identificador)
    terminal = TerminalBancaria(empresa_id=empresa.id, identificador_terminal=identificador)
    db.add(terminal)
    db.commit()
    db.refresh(terminal)
    return _salidas(db, [terminal])[0]


@router.get("/{terminal_id}", response_model=TerminalOut)
def obtener(terminal_id: uuid.UUID, db: DB, usuario: UsuarioActual):
    return _salidas(db, [obtener_terminal(db, usuario, terminal_id)])[0]


@router.patch("/{terminal_id}", response_model=TerminalOut)
def actualizar(terminal_id: uuid.UUID, datos: TerminalActualizar, db: DB, usuario: UsuarioActual):
    terminal = obtener_terminal(db, usuario, terminal_id)
    cambios = cambios_no_nulos(datos.model_dump(exclude_unset=True), {"identificador_terminal"})
    if "identificador_terminal" in cambios:
        cambios["identificador_terminal"] = cambios["identificador_terminal"].strip()
        _identificador_libre(db, terminal.empresa_id, cambios["identificador_terminal"], excepto=terminal.id)
    for campo, valor in cambios.items():
        setattr(terminal, campo, valor)
    db.commit()
    return _salidas(db, [terminal])[0]


def _cambiar_estado(db: Session, usuario, terminal_id: uuid.UUID, activa: bool) -> TerminalOut:
    terminal = obtener_terminal(db, usuario, terminal_id)
    if terminal.activa != activa:
        terminal.activa = activa
        registrar(db, usuario_id=usuario.id, entidad="Cliente", entidad_id=terminal.id,
                  accion=AccionBitacora.ACTIVAR if activa else AccionBitacora.DESACTIVAR)
        db.commit()
    return _salidas(db, [terminal])[0]


@router.post("/{terminal_id}/activar", response_model=TerminalOut)
def activar(terminal_id: uuid.UUID, db: DB, usuario: UsuarioActual):
    return _cambiar_estado(db, usuario, terminal_id, True)


@router.post("/{terminal_id}/desactivar", response_model=TerminalOut)
def desactivar(terminal_id: uuid.UUID, db: DB, usuario: UsuarioActual):
    """Un cliente inactivo no acepta capturas nuevas en ninguno de sus proyectos; su historial se conserva."""
    return _cambiar_estado(db, usuario, terminal_id, False)


@router.get("/{terminal_id}/saldo", response_model=SaldoOut)
def saldo(terminal_id: uuid.UUID, db: DB, usuario: UsuarioActual, al_dia: date | None = None):
    terminal = obtener_terminal(db, usuario, terminal_id)
    al_dia = al_dia or hoy()
    t = totales(db, terminal_id=terminal.id, hasta=al_dia)
    return SaldoOut(al_dia=al_dia, ingresos_brutos=t.ingresos_brutos, comisiones=t.comisiones,
                    ingresos_netos=t.ingresos_netos, salidas=t.salidas, saldo=t.saldo)
