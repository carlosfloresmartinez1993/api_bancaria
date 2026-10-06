"""Regla de acceso única del sistema.

Un contador solo ve y opera las empresas donde Empresa.usuario_id es su id,
y por extensión sus terminales, movimientos y salidas. Un admin ve todo.
Un recurso ajeno se reporta como inexistente (404) para no revelar que existe.
"""

import uuid
from typing import TypeVar

from sqlalchemy import Select, select
from sqlalchemy.orm import Session, joinedload

from app.core.errors import NoEncontrado
from app.models import Empresa, MovimientoTerminal, SalidaEmpresa, TerminalBancaria, Usuario

S = TypeVar("S", bound=Select)


def solo_propias(stmt: S, usuario: Usuario) -> S:
    """Aplica el filtro de propiedad. El statement debe incluir la tabla empresas."""
    if usuario.es_admin:
        return stmt
    return stmt.where(Empresa.usuario_id == usuario.id)


def obtener_empresa(db: Session, usuario: Usuario, empresa_id: uuid.UUID) -> Empresa:
    empresa = db.scalar(solo_propias(select(Empresa).where(Empresa.id == empresa_id), usuario))
    if empresa is None:
        raise NoEncontrado("Empresa no encontrada")
    return empresa


def obtener_terminal(db: Session, usuario: Usuario, terminal_id: uuid.UUID) -> TerminalBancaria:
    stmt = (
        select(TerminalBancaria)
        .join(TerminalBancaria.empresa)
        .where(TerminalBancaria.id == terminal_id)
    )
    terminal = db.scalar(solo_propias(stmt, usuario))
    if terminal is None:
        raise NoEncontrado("Terminal no encontrada")
    return terminal


def obtener_movimiento(db: Session, usuario: Usuario, movimiento_id: uuid.UUID) -> MovimientoTerminal:
    stmt = (
        select(MovimientoTerminal)
        .join(MovimientoTerminal.terminal)
        .join(TerminalBancaria.empresa)
        .options(joinedload(MovimientoTerminal.terminal))
        .where(MovimientoTerminal.id == movimiento_id)
    )
    movimiento = db.scalar(solo_propias(stmt, usuario))
    if movimiento is None:
        raise NoEncontrado("Movimiento no encontrado")
    return movimiento


def obtener_salida(db: Session, usuario: Usuario, salida_id: uuid.UUID) -> SalidaEmpresa:
    stmt = (
        select(SalidaEmpresa)
        .join(Empresa, SalidaEmpresa.empresa_id == Empresa.id)
        .where(SalidaEmpresa.id == salida_id)
    )
    salida = db.scalar(solo_propias(stmt, usuario))
    if salida is None:
        raise NoEncontrado("Salida no encontrada")
    return salida
