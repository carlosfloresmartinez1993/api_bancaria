import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import MovimientoTerminal, SalidaEmpresa, TerminalBancaria

CERO = Decimal("0.00")


def totales_empresa(db: Session, empresa_id: uuid.UUID, hasta: date | None = None) -> tuple[Decimal, Decimal]:
    """(ingresos netos, salidas) acumulados hasta la fecha indicada, inclusive."""
    ingresos = (
        select(func.coalesce(func.sum(MovimientoTerminal.monto_neto), 0))
        .join(TerminalBancaria, MovimientoTerminal.terminal_id == TerminalBancaria.id)
        .where(TerminalBancaria.empresa_id == empresa_id)
    )
    salidas = select(func.coalesce(func.sum(SalidaEmpresa.monto), 0)).where(SalidaEmpresa.empresa_id == empresa_id)
    if hasta is not None:
        ingresos = ingresos.where(MovimientoTerminal.fecha_movimiento <= hasta)
        salidas = salidas.where(SalidaEmpresa.fecha <= hasta)
    return Decimal(db.scalar(ingresos)).quantize(CERO), Decimal(db.scalar(salidas)).quantize(CERO)


def saldo_empresa(db: Session, empresa_id: uuid.UUID, hasta: date | None = None) -> Decimal:
    """saldo(E) = Σ netos de las terminales de E − Σ salidas de E. Nunca se almacena."""
    ingresos, salidas = totales_empresa(db, empresa_id, hasta)
    return ingresos - salidas
