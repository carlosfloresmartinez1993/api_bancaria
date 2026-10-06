import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import CheckConstraint, Computed, Date, DateTime, ForeignKey, Index, Numeric, Text, false, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, UUIDPk
from app.models.metodo_pago import MetodoPago
from app.models.proyecto import Proyecto


class Movimiento(UUIDPk, Base):
    """Entrada de dinero de un proyecto (corte de la terminal del cliente)."""

    __tablename__ = "movimientos"
    __table_args__ = (
        CheckConstraint("monto_bruto > 0", name="monto_bruto_positivo"),
        CheckConstraint("porcentaje_aplicado >= 0 AND porcentaje_aplicado < 100", name="porcentaje_rango"),
        Index("ix_movimientos_proyecto_fecha", "proyecto_id", "fecha_movimiento"),
        Index("ix_movimientos_fecha", "fecha_movimiento"),
    )

    proyecto_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("proyectos.id", ondelete="RESTRICT"))
    # Quién capturó: solo auditoría, no define acceso.
    usuario_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("usuarios.id", ondelete="RESTRICT"), index=True)
    metodo_pago_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("metodos_pago.id", ondelete="RESTRICT"), index=True)
    fecha_movimiento: Mapped[date] = mapped_column(Date)
    monto_bruto: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    porcentaje_aplicado: Mapped[Decimal] = mapped_column(Numeric(5, 2))
    # Columna generada por PostgreSQL: la API nunca la escribe.
    monto_neto: Mapped[Decimal] = mapped_column(
        Numeric(14, 2),
        Computed("round(monto_bruto * (1 - porcentaje_aplicado / 100), 2)", persisted=True),
    )
    # Por ahora solo se registra; más adelante servirá para el control de facturación.
    requiere_factura: Mapped[bool] = mapped_column(default=False, server_default=false())
    fecha_captura: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    observaciones: Mapped[str | None] = mapped_column(Text)

    proyecto: Mapped[Proyecto] = relationship()
    metodo_pago: Mapped[MetodoPago] = relationship()

    @property
    def terminal_id(self) -> uuid.UUID:
        return self.proyecto.terminal_id

    @property
    def empresa_id(self) -> uuid.UUID:
        return self.proyecto.terminal.empresa_id

    @property
    def comision(self) -> Decimal:
        return self.monto_bruto - self.monto_neto
