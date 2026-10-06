import uuid
from enum import StrEnum
from pathlib import Path

from fastapi import UploadFile

from app.core.config import settings
from app.core.errors import NoEncontrado, ReglaNegocio
from app.models import Empresa


class TipoArchivo(StrEnum):
    PDF1 = "pdf1"
    PDF2 = "pdf2"
    LOGO = "logo"


CAMPO = {
    TipoArchivo.PDF1: "documento_pdf_1_url",
    TipoArchivo.PDF2: "documento_pdf_2_url",
    TipoArchivo.LOGO: "logo_url",
}

MEDIA_TYPES = {"pdf": "application/pdf", "png": "image/png", "jpg": "image/jpeg", "webp": "image/webp"}
CHUNK = 64 * 1024


def _detectar_extension(cabecera: bytes) -> str | None:
    """Identifica el tipo real por su firma (magic bytes), no por el nombre ni el Content-Type."""
    if cabecera.startswith(b"%PDF-"):
        return "pdf"
    if cabecera.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png"
    if cabecera.startswith(b"\xff\xd8\xff"):
        return "jpg"
    if cabecera[:4] == b"RIFF" and cabecera[8:12] == b"WEBP":
        return "webp"
    return None


def _raiz() -> Path:
    return settings.UPLOAD_DIR.resolve()


def _ruta_absoluta(relativa: str) -> Path:
    ruta = (_raiz() / relativa).resolve()
    if not ruta.is_relative_to(_raiz()):  # defensa ante path traversal
        raise NoEncontrado("Archivo no encontrado")
    return ruta


async def guardar(empresa: Empresa, tipo: TipoArchivo, archivo: UploadFile) -> None:
    cabecera = await archivo.read(16)
    extension = _detectar_extension(cabecera)
    permitidas = {"pdf"} if tipo != TipoArchivo.LOGO else {"png", "jpg", "webp"}
    if extension not in permitidas:
        raise ReglaNegocio(f"Tipo de archivo no permitido; se esperaba: {', '.join(sorted(permitidas))}")

    limite = settings.MAX_UPLOAD_MB * 1024 * 1024
    relativa = f"empresas/{empresa.id}/{tipo.value}-{uuid.uuid4().hex}.{extension}"
    destino = _ruta_absoluta(relativa)
    destino.parent.mkdir(parents=True, exist_ok=True)
    temporal = destino.with_suffix(destino.suffix + ".part")

    escritos = len(cabecera)
    try:
        with temporal.open("wb") as salida:
            salida.write(cabecera)
            while bloque := await archivo.read(CHUNK):
                escritos += len(bloque)
                if escritos > limite:
                    raise ReglaNegocio(f"El archivo excede el máximo de {settings.MAX_UPLOAD_MB} MB")
                salida.write(bloque)
        temporal.replace(destino)
    finally:
        temporal.unlink(missing_ok=True)

    anterior = getattr(empresa, CAMPO[tipo])
    setattr(empresa, CAMPO[tipo], relativa)
    if anterior:
        eliminar_fisico(anterior)


def ruta_para_descarga(empresa: Empresa, tipo: TipoArchivo) -> tuple[Path, str]:
    relativa = getattr(empresa, CAMPO[tipo])
    if not relativa:
        raise NoEncontrado("La empresa no tiene ese archivo")
    ruta = _ruta_absoluta(relativa)
    if not ruta.is_file():
        raise NoEncontrado("Archivo no encontrado")
    return ruta, MEDIA_TYPES.get(ruta.suffix.lstrip("."), "application/octet-stream")


def eliminar(empresa: Empresa, tipo: TipoArchivo) -> None:
    relativa = getattr(empresa, CAMPO[tipo])
    if not relativa:
        raise NoEncontrado("La empresa no tiene ese archivo")
    setattr(empresa, CAMPO[tipo], None)
    eliminar_fisico(relativa)


def eliminar_fisico(relativa: str) -> None:
    try:
        _ruta_absoluta(relativa).unlink(missing_ok=True)
    except NoEncontrado:
        pass
