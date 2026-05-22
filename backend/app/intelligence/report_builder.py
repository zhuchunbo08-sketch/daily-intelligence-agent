from datetime import datetime
import json
import logging
import re

from app.core.config import get_settings
import app.db.model_helpers  # noqa: F401
from app.db.models import IntelligenceItem
from app.intelligence.text import BLOCKED_PHRASES
from app.llm.client import LLMClient

logger = logging.getLogger(__name__)


class ReportBuilder:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.llm = LLMClient()

    async def build(
        self,
        report_date: str,
        window_start: datetime,
        window_end: datetime,
        items: list[IntelligenceItem],
        observed_items: list[IntelligenceItem],
    ) -> str:
        template_report = self._build_template(
            report_date=report_date,
            window_start=window_start,
            window_end=window_end,
            items=items,
            observed_items=observed_items,
        )
        if not self.llm.enabled:
            return template_report
        try:
            return await self._build_with_ai(
                report_date=report_date,
                window_start=window_start,
                window_end=window_end,
                items=items,
                observed_items=observed_items,
                fallback_report=template_report,
            )
        except Exception:
            logger.exception("AI report generation failed, using template report")
            return template_report

    def _build_template(
        self,
        report_date: str,
        window_start: datetime,
        window_end: datetime,
        items: list[IntelligenceItem],
        observed_items: list[IntelligenceItem],
    ) -> str:
        top_items = sorted(items, key=lambda item: item.final_score, reverse=True)[
            : self.settings.max_items_per_report
        ]
        opportunity_items = [
            item
            for item in top_items
            if item.has_money_opportunity and not item.has_cutting_risk
        ][:5]
        cognition_items = [
            item for item in top_items if item.has_cognition_value and not item.has_cutting_risk
        ][:3]
        risk_items = sorted(
            [item for item in observed_items if item.has_cutting_risk or item.risk_score >= 6],
            key=lambda item: item.risk_score,
            reverse=True,
        )[:5]

        lines = [
            "# 每日破圈赚钱情报",
            "",
            f"日期：{report_date}",
            f"覆盖时间：{window_start:%Y-%m-%d %H:%M} - {window_end:%Y-%m-%d %H:%M}",
            "",
            "## 先说结论",
            "",
            f"- 今天最重要的变化：{self._one_line(top_items, '今天没有发现足够可信的新变化，宁可少报，不凑数。')}",
            f"- 今天最值得注意的赚钱机会：{self._one_line(opportunity_items, '暂未发现可信度足够的明确机会，相关信号放入观察。')}",
            f"- 今天最值得更新的认知：{self._one_line(cognition_items, '重点仍是持续观察政策、平台和技术变化的真实影响。')}",
            f"- 今天最需要避开的坑：{self._risk_line(risk_items)}",
            "",
            "## 一、今日最值得关注的 3-5 条变化",
            "",
        ]

        if top_items:
            for index, item in enumerate(top_items[:5], start=1):
                lines.extend(self._render_item(index, item))
        else:
            lines.append("今天没有通过新鲜度、可信度、去重和风险过滤的重点资讯。")

        lines.extend(["", "## 二、今日赚钱机会雷达", ""])
        if opportunity_items:
            for item in opportunity_items:
                opportunity = self._dict(item.analysis.get("opportunity"))
                lines.extend(
                    [
                        f"- {opportunity.get('name') or item.title}",
                        f"  - 状态：{opportunity.get('status', '观察中')}",
                        f"  - 适合谁：{opportunity.get('suitable_for', '需要进一步验证')}",
                        f"  - 第一行动：{opportunity.get('first_action', '先验证来源和真实需求')}",
                        f"  - 风险等级：{opportunity.get('risk_level', '中')}",
                    ]
                )
        else:
            lines.append("没有足够可信的明确机会。看起来像机会但证据不足的内容，已经放入观察名单。")

        lines.extend(["", "## 三、今日认知升级", ""])
        if cognition_items:
            for item in cognition_items:
                cognition = self._dict(item.analysis.get("cognition"))
                lines.extend(
                    [
                        f"- 旧认知：{cognition.get('old', '只看表面热度')}",
                        f"  新认知：{cognition.get('new', '先看结构性变化，再决定是否行动')}",
                        f"  长期意义：{cognition.get('long_term_meaning', '持续积累判断框架')}",
                    ]
                )
        else:
            lines.append("今天没有足够强的新认知信号。")

        lines.extend(["", "## 四、今日反割韭菜提醒", ""])
        if risk_items:
            for item in risk_items:
                risk = self._dict(item.analysis.get("risk"))
                lines.extend(
                    [
                        f"- {item.title}",
                        f"  - 风险：{risk.get('packaging_risk', '可能被包装成高收益项目')}",
                        f"  - 易踩坑：{risk.get('traps', '忽视来源、案例和合规性')}",
                    ]
                )
        else:
            lines.append("今天没有进入高风险名单的内容，但仍要警惕夸大收益、拉人头、刷单和不透明资金流。")

        lines.extend(["", "## 五、今日行动建议", ""])
        lines.extend(self._actions(top_items, opportunity_items))

        return self._sanitize("\n".join(lines))

    async def _build_with_ai(
        self,
        report_date: str,
        window_start: datetime,
        window_end: datetime,
        items: list[IntelligenceItem],
        observed_items: list[IntelligenceItem],
        fallback_report: str,
    ) -> str:
        payload = {
            "report_date": report_date,
            "window_start": window_start.isoformat(),
            "window_end": window_end.isoformat(),
            "push_items": [self._item_payload(item) for item in items[: self.settings.max_items_per_report]],
            "observed_risk_items": [
                self._item_payload(item)
                for item in sorted(observed_items, key=lambda x: x.risk_score, reverse=True)[:8]
            ],
            "fallback_report": fallback_report[:12000],
        }
        system_prompt = """
你是“每日破圈赚钱情报系统”的日报生成器。你必须只基于输入 JSON 生成日报，不能虚构来源、案例、数据或收益。
所有分类、摘要、机会、风险、深度理解、认知升级都来自输入中的 AI 分析结果。
如果证据不足，明确写“观察中”或“不推荐行动”，不要为了凑数补内容。
禁止出现：轻松月入过万、零基础暴富、稳赚不赔、躺赚、无脑复制。
输出 Markdown，不要解释你的生成过程。
"""
        user_prompt = f"""
请生成固定格式日报，结构必须包含：

# 每日破圈赚钱情报
日期：YYYY-MM-DD
覆盖时间：昨天 07:00 - 今天 07:00

## 先说结论
## 一、今日最值得关注的 3-5 条变化
## 二、今日赚钱机会雷达
## 三、今日认知升级
## 四、今日反割韭菜提醒
## 五、今日行动建议

每条重点资讯必须包含：
- 发生了什么
- 时间范围
- 来源
- 所属类别
- 可信度
- 新鲜度判断
- 为什么重要
- 影响行业
- 来源链接
- 用普通话说
- 我的理解 / 深度拆解
- 和我有什么关系
- 赚钱机会拆解
- 认知升级点
- 风险提醒

输入 JSON：
{json.dumps(payload, ensure_ascii=False)}
"""
        report = await self.llm.chat_text(system_prompt=system_prompt, user_prompt=user_prompt)
        report = report.strip()
        if not report.startswith("# 每日破圈赚钱情报"):
            report = fallback_report
        return self._sanitize(report)

    def _item_payload(self, item: IntelligenceItem) -> dict:
        return {
            "title": item.title,
            "url": item.url,
            "source": item.source,
            "source_type": item.source_type,
            "category": item.category,
            "published_at": item.published_at.isoformat() if item.published_at else None,
            "event_time": item.event_time.isoformat() if item.event_time else None,
            "summary": item.summary,
            "freshness_score": item.freshness_score,
            "money_score": item.money_score,
            "trend_score": item.trend_score,
            "cognition_score": item.cognition_score,
            "actionability_score": item.actionability_score,
            "risk_score": item.risk_score,
            "final_score": item.final_score,
            "credibility": item.credibility,
            "freshness_label": item.freshness_label,
            "worth_pushing": item.worth_pushing,
            "analysis": item.analysis,
        }

    def _render_item(self, index: int, item: IntelligenceItem) -> list[str]:
        analysis = item.analysis
        relationship = self._dict(analysis.get("relationship"))
        opportunity = self._dict(analysis.get("opportunity"))
        cognition = self._dict(analysis.get("cognition"))
        risk = self._dict(analysis.get("risk"))
        return [
            f"### {index}. {item.title}",
            "",
            f"- 发生了什么：{analysis.get('what_happened', item.summary or item.title)}",
            f"- 时间范围：{item.event_time or item.published_at}",
            f"- 来源：{item.source}",
            f"- 所属类别：{item.category}",
            f"- 可信度：{item.credibility or '中'}",
            f"- 新鲜度判断：{item.freshness_label or '确认是过去24小时内'}",
            f"- 为什么重要：{analysis.get('why_important', '')}",
            f"- 影响行业：{analysis.get('affected_industries', item.category or '')}",
            f"- 来源链接：{item.url}",
            "",
            "#### 用普通话说",
            "",
            "这件事简单理解就是：",
            "",
            analysis.get("plain_language", item.summary or item.title),
            "",
            "#### 我的理解 / 深度拆解",
            "",
            "这件事表面上看是：",
            "",
            analysis.get("what_happened", item.title),
            "",
            "但背后真正说明的是：",
            "",
            analysis.get("deep_insight", "需要继续观察它是否带来结构性变化。"),
            "",
            "#### 和我有什么关系",
            "",
            f"- 对普通人：{relationship.get('ordinary_people', '先观察，不盲目投入。')}",
            f"- 对小商家：{relationship.get('small_business', '关注是否影响获客或交付。')}",
            f"- 对淘宝/电商：{relationship.get('ecommerce', '关注平台规则、流量和消费需求变化。')}",
            f"- 对内容创作者：{relationship.get('creators', '关注新选题和新分发入口。')}",
            f"- 对想用 AI 提效的人：{relationship.get('ai_efficiency', '观察是否能自动化重复工作。')}",
            f"- 对想找新机会的人：{relationship.get('opportunity_seekers', '先验证真实需求和案例。')}",
            "",
            "#### 赚钱机会拆解",
            "",
            f"- 是否存在赚钱机会：{opportunity.get('status', '观察中')}",
            f"- 机会名称：{opportunity.get('name', item.title)}",
            f"- 机会来源：{opportunity.get('source', item.source)}",
            f"- 适合谁：{opportunity.get('suitable_for', '需要进一步验证的人')}",
            f"- 怎么赚钱：{opportunity.get('monetization', '先做小规模验证')}",
            f"- 需要什么能力：{opportunity.get('required_skills', '信息验证和执行能力')}",
            f"- 启动成本：{opportunity.get('startup_cost', '低到中')}",
            f"- 变现路径：{opportunity.get('path', '验证需求后再设计服务或产品')}",
            f"- 第一行动：{opportunity.get('first_action', '先找真实用户验证')}",
            f"- 风险等级：{opportunity.get('risk_level', '中')}",
            f"- 推荐指数：{opportunity.get('recommendation_index', '观察')}",
            "",
            "#### 认知升级点",
            "",
            f"- 旧认知：{cognition.get('old', '把热点当机会。')}",
            f"- 新认知：{cognition.get('new', '把热点拆成真实变化、受益方和可执行路径。')}",
            f"- 我应该改变的判断：{cognition.get('judgment_change', '先验证，再行动。')}",
            f"- 长期意义：{cognition.get('long_term_meaning', '训练对变化的判断力。')}",
            "",
            "#### 风险提醒",
            "",
            f"- 这件事有没有被人包装成割韭菜项目的可能：{risk.get('packaging_risk', '有可能，需要警惕夸大包装。')}",
            f"- 普通人容易踩什么坑：{risk.get('traps', '只看收益承诺，不看真实交付。')}",
            f"- 哪些话术要警惕：{risk.get('warning_words', '夸大收益、拉人头、刷单、资金盘')}",
            "",
        ]

    def _one_line(self, items: list[IntelligenceItem], fallback: str) -> str:
        if not items:
            return fallback
        return items[0].title

    def _risk_line(self, items: list[IntelligenceItem]) -> str:
        if not items:
            return "警惕夸大收益、拉人头、刷单、灰产和来源不透明项目。"
        return items[0].title

    def _actions(
        self, top_items: list[IntelligenceItem], opportunity_items: list[IntelligenceItem]
    ) -> list[str]:
        actions: list[str] = []
        for item in opportunity_items[:2]:
            opportunity = self._dict(item.analysis.get("opportunity"))
            actions.append(f"- {opportunity.get('first_action', '验证这条机会的真实需求')} 来源：{item.url}")
        if top_items:
            actions.append(f"- 选一条最相关的变化做 30 分钟验证：{top_items[0].title}")
        if not actions:
            actions.append("- 今天不强行动，维护观察名单，明天继续看是否出现连续信号。")
        return actions[:3]

    def _sanitize(self, content: str) -> str:
        replacements = {
            "轻松月入过万": "夸大收益承诺",
            "零基础暴富": "夸大入门门槛和收益",
            "稳赚不赔": "无风险收益承诺",
            "躺赚": "被动收益包装",
            "无脑复制": "低门槛复制包装",
        }
        for phrase, replacement in replacements.items():
            content = content.replace(phrase, replacement)
        for phrase in BLOCKED_PHRASES:
            if phrase in replacements:
                continue
            content = re.sub(re.escape(phrase), phrase, content)
        return content

    def _dict(self, value) -> dict:
        return value if isinstance(value, dict) else {}
