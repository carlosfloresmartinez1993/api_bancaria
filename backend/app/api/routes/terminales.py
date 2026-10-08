"""Clientes (terminales). En la API se conservan las rutas /terminales.

Un cliente puede tener empresa o no. Siempre tiene un responsable (usuario_id): el de su
empresa, o el contador que lo registró si no tiene empresa.
"""

import uuid
from datetime import date
from decimal import Decimal

from fastapi import APIRouter, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import DB, Admin, PaginacionDep, UsuarioActual
from app.api.utils import cambios_no_nulos, paginar
from app.core.errors import Conflicto, Prohibido, ReglaNegocio
from app.core.tiempo import hoy
from app.models import AccionBitacora, BitacoraAuditoria, Empresa, Proyecto, Rol, TerminalBancaria, Usuario
from app.schemas.comun import Pagina
from app.schemas.empresa import SaldoOut
from app.schemas.terminal import (
    MoverCliente,
    MovimientoClienteOut,
    ReasignarCliente,
    RevertirMovimiento,
    TerminalActualizar,
    TerminalCrear,
    TerminalOut,
)
from app.services.acceso import SIN_EMPRESA, clientes_propios, filtrar_empresa, obtener_empresa, obtener_terminal
from app.services.bitacora import registrar
from app.services.saldos import totales

router = APIRouter(prefix="/terminales", tags=["Clientes (terminales)"])


def _identificador_libre(db: Session, empresa_id: uuid.UUID | None, usuario_id: uuid.UUID, identificador: str,
                         excepto: uuid.UUID | None = None) -> None:
    """Único dentro de la empresa; sin empresa, único entre los clientes sin empresa del mismo responsable."""
    stmt = select(TerminalBancaria.id).where(TerminalBancaria.identificador_terminal == identificador)
    if empresa_id:
        stmt = stmt.where(TerminalBancaria.empresa_id == empresa_id)
    else:
        stmt = stmt.where(TerminalBancaria.empresa_id.is_(None), TerminalBancaria.usuario_id == usuario_id)
    if excepto:
        stmt = stmt.where(TerminalBancaria.id != excepto)
    if db.scalar(stmt):
        raise Conflicto("La empresa ya tiene un cliente con ese identificador" if empresa_id
                        else "Ya hay un cliente sin empresa con ese identificador")


def _salidas(db: Session, terminales: list[TerminalBancaria]) -> list[TerminalOut]:
    """Agrega a cada cliente cuántos proyectos tiene."""
    conteo = dict(
        db.execute(
            select(Proyecto.terminal_id, func.count())
            .where(Proyecto.terminal_id.in_([t.id for t in terminales]))
            .group_by(Proyecto.terminal_id)
        ).all()
    ) if terminales else {}
    return [TerminalOut.model_validate(t).model_copy(update={"num_proyectos": conteo.get(t.id, 0)})
            for t in terminales]


def _contador_activo(db: Session, usuario_id: uuid.UUID) -> Usuario:
    usuario = db.get(Usuario, usuario_id)
    if usuario is None or not usuario.activo or usuario.rol != Rol.CONTADOR:
        raise ReglaNegocio("El responsable debe ser un usuario activo con rol contador")
    return usuario


def _nombre_empresa(db: Session, empresa_id: uuid.UUID | None) -> str:
    return db.get(Empresa, empresa_id).nombre if empresa_id else SIN_EMPRESA


def _mover(db: Session, actor: Usuario, terminal: TerminalBancaria, empresa_id: uuid.UUID | None,
           usuario_id: uuid.UUID, motivo: str | None, revierte: uuid.UUID | None = None) -> None:
    """Cambia la empresa (y el responsable) del cliente y deja el registro en la bitácora.

    Los proyectos, entradas y salidas cuelgan del cliente, así que se mueven con él.
    """
    if (terminal.empresa_id, terminal.usuario_id) == (empresa_id, usuario_id):
        raise ReglaNegocio("El cliente ya está en esa empresa")
    _identificador_libre(db, empresa_id, usuario_id, terminal.identificador_terminal, excepto=terminal.id)
    antes = {"empresa_id": terminal.empresa_id, "empresa": _nombre_empresa(db, terminal.empresa_id),
             "usuario_id": terminal.usuario_id}
    despues = {"empresa_id": empresa_id, "empresa": _nombre_empresa(db, empresa_id), "usuario_id": usuario_id}
    saldo = totales(db, terminal_id=terminal.id).saldo
    terminal.empresa_id, terminal.usuario_id = empresa_id, usuario_id
    registrar(db, usuario_id=actor.id, entidad="Cliente", entidad_id=terminal.id, accion=AccionBitacora.MOVER_CLIENTE,
              detalle={"antes": antes, "despues": despues, "saldo_cliente": saldo, "motivo": motivo,
                       "revierte": revierte})


