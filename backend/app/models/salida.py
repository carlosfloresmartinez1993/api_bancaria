import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import CheckConstraint, Date, DateTime, ForeignKey, Index, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, UUIDPk
from app.models.metodo_pago import MetodoPago
from app.models.proyecto import Proyecto


class Salida(UUIDPk, Base):
    """Salida de dinero de un proyecto, registrada como control; la transferencia real la hace contabilidad."""

    __tablename__ = "salidas"
    __table_args__ = (
        CheckConstraint("monto > 0", name="monto_positivo"),
        Index("ix_salidas_proyecto_fecha", "proyecto_id", "fecha"),
    )

    proyecto_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("proyectos.id", ondelete="RESTRICT"))
    usuario_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("usuarios.id", ondelete="RESTRICT"), index=True)
    metodo_pago_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("metodos_pago.id", ondelete="RESTRICT"), index=True)
    monto: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    destino: Mapped[str] = mapped_column(String(255))
    fecha: Mapped[date] = mapped_column(Date)
    observaciones: Mapped[str | None] = mapped_column(Text)
    fecha_registro: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    proyecto: Mapped[Proyecto] = relationship()
    metodo_pago: Mapped[MetodoPago] = relationship()

    @property
    def terminal_id(self) -> uuid.UUID:
        return self.proyecto.terminal_id

    @property
    def empresa_id(self) -> uuid.UUID:
        return self.proyecto.terminal.empresa_id
