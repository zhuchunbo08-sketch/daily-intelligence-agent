from datetime import timedelta
import hashlib

from app.collectors.base import CollectedItem, SourceConfig
from app.core.time import daily_window
from app.intelligence.text import normalize_text


class PainKeywordsCollector:
    def collect(self, source: SourceConfig) -> list[CollectedItem]:
        _, window_end = daily_window()
        event_time = window_end - timedelta(hours=1)
        keywords = [
            normalize_text(part)
            for part in (source.query or "").replace("\n", ";").split(";")
            if normalize_text(part)
        ]
        items: list[CollectedItem] = []
        for keyword in keywords:
            digest = hashlib.sha256(f"{source.name}:{keyword}:{window_end:%Y-%m-%d}".encode("utf-8")).hexdigest()[:16]
            items.append(
                CollectedItem(
                    title=keyword,
                    url=f"pain-keyword://{source.name}/{digest}",
                    source=source.name,
                    source_type=source.type,
                    category_hint=source.category_hint or "痛点机会",
                    published_at=event_time,
                    event_time=event_time,
                    summary=f"可配置高频痛点关键词：{keyword}",
                    content=f"{keyword}。来源为可配置痛点关键词池，用于第一版验证痛点识别、变现方向和 7 天验证动作。",
                )
            )
        return items
