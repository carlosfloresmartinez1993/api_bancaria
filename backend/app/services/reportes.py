"""Módulo de reportes.

Todos los montos se calculan con consultas sobre las entradas (movimientos) y
las salidas; nada de esto se almacena. Cada consulta aplica también el filtro
de propiedad (defensa en profundidad), además de la validación de acceso que
hace la ruta.

Jerarquía: Empresa → Cliente (terminal) → Proyecto (con su % de comisión).
"""

import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import Decimal
from enum import StrEnum
from typing import Any

from sqlalchemy import Date, cast, func, or_, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.errors import ReglaNegocio
from app.models import (
    AccionBitacora,
    BitacoraAuditoria,
    Empresa,
    MetodoPago,
    Movimiento as Mov,
    Proyecto,
    Salida,
    TerminalBancaria as Terminal,
    Usuario,
)
from app.services.acceso import solo_propias, unir_jerarquia
from app.services.exportacion import Reporte
from app.services.saldos import CERO

COMISION = (Mov.monto_bruto - Mov.monto_neto)
MESES = ["", "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio",
         "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]
NOMBRE_USUARIO = (Usuario.nombre + " " + Usuario.apellidos)


# ---------------------------------------------------------------- utilidades
def validar_rango(desde: date | None, hasta: date | None) -> None:
    if desde and hasta and desde > hasta:
        raise ReglaNegocio("La fecha 'desde' no puede ser posterior a 'hasta'")


def _dec(valor: Any) -> Decimal:
    return Decimal(valor or 0).quantize(CERO)


def _sumar(filas: list[dict[str, Any]], *claves: str) -> dict[str, Decimal]:
    return {c: sum((f.get(c) or CERO for f in filas), CERO) for c in claves}


def escapar_like(texto: str) -> str:
    return texto.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _rango(stmt, columna, desde: date | None, hasta: date | None):
    if desde:
        stmt = stmt.where(columna >= desde)
    if hasta:
        stmt = stmt.where(columna <= hasta)
    return stmt


def _fecha_local(columna):
    """timestamptz -> fecha en la zona horaria del negocio."""
    return cast(func.timezone(settings.TIMEZONE, columna), Date)


def _movs(usuario: Usuario, *columnas):
    """Entradas con su proyecto, cliente y empresa, filtradas por propiedad."""
    return solo_propias(unir_jerarquia(select(*columnas).select_from(Mov), Mov.proyecto_id), usuario)


def _sals(usuario: Usuario, *columnas):
    """Salidas con su proyecto, cliente y empresa, filtradas por propiedad."""
    return solo_propias(unir_jerarquia(select(*columnas).select_from(Salida), Salida.proyecto_id), usuario)


@dataclass
class Alcance:
    """Qué parte de la jerarquía abarca un reporte. Listas vacías = todos."""

    empresa_id: uuid.UUID | None = None
    terminal_ids: list[uuid.UUID] = field(default_factory=list)
    proyecto_ids: list[uuid.UUID] = field(default_factory=list)
    metodo_pago_ids: list[uuid.UUID] = field(default_factory=list)

    def aplicar(self, stmt, metodo_col):
        if self.empresa_id:
            stmt = stmt.where(Empresa.id == self.empresa_id)
        if self.terminal_ids:
            stmt = stmt.where(Terminal.id.in_(self.terminal_ids))
        if self.proyecto_ids:
            stmt = stmt.where(Proyecto.id.in_(self.proyecto_ids))
        if self.metodo_pago_ids:
            stmt = stmt.where(metodo_col.in_(self.metodo_pago_ids))
        return stmt


def _descripcion_alcance(db: Session, alcance: Alcance) -> dict[str, Any]:
    """Parámetros legibles para el encabezado del PDF."""
    def nombres(modelo, columna, ids):
        return ", ".join(db.scalars(select(columna).where(modelo.id.in_(ids)).order_by(columna))) if ids else "Todos"

    empresa = db.get(Empresa, alcance.empresa_id).nombre if alcance.empresa_id else "Todas"
    return {
        "Empresa": empresa,
        "Clientes": nombres(Terminal, Terminal.identificador_terminal, alcance.terminal_ids),
        "Proyectos": nombres(Proyecto, Proyecto.nombre, alcance.proyecto_ids),
        "Métodos de pago": nombres(MetodoPago, MetodoPago.nombre, alcance.metodo_pago_ids),
    }


# ------------------------------------------------------ Constructor de reportes
class Contenido(StrEnum):
    ENTRADAS = "entradas"
    SALIDAS = "salidas"
    AMBOS = "ambos"


class Agrupar(StrEnum):
    EMPRESA = "empresa"
    CLIENTE = "cliente"
    PROYECTO = "proyecto"
    METODO_PAGO = "metodo_pago"
    DETALLE = "detalle"


# Para cada agrupación: (columnas de identidad, columnas a mostrar como (clave, etiqueta, expresión))
_GRUPOS = {
    Agrupar.EMPRESA: ([Empresa.id], [("empresa", "Empresa", Empresa.nombre)]),
    Agrupar.CLIENTE: ([Terminal.id], [("empresa", "Empresa", Empresa.nombre),
                                      ("cliente", "Cliente", Terminal.identificador_terminal)]),
    Agrupar.PROYECTO: ([Proyecto.id], [("empresa", "Empresa", Empresa.nombre),
                                       ("cliente", "Cliente", Terminal.identificador_terminal),
                                       ("proyecto", "Proyecto", Proyecto.nombre)]),
    Agrupar.METODO_PAGO: ([MetodoPago.id], [("metodo_pago", "Método de pago", MetodoPago.nombre)]),
}

_TITULOS_GRUPO = {
    Agrupar.EMPRESA: "por empresa", Agrupar.CLIENTE: "por cliente", Agrupar.PROYECTO: "por proyecto",
    Agrupar.METODO_PAGO: "por método de pago", Agrupar.DETALLE: "— detalle",
}
_TITULOS_CONTENIDO = {Contenido.ENTRADAS: "Entradas", Contenido.SALIDAS: "Salidas",
                      Contenido.AMBOS: "Entradas y salidas"}


def constructor(
    db: Session,
    usuario: Usuario,
    *,
    alcance: Alcance,
    desde: date | None,
    hasta: date | None,
    contenido: Contenido = Contenido.AMBOS,
    agrupar: Agrupar = Agrupar.PROYECTO,
    requiere_factura: bool | None = None,
    texto: str | None = None,
) -> Reporte:
    """Reporte a la medida: elige empresa, clientes, proyectos y métodos de pago, y cómo agrupar."""
    validar_rango(desde, hasta)
    con_entradas = contenido in (Contenido.ENTRADAS, Contenido.AMBOS)
    con_salidas = contenido in (Contenido.SALIDAS, Contenido.AMBOS)
    patron = f"%{escapar_like(texto.strip())}%" if texto and texto.strip() else None

    def entradas(*columnas):
        stmt = alcance.aplicar(_movs(usuario, *columnas), Mov.metodo_pago_id)
        stmt = _rango(stmt, Mov.fecha_movimiento, desde, hasta)
        if requiere_factura is not None:
            stmt = stmt.where(Mov.requiere_factura.is_(requiere_factura))
        if patron:
            stmt = stmt.where(Mov.observaciones.ilike(patron, escape="\\"))
        return stmt

    def salidas(*columnas):
        stmt = alcance.aplicar(_sals(usuario, *columnas), Salida.metodo_pago_id)
        stmt = _rango(stmt, Salida.fecha, desde, hasta)
        if patron:
            stmt = stmt.where(or_(Salida.destino.ilike(patron, escape="\\"),
                                  Salida.observaciones.ilike(patron, escape="\\")))
        return stmt

    titulo = f"{_TITULOS_CONTENIDO[contenido]} {_TITULOS_GRUPO[agrupar]}"
    parametros = {**_descripcion_alcance(db, alcance), "Desde": desde, "Hasta": hasta,
                  "Factura": {True: "Solo con factura", False: "Solo sin factura"}.get(requiere_factura)}

    if agrupar == Agrupar.DETALLE:
        return _constructor_detalle(db, titulo, parametros, entradas if con_entradas else None,
                                    salidas if con_salidas else None)

    identidad, mostrar = _GRUPOS[agrupar]
    claves = [c for c, _, _ in mostrar]
    expr = [e.label(c) for c, _, e in mostrar]
    filas: dict[tuple, dict[str, Any]] = {}

    def fila(r) -> dict[str, Any]:
        llave = tuple(getattr(r, f"_id{i}") for i in range(len(identidad)))
        if llave not in filas:
            filas[llave] = {c: getattr(r, c) for c in claves} | {
                "movimientos": 0, "monto_bruto": CERO, "comision": CERO, "monto_neto": CERO,
                "num_salidas": 0, "salidas": CERO,
            }
        return filas[llave]

    ids = [c.label(f"_id{i}") for i, c in enumerate(identidad)]
    union_metodo = agrupar == Agrupar.METODO_PAGO
    if con_entradas:
        stmt = entradas(*ids, *expr, func.count(Mov.id).label("n"), func.sum(Mov.monto_bruto).label("bruto"),
                        func.sum(Mov.monto_neto).label("neto"))
        if union_metodo:
            stmt = stmt.join(MetodoPago, Mov.metodo_pago_id == MetodoPago.id)
        for r in db.execute(stmt.group_by(*identidad, *[e for _, _, e in mostrar])):
            f = fila(r)
            f.update(movimientos=r.n, monto_bruto=_dec(r.bruto), monto_neto=_dec(r.neto),
                     comision=_dec(r.bruto) - _dec(r.neto))
    if con_salidas:
        stmt = salidas(*ids, *expr, func.count(Salida.id).label("n"), func.sum(Salida.monto).label("total"))
        if union_metodo:
            stmt = stmt.join(MetodoPago, Salida.metodo_pago_id == MetodoPago.id)
        for r in db.execute(stmt.group_by(*identidad, *[e for _, _, e in mostrar])):
            f = fila(r)
            f.update(num_salidas=r.n, salidas=_dec(r.total))

    resultado = sorted(filas.values(), key=lambda f: tuple(str(f[c]) for c in claves))
    columnas = [(c, e) for c, e, _ in mostrar]
    sumas: list[str] = []
    if con_entradas:
        columnas += [("movimientos", "Entradas"), ("monto_bruto", "Bruto"), ("comision", "Comisión"),
                     ("monto_neto", "Neto")]
        sumas += ["monto_bruto", "comision", "monto_neto"]
    if con_salidas:
        columnas += [("num_salidas", "Salidas (#)"), ("salidas", "Salidas")]
        sumas += ["salidas"]
    if con_entradas and con_salidas:
        for f in resultado:
            f["saldo"] = f["monto_neto"] - f["salidas"]
        columnas += [("saldo", "Saldo")]
        sumas += ["saldo"]
    totales: dict[str, Any] = _sumar(resultado, *sumas)
    if con_entradas:
        totales["movimientos"] = sum(f["movimientos"] for f in resultado)
    if con_salidas:
        totales["num_salidas"] = sum(f["num_salidas"] for f in resultado)
    return Reporte(titulo=titulo, columnas=columnas, filas=resultado, totales=totales, parametros=parametros)


def _constructor_detalle(db: Session, titulo: str, parametros: dict[str, Any], entradas, salidas) -> Reporte:
    lineas: list[tuple[tuple, dict[str, Any]]] = []
    if entradas:
        stmt = entradas(
            Mov.fecha_movimiento, Mov.fecha_captura, Empresa.nombre.label("empresa"),
            Terminal.identificador_terminal.label("cliente"), Proyecto.nombre.label("proyecto"),
            MetodoPago.nombre.label("metodo"), Mov.requiere_factura, Mov.monto_bruto, Mov.porcentaje_aplicado,
            Mov.monto_neto, Mov.observaciones, NOMBRE_USUARIO.label("registro"),
        ).join(MetodoPago, Mov.metodo_pago_id == MetodoPago.id).join(Usuario, Mov.usuario_id == Usuario.id)
        for r in db.execute(stmt):
            lineas.append(((r.fecha_movimiento, 0, r.fecha_captura), {
                "fecha": r.fecha_movimiento, "tipo": "Entrada", "empresa": r.empresa, "cliente": r.cliente,
                "proyecto": r.proyecto, "metodo_pago": r.metodo, "factura": "Sí" if r.requiere_factura else "No",
                "monto_bruto": r.monto_bruto, "porcentaje": r.porcentaje_aplicado,
                "comision": r.monto_bruto - r.monto_neto, "monto_neto": r.monto_neto, "salida": None,
                "concepto": r.observaciones, "registro": r.registro,
            }))
    if salidas:
        stmt = salidas(
            Salida.fecha, Salida.fecha_registro, Empresa.nombre.label("empresa"),
            Terminal.identificador_terminal.label("cliente"), Proyecto.nombre.label("proyecto"),
            MetodoPago.nombre.label("metodo"), Salida.monto, Salida.destino, NOMBRE_USUARIO.label("registro"),
        ).join(MetodoPago, Salida.metodo_pago_id == MetodoPago.id).join(Usuario, Salida.usuario_id == Usuario.id)
        for r in db.execute(stmt):
            lineas.append(((r.fecha, 1, r.fecha_registro), {
                "fecha": r.fecha, "tipo": "Salida", "empresa": r.empresa, "cliente": r.cliente,
                "proyecto": r.proyecto, "metodo_pago": r.metodo, "factura": None, "monto_bruto": None,
                "porcentaje": None, "comision": None, "monto_neto": None, "salida": r.monto,
                "concepto": r.destino, "registro": r.registro,
            }))
    lineas.sort(key=lambda x: x[0])
    filas = [linea for _, linea in lineas]

    columnas = [("fecha", "Fecha"), ("tipo", "Tipo"), ("empresa", "Empresa"), ("cliente", "Cliente"),
                ("proyecto", "Proyecto"), ("metodo_pago", "Método de pago")]
    sumas: list[str] = []
    if entradas:
        columnas += [("factura", "Factura"), ("monto_bruto", "Bruto"), ("porcentaje", "%"),
                     ("comision", "Comisión"), ("monto_neto", "Neto")]
        sumas += ["monto_bruto", "comision", "monto_neto"]
    if salidas:
        columnas += [("salida", "Salida")]
        sumas += ["salida"]
    columnas += [("concepto", "Concepto / destino"), ("registro", "Registró")]
    return Reporte(titulo=titulo, columnas=columnas, filas=filas, totales=_sumar(filas, *sumas),
                   parametros=parametros)


# ------------------------------------------------------------ Estado de cuenta
def estado_cuenta(db: Session, usuario: Usuario, *, alcance: Alcance, desde: date, hasta: date) -> Reporte:
    """Entradas netas y salidas en orden cronológico con saldo corrido, para una empresa o parte de ella."""
    validar_rango(desde, hasta)
    anterior = desde - timedelta(days=1)
    neto_previo = db.scalar(alcance.aplicar(
        _movs(usuario, func.coalesce(func.sum(Mov.monto_neto), 0)).where(Mov.fecha_movimiento <= anterior),
        Mov.metodo_pago_id))
    salidas_previas = db.scalar(alcance.aplicar(
        _sals(usuario, func.coalesce(func.sum(Salida.monto), 0)).where(Salida.fecha <= anterior),
        Salida.metodo_pago_id))
    saldo_inicial = _dec(neto_previo) - _dec(salidas_previas)

    ingresos = db.execute(alcance.aplicar(
        _movs(usuario, Mov.fecha_movimiento, Mov.fecha_captura, Terminal.identificador_terminal, Proyecto.nombre,
              MetodoPago.nombre.label("metodo"), Mov.monto_neto)
        .join(MetodoPago, Mov.metodo_pago_id == MetodoPago.id)
        .where(Mov.fecha_movimiento.between(desde, hasta)),
        Mov.metodo_pago_id,
    )).all()
    egresos = db.execute(alcance.aplicar(
        _sals(usuario, Salida.fecha, Salida.fecha_registro, Terminal.identificador_terminal, Proyecto.nombre,
              MetodoPago.nombre.label("metodo"), Salida.destino, Salida.monto)
        .join(MetodoPago, Salida.metodo_pago_id == MetodoPago.id)
        .where(Salida.fecha.between(desde, hasta)),
        Salida.metodo_pago_id,
    )).all()

    lineas = [((r.fecha_movimiento, 0, r.fecha_captura),
               {"fecha": r.fecha_movimiento, "tipo": "Entrada", "cliente": r.identificador_terminal,
                "proyecto": r.nombre, "metodo_pago": r.metodo, "concepto": "Corte de terminal",
                "ingreso": r.monto_neto, "salida": None}) for r in ingresos]
    lineas += [((r.fecha, 1, r.fecha_registro),
                {"fecha": r.fecha, "tipo": "Salida", "cliente": r.identificador_terminal, "proyecto": r.nombre,
                 "metodo_pago": r.metodo, "concepto": r.destino, "ingreso": None, "salida": r.monto})
               for r in egresos]
    lineas.sort(key=lambda x: x[0])

    saldo = saldo_inicial
    filas: list[dict[str, Any]] = [{"fecha": desde, "tipo": "", "cliente": None, "proyecto": None,
                                    "metodo_pago": None, "concepto": "Saldo inicial", "ingreso": None,
                                    "salida": None, "saldo": saldo_inicial}]
    for _, linea in lineas:
        saldo += (linea["ingreso"] or CERO) - (linea["salida"] or CERO)
        filas.append({**linea, "saldo": saldo})

    total_ingresos = sum((f["ingreso"] or CERO for f in filas), CERO)
    total_salidas = sum((f["salida"] or CERO for f in filas), CERO)
    empresa = db.get(Empresa, alcance.empresa_id) if alcance.empresa_id else None
    return Reporte(
        titulo=f"Estado de cuenta — {empresa.nombre}" if empresa else "Estado de cuenta",
        columnas=[("fecha", "Fecha"), ("tipo", "Tipo"), ("cliente", "Cliente"), ("proyecto", "Proyecto"),
                  ("metodo_pago", "Método de pago"), ("concepto", "Concepto"), ("ingreso", "Entrada neta"),
                  ("salida", "Salida"), ("saldo", "Saldo")],
        filas=filas,
        totales={"ingreso": total_ingresos, "salida": total_salidas, "saldo": saldo},
        parametros={**_descripcion_alcance(db, alcance), "Desde": desde, "Hasta": hasta,
                    "saldo_inicial": saldo_inicial, "saldo_final": saldo},
    )


# --------------------------------------- Auditoría de captura por contador (admin)
def auditoria_por_contador(db: Session, usuario_id, desde, hasta) -> Reporte:
    validar_rango(desde, hasta)
    stmt = (
        select(
            Usuario.id,
            NOMBRE_USUARIO.label("contador"),
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
        columnas=[("contador", "Contador"), ("correo", "Correo"), ("movimientos", "Entradas"),
                  ("monto_bruto", "Bruto"), ("monto_neto", "Neto"), ("ediciones", "Ediciones/eliminaciones"),
                  ("primera_captura", "Primera captura"), ("ultima_captura", "Última captura")],
        filas=filas,
        totales={**_sumar(filas, "monto_bruto", "monto_neto"), "movimientos": sum(f["movimientos"] for f in filas)},
        parametros={"usuario_id": usuario_id, "desde": desde, "hasta": hasta},
    )


# ------------------------------------------ Conciliación diaria por cliente y proyecto
def conciliacion_diaria(db: Session, usuario: Usuario, fecha: date, alcance: Alcance) -> Reporte:
    stmt = alcance.aplicar(_movs(
        usuario,
        Empresa.nombre.label("empresa"),
        Terminal.identificador_terminal.label("cliente"),
        Proyecto.nombre.label("proyecto"),
        func.count(Mov.id).label("movimientos"),
        func.sum(Mov.monto_bruto).label("monto_bruto"),
        func.sum(COMISION).label("comision"),
        func.sum(Mov.monto_neto).label("monto_neto"),
    ), Mov.metodo_pago_id).where(Mov.fecha_movimiento == fecha).group_by(
        Empresa.nombre, Terminal.id, Proyecto.id
    ).order_by(Empresa.nombre, Terminal.identificador_terminal, Proyecto.nombre)
    filas = [
        {**r._asdict(), "monto_bruto": _dec(r.monto_bruto), "comision": _dec(r.comision), "monto_neto": _dec(r.monto_neto)}
        for r in db.execute(stmt)
    ]
    return Reporte(
        titulo=f"Conciliación diaria — {fecha.isoformat()}",
        columnas=[("empresa", "Empresa"), ("cliente", "Cliente"), ("proyecto", "Proyecto"),
                  ("movimientos", "Entradas"), ("monto_bruto", "Bruto"), ("comision", "Comisión"),
                  ("monto_neto", "Neto")],
        filas=filas,
        totales={**_sumar(filas, "monto_bruto", "comision", "monto_neto"),
                 "movimientos": sum(f["movimientos"] for f in filas)},
        parametros={"Fecha": fecha, **_descripcion_alcance(db, alcance)},
    )


# ---------------------------------------- Resumen mensual por empresa (admin)
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

    mes_sal = func.extract("month", Salida.fecha)
    stmt_sal = _sals(
        usuario, Empresa.id, Empresa.nombre, mes_sal.label("mes"), func.sum(Salida.monto).label("salidas")
    ).where(func.extract("year", Salida.fecha) == anio).group_by(Empresa.id, Empresa.nombre, mes_sal)
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
        columnas=[("empresa", "Empresa"), ("mes", "Mes"), ("ingresos_brutos", "Entradas brutas"),
                  ("comisiones", "Comisiones"), ("ingresos_netos", "Entradas netas"), ("salidas", "Salidas"),
                  ("flujo_neto", "Flujo neto")],
        filas=filas,
        totales=_sumar(filas, "ingresos_brutos", "comisiones", "ingresos_netos", "salidas", "flujo_neto"),
        parametros={"anio": anio, "mes": mes, "empresa_id": empresa_id},
    )


# ----------------------------------------------- Bitácora general (admin)
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


# ------------------------------------------------------- Saldos por empresa
def saldos_empresas(db: Session, usuario: Usuario, al_dia: date) -> Reporte:
    ingresos = (
        select(Terminal.empresa_id, func.sum(Mov.monto_bruto).label("bruto"), func.sum(Mov.monto_neto).label("neto"))
        .select_from(Mov)
        .join(Proyecto, Mov.proyecto_id == Proyecto.id)
        .join(Terminal, Proyecto.terminal_id == Terminal.id)
        .where(Mov.fecha_movimiento <= al_dia)
        .group_by(Terminal.empresa_id)
        .subquery()
    )
    salidas = (
        select(Terminal.empresa_id, func.sum(Salida.monto).label("total"))
        .select_from(Salida)
        .join(Proyecto, Salida.proyecto_id == Proyecto.id)
        .join(Terminal, Proyecto.terminal_id == Terminal.id)
        .where(Salida.fecha <= al_dia)
        .group_by(Terminal.empresa_id)
        .subquery()
    )
    stmt = solo_propias(
        select(
            Empresa.nombre.label("empresa"),
            func.coalesce(ingresos.c.bruto, 0).label("bruto"),
            func.coalesce(ingresos.c.neto, 0).label("neto"),
            func.coalesce(salidas.c.total, 0).label("salidas"),
        )
        .outerjoin(ingresos, ingresos.c.empresa_id == Empresa.id)
        .outerjoin(salidas, salidas.c.empresa_id == Empresa.id)
        .order_by(Empresa.nombre),
        usuario,
    )
    filas = []
    for r in db.execute(stmt):
        bruto, neto, sal = _dec(r.bruto), _dec(r.neto), _dec(r.salidas)
        filas.append({"empresa": r.empresa, "ingresos_brutos": bruto, "comisiones": bruto - neto,
                      "ingresos_netos": neto, "salidas": sal, "saldo": neto - sal})
    return Reporte(
        titulo=f"Saldos de empresas al {al_dia.isoformat()}",
        columnas=[("empresa", "Empresa"), ("ingresos_brutos", "Entradas brutas"), ("comisiones", "Comisiones"),
                  ("ingresos_netos", "Entradas netas"), ("salidas", "Salidas"), ("saldo", "Saldo")],
        filas=filas,
        totales=_sumar(filas, "ingresos_brutos", "comisiones", "ingresos_netos", "salidas", "saldo"),
        parametros={"al_dia": al_dia},
    )


# ------------------------------------------------------ Cierre diario
def resumen_cierre(db: Session, dia: date) -> Reporte:
    stmt = (
        select(
            NOMBRE_USUARIO.label("contador"),
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
        columnas=[("contador", "Contador"), ("movimientos", "Entradas"), ("monto_bruto", "Bruto"),
                  ("comision", "Comisión"), ("monto_neto", "Neto")],
        filas=filas,
        totales={**_sumar(filas, "monto_bruto", "comision", "monto_neto"),
                 "movimientos": sum(f["movimientos"] for f in filas)},
        parametros={"fecha": dia},
    )
