from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.db.models import IntelligenceItem, Report
from app.jobs.daily_report_job import DailyReportJob

router = APIRouter(prefix="/api/reports", tags=["reports"])


@router.get("")
def list_reports(limit: int = 20, db: Session = Depends(get_db)):
    rows = db.query(Report).order_by(Report.id.desc()).limit(limit).all()
    return [
        {
            "id": row.id,
            "report_date": row.report_date,
            "title": row.title,
            "window_start": row.window_start,
            "window_end": row.window_end,
            "item_count": row.item_count,
            "pushed_at": row.pushed_at,
            "created_at": row.created_at,
        }
        for row in rows
    ]


@router.get("/latest")
def latest_report(db: Session = Depends(get_db)):
    report = db.query(Report).order_by(Report.id.desc()).first()
    if report is None:
        raise HTTPException(status_code=404, detail="No report yet")
    return {
        "id": report.id,
        "report_date": report.report_date,
        "title": report.title,
        "content": report.content,
        "item_count": report.item_count,
        "created_at": report.created_at,
        "pushed_at": report.pushed_at,
    }


@router.get("/{report_id}")
def get_report(report_id: int, db: Session = Depends(get_db)):
    report = db.get(Report, report_id)
    if report is None:
        raise HTTPException(status_code=404, detail="Report not found")
    return {
        "id": report.id,
        "report_date": report.report_date,
        "title": report.title,
        "content": report.content,
        "item_count": report.item_count,
        "created_at": report.created_at,
        "pushed_at": report.pushed_at,
    }


@router.post("/{report_id}/push")
async def push_report(report_id: int, db: Session = Depends(get_db)):
    report = db.get(Report, report_id)
    if report is None:
        raise HTTPException(status_code=404, detail="Report not found")
    items = (
        db.query(IntelligenceItem)
        .filter(
            IntelligenceItem.event_time >= report.window_start,
            IntelligenceItem.event_time < report.window_end,
            IntelligenceItem.worth_pushing.is_(True),
        )
        .order_by(IntelligenceItem.final_score.desc())
        .all()
    )
    try:
        await DailyReportJob()._push_report(db, report, items)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return {"status": "success", "report_id": report.id, "pushed_at": report.pushed_at}


@router.get("/{report_id}/items")
def list_report_items(report_id: int, db: Session = Depends(get_db)):
    report = db.get(Report, report_id)
    if report is None:
        raise HTTPException(status_code=404, detail="Report not found")
    rows = (
        db.query(IntelligenceItem)
        .filter(
            IntelligenceItem.event_time >= report.window_start,
            IntelligenceItem.event_time < report.window_end,
        )
        .order_by(IntelligenceItem.final_score.desc())
        .all()
    )
    return [
        {
            "id": item.id,
            "title": item.title,
            "url": item.url,
            "source": item.source,
            "source_type": item.source_type,
            "category": item.category,
            "published_at": item.published_at,
            "event_time": item.event_time,
            "collected_at": item.collected_at,
            "summary": item.summary,
            "content_hash": item.content_hash,
            "semantic_hash": item.semantic_hash,
            "freshness_score": item.freshness_score,
            "money_score": item.money_score,
            "trend_score": item.trend_score,
            "cognition_score": item.cognition_score,
            "actionability_score": item.actionability_score,
            "risk_score": item.risk_score,
            "final_score": item.final_score,
            "pushed_at": item.pushed_at,
            "worth_pushing": item.worth_pushing,
        }
        for item in rows
    ]
