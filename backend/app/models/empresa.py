import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, UUIDPk
from app.models.usuario import Usuario


class Empresa(UUIDPk, Base):
    __tablename__ = "empresas"

    # Contador (o admin) al que pertenece la empresa: único criterio de acceso.
    usuario_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("usuarios.id", ondelete="RESTRICT"), index=True)
    nombre: Mapped[str] = mapped_column(String(200))
    csf: Mapped[str] = mapped_column(String(100))
    # Rutas internas de los archivos; nunca se exponen tal cual en la API.
    documento_pdf_1_url: Mapped[str | None] = mapped_column(String(500))
    documento_pdf_2_url: Mapped[str | None] = mapped_column(String(500))
    logo_url: Mapped[str | None] = mapped_column(String(500))
    # Única cuenta bancaria de la empresa (solo informativa).
    banco: Mapped[str] = mapped_column(String(100))
    numero_cuenta: Mapped[str] = mapped_column(String(30))
    clabe: Mapped[str | None] = mapped_column(String(18))
    fecha_registro: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    propietario: Mapped[Usuario] = relationship()
