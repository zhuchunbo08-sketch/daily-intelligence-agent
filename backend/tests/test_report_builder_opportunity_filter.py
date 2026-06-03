import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import app.db.model_helpers  # noqa: F401
from app.db.models import IntelligenceItem
from app.intelligence.report_builder import ReportBuilder


def _item(
    title: str,
    summary: str,
    analysis: dict,
    final_score: float = 8.0,
    source_type: str = "rss",
    category: str = "赚钱机会",
    money_score: float = 7,
) -> IntelligenceItem:
    return IntelligenceItem(
        title=title,
        url=f"https://example.com/{abs(hash(title))}",
        source="test",
        source_type=source_type,
        category=category,
        summary=summary,
        content=summary,
        content_hash=str(abs(hash(title))),
        semantic_hash=str(abs(hash(summary))),
        freshness_score=8,
        money_score=money_score,
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


def test_risk_warning_does_not_reuse_unrelated_finance_method_for_ai_service():
    builder = ReportBuilder()
    ai_service = _item(
        "小企业AI培训参与或衍生服务",
        "为小商家整理客服话术库、常见问题知识库和 AI 自动回复配置，交付飞书表格小样。",
        {
            "opportunity": {
                "name": "小企业AI培训参与或衍生服务",
                "status": "是",
                "suitable_for": "淘宝/拼多多/抖音小商家和小老板",
            },
            "risk": {"traps": "IPO定价过高、未来不及预期导致暴跌；地缘政治风险（如与NASA合同变化）。"},
        },
    )

    lines = builder._render_risks([ai_service], ai_service)
    text = "\n".join(lines)

    assert "AI 客服话术库服务" in text
    assert "高价课程" in text
    assert "IPO" not in text
    assert "NASA" not in text


def test_radar_backed_ai_service_is_synced_into_pain_module():
    builder = ReportBuilder()
    ai_service = _item(
        "小企业AI培训参与或衍生服务",
        "为小商家整理客服话术库、常见问题知识库和 AI 自动回复配置，交付飞书表格小样。",
        {
            "opportunity": {
                "name": "小企业AI培训参与或衍生服务",
                "status": "是",
                "suitable_for": "淘宝/拼多多/抖音小商家和小老板",
            }
        },
    )

    pain_items = builder._sync_pain_items([], [ai_service])
    rendered = "\n".join(builder._render_pain_points(pain_items))

    assert pain_items == [ai_service]
    assert "小商家客户老问重复问题怎么办" in rendered
    assert "可配置痛点关键词池 / 小商家 AI 服务观察" in rendered


def test_ai_customer_service_pain_question_stays_consistent_and_specific():
    builder = ReportBuilder()
    ai_service = _item(
        "小企业主不懂AI，如何低成本快速学会并应用到业务？",
        "为小商家整理客服话术库、常见问题知识库和 AI 自动回复配置，交付飞书表格小样。",
        {
            "pain_point": {"question": "小企业主不懂AI，如何低成本快速学会并应用到业务？"},
            "opportunity": {
                "name": "小企业AI培训参与或衍生服务",
                "status": "是",
                "suitable_for": "淘宝/拼多多/抖音小商家和小老板",
            },
        },
    )

    rendered = "\n".join(builder._render_pain_points([ai_service]))

    assert "### 痛点 1：小商家客户老问重复问题怎么办" in rendered
    assert "- 高频问题：小商家客户老问重复问题怎么办" in rendered
    assert "- 适合在哪个平台验证：微信私域 / 飞书 / 淘宝服务市场 / 本地生活 / 公众号 / 飞书多维表格 / 企业服务" in rendered
    assert "- 7 天内验证动作：第 1 天" in rendered
    assert "- 启动成本：低" in rendered
    assert "- 风险：低" in rendered
    assert "小企业主不懂AI" not in rendered


def test_cognition_upgrade_uses_judgment_not_news_summary_for_ai_service():
    builder = ReportBuilder()
    ai_service = _item(
        "小企业AI培训参与或衍生服务",
        "为小商家整理客服话术库、常见问题知识库和 AI 自动回复配置，交付飞书表格小样。",
        {
            "opportunity": {
                "name": "小企业AI培训参与或衍生服务",
                "status": "是",
                "suitable_for": "淘宝/拼多多/抖音小商家和小老板",
            }
        },
    )

    lines = builder._render_cognition([], [ai_service], [ai_service], [])
    text = "\n".join(lines)

    assert len(lines) == 2
    assert "不要卖“会用工具”" in text
    assert "Spotify推出" not in text
    assert "TechCrunch报道" not in text


def test_pain_priority_favors_life_pain_over_generic_ai_usage():
    builder = ReportBuilder()
    pet_pain = _item(
        "宠物掉毛怎么处理",
        "宠物掉毛、猫毛清理和粘毛器差评是高频家庭清洁痛点。",
        {"pain_point": {"question": "宠物掉毛怎么处理"}},
        source_type="pain_keywords",
        category="痛点机会",
        money_score=7,
    )
    generic_ai = _item(
        "AI工具太多不知道怎么用",
        "很多人不知道怎么选择 AI 工具，但暂未聚焦到具体交付场景。",
        {"pain_point": {"question": "AI工具太多不知道怎么用"}},
        source_type="pain_keywords",
        category="痛点机会",
        money_score=7,
    )

    pain_items = builder._pain_items([generic_ai, pet_pain])

    assert pain_items[0] == pet_pain


def test_render_actions_outputs_only_one_action_and_observes_when_no_quality_opportunity():
    builder = ReportBuilder()
    ai_service = _item(
        "客户老问重复问题怎么办",
        "为小商家整理客服话术库、常见问题知识库和 AI 自动回复配置，交付飞书表格小样。",
        {
            "opportunity": {
                "name": "AI客服自动回复配置服务",
                "status": "是",
                "suitable_for": "淘宝/拼多多/抖音小商家和小老板",
                "startup_cost": "低",
                "risk_level": "低",
            }
        },
        source_type="pain_keywords",
        category="痛点机会",
    )

    assert builder._render_actions([], [], []) == ["1. 今天不建议行动，只观察趋势。"]
    actions = builder._render_actions([ai_service], [ai_service], [])
    assert len(actions) == 1
    assert "第 1 天" in actions[0]


def test_render_risks_keeps_at_most_two_items_and_drops_cross_topic_methods():
    builder = ReportBuilder()
    pet_risk = _item(
        "宠物掉毛怎么处理",
        "宠物除毛刷和粘毛器有具体商品需求。",
        {
            "risk": {
                "concept": "宠物掉毛清理工具",
                "traps": "高价 AI 课程包装、加盟代理骗局、承诺全自动无人客服。",
            }
        },
        source_type="pain_keywords",
        category="痛点机会",
    )
    xhs_risk = _item(
        "小红书发了没人看怎么办",
        "内容创作者想提高选题和转化。",
        {
            "risk": {
                "concept": "小红书流量诊断服务",
                "traps": "IPO定价过高、未来不及预期导致暴跌；地缘政治风险（如与NASA合同变化）。",
            }
        },
        source_type="pain_keywords",
        category="痛点机会",
    )
    real_risk = _item(
        "客户老问重复问题怎么办",
        "AI 客服话术库可以做低成本验证。",
        {
            "risk": {
                "concept": "AI 客服话术库服务",
                "traps": "警惕承诺全自动无人客服、只卖通用模板、不看真实店铺案例的项目。",
            }
        },
        source_type="pain_keywords",
        category="痛点机会",
    )

    lines = builder._render_risks([pet_risk, real_risk, xhs_risk])
    text = "\n".join(lines)

    assert len(lines) <= 2
    assert "AI 客服话术库服务" in text
    assert "宠物掉毛清理工具" not in text
    assert "小红书流量诊断服务" not in text
    assert "NASA" not in text
    assert "IPO" not in text


def test_trend_observation_has_no_three_day_action_or_commercial_model():
    builder = ReportBuilder()
    spotify = _item(
        "Spotify 与环球音乐达成 AI 翻唱分成协议",
        "海外版权分成和平台规则复杂，国内暂无直接迁移平台。",
        {
            "opportunity": {
                "name": "AI 翻唱版权分成",
                "status": "观察中",
                "startup_cost": "低",
            }
        },
    )

    assert builder._radar_status(spotify) == "观察中"
    assert builder._three_day_action(spotify) == "不建议做 3 天动作，本条只做趋势观察。"
    assert builder._best_commercial_learning_item([], [], [spotify]) is None


def test_radar_caps_at_three_and_requires_concrete_verifiable_offer():
    builder = ReportBuilder()
    samples = [
        ("宠物掉毛怎么处理", "宠物主需要宠物除毛选品表和清洁测评清单。", "宠物除毛选品表"),
        ("孩子不好管怎么办", "家长需要行为奖励表、亲子任务卡和可打印资料包。", "育儿奖励表资料包"),
        ("小红书发了没人看怎么办", "内容创作者需要选题模板、标题清单和账号诊断。", "小红书选题模板"),
        ("商家不会做详情页怎么办", "小商家需要详情页诊断、主图优化清单和改版建议。", "详情页诊断清单"),
    ]
    items = [
        _item(
            title,
            summary,
            {
                "opportunity": {
                    "name": name,
                    "status": "是",
                    "suitable_for": "宠物主、家长、内容创作者或淘宝小商家",
                    "startup_cost": "低",
                    "risk_level": "低",
                },
                "pain_point": {"question": title},
            },
            source_type="pain_keywords",
            category="痛点机会",
        )
        for title, summary, name in samples
    ]

    radar_items = builder._radar_items(items, pain_items=items)

    assert 1 <= len(radar_items) <= 3
    assert all(builder._radar_criteria_count(item) >= 6 for item in radar_items)
