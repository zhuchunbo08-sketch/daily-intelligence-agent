from datetime import datetime
from email.utils import parsedate_to_datetime
import logging

import feedparser

from app.collectors.base import CollectedItem, SourceConfig
from app.core.time import to_local_naive
from app.intelligence.text import clean_html, normalize_text

logger = logging.getLogger(__name__)


class RSSCollector:
    def collect(self, source: SourceConfig) -> list[CollectedItem]:
        logger.info("Collecting RSS source: %s", source.name)
        parsed = feedparser.parse(source.url)
        items: list[CollectedItem] = []
        for entry in parsed.entries:
            title = normalize_text(getattr(entry, "title", ""))
            url = getattr(entry, "link", "")
            if not title or not url:
                continue
            published_at = self._parse_time(entry)
            summary = clean_html(getattr(entry, "summary", ""))
            content = self._extract_content(entry, summary)
            items.append(
                CollectedItem(
                    title=title,
                    url=url,
                    source=source.name,
                    source_type=source.type,
                    category_hint=source.category_hint,
                    published_at=published_at,
                    event_time=published_at,
                    summary=summary,
                    content=content,
                )
            )
        return items

    def _parse_time(self, entry) -> datetime | None:
        for key in ("published", "updated", "created"):
            value = getattr(entry, key, None)
            if not value:
                continue
            try:
                dt = parsedate_to_datetime(value)
                return to_local_naive(dt)
            except (TypeError, ValueError):
                continue
        return None

    def _extract_content(self, entry, fallback: str) -> str:
        if getattr(entry, "content", None):
            parts = [clean_html(part.get("value", "")) for part in entry.content]
            return normalize_text(" ".join(part for part in parts if part))
        return fallback
