import uuid
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Query, Response
from fastapi.responses import JSONResponse

from app.api.deps import DB, Admin, UsuarioActual
from app.core.tiempo import hoy
from app.models import AccionBitacora, Usuario
from app.schemas.reporte import ReporteOut
from app.services import reportes as svc
from app.services.acceso import obtener_empresa, obtener_proyecto, obtener_terminal
from app.services.cierre import ejecutar_cierre
from app.services.exportacion import MEDIA, Formato, Reporte, exportar
from app.services.reportes import Agrupar, Alcance, Contenido
from app.services.serializacion import a_json

router = APIRouter(prefix="/reportes", tags=["Reportes"])

FormatoQ = Annotated[Formato, Query(description="json, csv, xlsx o pdf")]
Ids = Annotated[list[uuid.UUID] | None, Query()]


def responder(reporte: Reporte, formato: Formato, nombre: str, usuario: Usuario) -> Response:
    reporte.elaborado_por = usuario.nombre_completo
    if formato == Formato.JSON:
        cuerpo = {
            "titulo": reporte.titulo,
            "parametros": reporte.parametros,
            "columnas": [{"clave": c, "etiqueta": e} for c, e in reporte.columnas],
            "filas": reporte.filas,
            "totales": reporte.totales,
            "elaborado_por": reporte.elaborado_por,
        }
        return JSONResponse(a_json(cuerpo))
    extension = formato.value
    return Response(
        content=exportar(reporte, formato),
        media_type=MEDIA[formato],
        headers={"Content-Disposition": f'attachment; filename="{nombre}-{hoy().isoformat()}.{extension}"'},
    )


def _alcance(db, usuario: Usuario, empresa_id: uuid.UUID | None, terminal_id: list[uuid.UUID] | None,
             proyecto_id: list[uuid.UUID] | None, metodo_pago_id: list[uuid.UUID] | None) -> Alcance:
    """Valida que el usuario tenga acceso a cada elemento elegido (404 si alguno no es suyo)."""
    if empresa_id:
        obtener_empresa(db, usuario, empresa_id)
    for t in terminal_id or []:
        obtener_terminal(db, usuario, t)
    for p in proyecto_id or []:
        obtener_proyecto(db, usuario, p)
    return Alcance(empresa_id=empresa_id, terminal_ids=terminal_id or [], proyecto_ids=proyecto_id or [],
                   metodo_pago_ids=metodo_pago_id or [])


DOC = {"response_model": ReporteOut, "responses": {200: {"content": {m: {} for m in MEDIA.values()}}}}


@router.get("/constructor", **DOC, summary="Constructor de reportes: entradas y salidas por empresa, cliente o proyecto")
def constructor(
    db: DB,
    usuario: UsuarioActual,
    empresa_id: uuid.UUID | None = None,
    terminal_id: Ids = None,
    proyecto_id: Ids = None,
    metodo_pago_id: Ids = None,
    desde: date | None = None,
    hasta: date | None = None,
    contenido: Contenido = Contenido.AMBOS,
    agrupar: Agrupar = Agrupar.PROYECTO,
    requiere_factura: bool | None = None,
    texto: Annotated[str | None, Query(max_length=100)] = None,
    formato: FormatoQ = Formato.JSON,
):
    alcance = _alcance(db, usuario, empresa_id, terminal_id, proyecto_id, metodo_pago_id)
    reporte = svc.constructor(db, usuario, alcance=alcance, desde=desde, hasta=hasta, contenido=contenido,
                              agrupar=agrupar, requiere_factura=requiere_factura, texto=texto)
    return responder(reporte, formato, f"reporte-{agrupar.value}", usuario)


@router.get("/saldos", **DOC, summary="Saldo de cada empresa")
def saldos(db: DB, usuario: UsuarioActual, al_dia: date | None = None, formato: FormatoQ = Formato.JSON):
    return responder(svc.saldos_empresas(db, usuario, al_dia or hoy()), formato, "saldos", usuario)


@router.get("/estado-cuenta", **DOC, summary="Estado de cuenta con saldo corrido")
def estado_cuenta(db: DB, usuario: UsuarioActual, empresa_id: uuid.UUID, desde: date, hasta: date,
                  terminal_id: Ids = None, proyecto_id: Ids = None, metodo_pago_id: Ids = None,
                  formato: FormatoQ = Formato.JSON):
    alcance = _alcance(db, usuario, empresa_id, terminal_id, proyecto_id, metodo_pago_id)
    reporte = svc.estado_cuenta(db, usuario, alcance=alcance, desde=desde, hasta=hasta)
    return responder(reporte, formato, "estado-cuenta", usuario)


@router.get("/conciliacion-diaria", **DOC, summary="Conciliación diaria por cliente y proyecto")
def conciliacion_diaria(db: DB, usuario: UsuarioActual, fecha: date, empresa_id: uuid.UUID | None = None,
                        terminal_id: Ids = None, proyecto_id: Ids = None, formato: FormatoQ = Formato.JSON):
    alcance = _alcance(db, usuario, empresa_id, terminal_id, proyecto_id, None)
    return responder(svc.conciliacion_diaria(db, usuario, fecha, alcance), formato, "conciliacion", usuario)


@router.get("/resumen-mensual", **DOC, summary="Resumen mensual/anual por empresa (admin)")
def resumen_mensual(db: DB, admin: Admin, anio: Annotated[int, Query(ge=2000, le=2100)],
                    mes: Annotated[int | None, Query(ge=1, le=12)] = None, empresa_id: uuid.UUID | None = None,
                    formato: FormatoQ = Formato.JSON):
    return responder(svc.resumen_mensual(db, admin, anio, mes, empresa_id), formato, "resumen", admin)


@router.get("/auditoria-captura", **DOC, summary="Auditoría de captura por contador (admin)")
def auditoria_captura(db: DB, admin: Admin, usuario_id: uuid.UUID | None = None, desde: date | None = None,
                      hasta: date | None = None, formato: FormatoQ = Formato.JSON):
    return responder(svc.auditoria_por_contador(db, usuario_id, desde, hasta), formato, "auditoria-captura", admin)


@router.get("/bitacora", **DOC, summary="Bitácora de auditoría (admin)")
def bitacora(db: DB, admin: Admin, entidad: str | None = None, usuario_id: uuid.UUID | None = None,
             accion: AccionBitacora | None = None, desde: date | None = None, hasta: date | None = None,
             limit: Annotated[int, Query(ge=1, le=5000)] = 100, offset: Annotated[int, Query(ge=0)] = 0,
             formato: FormatoQ = Formato.JSON):
    reporte = svc.bitacora(db, entidad=entidad, usuario_id=usuario_id, accion=accion, desde=desde, hasta=hasta,
                           limit=limit, offset=offset)
    return responder(reporte, formato, "bitacora", admin)


@router.get("/cierre-diario", **DOC, summary="Resumen del cierre de un día (admin)")
def cierre_diario(db: DB, admin: Admin, fecha: date | None = None, formato: FormatoQ = Formato.JSON):
    return responder(svc.resumen_cierre(db, fecha or hoy()), formato, "cierre-diario", admin)


@router.post("/cierre-diario/enviar", summary="Envía (o reenvía) el cierre de un día por correo (admin)")
def enviar_cierre(_: Admin, fecha: date | None = None, forzar: bool = False):
    return a_json(ejecutar_cierre(fecha, forzar=forzar))
