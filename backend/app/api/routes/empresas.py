import uuid
from datetime import date

from fastapi import APIRouter, File, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy import select

from app.api.deps import DB, Admin, PaginacionDep, UsuarioActual
from app.api.utils import cambios_no_nulos, paginar
from app.core.errors import Prohibido, ReglaNegocio
from app.core.tiempo import hoy
from app.models import AccionBitacora, Empresa, Rol, Usuario
from app.schemas.comun import Pagina
from app.schemas.empresa import ArchivosEmpresa, EmpresaActualizar, EmpresaCrear, EmpresaOut, Reasignar, SaldoOut
from app.services import archivos
from app.services.acceso import obtener_empresa, solo_propias
from app.services.archivos import CAMPO, TipoArchivo
from app.services.bitacora import registrar
from app.services.reportes import escapar_like
from app.services.saldos import totales_empresa

router = APIRouter(prefix="/empresas", tags=["Empresas"])


def a_salida(empresa: Empresa) -> EmpresaOut:
    base = f"/empresas/{empresa.id}/archivos"
    enlaces = {t.value: (f"{base}/{t.value}" if getattr(empresa, CAMPO[t]) else None) for t in TipoArchivo}
    return EmpresaOut.model_validate(
        {**{c: getattr(empresa, c) for c in EmpresaOut.model_fields if c != "archivos"},
         "archivos": ArchivosEmpresa(**enlaces)}
    )


def _validar_propietario(db, usuario_id: uuid.UUID) -> Usuario:
    propietario = db.get(Usuario, usuario_id)
    if propietario is None or not propietario.activo:
        raise ReglaNegocio("El usuario indicado no existe o está inactivo")
    return propietario


@router.get("", response_model=Pagina[EmpresaOut])
def listar(db: DB, usuario: UsuarioActual, pag: PaginacionDep, q: str | None = None,
           usuario_id: uuid.UUID | None = None):
    """Un contador solo recibe sus empresas. Un admin puede filtrar por propietario."""
    stmt = solo_propias(select(Empresa), usuario).order_by(Empresa.nombre)
    if q:
        stmt = stmt.where(Empresa.nombre.ilike(f"%{escapar_like(q)}%", escape="\\"))
    if usuario_id and usuario.es_admin:
        stmt = stmt.where(Empresa.usuario_id == usuario_id)
    pagina = paginar(db, stmt, pag.limit, pag.offset)
    pagina["items"] = [a_salida(e) for e in pagina["items"]]
    return pagina


@router.post("", response_model=EmpresaOut, status_code=status.HTTP_201_CREATED)
def crear(datos: EmpresaCrear, db: DB, usuario: UsuarioActual):
    """La empresa queda a nombre del usuario autenticado (o del contador que indique un admin)."""
    propietario_id = usuario.id
    if datos.usuario_id and datos.usuario_id != usuario.id:
        if not usuario.es_admin:
            raise Prohibido("Solo un administrador puede registrar empresas a nombre de otro usuario")
        propietario_id = _validar_propietario(db, datos.usuario_id).id
    empresa = Empresa(**datos.model_dump(exclude={"usuario_id"}), usuario_id=propietario_id)
    db.add(empresa)
    db.commit()
    db.refresh(empresa)
    return a_salida(empresa)


@router.get("/{empresa_id}", response_model=EmpresaOut)
def obtener(empresa_id: uuid.UUID, db: DB, usuario: UsuarioActual):
    return a_salida(obtener_empresa(db, usuario, empresa_id))


@router.patch("/{empresa_id}", response_model=EmpresaOut)
def actualizar(empresa_id: uuid.UUID, datos: EmpresaActualizar, db: DB, usuario: UsuarioActual):
    empresa = obtener_empresa(db, usuario, empresa_id)
    cambios = cambios_no_nulos(datos.model_dump(exclude_unset=True), {"nombre", "csf", "banco", "numero_cuenta"})
    for campo, valor in cambios.items():
        setattr(empresa, campo, valor)
    db.commit()
    return a_salida(empresa)


@router.post("/{empresa_id}/reasignar", response_model=EmpresaOut)
def reasignar(empresa_id: uuid.UUID, datos: Reasignar, db: DB, admin: Admin):
    """Pasa la empresa (con sus terminales, movimientos y salidas) a otro contador."""
    empresa = obtener_empresa(db, admin, empresa_id)
    nuevo = _validar_propietario(db, datos.usuario_id)
    if nuevo.rol != Rol.CONTADOR:
        raise ReglaNegocio("Solo se puede reasignar a un usuario con rol contador")
    if empresa.usuario_id != nuevo.id:
        anterior = empresa.usuario_id
        empresa.usuario_id = nuevo.id
        registrar(db, usuario_id=admin.id, entidad="Empresa", entidad_id=empresa.id,
                  accion=AccionBitacora.REASIGNAR_EMPRESA, detalle={"antes": anterior, "despues": nuevo.id})
        db.commit()
    return a_salida(empresa)


@router.get("/{empresa_id}/saldo", response_model=SaldoOut)
def saldo(empresa_id: uuid.UUID, db: DB, usuario: UsuarioActual, al_dia: date | None = None):
    empresa = obtener_empresa(db, usuario, empresa_id)
    al_dia = al_dia or hoy()
    ingresos, salidas = totales_empresa(db, empresa.id, al_dia)
    return SaldoOut(empresa_id=empresa.id, al_dia=al_dia, ingresos_netos=ingresos, salidas=salidas,
                    saldo=ingresos - salidas)


# ---------------------------------------------------------------- archivos
@router.put("/{empresa_id}/archivos/{tipo}", response_model=EmpresaOut)
async def subir_archivo(empresa_id: uuid.UUID, tipo: TipoArchivo, db: DB, usuario: UsuarioActual,
                        archivo: UploadFile = File(...)):
    """pdf1 y pdf2 aceptan PDF; logo acepta PNG, JPG o WEBP. Se valida el contenido real del archivo."""
    empresa = obtener_empresa(db, usuario, empresa_id)
    await archivos.guardar(empresa, tipo, archivo)
    db.commit()
    return a_salida(empresa)


@router.get("/{empresa_id}/archivos/{tipo}", response_class=FileResponse)
def descargar_archivo(empresa_id: uuid.UUID, tipo: TipoArchivo, db: DB, usuario: UsuarioActual):
    empresa = obtener_empresa(db, usuario, empresa_id)
    ruta, media_type = archivos.ruta_para_descarga(empresa, tipo)
    return FileResponse(ruta, media_type=media_type, filename=f"{tipo.value}{ruta.suffix}")


@router.delete("/{empresa_id}/archivos/{tipo}", status_code=status.HTTP_204_NO_CONTENT)
def eliminar_archivo(empresa_id: uuid.UUID, tipo: TipoArchivo, db: DB, usuario: UsuarioActual):
    empresa = obtener_empresa(db, usuario, empresa_id)
    archivos.eliminar(empresa, tipo)
    db.commit()