def _historial(db: Session, terminal_id: uuid.UUID) -> list[BitacoraAuditoria]:
    return list(db.scalars(
        select(BitacoraAuditoria)
        .where(BitacoraAuditoria.entidad == "Cliente", BitacoraAuditoria.entidad_id == terminal_id,
               BitacoraAuditoria.accion == AccionBitacora.MOVER_CLIENTE)
        .order_by(BitacoraAuditoria.fecha.desc())
    ))


# ------------------------------------------------------------------ CRUD
@router.get("", response_model=Pagina[TerminalOut])
def listar(db: DB, usuario: UsuarioActual, pag: PaginacionDep, empresa_id: uuid.UUID | None = None,
           sin_empresa: bool | None = None, usuario_id: uuid.UUID | None = None, activa: bool | None = None):
    stmt = clientes_propios(
        select(TerminalBancaria).outerjoin(Empresa, TerminalBancaria.empresa_id == Empresa.id), usuario
    ).order_by(Empresa.nombre.nulls_last(), TerminalBancaria.identificador_terminal)
    stmt = filtrar_empresa(stmt, empresa_id, sin_empresa)
    if usuario_id and usuario.es_admin:
        stmt = stmt.where(TerminalBancaria.usuario_id == usuario_id)
    if activa is not None:
        stmt = stmt.where(TerminalBancaria.activa.is_(activa))
    pagina = paginar(db, stmt, pag.limit, pag.offset)
    pagina["items"] = _salidas(db, pagina["items"])
    return pagina


@router.post("", response_model=TerminalOut, status_code=status.HTTP_201_CREATED)
def crear(datos: TerminalCrear, db: DB, usuario: UsuarioActual):
    """Con empresa, el responsable es el de la empresa. Sin empresa, quien lo registra
    (o el contador que indique un admin)."""
    identificador = datos.identificador_terminal.strip()
    if datos.empresa_id:
        empresa = obtener_empresa(db, usuario, datos.empresa_id)
        empresa_id, responsable = empresa.id, empresa.usuario_id
    else:
        empresa_id, responsable = None, usuario.id
        if datos.usuario_id and datos.usuario_id != usuario.id:
            if not usuario.es_admin:
                raise Prohibido("Solo un administrador puede registrar clientes a nombre de otro usuario")
            responsable = _contador_activo(db, datos.usuario_id).id
    _identificador_libre(db, empresa_id, responsable, identificador)
    terminal = TerminalBancaria(empresa_id=empresa_id, usuario_id=responsable, identificador_terminal=identificador)
    db.add(terminal)
    db.commit()
    db.refresh(terminal)
    return _salidas(db, [terminal])[0]


@router.get("/{terminal_id}", response_model=TerminalOut)
def obtener(terminal_id: uuid.UUID, db: DB, usuario: UsuarioActual):
    return _salidas(db, [obtener_terminal(db, usuario, terminal_id)])[0]


@router.patch("/{terminal_id}", response_model=TerminalOut)
def actualizar(terminal_id: uuid.UUID, datos: TerminalActualizar, db: DB, usuario: UsuarioActual):
    terminal = obtener_terminal(db, usuario, terminal_id)
    cambios = cambios_no_nulos(datos.model_dump(exclude_unset=True), {"identificador_terminal"})
    if "identificador_terminal" in cambios:
        cambios["identificador_terminal"] = cambios["identificador_terminal"].strip()
        _identificador_libre(db, terminal.empresa_id, terminal.usuario_id, cambios["identificador_terminal"],
                             excepto=terminal.id)
    for campo, valor in cambios.items():
        setattr(terminal, campo, valor)
    db.commit()
    return _salidas(db, [terminal])[0]


def _cambiar_estado(db: Session, usuario, terminal_id: uuid.UUID, activa: bool) -> TerminalOut:
    terminal = obtener_terminal(db, usuario, terminal_id)
    if terminal.activa != activa:
        terminal.activa = activa
        registrar(db, usuario_id=usuario.id, entidad="Cliente", entidad_id=terminal.id,
                  accion=AccionBitacora.ACTIVAR if activa else AccionBitacora.DESACTIVAR)
        db.commit()
    return _salidas(db, [terminal])[0]


@router.post("/{terminal_id}/activar", response_model=TerminalOut)
def activar(terminal_id: uuid.UUID, db: DB, usuario: UsuarioActual):
    return _cambiar_estado(db, usuario, terminal_id, True)


@router.post("/{terminal_id}/desactivar", response_model=TerminalOut)
def desactivar(terminal_id: uuid.UUID, db: DB, usuario: UsuarioActual):
    """Un cliente inactivo no acepta capturas nuevas en ninguno de sus proyectos; su historial se conserva."""
    return _cambiar_estado(db, usuario, terminal_id, False)


@router.get("/{terminal_id}/saldo", response_model=SaldoOut)
def saldo(terminal_id: uuid.UUID, db: DB, usuario: UsuarioActual, al_dia: date | None = None):
    terminal = obtener_terminal(db, usuario, terminal_id)
    al_dia = al_dia or hoy()
    t = totales(db, terminal_id=terminal.id, hasta=al_dia)
    return SaldoOut(al_dia=al_dia, ingresos_brutos=t.ingresos_brutos, comisiones=t.comisiones,
                    ingresos_netos=t.ingresos_netos, salidas=t.salidas, saldo=t.saldo)


