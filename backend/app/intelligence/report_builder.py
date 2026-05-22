from datetime import datetime
from urllib.parse import urlparse
import re

from app.core.config import get_settings
import app.db.model_helpers  # noqa: F401
from app.db.models import IntelligenceItem
from app.intelligence.text import BLOCKED_PHRASES

FALLBACK = "暂无明确价值，但可作为趋势观察"
SECTION_HEADINGS = [
    "## 先说结论",
    "## 一、今日最值得关注的 3-5 条变化",
    "## 二、今日赚钱机会雷达",
    "## 三、今日认知升级",
    "## 四、今日反割韭菜提醒",
    "## 五、今日行动建议",
]
ITEM_SUBHEADINGS = [
    "#### 用普通话说",
    "#### 我的理解 / 深度拆解",
    "#### 国内映射",
    "#### 和我有什么关系",
    "#### 赚钱机会拆解",
    "#### 认知升级点",
    "#### 风险提醒",
]
HIGH_CAPITAL_KEYWORDS = [
    "融资",
    "上市",
    "IPO",
    "硬件研发",
    "专业化学",
    "气候科学",
    "AI底层模型",
    "底层模型",
    "巨额资本",
    "数据中心",
    "GPU",
    "芯片",
    "制造",
    "实验室",
    "算力",
    "药物研发",
    "自动驾驶",
    "碳移除",
    "carbon removal",
    "分子",
    "molecule",
    "molecules",
    "biotech",
    "fragrance",
    "scent molecule",
    "scent molecules",
]


