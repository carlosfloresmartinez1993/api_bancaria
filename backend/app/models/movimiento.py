import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import CheckConstraint, Computed, Date, DateTime, ForeignKey, Index, Numeric, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, UUIDPk
from app.models.terminal import TerminalBancaria


class MovimientoTerminal(UUIDPk, Base):
    __tablename__ = "movimientos_terminal"
    __table_args__ = (
        CheckConstraint("monto_bruto > 0", name="monto_bruto_positivo"),
        CheckConstraint("porcentaje_aplicado >= 0 AND porcentaje_aplicado < 100", name="porcentaje_rango"),
        Index("ix_movimientos_terminal_fecha", "terminal_id", "fecha_movimiento"),
        Index("ix_movimientos_fecha", "fecha_movimiento"),
    )

    terminal_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("terminales_bancarias.id", ondelete="RESTRICT"))
    # Quién capturó: solo auditoría, no define acceso.
    usuario_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("usuarios.id", ondelete="RESTRICT"), index=True)
    fecha_movimiento: Mapped[date] = mapped_column(Date)
    monto_bruto: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    porcentaje_aplicado: Mapped[Decimal] = mapped_column(Numeric(5, 2))
    # Columna generada por PostgreSQL: la API nunca la escribe.
    monto_neto: Mapped[Decimal] = mapped_column(
        Numeric(14, 2),
        Computed("round(monto_bruto * (1 - porcentaje_aplicado / 100), 2)", persisted=True),
    )
    fecha_captura: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    observaciones: Mapped[str | None] = mapped_column(Text)

    terminal: Mapped[TerminalBancaria] = relationship()

    @property
    def empresa_id(self) -> uuid.UUID:
        return self.terminal.empresa_id

    @property
    def comision(self) -> Decimal:
        return self.monto_bruto - self.monto_neto
