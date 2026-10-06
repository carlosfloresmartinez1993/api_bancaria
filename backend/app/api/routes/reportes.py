import uuid
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Query, Response
from fastapi.responses import JSONResponse

from app.api.deps import DB, Admin, UsuarioActual
from app.core.tiempo import hoy
from app.models import AccionBitacora
from app.schemas.reporte import ReporteOut
from app.services import reportes as svc
from app.services.acceso import obtener_empresa, obtener_terminal
from app.services.cierre import ejecutar_cierre
from app.services.exportacion import MEDIA, Formato, Reporte, exportar
from app.services.serializacion import a_json

router = APIRouter(prefix="/reportes", tags=["Reportes"])

FormatoQ = Annotated[Formato, Query(description="json, csv, xlsx o pdf")]


def responder(reporte: Reporte, formato: Formato, nombre: str) -> Response:
    if formato == Formato.JSON:
        cuerpo = {
            "titulo": reporte.titulo,
            "parametros": reporte.parametros,
            "columnas": [{"clave": c, "etiqueta": e} for c, e in reporte.columnas],
            "filas": reporte.filas,
            "totales": reporte.totales,
        }
        return JSONResponse(a_json(cuerpo))
    extension = formato.value
    return Response(
        content=exportar(reporte, formato),
        media_type=MEDIA[formato],
        headers={"Content-Disposition": f'attachment; filename="{nombre}-{hoy().isoformat()}.{extension}"'},
    )


DOC = {"response_model": ReporteOut, "responses": {200: {"content": {m: {} for m in MEDIA.values()}}}}


@router.get("/saldos", **DOC, summary="Saldo de cada empresa")
def saldos(db: DB, usuario: UsuarioActual, al_dia: date | None = None, formato: FormatoQ = Formato.JSON):
    return responder(svc.saldos_empresas(db, usuario, al_dia or hoy()), formato, "saldos")


@router.get("/totales-por-empresa", **DOC, summary="1. Movimientos totales por empresa (admin)")
def totales_por_empresa(db: DB, admin: Admin, empresa_id: uuid.UUID | None = None, desde: date | None = None,
                        hasta: date | None = None, formato: FormatoQ = Formato.JSON):
    return responder(svc.totales_por_empresa(db, admin, empresa_id, desde, hasta), formato, "totales-por-empresa")


@router.get("/auditoria-captura", **DOC, summary="2. Auditoría de captura por contador (admin)")
def auditoria_captura(db: DB, _: Admin, usuario_id: uuid.UUID | None = None, desde: date | None = None,
                      hasta: date | None = None, formato: FormatoQ = Formato.JSON):
    return responder(svc.auditoria_por_contador(db, usuario_id, desde, hasta), formato, "auditoria-captura")


@router.get("/movimientos-por-terminal", **DOC, summary="3. Movimientos por terminal")
def movimientos_por_terminal(db: DB, usuario: UsuarioActual, terminal_id: uuid.UUID, desde: date | None = None,
                             hasta: date | None = None, formato: FormatoQ = Formato.JSON):
    terminal = obtener_terminal(db, usuario, terminal_id)
    reporte = svc.movimientos_detalle(db, usuario, titulo=f"Movimientos — terminal {terminal.identificador_terminal}",
                                      terminal_id=terminal.id, desde=desde, hasta=hasta)
    return responder(reporte, formato, "movimientos-terminal")


@router.get("/movimientos-por-empresa", **DOC, summary="4. Movimientos por empresa")
def movimientos_por_empresa(db: DB, usuario: UsuarioActual, empresa_id: uuid.UUID, desde: date | None = None,
                            hasta: date | None = None, formato: FormatoQ = Formato.JSON):
    empresa = obtener_empresa(db, usuario, empresa_id)
    reporte = svc.movimientos_detalle(db, usuario, titulo=f"Movimientos — {empresa.nombre}",
                                      empresa_id=empresa.id, desde=desde, hasta=hasta)
    return responder(reporte, formato, "movimientos-empresa")


