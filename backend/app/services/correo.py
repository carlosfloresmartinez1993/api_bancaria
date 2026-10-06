import smtplib
import ssl
from email.message import EmailMessage

from app.core.config import settings


class CorreoNoConfigurado(RuntimeError):
    pass


def enviar_correo(
    destinatarios: list[str],
    asunto: str,
    texto: str,
    html: str | None = None,
    adjuntos: list[tuple[str, bytes, str, str]] | None = None,
) -> None:
    """adjuntos: lista de (nombre, contenido, maintype, subtype)."""
    if not settings.SMTP_HOST or not settings.SMTP_FROM:
        raise CorreoNoConfigurado("SMTP no configurado (SMTP_HOST / SMTP_FROM)")

    mensaje = EmailMessage()
    mensaje["Subject"] = asunto
    mensaje["From"] = settings.SMTP_FROM
    mensaje["To"] = ", ".join(destinatarios)
    mensaje.set_content(texto)
    if html:
        mensaje.add_alternative(html, subtype="html")
    for nombre, contenido, maintype, subtype in adjuntos or []:
        mensaje.add_attachment(contenido, maintype=maintype, subtype=subtype, filename=nombre)

    contexto = ssl.create_default_context()
    if settings.SMTP_SECURITY == "ssl":
        servidor: smtplib.SMTP = smtplib.SMTP_SSL(settings.SMTP_HOST, settings.SMTP_PORT, context=contexto, timeout=30)
    else:
        servidor = smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=30)
    with servidor:
        if settings.SMTP_SECURITY == "starttls":
            servidor.starttls(context=contexto)
        if settings.SMTP_USER and settings.SMTP_PASSWORD:
            servidor.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
        servidor.send_message(mensaje)
