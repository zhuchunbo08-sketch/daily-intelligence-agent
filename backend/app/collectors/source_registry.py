import json
import logging
from pathlib import Path

from sqlalchemy.orm import Session

from app.collectors.base import CollectedItem, SourceConfig
from app.collectors.gdelt_collector import GDELTCollector
from app.collectors.rss_collector import RSSCollector
from app.core.config import get_settings
from app.db.models import Source

logger = logging.getLogger(__name__)


class SourceRegistry:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.collectors = {
            "rss": RSSCollector(),
            "gdelt": GDELTCollector(),
        }

    def sync_sources(self, db: Session) -> None:
        path = Path(self.settings.sources_config_path)
        if not path.exists():
            logger.warning("Sources config not found: %s", path)
            return
        configs = json.loads(path.read_text(encoding="utf-8"))
        for raw in configs:
            source = db.query(Source).filter(Source.name == raw["name"]).first()
            if source is None:
                source = Source(name=raw["name"])
                db.add(source)
            source.source_type = raw["type"]
            source.url = raw["url"]
            source.query = raw.get("query")
            source.category_hint = raw.get("category_hint")
            source.enabled = raw.get("enabled", True)
        db.commit()

    def get_enabled_sources(self, db: Session) -> list[SourceConfig]:
        self.sync_sources(db)
        rows = db.query(Source).filter(Source.enabled.is_(True)).all()
        return [
            SourceConfig(
                name=row.name,
                type=row.source_type,
                url=row.url,
                query=row.query,
                category_hint=row.category_hint,
                enabled=row.enabled,
            )
            for row in rows
        ]

    def collect_all(self, db: Session) -> list[CollectedItem]:
        items: list[CollectedItem] = []
        for source in self.get_enabled_sources(db):
            collector = self.collectors.get(source.type)
            if not collector:
                logger.warning("Unsupported source type: %s", source.type)
                continue
            try:
                items.extend(collector.collect(source))
            except Exception:
                logger.exception("Collector failed: %s", source.name)
        return items
