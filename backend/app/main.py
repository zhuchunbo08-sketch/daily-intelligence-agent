from contextlib import asynccontextmanager

from fastapi import FastAPI

import app.db.model_helpers  # noqa: F401
from app.api.admin import router as admin_router
from app.api.opportunities import router as opportunities_router
from app.api.reports import router as reports_router
from app.api.runs import router as runs_router
from app.api.settings import router as settings_router
from app.api.sources import router as sources_router
from app.core.config import get_settings
from app.core.logging import configure_logging
from app.core.scheduler import start_scheduler, stop_scheduler
from app.db.database import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging()
    init_db()
    start_scheduler()
    yield
    stop_scheduler()


settings = get_settings()
app = FastAPI(title=settings.app_name, lifespan=lifespan)

app.include_router(admin_router)
app.include_router(runs_router)
app.include_router(reports_router)
app.include_router(sources_router)
app.include_router(opportunities_router)
app.include_router(settings_router)


@app.get("/health")
def health():
    return {"status": "ok", "app": settings.app_name, "timezone": settings.timezone}
