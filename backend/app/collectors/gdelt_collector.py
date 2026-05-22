from datetime import datetime
import logging

import httpx
from dateutil import parser

from app.collectors.base import CollectedItem, SourceConfig
from app.core.config import get_settings
from app.core.time import to_local_naive
from app.intelligence.text import clean_html, normalize_text

logger = logging.getLogger(__name__)


class GDELTCollector:
    def collect(self, source: SourceConfig) -> list[CollectedItem]:
        logger.info("Collecting GDELT source: %s", source.name)
        settings = get_settings()
        params = {
            "query": source.query or "",
            "mode": "ArtList",
            "format": "json",
            "maxrecords": 50,
            "sort": "HybridRel",
        }
        try:
            kwargs = {"params": params, "timeout": 30}
            if settings.proxy_url:
                kwargs["proxy"] = settings.proxy_url
            response = httpx.get(source.url, **kwargs)
            response.raise_for_status()
            data = response.json()
        except Exception:
            logger.exception("GDELT collection failed: %s", source.name)
            return []

        items: list[CollectedItem] = []
        for article in data.get("articles", []):
            title = normalize_text(article.get("title"))
            url = article.get("url")
            if not title or not url:
                continue
            published_at = self._parse_date(article.get("seendate"))
            domain = article.get("domain") or source.name
            summary = clean_html(article.get("socialimage") or "")
            content = normalize_text(article.get("title", ""))
            items.append(
                CollectedItem(
                    title=title,
                    url=url,
                    source=domain,
                    source_type=source.type,
                    category_hint=source.category_hint,
                    published_at=published_at,
                    event_time=published_at,
                    summary=summary,
                    content=content,
                )
            )
        return items

    def _parse_date(self, value: str | None) -> datetime | None:
        if not value:
            return None
        try:
            dt = parser.parse(value)
            return to_local_naive(dt)
        except (TypeError, ValueError):
            return None
