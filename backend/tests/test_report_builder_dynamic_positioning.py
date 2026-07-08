import json
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.db.models import IntelligenceItem
from app.intelligence.report_builder import NO_VALUABLE_REPORT, ReportBuilder


def _change_item() -> IntelligenceItem:
    analysis = {
        "what_happened": "一家全球平台开始调整创作者分成规则。",
        "why_important": "规则变化会改变内容供给、分发激励和小团队的变现路径。",
        "deep_insight": "平台规则变化真正影响的是谁拥有分发权，以及创作者是否还能靠单一平台稳定获得收入。",
        "cognition": {
            "judgment_change": "判断平台机会时，先看规则是否改变激励，而不是只看功能发布。",
        },
    }
    return IntelligenceItem(
        id=1,
        title="Global platform changes creator revenue share",
        url="https://example.com/platform-rule",
        source="Example",
        source_type="rss",
        category="商业",
        summary="一家全球平台开始调整创作者分成规则。",
        content="平台规则变化影响创作者经济和商业模式。",
        content_hash="dynamic-positioning-1",
        semantic_hash="dynamic-positioning-1",
        freshness_score=9,
        money_score=3,
        trend_score=8,
        cognition_score=8,
        actionability_score=2,
        risk_score=2,
        final_score=8,
        is_trustworthy=True,
        has_money_opportunity=False,
        has_cognition_value=True,
        has_cutting_risk=False,
        worth_pushing=True,
        analysis_json=json.dumps(analysis, ensure_ascii=False),
    )


def test_empty_day_returns_one_line_without_filling_modules():
    builder = ReportBuilder()

    report = builder._build_template(
        report_date="2026-07-08",
        window_start=datetime(2026, 7, 7, 7),
        window_end=datetime(2026, 7, 8, 7),
        items=[],
        observed_items=[],
    )

    assert report == NO_VALUABLE_REPORT
    assert builder.last_world_change_records == []


def test_dynamic_report_does_not_force_legacy_sections():
    builder = ReportBuilder()

    report = builder._build_template(
        report_date="2026-07-08",
        window_start=datetime(2026, 7, 7, 7),
        window_end=datetime(2026, 7, 8, 7),
        items=[],
        observed_items=[_change_item()],
    )

    assert report.startswith("# 每日商业观察")
    assert "## 世界发生了什么" in report
    assert "## 一个变化背后的商业规律" in report
    assert "## 二、今日赚钱机会雷达" not in report
    assert "## 六、今日行动建议" not in report
    assert "今天没有筛出" not in report
    assert len(builder.last_world_change_records) == 1
