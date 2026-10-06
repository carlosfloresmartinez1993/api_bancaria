"""Regla de acceso única del sistema.

Un contador solo ve y opera las empresas donde Empresa.usuario_id es su id,
y por extensión sus clientes (terminales), proyectos, movimientos y salidas.
Un admin ve todo. Un recurso ajeno se reporta como inexistente (404) para no
revelar que existe.
"""

import uuid
from typing import TypeVar

from sqlalchemy import Select, select
from sqlalchemy.orm import Session, joinedload

from app.core.errors import NoEncontrado
from app.models import Empresa, Movimiento, Proyecto, Salida, TerminalBancaria, Usuario

S = TypeVar("S", bound=Select)


def solo_propias(stmt: S, usuario: Usuario) -> S:
    """Aplica el filtro de propiedad. El statement debe incluir la tabla empresas."""
    if usuario.es_admin:
        return stmt
    return stmt.where(Empresa.usuario_id == usuario.id)


def unir_jerarquia(stmt: S, proyecto_id_col) -> S:
    """Une proyecto → terminal → empresa a partir de la columna proyecto_id de la consulta."""
    return (
        stmt.join(Proyecto, proyecto_id_col == Proyecto.id)
        .join(TerminalBancaria, Proyecto.terminal_id == TerminalBancaria.id)
        .join(Empresa, TerminalBancaria.empresa_id == Empresa.id)
    )


def obtener_empresa(db: Session, usuario: Usuario, empresa_id: uuid.UUID) -> Empresa:
    empresa = db.scalar(solo_propias(select(Empresa).where(Empresa.id == empresa_id), usuario))
    if empresa is None:
        raise NoEncontrado("Empresa no encontrada")
    return empresa


def obtener_terminal(db: Session, usuario: Usuario, terminal_id: uuid.UUID) -> TerminalBancaria:
    stmt = select(TerminalBancaria).join(TerminalBancaria.empresa).where(TerminalBancaria.id == terminal_id)
    terminal = db.scalar(solo_propias(stmt, usuario))
    if terminal is None:
        raise NoEncontrado("Cliente no encontrado")
    return terminal


def obtener_proyecto(db: Session, usuario: Usuario, proyecto_id: uuid.UUID) -> Proyecto:
    stmt = (
        select(Proyecto)
        .join(Proyecto.terminal)
        .join(TerminalBancaria.empresa)
        .options(joinedload(Proyecto.terminal))
        .where(Proyecto.id == proyecto_id)
    )
    proyecto = db.scalar(solo_propias(stmt, usuario))
    if proyecto is None:
        raise NoEncontrado("Proyecto no encontrado")
    return proyecto


def obtener_movimiento(db: Session, usuario: Usuario, movimiento_id: uuid.UUID) -> Movimiento:
    stmt = unir_jerarquia(select(Movimiento), Movimiento.proyecto_id).options(
        joinedload(Movimiento.proyecto).joinedload(Proyecto.terminal)
    ).where(Movimiento.id == movimiento_id)
    movimiento = db.scalar(solo_propias(stmt, usuario))
    if movimiento is None:
        raise NoEncontrado("Movimiento no encontrado")
    return movimiento


def obtener_salida(db: Session, usuario: Usuario, salida_id: uuid.UUID) -> Salida:
    stmt = unir_jerarquia(select(Salida), Salida.proyecto_id).options(
        joinedload(Salida.proyecto).joinedload(Proyecto.terminal)
    ).where(Salida.id == salida_id)
    salida = db.scalar(solo_propias(stmt, usuario))
    if salida is None:
        raise NoEncontrado("Salida no encontrada")
    return salida
