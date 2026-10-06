"""Módulo de reportes.

Todos los montos se calculan con consultas sobre los movimientos y las salidas;
nada de esto se almacena. Cada consulta aplica también el filtro de propiedad
(defensa en profundidad), además de la validación de acceso que hace la ruta.
"""

import uuid
from collections import defaultdict
from datetime import date, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import Date, cast, func, or_, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.errors import ReglaNegocio
from app.models import (
    AccionBitacora,
    BitacoraAuditoria,
    Empresa,
    MovimientoTerminal as Mov,
    SalidaEmpresa,
    TerminalBancaria as Terminal,
    Usuario,
)
from app.services.acceso import solo_propias
from app.services.exportacion import Reporte
from app.services.saldos import CERO, saldo_empresa

COMISION = (Mov.monto_bruto - Mov.monto_neto)
MESES = ["", "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio",
         "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]


# ---------------------------------------------------------------- utilidades
def validar_rango(desde: date | None, hasta: date | None) -> None:
    if desde and hasta and desde > hasta:
        raise ReglaNegocio("La fecha 'desde' no puede ser posterior a 'hasta'")


def _dec(valor: Any) -> Decimal:
    return Decimal(valor or 0).quantize(CERO)


def _sumar(filas: list[dict[str, Any]], *claves: str) -> dict[str, Decimal]:
    return {c: sum((f[c] or CERO for f in filas), CERO) for c in claves}


def escapar_like(texto: str) -> str:
    return texto.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _movs(usuario: Usuario, *columnas):
    stmt = (
        select(*columnas)
        .select_from(Mov)
        .join(Terminal, Mov.terminal_id == Terminal.id)
        .join(Empresa, Terminal.empresa_id == Empresa.id)
    )
    return solo_propias(stmt, usuario)


def _rango(stmt, columna, desde: date | None, hasta: date | None):
    if desde:
        stmt = stmt.where(columna >= desde)
    if hasta:
        stmt = stmt.where(columna <= hasta)
    return stmt


def _fecha_local(columna):
    """timestamptz -> fecha en la zona horaria del negocio."""
    return cast(func.timezone(settings.TIMEZONE, columna), Date)


# ------------------------------------------------ 1. Totales por empresa (admin)
def totales_por_empresa(db: Session, usuario: Usuario, empresa_id, desde, hasta) -> Reporte:
    validar_rango(desde, hasta)
    stmt = _movs(
        usuario,
        Empresa.nombre.label("empresa"),
        func.count(Mov.id).label("movimientos"),
        func.sum(Mov.monto_bruto).label("monto_bruto"),
        func.sum(COMISION).label("comision"),
        func.sum(Mov.monto_neto).label("monto_neto"),
    ).group_by(Empresa.id, Empresa.nombre).order_by(Empresa.nombre)
    stmt = _rango(stmt, Mov.fecha_movimiento, desde, hasta)
    if empresa_id:
        stmt = stmt.where(Empresa.id == empresa_id)
    filas = [
        {**r._asdict(), "monto_bruto": _dec(r.monto_bruto), "comision": _dec(r.comision), "monto_neto": _dec(r.monto_neto)}
        for r in db.execute(stmt)
    ]
    return Reporte(
        titulo="Movimientos totales por empresa",
        columnas=[("empresa", "Empresa"), ("movimientos", "Movimientos"), ("monto_bruto", "Bruto"),
                  ("comision", "Comisión"), ("monto_neto", "Neto")],
        filas=filas,
        totales={**_sumar(filas, "monto_bruto", "comision", "monto_neto"),
                 "movimientos": sum(f["movimientos"] for f in filas)},
        parametros={"empresa_id": empresa_id, "desde": desde, "hasta": hasta},
    )


# --------------------------------------- 2. Auditoría de captura por contador (admin)
def auditoria_por_contador(db: Session, usuario_id, desde, hasta) -> Reporte:
    validar_rango(desde, hasta)
    stmt = (
        select(
            Usuario.id,
            (Usuario.nombre + " " + Usuario.apellidos).label("contador"),
            Usuario.correo,
            func.count(Mov.id).label("movimientos"),
            func.sum(Mov.monto_bruto).label("monto_bruto"),
            func.sum(Mov.monto_neto).label("monto_neto"),
            func.min(Mov.fecha_captura).label("primera_captura"),
            func.max(Mov.fecha_captura).label("ultima_captura"),
        )
        .join(Mov, Mov.usuario_id == Usuario.id)
        .group_by(Usuario.id)
        .order_by("contador")
    )
    stmt = _rango(stmt, Mov.fecha_movimiento, desde, hasta)
    if usuario_id:
        stmt = stmt.where(Usuario.id == usuario_id)

    ediciones_stmt = (
        select(BitacoraAuditoria.usuario_id, func.count())
        .where(BitacoraAuditoria.accion.in_([AccionBitacora.EDITAR_MOVIMIENTO, AccionBitacora.ELIMINAR_MOVIMIENTO]))
        .group_by(BitacoraAuditoria.usuario_id)
    )
    ediciones_stmt = _rango(ediciones_stmt, _fecha_local(BitacoraAuditoria.fecha), desde, hasta)
    ediciones = dict(db.execute(ediciones_stmt).all())

    filas = []
    for r in db.execute(stmt):
        fila = r._asdict()
        fila.pop("id")
        fila.update(monto_bruto=_dec(r.monto_bruto), monto_neto=_dec(r.monto_neto),
                    ediciones=ediciones.get(r.id, 0))
        filas.append(fila)
    return Reporte(
        titulo="Auditoría de captura por contador",
        columnas=[("contador", "Contador"), ("correo", "Correo"), ("movimientos", "Movimientos"),
                  ("monto_bruto", "Bruto"), ("monto_neto", "Neto"), ("ediciones", "Ediciones/eliminaciones"),
                  ("primera_captura", "Primera captura"), ("ultima_captura", "Última captura")],
        filas=filas,
        totales={**_sumar(filas, "monto_bruto", "monto_neto"), "movimientos": sum(f["movimientos"] for f in filas)},
        parametros={"usuario_id": usuario_id, "desde": desde, "hasta": hasta},
    )


# ---------------------------------- 3 y 4. Detalle de movimientos (por terminal / empresa)
def movimientos_detalle(
    db: Session, usuario: Usuario, *, titulo: str, empresa_id=None, terminal_id=None, desde=None, hasta=None
) -> Reporte:
    validar_rango(desde, hasta)
    stmt = _movs(
        usuario,
        Mov.fecha_movimiento.label("fecha"),
        Empresa.nombre.label("empresa"),
        Terminal.identificador_terminal.label("terminal"),
        Mov.monto_bruto,
        Mov.porcentaje_aplicado.label("porcentaje"),
        COMISION.label("comision"),
        Mov.monto_neto,
        Usuario.correo.label("capturo"),
        Mov.observaciones,
    ).join(Usuario, Mov.usuario_id == Usuario.id).order_by(Mov.fecha_movimiento, Mov.fecha_captura)
    stmt = _rango(stmt, Mov.fecha_movimiento, desde, hasta)
    if empresa_id:
        stmt = stmt.where(Empresa.id == empresa_id)
    if terminal_id:
        stmt = stmt.where(Terminal.id == terminal_id)
    filas = [r._asdict() for r in db.execute(stmt)]
    return Reporte(
        titulo=titulo,
        columnas=[("fecha", "Fecha"), ("empresa", "Empresa"), ("terminal", "Terminal"), ("monto_bruto", "Bruto"),
                  ("porcentaje", "%"), ("comision", "Comisión"), ("monto_neto", "Neto"), ("capturo", "Capturó"),
                  ("observaciones", "Observaciones")],
        filas=filas,
        totales=_sumar(filas, "monto_bruto", "comision", "monto_neto"),
        parametros={"empresa_id": empresa_id, "terminal_id": terminal_id, "desde": desde, "hasta": hasta},
    )


# ------------------------------------------ 5. Conciliación diaria por terminal
def conciliacion_diaria(db: Session, usuario: Usuario, fecha: date, empresa_id=None, terminal_id=None) -> Reporte:
    stmt = _movs(
        usuario,
        Empresa.nombre.label("empresa"),
        Terminal.identificador_terminal.label("terminal"),
        func.count(Mov.id).label("movimientos"),
        func.sum(Mov.monto_bruto).label("monto_bruto"),
        func.sum(COMISION).label("comision"),
        func.sum(Mov.monto_neto).label("monto_neto"),
    ).where(Mov.fecha_movimiento == fecha).group_by(Empresa.nombre, Terminal.id).order_by(
        Empresa.nombre, Terminal.identificador_terminal
    )
    if empresa_id:
        stmt = stmt.where(Empresa.id == empresa_id)
    if terminal_id:
        stmt = stmt.where(Terminal.id == terminal_id)
    filas = [
        {**r._asdict(), "monto_bruto": _dec(r.monto_bruto), "comision": _dec(r.comision), "monto_neto": _dec(r.monto_neto)}
        for r in db.execute(stmt)
    ]
    return Reporte(
        titulo=f"Conciliación diaria por terminal — {fecha.isoformat()}",
        columnas=[("empresa", "Empresa"), ("terminal", "Terminal"), ("movimientos", "Movimientos"),
                  ("monto_bruto", "Bruto"), ("comision", "Comisión"), ("monto_neto", "Neto")],
        filas=filas,
        totales={**_sumar(filas, "monto_bruto", "comision", "monto_neto"),
                 "movimientos": sum(f["movimientos"] for f in filas)},
        parametros={"fecha": fecha, "empresa_id": empresa_id, "terminal_id": terminal_id},
    )


# ---------------------------------------- 6. Resumen mensual por empresa (admin)
def resumen_mensual(db: Session, usuario: Usuario, anio: int, mes: int | None, empresa_id=None) -> Reporte:
    mes_mov = func.extract("month", Mov.fecha_movimiento)
    stmt = _movs(
        usuario,
        Empresa.id,
        Empresa.nombre,
        mes_mov.label("mes"),
        func.sum(Mov.monto_bruto).label("bruto"),
        func.sum(COMISION).label("comision"),
        func.sum(Mov.monto_neto).label("neto"),
    ).where(func.extract("year", Mov.fecha_movimiento) == anio).group_by(Empresa.id, Empresa.nombre, mes_mov)

    mes_sal = func.extract("month", SalidaEmpresa.fecha)
    stmt_sal = solo_propias(
        select(Empresa.id, Empresa.nombre, mes_sal.label("mes"), func.sum(SalidaEmpresa.monto).label("salidas"))
        .select_from(SalidaEmpresa)
        .join(Empresa, SalidaEmpresa.empresa_id == Empresa.id)
        .where(func.extract("year", SalidaEmpresa.fecha) == anio)
        .group_by(Empresa.id, Empresa.nombre, mes_sal),
        usuario,
    )
    if mes:
        stmt, stmt_sal = stmt.where(mes_mov == mes), stmt_sal.where(mes_sal == mes)
    if empresa_id:
        stmt, stmt_sal = stmt.where(Empresa.id == empresa_id), stmt_sal.where(Empresa.id == empresa_id)

    acumulado: dict[tuple, dict[str, Any]] = defaultdict(
        lambda: {"ingresos_brutos": CERO, "comisiones": CERO, "ingresos_netos": CERO, "salidas": CERO}
    )
    for r in db.execute(stmt):
        a = acumulado[(r.nombre, r.id, int(r.mes))]
        a.update(ingresos_brutos=_dec(r.bruto), comisiones=_dec(r.comision), ingresos_netos=_dec(r.neto))
    for r in db.execute(stmt_sal):
        acumulado[(r.nombre, r.id, int(r.mes))]["salidas"] = _dec(r.salidas)

    filas = []
    for (nombre, _, numero_mes), valores in sorted(acumulado.items(), key=lambda kv: (kv[0][0], kv[0][2])):
        filas.append({"empresa": nombre, "mes": MESES[numero_mes], **valores,
                      "flujo_neto": valores["ingresos_netos"] - valores["salidas"]})
    return Reporte(
        titulo=f"Resumen {'mensual' if mes else 'anual'} por empresa — {anio}",
        columnas=[("empresa", "Empresa"), ("mes", "Mes"), ("ingresos_brutos", "Ingresos brutos"),
                  ("comisiones", "Comisiones"), ("ingresos_netos", "Ingresos netos"), ("salidas", "Salidas"),
                  ("flujo_neto", "Flujo neto")],
        filas=filas,
        totales=_sumar(filas, "ingresos_brutos", "comisiones", "ingresos_netos", "salidas", "flujo_neto"),
        parametros={"anio": anio, "mes": mes, "empresa_id": empresa_id},
    )


# ------------------------------------------------------ 7. Historial de salidas
def historial_salidas(db: Session, usuario: Usuario, empresa_id=None, desde=None, hasta=None,
                      texto: str | None = None) -> Reporte:
    validar_rango(desde, hasta)
    stmt = solo_propias(
        select(
            SalidaEmpresa.fecha,
            Empresa.nombre.label("empresa"),
            SalidaEmpresa.monto,
            SalidaEmpresa.destino,
            Usuario.correo.label("registro"),
            SalidaEmpresa.observaciones,
        )
        .select_from(SalidaEmpresa)
        .join(Empresa, SalidaEmpresa.empresa_id == Empresa.id)
        .join(Usuario, SalidaEmpresa.usuario_id == Usuario.id)
        .order_by(SalidaEmpresa.fecha, SalidaEmpresa.fecha_registro),
        usuario,
    )
    stmt = _rango(stmt, SalidaEmpresa.fecha, desde, hasta)
    if empresa_id:
        stmt = stmt.where(Empresa.id == empresa_id)
    if texto:
        patron = f"%{escapar_like(texto.strip())}%"
        stmt = stmt.where(or_(SalidaEmpresa.destino.ilike(patron, escape="\\"),
                              SalidaEmpresa.observaciones.ilike(patron, escape="\\")))
    filas = [r._asdict() for r in db.execute(stmt)]
    return Reporte(
        titulo="Historial de salidas",
        columnas=[("fecha", "Fecha"), ("empresa", "Empresa"), ("monto", "Monto"), ("destino", "Destino"),
                  ("registro", "Registró"), ("observaciones", "Observaciones")],
        filas=filas,
        totales=_sumar(filas, "monto"),
        parametros={"empresa_id": empresa_id, "desde": desde, "hasta": hasta, "texto": texto},
    )


# ---------------------------------------------------- 8. Estado de cuenta
def estado_cuenta(db: Session, usuario: Usuario, empresa: Empresa, desde: date, hasta: date) -> Reporte:
    validar_rango(desde, hasta)
    saldo_inicial = saldo_empresa(db, empresa.id, desde - timedelta(days=1))

    ingresos = db.execute(
        _movs(usuario, Mov.fecha_movimiento, Mov.fecha_captura, Terminal.identificador_terminal, Mov.monto_neto)
        .where(Empresa.id == empresa.id, Mov.fecha_movimiento.between(desde, hasta))
    ).all()
    salidas = db.execute(
        select(SalidaEmpresa.fecha, SalidaEmpresa.fecha_registro, SalidaEmpresa.destino, SalidaEmpresa.monto)
        .where(SalidaEmpresa.empresa_id == empresa.id, SalidaEmpresa.fecha.between(desde, hasta))
    ).all()

    lineas = [((r.fecha_movimiento, 0, r.fecha_captura),
               {"fecha": r.fecha_movimiento, "tipo": "Ingreso", "concepto": f"Terminal {r.identificador_terminal}",
                "ingreso": r.monto_neto, "salida": None}) for r in ingresos]
    lineas += [((r.fecha, 1, r.fecha_registro),
                {"fecha": r.fecha, "tipo": "Salida", "concepto": r.destino, "ingreso": None, "salida": r.monto})
               for r in salidas]
    lineas.sort(key=lambda x: x[0])

    saldo = saldo_inicial
    filas: list[dict[str, Any]] = [{"fecha": desde, "tipo": "", "concepto": "Saldo inicial",
                                    "ingreso": None, "salida": None, "saldo": saldo_inicial}]
    for _, linea in lineas:
        saldo += (linea["ingreso"] or CERO) - (linea["salida"] or CERO)
        filas.append({**linea, "saldo": saldo})

    total_ingresos = sum((f["ingreso"] or CERO for f in filas), CERO)
    total_salidas = sum((f["salida"] or CERO for f in filas), CERO)
    return Reporte(
        titulo=f"Estado de cuenta — {empresa.nombre}",
        columnas=[("fecha", "Fecha"), ("tipo", "Tipo"), ("concepto", "Concepto"), ("ingreso", "Ingreso neto"),
                  ("salida", "Salida"), ("saldo", "Saldo")],
        filas=filas,
        totales={"ingreso": total_ingresos, "salida": total_salidas, "saldo": saldo},
        parametros={"empresa_id": empresa.id, "desde": desde, "hasta": hasta,
                    "saldo_inicial": saldo_inicial, "saldo_final": saldo},
    )


# ------------------------------------------ 9. Comisiones por terminal (admin)
def comisiones_por_terminal(db: Session, usuario: Usuario, empresa_id=None, desde=None, hasta=None) -> Reporte:
    validar_rango(desde, hasta)
    stmt = _movs(
        usuario,
        Empresa.nombre.label("empresa"),
        Terminal.identificador_terminal.label("terminal"),
        func.count(Mov.id).label("movimientos"),
        func.sum(Mov.monto_bruto).label("monto_bruto"),
        func.sum(COMISION).label("comision"),
    ).group_by(Empresa.nombre, Terminal.id).order_by(func.sum(COMISION).desc())
    stmt = _rango(stmt, Mov.fecha_movimiento, desde, hasta)
    if empresa_id:
        stmt = stmt.where(Empresa.id == empresa_id)
    filas = [{**r._asdict(), "monto_bruto": _dec(r.monto_bruto), "comision": _dec(r.comision)}
             for r in db.execute(stmt)]
    return Reporte(
        titulo="Comisiones generadas por terminal",
        columnas=[("empresa", "Empresa"), ("terminal", "Terminal"), ("movimientos", "Movimientos"),
                  ("monto_bruto", "Bruto"), ("comision", "Comisión")],
        filas=filas,
        totales={**_sumar(filas, "monto_bruto", "comision"), "movimientos": sum(f["movimientos"] for f in filas)},
        parametros={"empresa_id": empresa_id, "desde": desde, "hasta": hasta},
    )


# ----------------------------------------------- 10. Bitácora general (admin)
def bitacora(db: Session, *, entidad=None, usuario_id=None, accion=None, desde=None, hasta=None,
             limit: int = 100, offset: int = 0) -> Reporte:
    validar_rango(desde, hasta)
    stmt = select(
        BitacoraAuditoria.fecha,
        func.coalesce(Usuario.correo, "sistema").label("usuario"),
        BitacoraAuditoria.accion,
        BitacoraAuditoria.entidad,
        BitacoraAuditoria.entidad_id,
        BitacoraAuditoria.detalle,
    ).outerjoin(Usuario, BitacoraAuditoria.usuario_id == Usuario.id)
    stmt = _rango(stmt, _fecha_local(BitacoraAuditoria.fecha), desde, hasta)
    if entidad:
        stmt = stmt.where(BitacoraAuditoria.entidad == entidad)
    if usuario_id:
        stmt = stmt.where(BitacoraAuditoria.usuario_id == usuario_id)
    if accion:
        stmt = stmt.where(BitacoraAuditoria.accion == accion)
    total = db.scalar(select(func.count()).select_from(stmt.subquery()))
    filas = [
        {**r._asdict(), "accion": r.accion.value}
        for r in db.execute(stmt.order_by(BitacoraAuditoria.fecha.desc()).limit(limit).offset(offset))
    ]
    return Reporte(
        titulo="Bitácora de auditoría",
        columnas=[("fecha", "Fecha"), ("usuario", "Usuario"), ("accion", "Acción"), ("entidad", "Entidad"),
                  ("entidad_id", "ID entidad"), ("detalle", "Detalle")],
        filas=filas,
        parametros={"entidad": entidad, "usuario_id": usuario_id, "accion": accion, "desde": desde,
                    "hasta": hasta, "total": total, "limit": limit, "offset": offset},
    )


# ------------------------------------------------------ Saldos de empresas
def saldos_empresas(db: Session, usuario: Usuario, al_dia: date) -> Reporte:
    ingresos = (
        select(Terminal.empresa_id, func.sum(Mov.monto_neto).label("total"))
        .join(Mov, Mov.terminal_id == Terminal.id)
        .where(Mov.fecha_movimiento <= al_dia)
        .group_by(Terminal.empresa_id)
        .subquery()
    )
    salidas = (
        select(SalidaEmpresa.empresa_id, func.sum(SalidaEmpresa.monto).label("total"))
        .where(SalidaEmpresa.fecha <= al_dia)
        .group_by(SalidaEmpresa.empresa_id)
        .subquery()
    )
    stmt = solo_propias(
        select(
            Empresa.nombre.label("empresa"),
            Empresa.banco,
            Empresa.numero_cuenta,
            func.coalesce(ingresos.c.total, 0).label("ingresos_netos"),
            func.coalesce(salidas.c.total, 0).label("salidas"),
        )
        .outerjoin(ingresos, ingresos.c.empresa_id == Empresa.id)
        .outerjoin(salidas, salidas.c.empresa_id == Empresa.id)
        .order_by(Empresa.nombre),
        usuario,
    )
    filas = []
    for r in db.execute(stmt):
        ing, sal = _dec(r.ingresos_netos), _dec(r.salidas)
        filas.append({**r._asdict(), "ingresos_netos": ing, "salidas": sal, "saldo": ing - sal})
    return Reporte(
        titulo=f"Saldos de empresas al {al_dia.isoformat()}",
        columnas=[("empresa", "Empresa"), ("banco", "Banco"), ("numero_cuenta", "Cuenta"),
                  ("ingresos_netos", "Ingresos netos"), ("salidas", "Salidas"), ("saldo", "Saldo")],
        filas=filas,
        totales=_sumar(filas, "ingresos_netos", "salidas", "saldo"),
        parametros={"al_dia": al_dia},
    )


# ------------------------------------------------------ Cierre diario
def resumen_cierre(db: Session, dia: date) -> Reporte:
    stmt = (
        select(
            (Usuario.nombre + " " + Usuario.apellidos).label("contador"),
            func.count(Mov.id).label("movimientos"),
            func.sum(Mov.monto_bruto).label("monto_bruto"),
            func.sum(COMISION).label("comision"),
            func.sum(Mov.monto_neto).label("monto_neto"),
        )
        .join(Mov, Mov.usuario_id == Usuario.id)
        .where(Mov.fecha_movimiento == dia)
        .group_by(Usuario.id)
        .order_by("contador")
    )
    filas = [
        {**r._asdict(), "monto_bruto": _dec(r.monto_bruto), "comision": _dec(r.comision), "monto_neto": _dec(r.monto_neto)}
        for r in db.execute(stmt)
    ]
    return Reporte(
        titulo=f"Cierre diario — {dia.isoformat()}",
        columnas=[("contador", "Contador"), ("movimientos", "Movimientos"), ("monto_bruto", "Bruto"),
                  ("comision", "Comisión"), ("monto_neto", "Neto")],
        filas=filas,
        totales={**_sumar(filas, "monto_bruto", "comision", "monto_neto"),
                 "movimientos": sum(f["movimientos"] for f in filas)},
        parametros={"fecha": dia},
    )
