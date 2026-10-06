import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import or_, select, update
from sqlalchemy.orm import Session

from app.core.errors import ReglaNegocio
from app.core.tiempo import hoy
from app.models import AccionBitacora, HistorialPorcentajeProyecto as Historial, Movimiento, Proyecto
from app.services.bitacora import registrar


def condicion_vigente(dia: date):
    return (
        Historial.fecha_inicio_vigencia <= dia,
        or_(Historial.fecha_fin_vigencia.is_(None), Historial.fecha_fin_vigencia > dia),
    )


def porcentaje_vigente(db: Session, proyecto_id: uuid.UUID, dia: date) -> Decimal:
    """porcentaje_vigente(P, d): el % que regía para el proyecto P el día d."""
    porcentaje = db.scalar(
        select(Historial.porcentaje).where(Historial.proyecto_id == proyecto_id, *condicion_vigente(dia))
    )
    if porcentaje is None:
        raise ReglaNegocio(f"El proyecto no tiene un porcentaje vigente para el {dia.isoformat()}")
    return porcentaje


def crear_porcentaje_inicial(db: Session, proyecto: Proyecto, porcentaje: Decimal, desde: date) -> None:
    db.add(Historial(proyecto_id=proyecto.id, porcentaje=porcentaje, fecha_inicio_vigencia=desde))


def cambiar_porcentaje(
    db: Session,
    *,
    proyecto: Proyecto,
    nuevo: Decimal,
    desde: date | None,
    usuario_id: uuid.UUID,
    motivo: str | None,
) -> tuple[Historial, int]:
    """Cambia el % de un proyecto a partir de `desde`.

    - Si `desde` coincide con el inicio del periodo abierto, se corrige ese periodo.
    - Si es posterior, se cierra el periodo abierto y se abre uno nuevo.
    - No se permite reescribir periodos anteriores al abierto.
    Los movimientos con fecha >= `desde` se recalculan, porque la regla es
    "se aplica el % que regía el día del movimiento".
    """
    desde = desde or hoy()
    abierto = db.scalar(
        select(Historial)
        .where(Historial.proyecto_id == proyecto.id, Historial.fecha_fin_vigencia.is_(None))
        .with_for_update()
    )
    if abierto is None:  # no debería ocurrir: todo proyecto nace con un porcentaje
        raise ReglaNegocio("El proyecto no tiene un porcentaje registrado")
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
        db.flush()  # cerrar primero: solo puede haber un periodo abierto por proyecto
        registro = Historial(proyecto_id=proyecto.id, porcentaje=nuevo, fecha_inicio_vigencia=desde)
        db.add(registro)

    resultado = db.execute(
        update(Movimiento)
        .where(Movimiento.proyecto_id == proyecto.id, Movimiento.fecha_movimiento >= desde)
        .values(porcentaje_aplicado=nuevo)
        .execution_options(synchronize_session=False)
    )
    recalculados = resultado.rowcount or 0

    registrar(
        db,
        usuario_id=usuario_id,
        entidad="Proyecto",
        entidad_id=proyecto.id,
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
