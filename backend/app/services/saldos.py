import uuid
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Movimiento, Proyecto, Salida, TerminalBancaria

CERO = Decimal("0.00")


@dataclass
class Totales:
    ingresos_brutos: Decimal
    comisiones: Decimal
    ingresos_netos: Decimal
    salidas: Decimal

    @property
    def saldo(self) -> Decimal:
        """saldo = Σ netos − Σ salidas. Nunca se almacena."""
        return self.ingresos_netos - self.salidas


def _alcance(stmt, proyecto_col, *, empresa_id=None, terminal_id=None, proyecto_id=None):
    if proyecto_id is not None:
        return stmt.where(proyecto_col == proyecto_id)
    stmt = stmt.join(Proyecto, proyecto_col == Proyecto.id)
    if terminal_id is not None:
        return stmt.where(Proyecto.terminal_id == terminal_id)
    return stmt.join(TerminalBancaria, Proyecto.terminal_id == TerminalBancaria.id).where(
        TerminalBancaria.empresa_id == empresa_id
    )


def totales(
    db: Session,
    *,
    empresa_id: uuid.UUID | None = None,
    terminal_id: uuid.UUID | None = None,
    proyecto_id: uuid.UUID | None = None,
    hasta: date | None = None,
) -> Totales:
    """Ingresos y salidas acumulados de una empresa, un cliente (terminal) o un proyecto, hasta una fecha inclusive."""
    alcance = {"empresa_id": empresa_id, "terminal_id": terminal_id, "proyecto_id": proyecto_id}
    if sum(v is not None for v in alcance.values()) != 1:
        raise ValueError("Indica exactamente uno: empresa_id, terminal_id o proyecto_id")

    ingresos = _alcance(
        select(
            func.coalesce(func.sum(Movimiento.monto_bruto), 0),
            func.coalesce(func.sum(Movimiento.monto_neto), 0),
        ).select_from(Movimiento),
        Movimiento.proyecto_id,
        **alcance,
    )
    salidas = _alcance(select(func.coalesce(func.sum(Salida.monto), 0)).select_from(Salida), Salida.proyecto_id,
                       **alcance)
    if hasta is not None:
        ingresos = ingresos.where(Movimiento.fecha_movimiento <= hasta)
        salidas = salidas.where(Salida.fecha <= hasta)

    bruto, neto = db.execute(ingresos).one()
    bruto, neto = Decimal(bruto).quantize(CERO), Decimal(neto).quantize(CERO)
    return Totales(ingresos_brutos=bruto, comisiones=bruto - neto, ingresos_netos=neto,
                   salidas=Decimal(db.scalar(salidas)).quantize(CERO))
