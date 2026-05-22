import hashlib
import re
from html import unescape

from bs4 import BeautifulSoup


BLOCKED_PHRASES = [
    "轻松月入过万",
    "零基础暴富",
    "稳赚不赔",
    "躺赚",
    "无脑复制",
    "资金盘",
    "传销",
    "博彩",
    "刷单",
    "虚假副业",
    "拉人头",
]


def clean_html(value: str | None) -> str:
    if not value:
        return ""
    soup = BeautifulSoup(value, "html.parser")
    text = soup.get_text(" ", strip=True)
    return normalize_text(unescape(text))


def normalize_text(value: str | None) -> str:
    if not value:
        return ""
    value = re.sub(r"\s+", " ", value).strip()
    return value


def normalize_for_hash(value: str | None) -> str:
    value = normalize_text(value).lower()
    value = re.sub(r"https?://\S+", "", value)
    value = re.sub(r"[^\w\u4e00-\u9fff]+", "", value)
    return value


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def content_hash(title: str, content: str) -> str:
    body = normalize_for_hash(f"{title} {content}")[:8000]
    return sha256_text(body)


def semantic_hash(title: str, summary: str, content: str) -> str:
    normalized = normalize_for_hash(f"{title} {summary} {content}")
    tokens = re.findall(r"[\u4e00-\u9fff]{2,}|[a-z0-9]{3,}", normalized)
    signature = "".join(sorted(set(tokens[:120])))
    return sha256_text(signature or normalized[:1000])


def contains_blocked_phrase(value: str) -> bool:
    lowered = value.lower()
    return any(phrase.lower() in lowered for phrase in BLOCKED_PHRASES)
