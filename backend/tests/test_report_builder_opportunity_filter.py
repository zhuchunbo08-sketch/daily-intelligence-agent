import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import app.db.model_helpers  # noqa: F401
from app.db.models import IntelligenceItem
from app.intelligence.report_builder import ReportBuilder


def _item(title: str, summary: str, analysis: dict, final_score: float = 8.0) -> IntelligenceItem:
    return IntelligenceItem(
        title=title,
        url=f"https://example.com/{abs(hash(title))}",
        source="test",
        source_type="rss",
        category="赚钱机会",
        summary=summary,
        content=summary,
        content_hash=str(abs(hash(title))),
        semantic_hash=str(abs(hash(summary))),
        freshness_score=8,
        money_score=7,
        trend_score=6,
        cognition_score=5,
        actionability_score=7,
        risk_score=2,
        final_score=final_score,
        has_money_opportunity=True,
        has_cognition_value=True,
        has_cutting_risk=False,
        worth_pushing=True,
        analysis_json=json.dumps(analysis, ensure_ascii=False),
    )


def test_radar_does_not_fill_empty_pain_day_with_vague_trends():
    builder = ReportBuilder()
    vague_audio = _item(
        "音频内容策展与过滤工具",
        "海外音频应用出现内容策展和过滤工具，但缺少明确付费对象和低成本交付物。",
        {"opportunity": {"name": "音频内容策展与过滤工具", "status": "是", "startup_cost": "低"}},
    )
    vague_forum = _item(
        "Forum内容创作者/社区运营",
        "海外新应用趋势，Forum 内容创作者和社区运营可能受益，但暂无国内具体交付物。",
        {"opportunity": {"name": "Forum内容创作者/社区运营", "status": "是", "startup_cost": "低"}},
    )
    concrete_service = _item(
        "小企业AI培训参与或衍生服务",
        "为小商家整理客服话术库、常见问题知识库和 AI 自动回复配置，交付飞书表格小样。",
        {
            "opportunity": {
                "name": "小企业AI培训参与或衍生服务",
                "status": "是",
                "suitable_for": "淘宝/拼多多/抖音小商家和小老板",
                "startup_cost": "低",
                "risk_level": "低",
            }
        },
    )
    duplicate_service = _item(
        "客户老问重复问题怎么办",
        "小商家可以整理客服话术库、常见问题知识库和 AI 自动回复配置，交付飞书表格小样。",
        {
            "opportunity": {
                "name": "AI客服自动回复配置服务",
                "status": "是",
                "suitable_for": "淘宝/拼多多/抖音小商家和小老板",
                "startup_cost": "低",
                "risk_level": "低",
            }
        },
    )

    radar_items = builder._radar_items([vague_audio, vague_forum, concrete_service, duplicate_service], pain_items=[])

    assert radar_items == [concrete_service]
    assert builder._opportunity_name(concrete_service) == "为小商家做 AI 客服话术库和自动回复配置服务"


def test_radar_empty_when_no_concrete_low_cost_offer():
    builder = ReportBuilder()
    vague_audio = _item(
        "音频内容策展与过滤工具",
        "海外音频应用出现内容策展和过滤工具，但缺少明确付费对象和低成本交付物。",
        {"opportunity": {"name": "音频内容策展与过滤工具", "status": "是", "startup_cost": "低"}},
    )
    vague_forum = _item(
        "Forum内容创作者/社区运营",
        "海外新应用趋势，Forum 内容创作者和社区运营可能受益，但暂无国内具体交付物。",
        {"opportunity": {"name": "Forum内容创作者/社区运营", "status": "是", "startup_cost": "低"}},
    )

    assert builder._radar_items([vague_audio, vague_forum], pain_items=[]) == []
