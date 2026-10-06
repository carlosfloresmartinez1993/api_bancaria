import uuid
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import DB, PaginacionDep, UsuarioActual
from app.api.utils import cambios_no_nulos, paginar, validar_no_futura
from app.core.tiempo import hoy
from app.models import AccionBitacora, Empresa, SalidaEmpresa
from app.schemas.comun import Pagina
from app.schemas.salida import SalidaActualizar, SalidaCrear, SalidaOut, SalidaRegistrada
from app.services.acceso import obtener_empresa, obtener_salida, solo_propias
from app.services.bitacora import instantanea, registrar
from app.services.reportes import escapar_like, validar_rango
from app.services.saldos import saldo_empresa

router = APIRouter(prefix="/salidas", tags=["Salidas de dinero"])

CAMPOS = ("monto", "destino", "fecha", "observaciones")


def _con_saldo(db: Session, salida: SalidaEmpresa) -> SalidaRegistrada:
    """El sistema es un control paralelo: no bloquea salidas, pero advierte si el saldo queda negativo."""
    saldo = saldo_empresa(db, salida.empresa_id)
    advertencia = None
    if saldo < 0:
        advertencia = (f"El saldo de la empresa quedó negativo ({saldo:,.2f}). "
                       "Probablemente falta capturar algún ingreso.")
    return SalidaRegistrada(salida=SalidaOut.model_validate(salida), saldo_empresa=saldo, advertencia=advertencia)


@router.get("", response_model=Pagina[SalidaOut])
def listar(db: DB, usuario: UsuarioActual, pag: PaginacionDep, empresa_id: uuid.UUID | None = None,
           desde: date | None = None, hasta: date | None = None,
           texto: Annotated[str | None, Query(max_length=100, description="Búsqueda en destino")] = None):
    validar_rango(desde, hasta)
    stmt = solo_propias(
        select(SalidaEmpresa).join(Empresa, SalidaEmpresa.empresa_id == Empresa.id), usuario
    ).order_by(SalidaEmpresa.fecha.desc(), SalidaEmpresa.fecha_registro.desc())
    if empresa_id:
        stmt = stmt.where(SalidaEmpresa.empresa_id == empresa_id)
    if desde:
        stmt = stmt.where(SalidaEmpresa.fecha >= desde)
    if hasta:
        stmt = stmt.where(SalidaEmpresa.fecha <= hasta)
    if texto:
        stmt = stmt.where(SalidaEmpresa.destino.ilike(f"%{escapar_like(texto)}%", escape="\\"))
    return paginar(db, stmt, pag.limit, pag.offset)


@router.post("", response_model=SalidaRegistrada, status_code=status.HTTP_201_CREATED)
def registrar_salida(datos: SalidaCrear, db: DB, usuario: UsuarioActual):
    empresa = obtener_empresa(db, usuario, datos.empresa_id)
    fecha = datos.fecha or hoy()
    validar_no_futura(fecha)
    salida = SalidaEmpresa(
        empresa_id=empresa.id, usuario_id=usuario.id, monto=datos.monto, destino=datos.destino.strip(),
        fecha=fecha, observaciones=datos.observaciones,
    )
    db.add(salida)
    db.commit()
    db.refresh(salida)
    return _con_saldo(db, salida)


@router.get("/{salida_id}", response_model=SalidaOut)
def obtener(salida_id: uuid.UUID, db: DB, usuario: UsuarioActual):
    return obtener_salida(db, usuario, salida_id)


@router.patch("/{salida_id}", response_model=SalidaRegistrada)
def corregir(salida_id: uuid.UUID, datos: SalidaActualizar, db: DB, usuario: UsuarioActual):
    salida = obtener_salida(db, usuario, salida_id)
    cambios = cambios_no_nulos(datos.model_dump(exclude_unset=True, exclude={"motivo"}), {"monto", "destino", "fecha"})
    if "fecha" in cambios:
        validar_no_futura(cambios["fecha"])
    antes = instantanea(salida, CAMPOS)
    for campo, valor in cambios.items():
        setattr(salida, campo, valor)
    despues = instantanea(salida, CAMPOS)
    if antes != despues:
        registrar(db, usuario_id=usuario.id, entidad="SalidaEmpresa", entidad_id=salida.id,
                  accion=AccionBitacora.EDITAR_SALIDA,
                  detalle={"antes": antes, "despues": despues, "motivo": datos.motivo})
        db.commit()
    return _con_saldo(db, salida)


@router.delete("/{salida_id}", status_code=status.HTTP_204_NO_CONTENT)
def eliminar(salida_id: uuid.UUID, db: DB, usuario: UsuarioActual,
             motivo: Annotated[str | None, Query(max_length=500)] = None):
    salida = obtener_salida(db, usuario, salida_id)
    registrar(db, usuario_id=usuario.id, entidad="SalidaEmpresa", entidad_id=salida.id,
              accion=AccionBitacora.ELIMINAR_SALIDA,
              detalle={"antes": {**instantanea(salida, CAMPOS), "empresa_id": str(salida.empresa_id)},
                       "motivo": motivo})
    db.delete(salida)
    db.commit()
