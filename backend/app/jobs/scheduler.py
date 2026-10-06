import logging
from zoneinfo import ZoneInfo

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from app.core.config import settings
from app.services.cierre import ejecutar_cierre

logger = logging.getLogger(__name__)


def iniciar_scheduler() -> BackgroundScheduler:
    """Programa el cierre diario.

    Con varios workers de uvicorn/gunicorn, habilitar SCHEDULER_ENABLED en uno
    solo, o usar cron del sistema con `python -m app.cli cierre`. Aun así, el
    candado de PostgreSQL evita envíos duplicados.
    """
    zona = ZoneInfo(settings.TIMEZONE)
    scheduler = BackgroundScheduler(timezone=zona)
    scheduler.add_job(
        ejecutar_cierre,
        CronTrigger(hour=settings.CIERRE_HORA, minute=settings.CIERRE_MINUTO, timezone=zona),
        id="cierre_diario",
        replace_existing=True,
        coalesce=True,
        misfire_grace_time=3600,
    )
    scheduler.start()
    logger.info("Cierre diario programado a las %02d:%02d (%s)", settings.CIERRE_HORA, settings.CIERRE_MINUTO, zona)
    return scheduler
