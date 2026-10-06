import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import CheckConstraint, Date, DateTime, ForeignKey, Index, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, UUIDPk


class SalidaEmpresa(UUIDPk, Base):
    """Salida de dinero registrada como control; la transferencia real la hace contabilidad."""

    __tablename__ = "salidas_empresa"
    __table_args__ = (
        CheckConstraint("monto > 0", name="monto_positivo"),
        Index("ix_salidas_empresa_fecha", "empresa_id", "fecha"),
    )

    empresa_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("empresas.id", ondelete="RESTRICT"))
    usuario_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("usuarios.id", ondelete="RESTRICT"), index=True)
    monto: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    destino: Mapped[str] = mapped_column(String(255))
    fecha: Mapped[date] = mapped_column(Date)
    observaciones: Mapped[str | None] = mapped_column(Text)
    fecha_registro: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
