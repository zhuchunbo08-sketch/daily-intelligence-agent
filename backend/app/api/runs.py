from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.db.models import RunLog
from app.jobs.daily_report_job import DailyReportJob

router = APIRouter(prefix="/api/runs", tags=["runs"])


@router.post("/daily")
async def trigger_daily_report(db: Session = Depends(get_db)):
    try:
        return await DailyReportJob().run(db)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("")
def list_runs(limit: int = 20, db: Session = Depends(get_db)):
    rows = db.query(RunLog).order_by(RunLog.id.desc()).limit(limit).all()
    return [
        {
            "id": row.id,
            "job_name": row.job_name,
            "status": row.status,
            "window_start": row.window_start,
            "window_end": row.window_end,
            "started_at": row.started_at,
            "finished_at": row.finished_at,
            "message": row.message,
            "error": row.error,
        }
        for row in rows
    ]
