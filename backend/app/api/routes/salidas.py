import uuid
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Query, status
from sqlalchemy import or_, select
from sqlalchemy.orm import Session, joinedload

from app.api.deps import DB, PaginacionDep, UsuarioActual
from app.api.utils import cambios_no_nulos, paginar, validar_no_futura
from app.core.errors import ReglaNegocio
from app.core.tiempo import hoy
from app.models import AccionBitacora, Proyecto, Salida, TerminalBancaria
from app.schemas.comun import Pagina
from app.schemas.salida import SalidaActualizar, SalidaCrear, SalidaOut, SalidaRegistrada
from app.services.acceso import clientes_propios, filtrar_empresa, mismo_grupo, obtener_proyecto, obtener_salida, unir_jerarquia
from app.services.bitacora import instantanea, registrar
from app.services.metodos_pago import validar_metodo_pago
from app.services.reportes import escapar_like, validar_rango
from app.services.saldos import totales

router = APIRouter(prefix="/salidas", tags=["Salidas de dinero"])

CAMPOS = ("proyecto_id", "monto", "destino", "fecha", "metodo_pago_id", "observaciones")


def _con_saldo(db: Session, salida: Salida) -> SalidaRegistrada:
    """El sistema es un control paralelo: no bloquea salidas, pero advierte si el saldo del proyecto queda negativo."""
    saldo_proyecto = totales(db, proyecto_id=salida.proyecto_id).saldo
    saldo_empresa = totales(db, empresa_id=salida.empresa_id).saldo if salida.empresa_id else None
    advertencia = None
    if saldo_proyecto < 0:
        advertencia = (f"El saldo del proyecto quedó negativo ({saldo_proyecto:,.2f}). "
                       "Probablemente falta capturar alguna entrada.")
    return SalidaRegistrada(salida=SalidaOut.model_validate(salida), saldo_proyecto=saldo_proyecto,
                            saldo_empresa=saldo_empresa, advertencia=advertencia)


@router.get("", response_model=Pagina[SalidaOut])
def listar(db: DB, usuario: UsuarioActual, pag: PaginacionDep, empresa_id: uuid.UUID | None = None,
           sin_empresa: bool | None = None, terminal_id: uuid.UUID | None = None, proyecto_id: uuid.UUID | None = None,
           metodo_pago_id: uuid.UUID | None = None, desde: date | None = None, hasta: date | None = None,
           texto: Annotated[str | None, Query(max_length=100, description="Búsqueda en destino")] = None):
    validar_rango(desde, hasta)
    stmt = clientes_propios(
        unir_jerarquia(select(Salida), Salida.proyecto_id).options(
            joinedload(Salida.proyecto).joinedload(Proyecto.terminal)
        ),
        usuario,
    ).order_by(Salida.fecha.desc(), Salida.fecha_registro.desc())
    stmt = filtrar_empresa(stmt, empresa_id, sin_empresa)
    if terminal_id:
        stmt = stmt.where(TerminalBancaria.id == terminal_id)
    if proyecto_id:
        stmt = stmt.where(Salida.proyecto_id == proyecto_id)
    if metodo_pago_id:
        stmt = stmt.where(Salida.metodo_pago_id == metodo_pago_id)
    if desde:
        stmt = stmt.where(Salida.fecha >= desde)
    if hasta:
        stmt = stmt.where(Salida.fecha <= hasta)
    if texto:
        patron = f"%{escapar_like(texto.strip())}%"
        stmt = stmt.where(or_(Salida.destino.ilike(patron, escape="\\"),
                              Salida.observaciones.ilike(patron, escape="\\")))
    return paginar(db, stmt, pag.limit, pag.offset)


@router.post("", response_model=SalidaRegistrada, status_code=status.HTTP_201_CREATED)
def registrar_salida(datos: SalidaCrear, db: DB, usuario: UsuarioActual):
    proyecto = obtener_proyecto(db, usuario, datos.proyecto_id)
    if not proyecto.activo:
        raise ReglaNegocio("El proyecto está inactivo; no acepta salidas nuevas")
    fecha = datos.fecha or hoy()
    validar_no_futura(fecha)
    validar_metodo_pago(db, datos.metodo_pago_id)
    salida = Salida(
        proyecto_id=proyecto.id, usuario_id=usuario.id, metodo_pago_id=datos.metodo_pago_id, monto=datos.monto,
        destino=datos.destino.strip(), fecha=fecha, observaciones=datos.observaciones,
    )
    db.add(salida)
    db.commit()
    return _con_saldo(db, obtener_salida(db, usuario, salida.id))


@router.get("/{salida_id}", response_model=SalidaOut)
def obtener(salida_id: uuid.UUID, db: DB, usuario: UsuarioActual):
    return obtener_salida(db, usuario, salida_id)


@router.patch("/{salida_id}", response_model=SalidaRegistrada)
def corregir(salida_id: uuid.UUID, datos: SalidaActualizar, db: DB, usuario: UsuarioActual):
    salida = obtener_salida(db, usuario, salida_id)
    cambios = cambios_no_nulos(datos.model_dump(exclude_unset=True, exclude={"motivo"}),
                               {"proyecto_id", "monto", "destino", "fecha", "metodo_pago_id"})
    if "proyecto_id" in cambios and cambios["proyecto_id"] != salida.proyecto_id:
        destino = obtener_proyecto(db, usuario, cambios["proyecto_id"])
        if not mismo_grupo(destino.terminal, salida.proyecto.terminal):
            raise ReglaNegocio("Solo se puede mover la salida a otro proyecto de la misma empresa "
                               "(o del mismo cliente, si no tiene empresa)")
        if not destino.activo:
            raise ReglaNegocio("El proyecto destino está inactivo")
    if "fecha" in cambios:
        validar_no_futura(cambios["fecha"])
    if "metodo_pago_id" in cambios and cambios["metodo_pago_id"] != salida.metodo_pago_id:
        validar_metodo_pago(db, cambios["metodo_pago_id"])
    antes = instantanea(salida, CAMPOS)
    for campo, valor in cambios.items():
        setattr(salida, campo, valor)
    despues = instantanea(salida, CAMPOS)
    if antes != despues:
        registrar(db, usuario_id=usuario.id, entidad="Salida", entidad_id=salida.id,
                  accion=AccionBitacora.EDITAR_SALIDA,
                  detalle={"antes": antes, "despues": despues, "motivo": datos.motivo})
        db.commit()
    return _con_saldo(db, obtener_salida(db, usuario, salida_id))


@router.delete("/{salida_id}", status_code=status.HTTP_204_NO_CONTENT)
def eliminar(salida_id: uuid.UUID, db: DB, usuario: UsuarioActual,
             motivo: Annotated[str | None, Query(max_length=500)] = None):
    salida = obtener_salida(db, usuario, salida_id)
    registrar(db, usuario_id=usuario.id, entidad="Salida", entidad_id=salida.id,
              accion=AccionBitacora.ELIMINAR_SALIDA,
              detalle={"antes": instantanea(salida, CAMPOS), "motivo": motivo})
    db.delete(salida)
    db.commit()
