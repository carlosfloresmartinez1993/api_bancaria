import uuid
from datetime import date, datetime
from decimal import Decimal

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
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, UUIDPk
from app.models.terminal import TerminalBancaria


class Proyecto(UUIDPk, Base):
    """Proyecto de un cliente (terminal). Aquí vive el porcentaje de comisión."""

    __tablename__ = "proyectos"
    __table_args__ = (UniqueConstraint("terminal_id", "nombre", name="uq_proyecto_por_terminal"),)

    terminal_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("terminales_bancarias.id", ondelete="RESTRICT"), index=True)
    nombre: Mapped[str] = mapped_column(String(100))
    activo: Mapped[bool] = mapped_column(default=True, server_default=true())
    fecha_registro: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    terminal: Mapped[TerminalBancaria] = relationship()

    @property
    def empresa_id(self) -> uuid.UUID:
        return self.terminal.empresa_id


class HistorialPorcentajeProyecto(UUIDPk, Base):
    """Fuente única del porcentaje de comisión de cada proyecto.

    Un registro rige desde fecha_inicio_vigencia (inclusive) hasta
    fecha_fin_vigencia (exclusiva); NULL en la fecha fin = vigente.
    """

    __tablename__ = "historial_porcentajes_proyecto"
    __table_args__ = (
        CheckConstraint("porcentaje >= 0 AND porcentaje < 100", name="porcentaje_rango"),
        CheckConstraint(
            "fecha_fin_vigencia IS NULL OR fecha_fin_vigencia > fecha_inicio_vigencia", name="vigencia_valida"
        ),
        # Solo puede haber un registro abierto por proyecto.
        Index(
            "uq_historial_abierto_por_proyecto",
            "proyecto_id",
            unique=True,
            postgresql_where=text("fecha_fin_vigencia IS NULL"),
        ),
        Index("ix_historial_proyecto_inicio", "proyecto_id", "fecha_inicio_vigencia"),
    )

    proyecto_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("proyectos.id", ondelete="RESTRICT"))
    porcentaje: Mapped[Decimal] = mapped_column(Numeric(5, 2))
    fecha_inicio_vigencia: Mapped[date] = mapped_column(Date)
    fecha_fin_vigencia: Mapped[date | None] = mapped_column(Date)
