from dataclasses import dataclass
from datetime import datetime


@dataclass
class SourceConfig:
    name: str
    type: str
    url: str
    query: str | None = None
    category_hint: str | None = None
    enabled: bool = True


@dataclass
class CollectedItem:
    title: str
    url: str
    source: str
    source_type: str
    category_hint: str | None
    published_at: datetime | None
    event_time: datetime | None
    summary: str
    content: str
