import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import or_, select, update
from sqlalchemy.orm import Session

from app.core.errors import ReglaNegocio
from app.core.tiempo import hoy
from app.models import AccionBitacora, HistorialPorcentajeTerminal as Historial, MovimientoTerminal, TerminalBancaria
from app.services.bitacora import registrar


def condicion_vigente(dia: date):
    return (
        Historial.fecha_inicio_vigencia <= dia,
        or_(Historial.fecha_fin_vigencia.is_(None), Historial.fecha_fin_vigencia > dia),
    )


def porcentaje_vigente(db: Session, terminal_id: uuid.UUID, dia: date) -> Decimal:
    """porcentaje_vigente(T, d): el % que regía para la terminal T el día d."""
    porcentaje = db.scalar(
        select(Historial.porcentaje).where(Historial.terminal_id == terminal_id, *condicion_vigente(dia))
    )
    if porcentaje is None:
        raise ReglaNegocio(f"La terminal no tiene un porcentaje vigente para el {dia.isoformat()}")
    return porcentaje


def crear_porcentaje_inicial(db: Session, terminal: TerminalBancaria, porcentaje: Decimal, desde: date) -> None:
    db.add(Historial(terminal_id=terminal.id, porcentaje=porcentaje, fecha_inicio_vigencia=desde))


def cambiar_porcentaje(
    db: Session,
    *,
    terminal: TerminalBancaria,
    nuevo: Decimal,
    desde: date | None,
    usuario_id: uuid.UUID,
    motivo: str | None,
) -> tuple[Historial, int]:
    """Cambia el % de una terminal a partir de `desde`.

    - Si `desde` coincide con el inicio del periodo abierto, se corrige ese periodo.
    - Si es posterior, se cierra el periodo abierto y se abre uno nuevo.
    - No se permite reescribir periodos anteriores al abierto.
    Los movimientos con fecha >= `desde` se recalculan, porque la regla es
    "se aplica el % que regía el día del movimiento".
    """
    desde = desde or hoy()
    abierto = db.scalar(
        select(Historial)
        .where(Historial.terminal_id == terminal.id, Historial.fecha_fin_vigencia.is_(None))
        .with_for_update()
    )
    if abierto is None:  # no debería ocurrir: toda terminal nace con un porcentaje
        raise ReglaNegocio("La terminal no tiene un porcentaje registrado")
    if desde < abierto.fecha_inicio_vigencia:
        raise ReglaNegocio(
            "La fecha de vigencia debe ser igual o posterior al "
            f"{abierto.fecha_inicio_vigencia.isoformat()}; no se pueden reescribir periodos anteriores"
        )

    anterior = abierto.porcentaje
    if desde == abierto.fecha_inicio_vigencia:
        abierto.porcentaje = nuevo
        registro = abierto
    else:
        abierto.fecha_fin_vigencia = desde
        db.flush()  # cerrar primero: solo puede haber un periodo abierto por terminal
        registro = Historial(terminal_id=terminal.id, porcentaje=nuevo, fecha_inicio_vigencia=desde)
        db.add(registro)

    resultado = db.execute(
        update(MovimientoTerminal)
        .where(MovimientoTerminal.terminal_id == terminal.id, MovimientoTerminal.fecha_movimiento >= desde)
        .values(porcentaje_aplicado=nuevo)
        .execution_options(synchronize_session=False)
    )
    recalculados = resultado.rowcount or 0

    registrar(
        db,
        usuario_id=usuario_id,
        entidad="TerminalBancaria",
        entidad_id=terminal.id,
        accion=AccionBitacora.CAMBIO_PORCENTAJE,
        detalle={
            "anterior": anterior,
            "nuevo": nuevo,
            "vigente_desde": desde,
            "movimientos_recalculados": recalculados,
            "motivo": motivo,
        },
    )
    db.flush()
    return registro, recalculados
