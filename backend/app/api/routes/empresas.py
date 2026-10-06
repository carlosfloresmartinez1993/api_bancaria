import uuid
from datetime import date

from fastapi import APIRouter, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import DB, Admin, PaginacionDep, UsuarioActual
from app.api.utils import cambios_no_nulos, paginar
from app.core.errors import Prohibido, ReglaNegocio
from app.core.tiempo import hoy
from app.models import AccionBitacora, Empresa, Rol, TerminalBancaria, Usuario
from app.schemas.comun import Pagina
from app.schemas.empresa import EmpresaActualizar, EmpresaCrear, EmpresaOut, Reasignar, SaldoOut
from app.services.acceso import obtener_empresa, solo_propias
from app.services.bitacora import registrar
from app.services.reportes import escapar_like
from app.services.saldos import totales

router = APIRouter(prefix="/empresas", tags=["Empresas"])


def _salidas(db: Session, empresas: list[Empresa]) -> list[EmpresaOut]:
    """Agrega a cada empresa cuántos clientes (terminales) tiene."""
    conteo = dict(
        db.execute(
            select(TerminalBancaria.empresa_id, func.count())
            .where(TerminalBancaria.empresa_id.in_([e.id for e in empresas]))
            .group_by(TerminalBancaria.empresa_id)
        ).all()
    ) if empresas else {}
    return [EmpresaOut.model_validate(e).model_copy(update={"num_clientes": conteo.get(e.id, 0)}) for e in empresas]


def _validar_propietario(db, usuario_id: uuid.UUID) -> Usuario:
    propietario = db.get(Usuario, usuario_id)
    if propietario is None or not propietario.activo:
        raise ReglaNegocio("El usuario indicado no existe o está inactivo")
    return propietario


def _limpiar(datos: dict) -> dict:
    """Los textos opcionales vacíos se guardan como NULL."""
    return {k: (v.strip() or None) if isinstance(v, str) and k != "nombre" else v for k, v in datos.items()}


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
    pagina["items"] = _salidas(db, pagina["items"])
    return pagina


@router.post("", response_model=EmpresaOut, status_code=status.HTTP_201_CREATED)
def crear(datos: EmpresaCrear, db: DB, usuario: UsuarioActual):
    """La empresa queda a nombre del usuario autenticado (o del contador que indique un admin)."""
    propietario_id = usuario.id
    if datos.usuario_id and datos.usuario_id != usuario.id:
        if not usuario.es_admin:
            raise Prohibido("Solo un administrador puede registrar empresas a nombre de otro usuario")
        propietario_id = _validar_propietario(db, datos.usuario_id).id
    empresa = Empresa(**_limpiar(datos.model_dump(exclude={"usuario_id"})), usuario_id=propietario_id)
    empresa.nombre = empresa.nombre.strip()
    db.add(empresa)
    db.commit()
    db.refresh(empresa)
    return _salidas(db, [empresa])[0]


@router.get("/{empresa_id}", response_model=EmpresaOut)
def obtener(empresa_id: uuid.UUID, db: DB, usuario: UsuarioActual):
    return _salidas(db, [obtener_empresa(db, usuario, empresa_id)])[0]


@router.patch("/{empresa_id}", response_model=EmpresaOut)
def actualizar(empresa_id: uuid.UUID, datos: EmpresaActualizar, db: DB, usuario: UsuarioActual):
    empresa = obtener_empresa(db, usuario, empresa_id)
    cambios = _limpiar(cambios_no_nulos(datos.model_dump(exclude_unset=True), {"nombre"}))
    for campo, valor in cambios.items():
        setattr(empresa, campo, valor.strip() if campo == "nombre" else valor)
    db.commit()
    return _salidas(db, [empresa])[0]


@router.post("/{empresa_id}/reasignar", response_model=EmpresaOut)
def reasignar(empresa_id: uuid.UUID, datos: Reasignar, db: DB, admin: Admin):
    """Pasa la empresa (con sus clientes, proyectos, movimientos y salidas) a otro contador."""
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
    return _salidas(db, [empresa])[0]


@router.get("/{empresa_id}/saldo", response_model=SaldoOut)
def saldo(empresa_id: uuid.UUID, db: DB, usuario: UsuarioActual, al_dia: date | None = None):
    empresa = obtener_empresa(db, usuario, empresa_id)
    al_dia = al_dia or hoy()
    t = totales(db, empresa_id=empresa.id, hasta=al_dia)
    return SaldoOut(al_dia=al_dia, ingresos_brutos=t.ingresos_brutos, comisiones=t.comisiones,
                    ingresos_netos=t.ingresos_netos, salidas=t.salidas, saldo=t.saldo)
