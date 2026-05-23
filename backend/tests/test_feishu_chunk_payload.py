import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.notifications.feishu import REPORT_TITLE, SEGMENT_TITLE_PREFIX, FeishuNotifier


def _collect_markdown_body_values(value):
    found = []
    if isinstance(value, dict):
        if value.get("tag") == "markdown" and isinstance(value.get("content"), str):
            found.append(value["content"])
        for key, child in value.items():
            if key == "text" and isinstance(child, str):
                found.append(child)
            found.extend(_collect_markdown_body_values(child))
    elif isinstance(value, list):
        for child in value:
            found.extend(_collect_markdown_body_values(child))
    return found


def _has_standalone_report_title(text: str) -> bool:
    return any(line.strip().lstrip("#").strip() == REPORT_TITLE for line in text.splitlines())


def test_split_and_payload_never_put_segment_title_in_markdown_content():
    notifier = FeishuNotifier()
    content = "# 每日破圈赚钱情报\n\n" + "\n\n".join(f"段落 {i}：" + "内容" * 20 for i in range(10))

    assert SEGMENT_TITLE_PREFIX not in content

    chunks = notifier._split(content, 80)
    assert len(chunks) > 1
    assert all(SEGMENT_TITLE_PREFIX not in chunk for chunk in chunks)
    assert all(not _has_standalone_report_title(chunk) for chunk in chunks)

    payloads = [notifier._payload("每日破圈赚钱情报 (2/2)", chunk) for chunk in chunks]
    for payload in payloads:
        for value in _collect_markdown_body_values(payload):
            assert SEGMENT_TITLE_PREFIX not in value
            assert not _has_standalone_report_title(value)


def test_strip_segment_titles_removes_existing_leaks_anywhere():
    notifier = FeishuNotifier()
    content = "# 每日破圈赚钱情报\n\n每日破圈赚钱情报\n\n每日破圈赚钱情报 (2/2)\n\n正文"

    cleaned = notifier._strip_segment_titles(content)

    assert SEGMENT_TITLE_PREFIX not in cleaned
    assert not _has_standalone_report_title(cleaned)
