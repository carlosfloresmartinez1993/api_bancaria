"""Regla de acceso única del sistema.

Un contador ve y opera:
- las empresas donde Empresa.usuario_id es su id, y
- los clientes (terminales) donde TerminalBancaria.usuario_id es su id, tengan empresa o no,
  y por extensión sus proyectos, entradas y salidas.
El responsable de un cliente con empresa es siempre el de la empresa (lo garantiza la base de
datos). Un admin ve todo. Un recurso ajeno se reporta como inexistente (404) para no revelar
que existe.
"""

import uuid
from typing import TypeVar

from sqlalchemy import Select, select
from sqlalchemy.orm import Session, joinedload

from app.core.errors import NoEncontrado
from app.models import Empresa, Movimiento, Proyecto, Salida, TerminalBancaria, Usuario

S = TypeVar("S", bound=Select)

SIN_EMPRESA = "Sin empresa"


def solo_propias(stmt: S, usuario: Usuario) -> S:
    """Filtro de propiedad para consultas de EMPRESAS. El statement debe incluir la tabla empresas."""
    if usuario.es_admin:
        return stmt
    return stmt.where(Empresa.usuario_id == usuario.id)


def clientes_propios(stmt: S, usuario: Usuario) -> S:
    """Filtro de propiedad para consultas de clientes y de lo que cuelga de ellos.

    El statement debe incluir la tabla terminales_bancarias.
    """
    if usuario.es_admin:
        return stmt
    return stmt.where(TerminalBancaria.usuario_id == usuario.id)


def unir_jerarquia(stmt: S, proyecto_id_col) -> S:
    """Une proyecto → cliente → empresa (opcional) a partir de la columna proyecto_id de la consulta."""
    return (
        stmt.join(Proyecto, proyecto_id_col == Proyecto.id)
        .join(TerminalBancaria, Proyecto.terminal_id == TerminalBancaria.id)
        .outerjoin(Empresa, TerminalBancaria.empresa_id == Empresa.id)
    )


def filtrar_empresa(stmt: S, empresa_id: uuid.UUID | None, sin_empresa: bool | None) -> S:
    """Filtro por empresa o por clientes sin empresa. El statement debe incluir terminales_bancarias."""
    if empresa_id:
        stmt = stmt.where(TerminalBancaria.empresa_id == empresa_id)
    if sin_empresa:
        stmt = stmt.where(TerminalBancaria.empresa_id.is_(None))
    return stmt


def obtener_empresa(db: Session, usuario: Usuario, empresa_id: uuid.UUID) -> Empresa:
    empresa = db.scalar(solo_propias(select(Empresa).where(Empresa.id == empresa_id), usuario))
    if empresa is None:
        raise NoEncontrado("Empresa no encontrada")
    return empresa


def obtener_terminal(db: Session, usuario: Usuario, terminal_id: uuid.UUID) -> TerminalBancaria:
    terminal = db.scalar(clientes_propios(select(TerminalBancaria).where(TerminalBancaria.id == terminal_id), usuario))
    if terminal is None:
        raise NoEncontrado("Cliente no encontrado")
    return terminal


def obtener_proyecto(db: Session, usuario: Usuario, proyecto_id: uuid.UUID) -> Proyecto:
    stmt = (
        select(Proyecto)
        .join(Proyecto.terminal)
        .options(joinedload(Proyecto.terminal))
        .where(Proyecto.id == proyecto_id)
    )
    proyecto = db.scalar(clientes_propios(stmt, usuario))
    if proyecto is None:
        raise NoEncontrado("Proyecto no encontrado")
    return proyecto


def obtener_movimiento(db: Session, usuario: Usuario, movimiento_id: uuid.UUID) -> Movimiento:
    stmt = unir_jerarquia(select(Movimiento), Movimiento.proyecto_id).options(
        joinedload(Movimiento.proyecto).joinedload(Proyecto.terminal)
    ).where(Movimiento.id == movimiento_id)
    movimiento = db.scalar(clientes_propios(stmt, usuario))
    if movimiento is None:
        raise NoEncontrado("Movimiento no encontrado")
    return movimiento


def obtener_salida(db: Session, usuario: Usuario, salida_id: uuid.UUID) -> Salida:
    stmt = unir_jerarquia(select(Salida), Salida.proyecto_id).options(
        joinedload(Salida.proyecto).joinedload(Proyecto.terminal)
    ).where(Salida.id == salida_id)
    salida = db.scalar(clientes_propios(stmt, usuario))
    if salida is None:
        raise NoEncontrado("Salida no encontrada")
    return salida


def mismo_grupo(a: TerminalBancaria, b: TerminalBancaria) -> bool:
    """Dos clientes son del mismo grupo si comparten empresa; un cliente sin empresa solo consigo mismo.

    Regla para mover entradas y salidas entre proyectos.
    """
    if a.empresa_id is None or b.empresa_id is None:
        return a.id == b.id
    return a.empresa_id == b.empresa_id