# ------------------------------------------------------------ cambiar de empresa
@router.post("/{terminal_id}/empresa", response_model=TerminalOut)
def mover(terminal_id: uuid.UUID, datos: MoverCliente, db: DB, usuario: UsuarioActual):
    """Asocia el cliente a una empresa o lo deja sin empresa, con todos sus proyectos, entradas y salidas.

    Un contador solo puede moverlo entre sus propias empresas (o dejarlo sin empresa); un admin, a
    cualquier empresa, y el cliente pasa al responsable de esa empresa. Se puede revertir.
    """
    terminal = obtener_terminal(db, usuario, terminal_id)
    if datos.empresa_id:
        empresa = obtener_empresa(db, usuario, datos.empresa_id)
        destino, responsable = empresa.id, empresa.usuario_id
    else:
        destino, responsable = None, terminal.usuario_id
    _mover(db, usuario, terminal, destino, responsable, datos.motivo)
    db.commit()
    return _salidas(db, [terminal])[0]


@router.get("/{terminal_id}/historial-empresa", response_model=list[MovimientoClienteOut])
def historial_empresa(terminal_id: uuid.UUID, db: DB, usuario: UsuarioActual):
    terminal = obtener_terminal(db, usuario, terminal_id)
    registros = _historial(db, terminal.id)
    nombres = dict(db.execute(select(Usuario.id, Usuario.nombre + " " + Usuario.apellidos)).all())
    resultado = []
    for i, r in enumerate(registros):
        d = r.detalle
        saldo = d.get("saldo_cliente")
        resultado.append(MovimientoClienteOut(
            id=r.id, fecha=r.fecha, realizado_por=nombres.get(r.usuario_id, "sistema"),
            empresa_antes=d["antes"]["empresa"], empresa_despues=d["despues"]["empresa"],
            saldo_movido=Decimal(saldo) if saldo is not None else None, motivo=d.get("motivo"),
            es_reversion=bool(d.get("revierte")), se_puede_revertir=i == 0,
        ))
    return resultado


@router.post("/{terminal_id}/revertir-movimiento", response_model=TerminalOut)
def revertir(terminal_id: uuid.UUID, datos: RevertirMovimiento, db: DB, usuario: UsuarioActual):
    """Deshace el último cambio de empresa: el cliente vuelve exactamente a donde estaba,
    con el mismo responsable, y los saldos de ambas empresas regresan a como eran."""
    terminal = obtener_terminal(db, usuario, terminal_id)
    registros = _historial(db, terminal.id)
    if not registros:
        raise ReglaNegocio("El cliente no tiene cambios de empresa que revertir")
    ultimo = registros[0]
    antes, despues = ultimo.detalle["antes"], ultimo.detalle["despues"]
    actual = {"empresa_id": str(terminal.empresa_id) if terminal.empresa_id else None,
              "usuario_id": str(terminal.usuario_id)}
    if actual != {"empresa_id": despues["empresa_id"], "usuario_id": despues["usuario_id"]}:
        raise Conflicto("El cliente cambió después de ese movimiento; revisa su historial")

    if antes["empresa_id"]:
        empresa = obtener_empresa(db, usuario, uuid.UUID(antes["empresa_id"]))
        destino, responsable = empresa.id, empresa.usuario_id
    else:
        destino, responsable = None, uuid.UUID(antes["usuario_id"])
    if not usuario.es_admin and responsable != usuario.id:
        raise Prohibido("Solo un administrador puede revertir este movimiento")
    motivo = datos.motivo or f"Reversión del cambio del {ultimo.fecha:%d/%m/%Y %H:%M}"
    _mover(db, usuario, terminal, destino, responsable, motivo, revierte=ultimo.id)
    db.commit()
    return _salidas(db, [terminal])[0]


@router.post("/{terminal_id}/reasignar", response_model=TerminalOut)
def reasignar(terminal_id: uuid.UUID, datos: ReasignarCliente, db: DB, admin: Admin):
    """Cambia el responsable de un cliente sin empresa. (Un cliente con empresa cambia de
    responsable reasignando la empresa.)"""
    terminal = obtener_terminal(db, admin, terminal_id)
    if terminal.empresa_id:
        raise ReglaNegocio("El cliente pertenece a una empresa: reasigna la empresa")
    nuevo = _contador_activo(db, datos.usuario_id)
    if nuevo.id != terminal.usuario_id:
        _identificador_libre(db, None, nuevo.id, terminal.identificador_terminal, excepto=terminal.id)
        anterior = terminal.usuario_id
        terminal.usuario_id = nuevo.id
        registrar(db, usuario_id=admin.id, entidad="Cliente", entidad_id=terminal.id,
                  accion=AccionBitacora.REASIGNAR_CLIENTE, detalle={"antes": anterior, "despues": nuevo.id})
        db.commit()
    return _salidas(db, [terminal])[0]
