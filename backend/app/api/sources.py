from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.collectors.source_registry import SourceRegistry
from app.db.database import get_db
from app.db.models import Source

router = APIRouter(prefix="/api/sources", tags=["sources"])


@router.get("")
def list_sources(db: Session = Depends(get_db)):
    SourceRegistry().sync_sources(db)
    rows = db.query(Source).order_by(Source.id.asc()).all()
    return [
        {
            "id": row.id,
            "name": row.name,
            "source_type": row.source_type,
            "url": row.url,
            "query": row.query,
            "category_hint": row.category_hint,
            "enabled": row.enabled,
            "created_at": row.created_at,
            "updated_at": row.updated_at,
        }
        for row in rows
    ]


@router.post("/sync")
def sync_sources(db: Session = Depends(get_db)):
    SourceRegistry().sync_sources(db)
    return {"status": "success"}
