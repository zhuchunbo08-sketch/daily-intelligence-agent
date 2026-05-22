from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.db.models import IntelligenceItem

router = APIRouter(prefix="/api/opportunities", tags=["opportunities"])


@router.get("")
def list_opportunities(limit: int = 20, db: Session = Depends(get_db)):
    rows = (
        db.query(IntelligenceItem)
        .filter(
            IntelligenceItem.has_money_opportunity.is_(True),
            IntelligenceItem.has_cutting_risk.is_(False),
        )
        .order_by(IntelligenceItem.final_score.desc())
        .limit(limit)
        .all()
    )
    return [
        {
            "id": item.id,
            "title": item.title,
            "url": item.url,
            "source": item.source,
            "category": item.category,
            "event_time": item.event_time,
            "money_score": item.money_score,
            "risk_score": item.risk_score,
            "final_score": item.final_score,
            "worth_pushing": item.worth_pushing,
        }
        for item in rows
    ]
