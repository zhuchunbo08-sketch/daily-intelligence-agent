from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

from app.core.config import get_settings


def app_tz() -> ZoneInfo:
    return ZoneInfo(get_settings().timezone)


def now_local() -> datetime:
    return datetime.now(app_tz()).replace(tzinfo=None)


def to_local_naive(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value
    return value.astimezone(app_tz()).replace(tzinfo=None)


def daily_window(reference: datetime | None = None) -> tuple[datetime, datetime]:
    settings = get_settings()
    ref = reference or now_local()
    today_run = datetime.combine(
        ref.date(),
        time(hour=settings.daily_run_hour, minute=settings.daily_run_minute),
    )
    if ref < today_run:
        window_end = today_run - timedelta(days=1)
    else:
        window_end = today_run
    window_start = window_end - timedelta(days=1)
    return window_start, window_end
