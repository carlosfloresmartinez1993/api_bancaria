import uuid
from datetime import date

from fastapi import APIRouter, status
from sqlalchemy import and_, func, select
from sqlalchemy.orm import Session, joinedload

from app.api.deps import DB, PaginacionDep, UsuarioActual
from app.api.utils import cambios_no_nulos, validar_no_futura
from app.core.errors import Conflicto
from app.core.tiempo import hoy
from app.models import AccionBitacora, Empresa, HistorialPorcentajeProyecto as Historial, Proyecto, TerminalBancaria
from app.schemas.comun import Pagina
from app.schemas.empresa import SaldoOut
from app.schemas.proyecto import (
    CambioPorcentaje,
    CambioPorcentajeOut,
    HistorialOut,
    ProyectoActualizar,
    ProyectoCrear,
    ProyectoOut,
)
from app.services.acceso import clientes_propios, filtrar_empresa, obtener_proyecto, obtener_terminal
from app.services.bitacora import registrar
from app.services.porcentajes import cambiar_porcentaje, condicion_vigente, crear_porcentaje_inicial, porcentaje_vigente
from app.services.saldos import totales

router = APIRouter(prefix="/proyectos", tags=["Proyectos"])


def _nombre_libre(db: Session, terminal_id: uuid.UUID, nombre: str, excepto: uuid.UUID | None = None):
    stmt = select(Proyecto.id).where(Proyecto.terminal_id == terminal_id, Proyecto.nombre == nombre)
    if excepto:
        stmt = stmt.where(Proyecto.id != excepto)
    if db.scalar(stmt):
        raise Conflicto("El cliente ya tiene un proyecto con ese nombre")


def _salida(db: Session, proyecto: Proyecto) -> ProyectoOut:
    salida = ProyectoOut.model_validate(proyecto)
    salida.porcentaje_vigente = db.scalar(
        select(Historial.porcentaje).where(Historial.proyecto_id == proyecto.id, *condicion_vigente(hoy()))
    )
    return salida


@router.get("", response_model=Pagina[ProyectoOut])
def listar(db: DB, usuario: UsuarioActual, pag: PaginacionDep, empresa_id: uuid.UUID | None = None,
           sin_empresa: bool | None = None, terminal_id: uuid.UUID | None = None, activo: bool | None = None):
    stmt = clientes_propios(
        select(Proyecto, Historial.porcentaje)
        .join(TerminalBancaria, Proyecto.terminal_id == TerminalBancaria.id)
        .outerjoin(Empresa, TerminalBancaria.empresa_id == Empresa.id)
        .outerjoin(Historial, and_(Historial.proyecto_id == Proyecto.id, *condicion_vigente(hoy())))
        .options(joinedload(Proyecto.terminal)),
        usuario,
    ).order_by(Empresa.nombre.nulls_last(), TerminalBancaria.identificador_terminal, Proyecto.nombre)
    stmt = filtrar_empresa(stmt, empresa_id, sin_empresa)
    if terminal_id:
        stmt = stmt.where(Proyecto.terminal_id == terminal_id)
    if activo is not None:
        stmt = stmt.where(Proyecto.activo.is_(activo))
    total = db.scalar(select(func.count()).select_from(stmt.order_by(None).subquery()))
    items = []
    for proyecto, porcentaje in db.execute(stmt.limit(pag.limit).offset(pag.offset)):
        salida = ProyectoOut.model_validate(proyecto)
        salida.porcentaje_vigente = porcentaje
        items.append(salida)
    return {"items": items, "total": total, "limit": pag.limit, "offset": pag.offset}


@router.post("", response_model=ProyectoOut, status_code=status.HTTP_201_CREATED)
def crear(datos: ProyectoCrear, db: DB, usuario: UsuarioActual):
    terminal = obtener_terminal(db, usuario, datos.terminal_id)
    desde = datos.vigente_desde or hoy()
    validar_no_futura(desde, "fecha de vigencia inicial")
    nombre = datos.nombre.strip()
    _nombre_libre(db, terminal.id, nombre)
    proyecto = Proyecto(terminal_id=terminal.id, nombre=nombre)
    db.add(proyecto)
    db.flush()
    crear_porcentaje_inicial(db, proyecto, datos.porcentaje_inicial, desde)
    db.commit()
    return _salida(db, obtener_proyecto(db, usuario, proyecto.id))


