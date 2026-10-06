from datetime import datetime

from sqlalchemy import DateTime, String, func, true
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, UUIDPk


class MetodoPago(UUIDPk, Base):
    """Catálogo de métodos de pago (transferencia, depósito, efectivo…). El admin puede agregar más."""

    __tablename__ = "metodos_pago"

    nombre: Mapped[str] = mapped_column(String(50), unique=True)
    activo: Mapped[bool] = mapped_column(default=True, server_default=true())
    fecha_registro: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
