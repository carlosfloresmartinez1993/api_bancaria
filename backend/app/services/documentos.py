"""Factura (PDF) de una entrada: validación, nombre y clave en el almacenamiento."""
import logging
import uuid
from pathlib import PurePath
from urllib.parse import quote

from fastapi import UploadFile

from app.core.config import settings
from app.core.errors import ReglaNegocio
from app.services.almacenamiento import almacenamiento

log = logging.getLogger(__name__)
CHUNK = 64 * 1024


def nombre_limpio(original: str | None) -> str:
    # Solo el nombre (sin la ruta del equipo del usuario) y sin caracteres de control.
    nombre = PurePath((original or "").replace("\\", "/")).name
    nombre = "".join(c for c in nombre if c.isprintable()).strip() or "documento.pdf"
    if not nombre.lower().endswith(".pdf"):
        nombre += ".pdf"
    return nombre[-255:]


async def leer_pdf(archivo: UploadFile) -> bytes:
    """Lee el archivo con límite de tamaño y valida que sea PDF por su contenido, no por la extensión."""
    limite = settings.MAX_DOCUMENTO_MB * 1024 * 1024
    partes: list[bytes] = []
    leidos = 0
    while bloque := await archivo.read(CHUNK):
        leidos += len(bloque)
        if leidos > limite:
            raise ReglaNegocio(f"El archivo excede el máximo de {settings.MAX_DOCUMENTO_MB} MB")
        partes.append(bloque)
    contenido = b"".join(partes)
    if not contenido.startswith(b"%PDF-"):
        raise ReglaNegocio("Solo se aceptan archivos PDF")
    return contenido


def nueva_clave(movimiento_id: uuid.UUID) -> str:
    # Nombre aleatorio: no depende del nombre que puso el usuario y no choca al reemplazar.
    return f"entradas/{movimiento_id}/{uuid.uuid4().hex}.pdf"


def borrar_sin_fallar(clave: str | None) -> None:
    """Borra un archivo que ya no usa ningún registro. Si falla, solo queda huérfano: se registra y sigue."""
    if not clave:
        return
    try:
        almacenamiento().eliminar(clave)
    except Exception:  # noqa: BLE001 - el cambio en la BD ya se confirmó
        log.exception("No se pudo borrar el archivo %s del almacenamiento", clave)


def disposicion(nombre: str) -> str:
    """Content-Disposition que abre el PDF en el navegador y conserva acentos en el nombre."""
    ascii_ = nombre.encode("ascii", "replace").decode().replace('"', "").replace("?", "_")
    return f"inline; filename=\"{ascii_}\"; filename*=UTF-8''{quote(nombre)}"