@router.get("/{proyecto_id}", response_model=ProyectoOut)
def obtener(proyecto_id: uuid.UUID, db: DB, usuario: UsuarioActual):
    return _salida(db, obtener_proyecto(db, usuario, proyecto_id))


@router.patch("/{proyecto_id}", response_model=ProyectoOut)
def actualizar(proyecto_id: uuid.UUID, datos: ProyectoActualizar, db: DB, usuario: UsuarioActual):
    proyecto = obtener_proyecto(db, usuario, proyecto_id)
    cambios = cambios_no_nulos(datos.model_dump(exclude_unset=True), {"nombre"})
    if "nombre" in cambios:
        cambios["nombre"] = cambios["nombre"].strip()
        _nombre_libre(db, proyecto.terminal_id, cambios["nombre"], excepto=proyecto.id)
    for campo, valor in cambios.items():
        setattr(proyecto, campo, valor)
    db.commit()
    return _salida(db, proyecto)


def _cambiar_estado(db: Session, usuario, proyecto_id: uuid.UUID, activo: bool) -> ProyectoOut:
    proyecto = obtener_proyecto(db, usuario, proyecto_id)
    if proyecto.activo != activo:
        proyecto.activo = activo
        registrar(db, usuario_id=usuario.id, entidad="Proyecto", entidad_id=proyecto.id,
                  accion=AccionBitacora.ACTIVAR if activo else AccionBitacora.DESACTIVAR)
        db.commit()
    return _salida(db, proyecto)


@router.post("/{proyecto_id}/activar", response_model=ProyectoOut)
def activar(proyecto_id: uuid.UUID, db: DB, usuario: UsuarioActual):
    return _cambiar_estado(db, usuario, proyecto_id, True)


@router.post("/{proyecto_id}/desactivar", response_model=ProyectoOut)
def desactivar(proyecto_id: uuid.UUID, db: DB, usuario: UsuarioActual):
    """Un proyecto inactivo no acepta entradas ni salidas nuevas; su historial se conserva."""
    return _cambiar_estado(db, usuario, proyecto_id, False)


@router.get("/{proyecto_id}/porcentajes", response_model=list[HistorialOut])
def historial_porcentajes(proyecto_id: uuid.UUID, db: DB, usuario: UsuarioActual):
    proyecto = obtener_proyecto(db, usuario, proyecto_id)
    return db.scalars(
        select(Historial).where(Historial.proyecto_id == proyecto.id).order_by(Historial.fecha_inicio_vigencia)
    ).all()


@router.post("/{proyecto_id}/porcentajes", response_model=CambioPorcentajeOut, status_code=status.HTTP_201_CREATED)
def nuevo_porcentaje(proyecto_id: uuid.UUID, datos: CambioPorcentaje, db: DB, usuario: UsuarioActual):
    proyecto = obtener_proyecto(db, usuario, proyecto_id)
    registro, recalculados = cambiar_porcentaje(
        db, proyecto=proyecto, nuevo=datos.porcentaje, desde=datos.vigente_desde,
        usuario_id=usuario.id, motivo=datos.motivo,
    )
    db.commit()
    return CambioPorcentajeOut(historial=HistorialOut.model_validate(registro), movimientos_recalculados=recalculados)


@router.get("/{proyecto_id}/porcentaje-vigente", response_model=HistorialOut,
            summary="Porcentaje que rige un día dado (por defecto, hoy)")
def porcentaje_en_fecha(proyecto_id: uuid.UUID, db: DB, usuario: UsuarioActual, dia: date | None = None):
    proyecto = obtener_proyecto(db, usuario, proyecto_id)
    fecha = dia or hoy()
    porcentaje_vigente(db, proyecto.id, fecha)  # lanza 422 si no hay
    return db.scalar(select(Historial).where(Historial.proyecto_id == proyecto.id, *condicion_vigente(fecha)))


@router.get("/{proyecto_id}/saldo", response_model=SaldoOut)
def saldo(proyecto_id: uuid.UUID, db: DB, usuario: UsuarioActual, al_dia: date | None = None):
    proyecto = obtener_proyecto(db, usuario, proyecto_id)
    al_dia = al_dia or hoy()
    t = totales(db, proyecto_id=proyecto.id, hasta=al_dia)
    return SaldoOut(al_dia=al_dia, ingresos_brutos=t.ingresos_brutos, comisiones=t.comisiones,
                    ingresos_netos=t.ingresos_netos, salidas=t.salidas, saldo=t.saldo)