class ReportBuilder:
    def __init__(self) -> None:
        self.settings = get_settings()

    async def build(
        self,
        report_date: str,
        window_start: datetime,
        window_end: datetime,
        items: list[IntelligenceItem],
        observed_items: list[IntelligenceItem],
    ) -> str:
        report = self._build_template(
            report_date=report_date,
            window_start=window_start,
            window_end=window_end,
            items=items,
            observed_items=observed_items,
        )
        self._validate_report_structure(report)
        return report

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
        radar_items = self._radar_items(top_items)
        cognition_items = self._cognition_items(top_items)
        risk_items = self._risk_items(observed_items)

        lines = [
            "# 每日破圈赚钱情报",
            "",
            f"日期：{report_date}",
            f"覆盖时间：{window_start:%Y-%m-%d %H:%M} - {window_end:%Y-%m-%d %H:%M}",
            "",
            "## 先说结论",
            "",
            f"- 今天最重要的变化：{self._text(top_items[0].title if top_items else None)}",
            f"- 今天最值得注意的赚钱机会：{self._text(self._opportunity_name(radar_items[0]) if radar_items else None)}",
            f"- 今天最值得更新的认知：{self._text(self._cognition(top_items[0]).get('new') if top_items else None)}",
            f"- 今天最需要避开的坑：{self._text(self._risk_title(risk_items[0]) if risk_items else '高收益副业包装、拉人头项目、刷单和不透明资金流')}",
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
        lines.extend(self._render_radar(radar_items))

        lines.extend(["", "## 三、今日认知升级", ""])
        lines.extend(self._render_cognition_summary(cognition_items))

        lines.extend(["", "## 四、今日反割韭菜提醒", ""])
        lines.extend(self._render_risk_summary(risk_items))

        lines.extend(["", "## 五、今日行动建议", ""])
        lines.extend(self._render_actions(radar_items, top_items))

        return self._sanitize("\n".join(lines).strip() + "\n")

    def _render_item(self, index: int, item: IntelligenceItem) -> list[str]:
        analysis = item.analysis
        relationship = self._relationship(item)
        opportunity = self._opportunity(item)
        cognition = self._cognition(item)
        risk = self._risk(item)
        domestic = self._domestic_mapping(item)
        recommendation = self._recommendation_index(item)
        status = self._opportunity_status(item)

        return [
            f"### {index}. {self._text(item.title)}",
            f"- 发生了什么：{self._text(analysis.get('what_happened'), item.summary or item.title)}",
            f"- 时间范围：{self._text(item.event_time or item.published_at)}",
            f"- 来源：{self._text(item.source)}",
            f"- 所属类别：{self._text(item.category)}",
            f"- 可信度：{self._text(item.credibility, '中')}",
            f"- 新鲜度判断：{self._text(item.freshness_label, '确认是过去24小时内')}",
            f"- 为什么重要：{self._text(analysis.get('why_important'))}",
            f"- 影响行业：{self._text(analysis.get('affected_industries'), item.category)}",
            f"- 来源链接：{self._text(item.url)}",
            "",
            "#### 用普通话说",
            self._text(analysis.get("plain_language"), item.summary or item.title),
            "",
            "#### 我的理解 / 深度拆解",
            self._text(analysis.get("deep_insight")),
            "",
            "#### 国内映射",
            f"- 中国有没有类似平台/场景：{domestic['similar_scene']}",
            f"- 中国普通人能不能直接用：{domestic['direct_use']}",
            f"- 如果不能直接用，能迁移到哪里：{domestic['migration_target']}",
            f"- 适合迁移到：{domestic['platforms']}",
            f"- 对我这种关注 AI、自动化、淘宝/电商、内容变现的人是否有价值：{domestic['personal_value']}",
            "",
            "#### 和我有什么关系",
            f"- 对普通人：{relationship['ordinary_people']}",
            f"- 对小商家：{relationship['small_business']}",
            f"- 对淘宝/电商：{relationship['ecommerce']}",
            f"- 对内容创作者：{relationship['creators']}",
            f"- 对想用 AI 提效的人：{relationship['ai_efficiency']}",
            f"- 对想找新机会的人：{relationship['opportunity_seekers']}",
            "",
            "#### 赚钱机会拆解",
            f"- 是否存在赚钱机会：{status}",
            f"- 机会名称：{self._opportunity_name(item)}",
            f"- 适合谁：{self._text(opportunity.get('suitable_for'))}",
            f"- 不适合谁：{self._not_suitable_for(item)}",
            f"- 怎么赚钱：{self._text(opportunity.get('monetization'))}",
            f"- 第一个可执行动作：{self._first_action(item)}",
            f"- 3 天内能做什么：{self._three_day_action(item)}",
            f"- 启动成本：{self._startup_cost(item)}",
            f"- 风险等级：{self._risk_level(item)}",
            f"- 推荐指数：{recommendation}",
            f"- 是否适合中国大陆普通人：{self._mainland_fit(item)}",
            f"- 是否适合我：{self._fit_me(item)}",
            "",
            "#### 认知升级点",
            f"- 旧认知：{self._text(cognition.get('old'))}",
            f"- 新认知：{self._text(cognition.get('new'))}",
            f"- 我应该改变的判断：{self._text(cognition.get('judgment_change'))}",
            f"- 长期意义：{self._text(cognition.get('long_term_meaning'))}",
            "",
            "#### 风险提醒",
            f"- 可能被包装成什么割韭菜项目：{self._text(risk.get('packaging_risk'), '高收益副业课、代运营捷径、自动化暴利项目')}",
            f"- 常见忽悠话术：{self._text(risk.get('warning_words'), '承诺固定收益、强调不需要能力、催促立刻付费')}",
            f"- 普通人判断真假的方法：{self._text(risk.get('traps'), '先查来源、看真实交付、找独立案例、避免先交大额费用')}",
            "",
        ]

    def _render_radar(self, items: list[IntelligenceItem]) -> list[str]:
        if not items:
            return [
                "- 机会名称：暂无明确价值，但可作为趋势观察",
                "  来源：暂无明确价值，但可作为趋势观察",
                "  状态：观察中",
                "  适合谁：暂无明确价值，但可作为趋势观察",
                "  第一行动：今天花 30 分钟在小红书、抖音、淘宝搜索“AI 自动化 电商 提效”，记录 10 个真实需求句子。",
                "  3 天内动作：用表格整理 10 个需求、3 个已有解决方案、1 个可做的小样方向。",
                "  风险等级：中",
                "  推荐指数：2",
                "  中国落地价值：可作为趋势观察，暂不作为推荐机会。",
            ]

        lines: list[str] = []
        for item in items:
            lines.extend(
                [
                    f"- 机会名称：{self._opportunity_name(item)}",
                    f"  来源：{self._text(item.source)}",
                    f"  状态：{self._radar_status(item)}",
                    f"  适合谁：{self._text(self._opportunity(item).get('suitable_for'))}",
                    f"  第一行动：{self._first_action(item)}",
                    f"  3 天内动作：{self._three_day_action(item)}",
                    f"  风险等级：{self._risk_level(item)}",
                    f"  推荐指数：{self._recommendation_index(item)}",
                    f"  中国落地价值：{self._domestic_mapping(item)['personal_value']}",
                ]
            )
        return lines

    def _render_cognition_summary(self, items: list[IntelligenceItem]) -> list[str]:
        if not items:
            return [
                "- 旧认知：看到海外新产品就等于看到国内机会。",
                "  新认知：先判断它能否迁移到国内平台、是否有明确服务对象、普通人 7 天内能否验证。",
                "  为什么重要：这能避免把资本密集型趋势误判成普通人项目。",
                "  我应该怎么调整判断：先做国内映射和低成本验证，再决定是否投入。",
            ]

        lines: list[str] = []
        seen: set[str] = set()
        for item in items:
            cognition = self._cognition(item)
            old = self._text(cognition.get("old"))
            new = self._text(cognition.get("new"))
            key = f"{old}|{new}"
            if key in seen:
                continue
            seen.add(key)
            lines.extend(
                [
                    f"- 旧认知：{old}",
                    f"  新认知：{new}",
                    f"  为什么重要：{self._text(cognition.get('long_term_meaning'))}",
                    f"  我应该怎么调整判断：{self._text(cognition.get('judgment_change'))}",
                ]
            )
            if len(seen) >= 3:
                break
        return lines

    def _render_risk_summary(self, items: list[IntelligenceItem]) -> list[str]:
        if not items:
            return [
                "- 风险项目/概念：高收益副业包装",
                "  为什么有风险：常把不确定的流量机会包装成确定收益，忽略交付难度和平台规则。",
                "  常见话术：限时名额、无需能力、复制模板、保证结果、先交费用。",
                "  判断方法：要求对方展示真实交付、独立案例、退款规则和可验证客户来源。",
                "  建议：不支付大额费用，先用公开资料和免费工具做 1 次小样验证。",
            ]

        lines: list[str] = []
        for item in items[:5]:
            risk = self._risk(item)
            lines.extend(
                [
                    f"- 风险项目/概念：{self._risk_title(item)}",
                    f"  为什么有风险：{self._text(risk.get('packaging_risk'), '可能把趋势包装成确定收益项目')}",
                    f"  常见话术：{self._text(risk.get('warning_words'), '保证收益、无需能力、限时上车、复制即可')}",
                    f"  判断方法：{self._text(risk.get('traps'), '看来源、看交付、看真实客户、看是否要求先交大额费用')}",
                    "  建议：先记录为风险观察，不支付费用，不转发推广，不拉人参与。",
                ]
            )
        return lines

    def _render_actions(
        self, radar_items: list[IntelligenceItem], top_items: list[IntelligenceItem]
    ) -> list[str]:
        actions: list[str] = []
        if radar_items:
            item = radar_items[0]
            keyword = self._keyword(item)
            actions.append(
                f"- 今天花 30 分钟在小红书、抖音、淘宝分别搜索“{keyword}”，每个平台记录 5 条真实用户需求。"
            )
            actions.append(
                f"- 用飞书表格建 4 列：需求原话、现有解决方案、可迁移平台、能否 7 天验证，把“{self._opportunity_name(item)}”拆成 3 个小样方向。"
            )
            actions.append(f"- 找 3 个淘宝/电商或内容创作者，拿“{keyword}”相关问题问他们现在怎么解决、愿不愿意付费。")
        elif top_items:
            item = top_items[0]
            keyword = self._keyword(item)
            actions.append(
                f"- 今天花 30 分钟搜索“{keyword} 国内案例”，只记录有真实产品、真实客户或真实交易截图的 5 个案例。"
            )
            actions.append(
                f"- 用一页文档写清楚“{keyword}”能迁移到抖音、小红书、淘宝还是企业服务，并列出 3 个不能做的原因。"
            )
        else:
            actions.append("- 今天花 30 分钟检查数据源列表，新增 3 个与你关注的 AI、电商、自动化相关 RSS 或公告源。")
        return actions[:3]

    def _radar_items(self, items: list[IntelligenceItem]) -> list[IntelligenceItem]:
        selected: list[IntelligenceItem] = []
        for item in items:
            if self._is_high_capital(item) or item.risk_score >= 7:
                continue
            if not item.has_money_opportunity or item.money_score < 5:
                continue
            if self._radar_criteria_count(item) >= 3:
                selected.append(item)
        return selected[:5]

    def _radar_criteria_count(self, item: IntelligenceItem) -> int:
        opportunity = self._opportunity(item)
        criteria = [
            self._seven_day_verifiable(item),
            self._startup_cost(item) in {"低", "中"},
            not self._depends_on_overseas_restriction(item),
            self._can_migrate_to_china(item),
            self._has_clear_service_object(opportunity),
            self._has_executable_first_step(item),
            self._risk_level(item) != "高",
        ]
        return sum(1 for value in criteria if value)

    def _cognition_items(self, items: list[IntelligenceItem]) -> list[IntelligenceItem]:
        return [item for item in items if item.has_cognition_value or item.cognition_score >= 4][:3]

    def _risk_items(self, observed_items: list[IntelligenceItem]) -> list[IntelligenceItem]:
        return sorted(
            [item for item in observed_items if item.has_cutting_risk or item.risk_score >= 6],
            key=lambda item: item.risk_score,
            reverse=True,
        )[:5]

    def _relationship(self, item: IntelligenceItem) -> dict:
        relationship = self._dict(item.analysis.get("relationship"))
        return {
            "ordinary_people": self._text(relationship.get("ordinary_people")),
            "small_business": self._text(relationship.get("small_business")),
            "ecommerce": self._text(relationship.get("ecommerce")),
            "creators": self._text(relationship.get("creators")),
            "ai_efficiency": self._text(relationship.get("ai_efficiency")),
            "opportunity_seekers": self._text(relationship.get("opportunity_seekers")),
        }

    def _opportunity(self, item: IntelligenceItem) -> dict:
        return self._dict(item.analysis.get("opportunity"))

    def _cognition(self, item: IntelligenceItem) -> dict:
        cognition = self._dict(item.analysis.get("cognition"))
        return {
            "old": self._text(cognition.get("old"), "把新闻热度直接当成机会。"),
            "new": self._text(cognition.get("new"), "先看国内迁移、服务对象、验证成本和风险，再判断机会。"),
            "judgment_change": self._text(cognition.get("judgment_change"), "先做低成本验证，不把资本趋势当成普通人项目。"),
            "long_term_meaning": self._text(cognition.get("long_term_meaning"), "长期能提升对平台变化、技术变化和商业机会的判断力。"),
        }

    def _risk(self, item: IntelligenceItem) -> dict:
        risk = self._dict(item.analysis.get("risk"))
        return {
            "packaging_risk": self._text(risk.get("packaging_risk"), "可能被包装成高收益副业、代运营捷径或自动化暴利项目。"),
            "warning_words": self._text(risk.get("warning_words"), "保证收益、无需能力、限时上车、复制即可。"),
            "traps": self._text(risk.get("traps"), "先查来源、看真实交付、找独立案例、避免先交大额费用。"),
        }

    def _domestic_mapping(self, item: IntelligenceItem) -> dict:
        mapping = self._dict(item.analysis.get("domestic_mapping"))
        platforms = self._platforms(item)
        is_overseas = self._is_overseas(item)
        return {
            "similar_scene": self._text(
                mapping.get("similar_scene"),
                "有，可对照抖音、小红书、淘宝、视频号、公众号、知识付费或企业服务场景。",
            ),
            "direct_use": self._text(
                mapping.get("direct_use"),
                "海外平台新闻通常不能直接照搬，需要先做国内平台、支付、账号和合规迁移。"
                if is_overseas
                else "可以先在国内平台做低成本验证，但仍要检查平台规则和合规边界。",
            ),
            "migration_target": self._text(
                mapping.get("migration_target"),
                "迁移到国内内容平台、电商平台、私域服务或企业自动化服务。",
            ),
            "platforms": self._text(mapping.get("platforms"), platforms),
            "personal_value": self._text(
                mapping.get("personal_value"),
                "有观察价值，尤其适合用来判断 AI、自动化、电商运营和内容变现是否出现新需求。",
            ),
        }

    def _platforms(self, item: IntelligenceItem) -> str:
        text = self._item_text(item)
        platforms: list[str] = []
        if any(word in text for word in ["video", "视频", "creator", "内容", "viral", "short"]):
            platforms.extend(["抖音", "小红书", "视频号"])
        if any(word in text for word in ["ecommerce", "commerce", "电商", "淘宝", "shop"]):
            platforms.extend(["淘宝", "抖音", "小红书"])
        if any(word in text for word in ["ai", "automation", "自动化", "saas", "企业"]):
            platforms.extend(["企业服务", "公众号", "知识付费"])
        if not platforms:
            platforms.extend(["抖音", "小红书", "淘宝", "公众号", "企业服务"])
        return " / ".join(dict.fromkeys(platforms))

    def _opportunity_status(self, item: IntelligenceItem) -> str:
        raw = self._text(self._opportunity(item).get("status"), "观察中")
        if self._is_high_capital(item) or item.risk_score >= 8:
            return "不建议碰"
        if self._startup_cost(item) == "高" or not self._mainland_fit_bool(item):
            return "观察中"
        if raw in {"是", "可测试"} and self._radar_criteria_count(item) >= 3:
            return "是"
        if raw in {"否", "不建议碰"}:
            return raw
        return "观察中"

    def _radar_status(self, item: IntelligenceItem) -> str:
        if self._is_high_capital(item) or item.risk_score >= 8:
            return "不建议碰"
        if self._radar_criteria_count(item) >= 4:
            return "可测试"
        return "观察中"

    def _opportunity_name(self, item: IntelligenceItem) -> str:
        return self._text(self._opportunity(item).get("name"), item.title)

    def _not_suitable_for(self, item: IntelligenceItem) -> str:
        value = self._opportunity(item).get("not_suitable_for")
        if self._valid(value):
            return self._text(value)
        if self._is_high_capital(item):
            return "不适合缺少资本、专业团队、硬件研发或行业资质的普通人直接投入。"
        return "不适合没有时间做需求验证、只想直接复制收益的人。"

    def _first_action(self, item: IntelligenceItem) -> str:
        opportunity = self._opportunity(item)
        value = opportunity.get("first_action") or opportunity.get("first_step")
        if self._valid(value) and not self._is_vague_action(str(value)):
            return self._text(value)
        keyword = self._keyword(item)
        return f"今天花 30 分钟在小红书、抖音、淘宝搜索“{keyword}”，记录 10 条真实需求。"

    def _three_day_action(self, item: IntelligenceItem) -> str:
        value = self._opportunity(item).get("three_day_action")
        if self._valid(value) and not self._is_vague_action(str(value)):
            return self._text(value)
        keyword = self._keyword(item)
        return f"第 1 天收集 10 条需求，第 2 天做 1 页服务说明，第 3 天找 3 个潜在用户验证“{keyword}”是否值得付费。"

    def _startup_cost(self, item: IntelligenceItem) -> str:
        value = str(self._opportunity(item).get("startup_cost") or "")
        text = f"{value} {self._item_text(item)}".lower()
        if any(word.lower() in text for word in HIGH_CAPITAL_KEYWORDS):
            return "高"
        if any(word in value for word in ["高", "重", "大"]):
            return "高"
        if any(word in value for word in ["中"]):
            return "中"
        return "低"

    def _risk_level(self, item: IntelligenceItem) -> str:
        value = str(self._opportunity(item).get("risk_level") or "")
        if item.risk_score >= 7 or "高" in value:
            return "高"
        if item.risk_score >= 4 or "中" in value:
            return "中"
        return "低"

    def _recommendation_index(self, item: IntelligenceItem) -> int:
        value = self._opportunity(item).get("recommendation_index")
        match = re.search(r"\d+", str(value or ""))
        if match:
            return max(1, min(5, int(match.group(0))))
        if self._is_high_capital(item) or item.risk_score >= 8:
            return 1
        if self._radar_criteria_count(item) >= 5:
            return 4
        if self._radar_criteria_count(item) >= 3:
            return 3
        return 2

    def _mainland_fit(self, item: IntelligenceItem) -> str:
        if self._mainland_fit_bool(item):
            return "适合先做低成本验证，但不能照搬海外平台规则。"
        return "不适合直接照搬，只能作为趋势观察或迁移参考。"

    def _mainland_fit_bool(self, item: IntelligenceItem) -> bool:
        return not self._depends_on_overseas_restriction(item) and not self._is_high_capital(item)

    def _fit_me(self, item: IntelligenceItem) -> str:
        text = self._item_text(item)
        if any(word in text for word in ["ai", "自动化", "电商", "淘宝", "内容", "creator", "video", "saas"]):
            return "适合你作为 AI、自动化、电商或内容变现方向的观察和小样验证。"
        return "可作为趋势观察，暂不作为优先行动方向。"

    def _seven_day_verifiable(self, item: IntelligenceItem) -> bool:
        return self._has_executable_first_step(item) and self._startup_cost(item) in {"低", "中"}

    def _has_clear_service_object(self, opportunity: dict) -> bool:
        value = opportunity.get("suitable_for")
        return self._valid(value) and "所有人" not in str(value)

    def _has_executable_first_step(self, item: IntelligenceItem) -> bool:
        action = self._first_action(item)
        return self._valid(action) and not self._is_vague_action(action)

    def _can_migrate_to_china(self, item: IntelligenceItem) -> bool:
        return self._domestic_mapping(item)["platforms"] != FALLBACK

    def _depends_on_overseas_restriction(self, item: IntelligenceItem) -> bool:
        text = self._item_text(item).lower()
        restricted_words = ["yc", "y combinator", "us only", "美国账号", "海外账号", "stripe", "openai credits"]
        return any(word in text for word in restricted_words)

    def _is_high_capital(self, item: IntelligenceItem) -> bool:
        text = self._item_text(item)
        return any(word.lower() in text.lower() for word in HIGH_CAPITAL_KEYWORDS)

    def _is_overseas(self, item: IntelligenceItem) -> bool:
        domain = urlparse(item.url or "").netloc.lower()
        if domain.endswith(".cn") or "gov.cn" in domain:
            return False
        if re.search(r"[\u4e00-\u9fff]", item.title or ""):
            return False
        return True

    def _keyword(self, item: IntelligenceItem) -> str:
        title = re.sub(r"https?://\S+", "", item.title or "").strip()
        words = re.findall(r"[\u4e00-\u9fff]{2,}|[A-Za-z][A-Za-z0-9+-]{2,}", title)
        if not words:
            return "AI 自动化 电商提效"
        return " ".join(words[:4])

    def _risk_title(self, item: IntelligenceItem) -> str:
        return self._text(self._opportunity_name(item), item.title)

    def _item_text(self, item: IntelligenceItem) -> str:
        analysis = item.analysis
        return " ".join(
            [
                str(item.title or ""),
                str(item.summary or ""),
                str(item.content or ""),
                str(item.source or ""),
                str(item.category or ""),
                str(analysis),
            ]
        )

    def _text(self, value, fallback: str | None = None) -> str:
        fallback = fallback or FALLBACK
        if isinstance(value, datetime):
            return value.strftime("%Y-%m-%d %H:%M")
        if not self._valid(value):
            return fallback
        text = str(value).strip()
        return text if self._valid(text) else fallback

    def _valid(self, value) -> bool:
        if value is None:
            return False
        text = str(value).strip()
        if not text:
            return False
        return text not in {"无", "/", "\\", "-", "N/A", "n/a", "None", "none", "暂无", "无。", "/。"}

    def _dict(self, value) -> dict:
        return value if isinstance(value, dict) else {}

    def _is_vague_action(self, value: str) -> bool:
        stripped = value.strip()
        vague = {"关注", "尝试", "准备", "了解", "持续关注", "进一步了解", "观察"}
        return stripped in vague or len(stripped) < 12

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

    def _validate_report_structure(self, report: str) -> None:
        positions = []
        for heading in SECTION_HEADINGS:
            count = report.count(heading)
            if count != 1:
                raise ValueError(f"Report structure invalid: {heading} appears {count} times")
            positions.append(report.index(heading))
        if positions != sorted(positions):
            raise ValueError("Report structure invalid: section order is wrong")

        section_one_start = report.index("## 一、今日最值得关注的 3-5 条变化")
        section_two_start = report.index("## 二、今日赚钱机会雷达")
        item_area = report[section_one_start:section_two_start]
        item_starts = [match.start() for match in re.finditer(r"^### \d+\. ", item_area, re.M)]
        for index, start in enumerate(item_starts):
            end = item_starts[index + 1] if index + 1 < len(item_starts) else len(item_area)
            block = item_area[start:end]
            sub_positions = []
            for subheading in ITEM_SUBHEADINGS:
                count = block.count(subheading)
                if count != 1:
                    raise ValueError(
                        f"Report structure invalid: item {index + 1} has {count} occurrences of {subheading}"
                    )
                sub_positions.append(block.index(subheading))
            if sub_positions != sorted(sub_positions):
                raise ValueError(f"Report structure invalid: item {index + 1} subheading order is wrong")

        forbidden_inside_item = [
            "## 二、今日赚钱机会雷达",
            "## 三、今日认知升级",
            "## 四、今日反割韭菜提醒",
            "## 五、今日行动建议",
        ]
        for heading in forbidden_inside_item:
            if heading in item_area:
                raise ValueError(f"Report structure invalid: {heading} appears inside item area")

        bad_values = [": 无", "：无", ": /", "：/", "： \n", ": \n"]
        for value in bad_values:
            if value in report:
                raise ValueError(f"Report structure invalid: empty marker found {value!r}")
