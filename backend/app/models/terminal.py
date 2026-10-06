import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint, func, true
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, UUIDPk
from app.models.empresa import Empresa


class TerminalBancaria(UUIDPk, Base):
    """Terminal punto de venta de una empresa. En la interfaz se llama «Cliente»."""

    __tablename__ = "terminales_bancarias"
    __table_args__ = (UniqueConstraint("empresa_id", "identificador_terminal", name="uq_terminal_por_empresa"),)

    empresa_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("empresas.id", ondelete="RESTRICT"), index=True)
    identificador_terminal: Mapped[str] = mapped_column(String(100))
    activa: Mapped[bool] = mapped_column(default=True, server_default=true())
    fecha_registro: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    empresa: Mapped[Empresa] = relationship()
