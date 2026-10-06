import html
import logging
from datetime import date

from sqlalchemy import exists, func, select

from app.core.config import settings
from app.core.tiempo import hoy
from app.db.session import SessionLocal
from app.models import AccionBitacora, BitacoraAuditoria, Rol, Usuario
from app.services.bitacora import registrar
from app.services.correo import enviar_correo
from app.services.exportacion import Reporte, a_pdf
from app.services.reportes import resumen_cierre

logger = logging.getLogger(__name__)

# Candado de PostgreSQL: si varios procesos intentan el cierre a la vez, solo uno lo ejecuta.
LOCK_CIERRE = 740_281_113


def _cuerpo(reporte: Reporte) -> tuple[str, str]:
    t = reporte.totales or {}
    texto_lineas = [reporte.titulo, ""]
    for f in reporte.filas:
        texto_lineas.append(
            f"{f['contador']}: {f['movimientos']} movimientos, bruto {f['monto_bruto']:,.2f}, "
            f"comisión {f['comision']:,.2f}, neto {f['monto_neto']:,.2f}"
        )
    texto_lineas += ["", f"TOTAL: {t.get('movimientos', 0)} movimientos, neto {t.get('monto_neto', 0):,.2f}"]

    filas_html = "".join(
        f"<tr><td>{html.escape(f['contador'])}</td><td align='right'>{f['movimientos']}</td>"
        f"<td align='right'>{f['monto_bruto']:,.2f}</td><td align='right'>{f['comision']:,.2f}</td>"
        f"<td align='right'>{f['monto_neto']:,.2f}</td></tr>"
        for f in reporte.filas
    ) or "<tr><td colspan='5'>Sin movimientos capturados</td></tr>"
    cuerpo_html = (
        f"<h2>{html.escape(reporte.titulo)}</h2>"
        "<table border='1' cellpadding='6' cellspacing='0'>"
        "<tr><th>Contador</th><th>Movimientos</th><th>Bruto</th><th>Comisión</th><th>Neto</th></tr>"
        f"{filas_html}"
        f"<tr><th>Total</th><th align='right'>{t.get('movimientos', 0)}</th>"
        f"<th align='right'>{t.get('monto_bruto', 0):,.2f}</th><th align='right'>{t.get('comision', 0):,.2f}</th>"
        f"<th align='right'>{t.get('monto_neto', 0):,.2f}</th></tr></table>"
    )
    return "\n".join(texto_lineas), cuerpo_html


def ejecutar_cierre(dia: date | None = None, forzar: bool = False) -> dict:
    """Calcula el cierre del día con una consulta, lo envía a los admins y lo registra en la bitácora."""
    dia = dia or hoy()
    with SessionLocal() as db:
        if not db.scalar(select(func.pg_try_advisory_xact_lock(LOCK_CIERRE))):
            return {"fecha": dia, "estado": "en_proceso"}

        ya_enviado = db.scalar(
            select(
                exists().where(
                    BitacoraAuditoria.accion == AccionBitacora.CIERRE_ENVIADO,
                    BitacoraAuditoria.detalle["fecha"].astext == dia.isoformat(),
                )
            )
        )
        if ya_enviado and not forzar:
            return {"fecha": dia, "estado": "ya_enviado"}

        reporte = resumen_cierre(db, dia)
        reporte.elaborado_por = "Cierre automático del sistema"
        destinatarios = list(
            db.scalars(select(Usuario.correo).where(Usuario.rol == Rol.ADMIN, Usuario.activo.is_(True)))
        )
        try:
            if not destinatarios:
                raise RuntimeError("No hay administradores activos para recibir el cierre")
            texto, cuerpo_html = _cuerpo(reporte)
            adjuntos = []
            if settings.CIERRE_ADJUNTAR_PDF:
                adjuntos.append((f"cierre-{dia.isoformat()}.pdf", a_pdf(reporte), "application", "pdf"))
            enviar_correo(destinatarios, f"Cierre diario {dia:%d/%m/%Y}", texto, cuerpo_html, adjuntos)
            accion, estado = AccionBitacora.CIERRE_ENVIADO, "enviado"
            detalle = {"fecha": dia, "destinatarios": destinatarios, "totales": reporte.totales}
        except Exception as exc:  # se registra cualquier falla para poder reintentar
            logger.exception("Falló el envío del cierre diario del %s", dia)
            accion, estado = AccionBitacora.CIERRE_ERROR, "error"
            detalle = {"fecha": dia, "error": str(exc)}

        registrar(db, usuario_id=None, entidad="CierreDiario", entidad_id=None, accion=accion, detalle=detalle)
        db.commit()
        return {"fecha": dia, "estado": estado, "detalle": detalle}
