import json

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.db.models import TrendMemory

router = APIRouter(prefix="/api/trends", tags=["trends"])


@router.get("")
def list_trends(limit: int = 50, status: str | None = None, db: Session = Depends(get_db)):
    query = db.query(TrendMemory).order_by(TrendMemory.observed_at.desc(), TrendMemory.id.desc())
    if status:
        query = query.filter(TrendMemory.status == status)
    rows = query.limit(limit).all()
    return [
        {
            "id": row.id,
            "report_id": row.report_id,
            "item_id": row.item_id,
            "observed_at": row.observed_at,
            "trend_key": row.trend_key,
            "title": row.title,
            "category": row.category,
            "source": row.source,
            "url": row.url,
            "judgment": row.judgment,
            "evidence": json.loads(row.evidence_json or "{}"),
            "status": row.status,
            "created_at": row.created_at,
            "updated_at": row.updated_at,
        }
        for row in rows
    ]
