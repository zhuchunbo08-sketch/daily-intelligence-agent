import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from app.core.config import get_settings
from app.core.time import app_tz
from app.db.database import SessionLocal
from app.jobs.daily_report_job import DailyReportJob

logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler(timezone=app_tz())


async def scheduled_daily_report() -> None:
    db = SessionLocal()
    try:
        job = DailyReportJob()
        await job.run(db)
    finally:
        db.close()


def start_scheduler() -> None:
    settings = get_settings()
    if scheduler.running:
        return
    scheduler.add_job(
        scheduled_daily_report,
        CronTrigger(
            hour=settings.daily_run_hour,
            minute=settings.daily_run_minute,
            timezone=app_tz(),
        ),
        id="daily_report_0700",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )
    scheduler.start()
    logger.info(
        "Scheduler started: daily report at %02d:%02d %s",
        settings.daily_run_hour,
        settings.daily_run_minute,
        settings.timezone,
    )


def stop_scheduler() -> None:
    if scheduler.running:
        scheduler.shutdown(wait=False)
