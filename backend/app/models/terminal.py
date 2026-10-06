import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    String,
    UniqueConstraint,
    func,
    text,
    true,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, UUIDPk
from app.models.empresa import Empresa


class TerminalBancaria(UUIDPk, Base):
    __tablename__ = "terminales_bancarias"
    __table_args__ = (UniqueConstraint("empresa_id", "identificador_terminal", name="uq_terminal_por_empresa"),)

    empresa_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("empresas.id", ondelete="RESTRICT"), index=True)
    identificador_terminal: Mapped[str] = mapped_column(String(100))
    activa: Mapped[bool] = mapped_column(default=True, server_default=true())
    datos_extra: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, server_default=text("'{}'::jsonb"))
    fecha_registro: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    empresa: Mapped[Empresa] = relationship()


class HistorialPorcentajeTerminal(UUIDPk, Base):
    """Fuente única del porcentaje de comisión de cada terminal.

    Un registro rige desde fecha_inicio_vigencia (inclusive) hasta
    fecha_fin_vigencia (exclusiva); NULL en la fecha fin = vigente.
    """

    __tablename__ = "historial_porcentajes_terminal"
    __table_args__ = (
        CheckConstraint("porcentaje >= 0 AND porcentaje < 100", name="porcentaje_rango"),
        CheckConstraint(
            "fecha_fin_vigencia IS NULL OR fecha_fin_vigencia > fecha_inicio_vigencia", name="vigencia_valida"
        ),
        # Solo puede haber un registro abierto por terminal.
        Index(
            "uq_historial_abierto_por_terminal",
            "terminal_id",
            unique=True,
            postgresql_where=text("fecha_fin_vigencia IS NULL"),
        ),
        Index("ix_historial_terminal_inicio", "terminal_id", "fecha_inicio_vigencia"),
    )

    terminal_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("terminales_bancarias.id", ondelete="RESTRICT"))
    porcentaje: Mapped[Decimal] = mapped_column(Numeric(5, 2))
    fecha_inicio_vigencia: Mapped[date] = mapped_column(Date)
    fecha_fin_vigencia: Mapped[date | None] = mapped_column(Date)
