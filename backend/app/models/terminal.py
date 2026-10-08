import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, ForeignKeyConstraint, Index, String, UniqueConstraint, func, text, true
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, UUIDPk
from app.models.empresa import Empresa


class TerminalBancaria(UUIDPk, Base):
    """Terminal punto de venta. En la interfaz se llama «Cliente».

    Puede pertenecer a una empresa o no tener empresa. Siempre tiene un responsable
    (`usuario_id`), que define quién la ve y la opera: si tiene empresa es el responsable
    de la empresa (lo garantiza la llave compuesta, que además lo actualiza al reasignar
    la empresa); si no tiene, es el contador que la registró.
    """

    __tablename__ = "terminales_bancarias"
    __table_args__ = (
        UniqueConstraint("empresa_id", "identificador_terminal", name="uq_terminal_por_empresa"),
        # Sin empresa, el identificador es único entre los clientes del mismo responsable.
        Index(
            "uq_terminal_sin_empresa_por_responsable",
            "usuario_id",
            "identificador_terminal",
            unique=True,
            postgresql_where=text("empresa_id IS NULL"),
        ),
        ForeignKeyConstraint(
            ["empresa_id", "usuario_id"],
            ["empresas.id", "empresas.usuario_id"],
            name="fk_terminal_responsable_de_la_empresa",
            onupdate="CASCADE",
            ondelete="RESTRICT",
        ),
    )

    empresa_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("empresas.id", ondelete="RESTRICT"), index=True)
    usuario_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("usuarios.id", ondelete="RESTRICT"), index=True)
    identificador_terminal: Mapped[str] = mapped_column(String(100))
    activa: Mapped[bool] = mapped_column(default=True, server_default=true())
    fecha_registro: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    empresa: Mapped[Empresa | None] = relationship(
        primaryjoin="TerminalBancaria.empresa_id == Empresa.id", foreign_keys=[empresa_id], viewonly=True
    )
