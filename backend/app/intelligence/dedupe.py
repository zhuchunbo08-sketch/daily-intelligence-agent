from difflib import SequenceMatcher
import logging

from sqlalchemy.orm import Session

from app.collectors.base import CollectedItem
from app.db.models import IntelligenceItem
from app.intelligence.text import content_hash, normalize_for_hash, semantic_hash

logger = logging.getLogger(__name__)


class DedupeResult:
    def __init__(self, item: CollectedItem, content_hash_value: str, semantic_hash_value: str):
        self.item = item
        self.content_hash = content_hash_value
        self.semantic_hash = semantic_hash_value


class DedupeService:
    def __init__(self, title_threshold: float = 0.88) -> None:
        self.title_threshold = title_threshold

    def filter_new(self, db: Session, items: list[CollectedItem]) -> list[DedupeResult]:
        seen_urls: set[str] = set()
        seen_titles: list[str] = []
        seen_content_hashes: set[str] = set()
        seen_semantic_hashes: set[str] = set()
        results: list[DedupeResult] = []

        existing_urls = {row[0] for row in db.query(IntelligenceItem.url).all()}
        existing_content_hashes = {row[0] for row in db.query(IntelligenceItem.content_hash).all()}
        existing_semantic_hashes = {row[0] for row in db.query(IntelligenceItem.semantic_hash).all()}
        existing_titles = [
            row[0] for row in db.query(IntelligenceItem.title).order_by(IntelligenceItem.id.desc()).limit(500).all()
        ]

        for item in items:
            if item.url in seen_urls or item.url in existing_urls:
                continue

            normalized_title = normalize_for_hash(item.title)
            if self._is_similar_title(normalized_title, seen_titles + existing_titles):
                continue

            chash = content_hash(item.title, item.content or item.summary)
            if chash in seen_content_hashes or chash in existing_content_hashes:
                continue

            shash = semantic_hash(item.title, item.summary, item.content)
            if shash in seen_semantic_hashes or shash in existing_semantic_hashes:
                continue

            seen_urls.add(item.url)
            seen_titles.append(normalized_title)
            seen_content_hashes.add(chash)
            seen_semantic_hashes.add(shash)
            results.append(DedupeResult(item, chash, shash))

        logger.info("Dedupe kept %s/%s items", len(results), len(items))
        return results

    def _is_similar_title(self, title: str, others: list[str]) -> bool:
        if not title:
            return True
        for other in others:
            other_normalized = normalize_for_hash(other)
            if not other_normalized:
                continue
            if SequenceMatcher(None, title, other_normalized).ratio() >= self.title_threshold:
                return True
        return False