@router.get("/conciliacion-diaria", **DOC, summary="5. Conciliación diaria por terminal")
def conciliacion_diaria(db: DB, usuario: UsuarioActual, fecha: date, empresa_id: uuid.UUID | None = None,
                        terminal_id: uuid.UUID | None = None, formato: FormatoQ = Formato.JSON):
    if empresa_id:
        obtener_empresa(db, usuario, empresa_id)
    if terminal_id:
        obtener_terminal(db, usuario, terminal_id)
    return responder(svc.conciliacion_diaria(db, usuario, fecha, empresa_id, terminal_id), formato, "conciliacion")


@router.get("/resumen-mensual", **DOC, summary="6. Resumen mensual/anual por empresa (admin)")
def resumen_mensual(db: DB, admin: Admin, anio: Annotated[int, Query(ge=2000, le=2100)],
                    mes: Annotated[int | None, Query(ge=1, le=12)] = None, empresa_id: uuid.UUID | None = None,
                    formato: FormatoQ = Formato.JSON):
    return responder(svc.resumen_mensual(db, admin, anio, mes, empresa_id), formato, "resumen")


@router.get("/salidas", **DOC, summary="7. Historial de salidas")
def historial_salidas(db: DB, usuario: UsuarioActual, empresa_id: uuid.UUID | None = None,
                      desde: date | None = None, hasta: date | None = None,
                      texto: Annotated[str | None, Query(max_length=100)] = None, formato: FormatoQ = Formato.JSON):
    if empresa_id:
        obtener_empresa(db, usuario, empresa_id)
    return responder(svc.historial_salidas(db, usuario, empresa_id, desde, hasta, texto), formato, "salidas")


@router.get("/estado-cuenta", **DOC, summary="8. Estado de cuenta de la empresa")
def estado_cuenta(db: DB, usuario: UsuarioActual, empresa_id: uuid.UUID, desde: date, hasta: date,
                  formato: FormatoQ = Formato.JSON):
    empresa = obtener_empresa(db, usuario, empresa_id)
    return responder(svc.estado_cuenta(db, usuario, empresa, desde, hasta), formato, "estado-cuenta")


@router.get("/comisiones-por-terminal", **DOC, summary="9. Comisiones generadas por terminal (admin)")
def comisiones(db: DB, admin: Admin, empresa_id: uuid.UUID | None = None, desde: date | None = None,
               hasta: date | None = None, formato: FormatoQ = Formato.JSON):
    return responder(svc.comisiones_por_terminal(db, admin, empresa_id, desde, hasta), formato, "comisiones")


@router.get("/bitacora", **DOC, summary="10. Bitácora de auditoría (admin)")
def bitacora(db: DB, _: Admin, entidad: str | None = None, usuario_id: uuid.UUID | None = None,
             accion: AccionBitacora | None = None, desde: date | None = None, hasta: date | None = None,
             limit: Annotated[int, Query(ge=1, le=5000)] = 100, offset: Annotated[int, Query(ge=0)] = 0,
             formato: FormatoQ = Formato.JSON):
    reporte = svc.bitacora(db, entidad=entidad, usuario_id=usuario_id, accion=accion, desde=desde, hasta=hasta,
                           limit=limit, offset=offset)
    return responder(reporte, formato, "bitacora")


@router.get("/cierre-diario", **DOC, summary="Resumen del cierre de un día (admin)")
def cierre_diario(db: DB, _: Admin, fecha: date | None = None, formato: FormatoQ = Formato.JSON):
    return responder(svc.resumen_cierre(db, fecha or hoy()), formato, "cierre-diario")


@router.post("/cierre-diario/enviar", summary="Envía (o reenvía) el cierre de un día por correo (admin)")
def enviar_cierre(_: Admin, fecha: date | None = None, forzar: bool = False):
    return a_json(ejecutar_cierre(fecha, forzar=forzar))
