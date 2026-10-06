from datetime import datetime

from sqlalchemy import DateTime, String, func, true
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, UUIDPk
from app.models.enums import Rol, enum_columna


class Usuario(UUIDPk, Base):
    __tablename__ = "usuarios"

    nombre: Mapped[str] = mapped_column(String(100))
    apellidos: Mapped[str] = mapped_column(String(150))
    correo: Mapped[str] = mapped_column(String(254), unique=True)
    password_hash: Mapped[str] = mapped_column(String(100))
    rol: Mapped[Rol] = mapped_column(enum_columna(Rol, "rol_usuario", 20))
    activo: Mapped[bool] = mapped_column(default=True, server_default=true())
    fecha_creacion: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    @property
    def es_admin(self) -> bool:
        return self.rol == Rol.ADMIN

    @property
    def nombre_completo(self) -> str:
        return f"{self.nombre} {self.apellidos}"
