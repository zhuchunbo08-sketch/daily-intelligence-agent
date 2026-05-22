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
    "## 一、今日最值得关注的 3 条变化",
    "## 二、今日赚钱机会雷达",
    "## 三、全网高频痛点与变现机会",
    "## 四、今日认知升级",
    "## 五、今日反割韭菜提醒",
    "## 六、今日行动建议",
]

LOW_VALUE_NEWS_KEYWORDS = [
    "访问",
    "会见",
    "会谈",
    "出席会议",
    "外交",
    "致辞",
    "讲话",
    "友好交流",
    "领导人",
    "元首",
    "部长会见",
    "delegation",
    "visited",
    "met with",
    "summit",
]
BUSINESS_RELEVANCE_KEYWORDS = [
    "AI",
    "人工智能",
    "自动化",
    "电商",
    "淘宝",
    "拼多多",
    "抖音",
    "小红书",
    "视频号",
    "SaaS",
    "平台",
    "流量",
    "工具",
    "商业",
    "创业",
    "就业",
    "消费",
    "出海",
    "跨境",
    "规则",
    "监管",
    "补贴",
    "税",
    "新政",
    "收入",
    "变现",
    "creator",
    "ecommerce",
    "automation",
    "small business",
    "startup",
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
    "molecule",
    "biotech",
    "fragrance",
    "raises",
    "raised",
    "fund",
    "funding",
    "$",
    "million",
    "billion",
]
NON_ORDINARY_OPPORTUNITY_KEYWORDS = [
    "law enforcement",
    "shuts down",
    "shutdown",
    "ransomware",
    "vpn service",
    "data breach",
    "lawsuit",
    "sanction",
    "criminal",
    "police",
    "trump",
    "executive order",
    "therapy",
    "mental health",
    "medical",
    "clinical",
    "patient",
    "心理治疗",
    "医疗",
    "临床",
    "患者",
    "执法",
    "关停",
    "勒索软件",
    "数据泄露",
    "诉讼",
]
ORDINARY_RELEVANCE_KEYWORDS = [
    "ai",
    "artificial intelligence",
    "automation",
    "ecommerce",
    "creator",
    "content",
    "search",
    "spotify",
    "remix",
    "cover",
    "kids",
    "screen time",
    "小红书",
    "抖音",
    "淘宝",
    "电商",
    "内容",
    "创作者",
    "自动化",
    "工具",
    "育儿",
    "孩子",
]
EN_TITLE_PATTERNS = [
    (["spotify", "ai", "cover"], "音乐平台开放 AI 翻唱和混音：创作者版权变现规则在变化"),
    (["universal music", "ai"], "音乐版权方开始接纳 AI 二创：内容创作者要重看授权边界"),
    (["spotify", "q&a"], "音频平台加入 AI 问答和简报：内容资料再加工服务值得观察"),
    (["spotify", "briefing"], "音频平台加入 AI 简报生成：知识内容自动化有新场景"),
    (["spotify", "elevenlabs"], "AI 有声书制作门槛下降：音频内容服务出现低成本切口"),
    (["audiobook", "elevenlabs"], "AI 有声书制作门槛下降：音频内容服务出现低成本切口"),
    (["executive order", "ai"], "美国 AI 行政令变化：政策信号只适合观察，不直接当机会"),
    (["kids", "screen time"], "儿童屏幕时间产品转向健康导向：育儿内容和工具有新切口"),
    (["search engines", "google"], "搜索入口正在重新分化：AI 搜索和垂直搜索值得重新观察"),
    (["fragrance"], "气味研发创业公司融资：香氛行业出现技术化改造信号"),
    (["vpn", "ransomware"], "执法关停高风险 VPN 服务：安全事件不宜包装成普通人机会"),
    (["capital", "fund"], "资本正在流向新赛道：普通人只适合做趋势观察"),
]
PAIN_KEYWORDS = [
    "怎么",
    "怎么办",
    "不会",
    "太难",
    "痛点",
    "问题",
    "差评",
    "评论",
    "效率",
    "重复",
    "客服",
    "详情页",
    "主图",
    "选题",
    "播放量",
    "转化",
    "收纳",
    "清洁",
    "育儿",
    "孩子",
    "老人",
    "宠物",
    "做饭",
    "prompt",
    "AI工具",
    "how to",
    "problem",
    "struggling",
    "pain point",
]
FORBIDDEN_ACTIONS = {"关注", "了解", "尝试", "准备", "观察", "持续关注", "进一步了解"}


class ReportBuilder:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.last_filtered_news: list[dict] = []
        self.last_filtered_pain_points: list[dict] = []

    async def build(
        self,
        report_date: str,
        window_start: datetime,
        window_end: datetime,
        items: list[IntelligenceItem],
        observed_items: list[IntelligenceItem],
    ) -> str:
        report = self._build_template(report_date, window_start, window_end, items, observed_items)
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
        self.last_filtered_news = []
        self.last_filtered_pain_points = []
        change_items = self._change_items(observed_items)
        radar_items = self._radar_items(observed_items)
        pain_items = self._pain_items(observed_items)
        cognition_items = self._cognition_items(change_items + radar_items + pain_items)
        risk_items = self._risk_items(observed_items)

        lines = [
            "# 每日破圈赚钱情报",
            "",
            f"日期：{report_date}",
            f"覆盖时间：{window_start:%Y-%m-%d %H:%M} - {window_end:%Y-%m-%d %H:%M}",
            "",
            "## 先说结论",
            f"- 今天最重要的趋势：{self._headline(change_items, '没有发现足够重要且可落地的趋势变化')}",
            f"- 今天最值得看的机会：{self._headline(radar_items, '没有发现普通人 7 天内能验证的明确机会')}",
            f"- 今天最值得关注的痛点：{self._pain_headline(pain_items)}",
            f"- 今天最值得避开的坑：{self._risk_headline(risk_items)}",
            f"- 今天我建议你做的一件事：{self._one_action(pain_items, radar_items, change_items)}",
            "",
            "## 一、今日最值得关注的 3 条变化",
            "",
        ]

        if change_items:
            for index, item in enumerate(change_items[:3], start=1):
                lines.extend(self._render_change_item(index, item))
        else:
            lines.append("今天没有通过商业相关性、可落地性和风险过滤的重点变化。")

        lines.extend(["", "## 二、今日赚钱机会雷达", ""])
        lines.extend(self._render_radar(radar_items))

        lines.extend(["", "## 三、全网高频痛点与变现机会", ""])
        lines.extend(self._render_pain_points(pain_items))

        lines.extend(["", "## 四、今日认知升级", ""])
        lines.extend(self._render_cognition(cognition_items))

        lines.extend(["", "## 五、今日反割韭菜提醒", ""])
        lines.extend(self._render_risks(risk_items))

        lines.extend(["", "## 六、今日行动建议", ""])
        lines.extend(self._render_actions(pain_items, radar_items, change_items))

        return self._sanitize("\n".join(lines).strip() + "\n")

    def _render_change_item(self, index: int, item: IntelligenceItem) -> list[str]:
        analysis = item.analysis
        return [
            f"### {index}. {self._title_zh(item)}",
            "",
            f"- 发生了什么：{self._sentence(analysis.get('what_happened'), item.summary or item.title)}",
            f"- 为什么重要：{self._sentence(analysis.get('why_important'), '它可能改变成本、效率、流量或平台规则。')}",
            f"- 和我有什么关系：{self._sentence(self._relationship_line(item), '可作为 AI、自动化、电商或内容变现方向的观察信号。')}",
            f"- 中国落地价值：{self._sentence(self._domestic_value(item), '需要先做国内平台迁移和低成本验证。')}",
            f"- 机会判断：{self._radar_status(item)}",
            f"- 风险提醒：{self._sentence(self._risk(item).get('packaging_risk'), '不要把趋势直接当成确定收益项目。')}",
            f"- 来源：{item.url}",
            "",
            "#### 我的理解",
            self._understanding(item),
            "",
            "#### 历史类比 / 发达国家参照",
            f"- 可比案例：{self._historical_field(item, 'comparable_case')}",
            f"- 发生时期：{self._historical_field(item, 'period')}",
            f"- 当时带来的机会：{self._historical_field(item, 'opportunities')}",
            f"- 中国现在是否类似：{self._historical_field(item, 'china_stage')}",
            f"- 对普通人的启发：{self._historical_field(item, 'insight')}",
            "",
            "#### 认知破界",
            f"- 大多数人的误解：{self._breakthrough_field(item, 'common_misread')}",
            f"- 高认知视角：{self._breakthrough_field(item, 'high_level_view')}",
            f"- 我应该更新的判断：{self._breakthrough_field(item, 'new_judgment')}",
            f"- 3 年后可能变成：{self._breakthrough_field(item, 'three_year_view')}",
            "",
            "#### 可执行动作",
            self._first_action(item),
            "",
        ]

    def _render_radar(self, items: list[IntelligenceItem]) -> list[str]:
        if not items:
            return ["今天没有符合“普通人或小团队 7 天内可验证、低/中成本、风险不高”的新闻机会。"]
        lines: list[str] = []
        for item in items[:5]:
            lines.extend(
                [
                    f"- 机会名称：{self._opportunity_name(item)}",
                    f"  来源：{item.source}",
                    f"  状态：{self._radar_status(item)}",
                    f"  适合谁：{self._text(self._opportunity(item).get('suitable_for'), '有相关经验、能做低成本验证的小团队')}",
                    f"  第一行动：{self._first_action(item)}",
                    f"  3 天内动作：{self._three_day_action(item)}",
                    f"  风险等级：{self._risk_level(item)}",
                    f"  推荐指数：{self._recommendation_index(item)}",
                    f"  中国落地价值：{self._domestic_value(item)}",
                ]
            )
        return lines

    def _render_pain_points(self, items: list[IntelligenceItem]) -> list[str]:
        if not items:
            return ["今天没有筛出足够具体、可变现、普通人 7 天内能验证的高频痛点。"]
        lines: list[str] = []
        for index, item in enumerate(items[:3], start=1):
            pain = self._pain(item)
            lines.extend(
                [
                    f"### 痛点 {index}：{self._pain_title(item)}",
                    "",
                    f"- 高频问题：{self._text(pain.get('question'), self._title_zh(item))}",
                    f"- 来源平台：{item.source}",
                    f"- 目标人群：{self._audience(item)}",
                    f"- 背后真实需求：{self._text(pain.get('real_need'), self._pain_need(item))}",
                    f"- 为什么这是个需求：{self._text(pain.get('why_need'), '它反复出现在搜索、评论或社区讨论中，并且对应省时间、省钱、省心或提高收入。')}",
                    f"- 现有解决方案有什么不足：{self._text(pain.get('current_gap'), '现有方案要么太泛，要么不够场景化，普通人不知道怎么直接落地。')}",
                    "- 可以变成什么：",
                    f"  - 商品：{self._text(pain.get('product'), self._pain_product(item))}",
                    f"  - 服务：{self._text(pain.get('service'), self._pain_service(item))}",
                    f"  - 内容：{self._text(pain.get('content'), self._pain_content(item))}",
                    f"  - 工具：{self._text(pain.get('tool'), self._pain_tool(item))}",
                    f"  - AI 自动化：{self._text(pain.get('ai_automation'), self._pain_ai(item))}",
                    f"- 适合在哪个平台验证：{self._pain_platforms(item)}",
                    f"- 发达国家/成熟市场是否已有类似产品或服务：{self._pain_mature_market(item)}",
                    f"- 认知破界：{self._pain_breakthrough(item)}",
                    f"- 7 天内验证动作：{self._pain_action(item)}",
                    f"- 启动成本：{self._startup_cost(item)}",
                    f"- 难度：{self._difficulty(item)}",
                    f"- 风险：{self._risk_level(item)}",
                    f"- 推荐指数：{self._recommendation_index(item)}",
                    f"- 是否适合我：{self._fit_me(item)}",
                    "",
                ]
            )
        return lines

    def _render_cognition(self, items: list[IntelligenceItem]) -> list[str]:
        if not items:
            return ["- 真正值得看的不是热点本身，而是它能否变成可验证的国内场景、明确人群和低成本动作。"]
        lines: list[str] = []
        seen: set[str] = set()
        for item in items:
            cognition = self._cognition(item)
            line = self._sentence(
                cognition.get("new"),
                "先判断是否能迁移到国内场景，再判断普通人能否低成本验证。",
            )
            if line in seen:
                continue
            seen.add(line)
            lines.append(f"- {line}")
            if len(lines) >= 3:
                break
        return lines

    def _render_risks(self, items: list[IntelligenceItem]) -> list[str]:
        if not items:
            return [
                "- 风险概念：高收益副业包装\n  判断方法：凡是承诺固定收益、强调无需能力、催促先付费的项目，先要求真实交付案例和退款规则。"
            ]
        lines: list[str] = []
        for item in items[:3]:
            risk = self._risk(item)
            lines.append(
                f"- 风险概念：{self._risk_title(item)}\n"
                f"  判断方法：{self._sentence(risk.get('traps'), '看来源、看交付、看真实客户，避免先交大额费用。')}"
            )
        return lines

    def _render_actions(
        self,
        pain_items: list[IntelligenceItem],
        radar_items: list[IntelligenceItem],
        change_items: list[IntelligenceItem],
    ) -> list[str]:
        actions: list[str] = []
        for item in pain_items[:2]:
            actions.append(f"- {self._pain_action(item)}")
        if radar_items:
            actions.append(f"- {self._first_action(radar_items[0])}")
        elif change_items:
            keyword = self._keyword(change_items[0])
            actions.append(
                f"- 今天在小红书、淘宝、抖音分别搜索“{keyword}”，记录 20 条笔记/商品/视频的价格、评论痛点和成交形式。"
            )
        if not actions:
            actions.append("- 今天用 30 分钟新增 3 个痛点类数据源，并记录每个来源最近 10 个问题标题。")
        return actions[:3]

    def _change_items(self, items: list[IntelligenceItem]) -> list[IntelligenceItem]:
        candidates: list[IntelligenceItem] = []
        for item in sorted(items, key=lambda x: x.final_score, reverse=True):
            reason = self._change_filter_reason(item)
            if reason:
                self.last_filtered_news.append({"title": item.title, "reason": reason})
                continue
            candidates.append(item)
        return candidates[:3]

    def _radar_items(self, items: list[IntelligenceItem]) -> list[IntelligenceItem]:
        selected: list[IntelligenceItem] = []
        for item in sorted(items, key=lambda x: x.final_score, reverse=True):
            if self._is_pain_item(item):
                continue
            if self._change_filter_reason(item):
                continue
            if self._is_high_capital(item) or self._is_non_ordinary_opportunity(item) or item.risk_score >= 7:
                continue
            if self._radar_criteria_count(item) < 5:
                continue
            selected.append(item)
        return selected[:5]

    def _pain_items(self, items: list[IntelligenceItem]) -> list[IntelligenceItem]:
        selected: list[IntelligenceItem] = []
        for item in sorted(items, key=lambda x: x.final_score, reverse=True):
            if not self._is_pain_item(item):
                continue
            reason = self._pain_filter_reason(item)
            if reason:
                self.last_filtered_pain_points.append({"title": item.title, "reason": reason})
                continue
            selected.append(item)
        return selected[:3]

    def _change_filter_reason(self, item: IntelligenceItem) -> str | None:
        text = self._item_text(item).lower()
        if self._is_pain_item(item):
            return "痛点类内容进入痛点模块，不进入新闻变化模块"
        if any(keyword.lower() in text for keyword in LOW_VALUE_NEWS_KEYWORDS) and not self._has_business_relevance(item):
            return "政治访问、会见、外交辞令或普通会议，且没有明确商业影响"
        if self._is_non_ordinary_opportunity(item):
            return "执法、安全、诉讼或事故类资讯，不适合作为普通人赚钱机会"
        if self._is_high_capital(item) and not self._has_ordinary_relevance(item):
            return "融资、硬件研发、专业科研或资本密集项目，只适合趋势观察"
        if not self._has_business_relevance(item):
            return "缺少商业、平台、技术、政策红利或普通人可验证机会"
        if item.has_cutting_risk or item.risk_score >= 8:
            return "风险过高"
        return None

    def _pain_filter_reason(self, item: IntelligenceItem) -> str | None:
        text = self._filter_text(item).lower()
        if any(word in text for word in ["博彩", "传销", "刷单", "灰产", "彩票", "casino"]):
            return "违法灰产或高风险变现方向"
        if not any(keyword.lower() in text for keyword in PAIN_KEYWORDS):
            return "问题不够具体，缺少明确痛点表达"
        if not self._has_business_relevance(item) and item.money_score < 4:
            return "暂未看到明确付费可能"
        if self._startup_cost(item) == "高":
            return "启动成本高，不适合普通人 7 天验证"
        return None

    def _cognition_items(self, items: list[IntelligenceItem]) -> list[IntelligenceItem]:
        return [item for item in items if item.has_cognition_value or item.cognition_score >= 4][:3]

    def _risk_items(self, items: list[IntelligenceItem]) -> list[IntelligenceItem]:
        return sorted(
            [item for item in items if item.has_cutting_risk or item.risk_score >= 6],
            key=lambda x: x.risk_score,
            reverse=True,
        )[:3]

    def _is_pain_item(self, item: IntelligenceItem) -> bool:
        source_text = f"{item.source or ''} {item.source_type or ''} {item.category or ''}".lower()
        return item.category == "痛点机会" or "痛点" in source_text or item.source_type == "pain_keywords"

    def _has_business_relevance(self, item: IntelligenceItem) -> bool:
        text = self._filter_text(item).lower()
        return self._contains_any_keyword(text, BUSINESS_RELEVANCE_KEYWORDS)

    def _has_ordinary_relevance(self, item: IntelligenceItem) -> bool:
        text = self._filter_text(item).lower()
        return self._contains_any_keyword(text, ORDINARY_RELEVANCE_KEYWORDS)

    def _radar_criteria_count(self, item: IntelligenceItem) -> int:
        criteria = [
            self._startup_cost(item) in {"低", "中"},
            self._risk_level(item) != "高",
            self._has_executable_first_step(item),
            self._can_migrate_to_china(item),
            self._has_clear_service_object(item),
            not self._depends_on_overseas_restriction(item),
            not self._is_high_capital(item),
            not self._is_non_ordinary_opportunity(item),
            self._has_ordinary_relevance(item),
        ]
        return sum(1 for value in criteria if value)

    def _headline(self, items: list[IntelligenceItem], fallback: str) -> str:
        if not items:
            return fallback
        return self._title_zh(items[0])

    def _pain_headline(self, items: list[IntelligenceItem]) -> str:
        if not items:
            return "没有筛出足够具体、可变现的高频痛点"
        return self._pain_title(items[0])

    def _risk_headline(self, items: list[IntelligenceItem]) -> str:
        if not items:
            return "高收益副业包装、刷单、拉人头和不透明代运营"
        return self._risk_title(items[0])

    def _one_action(
        self,
        pain_items: list[IntelligenceItem],
        radar_items: list[IntelligenceItem],
        change_items: list[IntelligenceItem],
    ) -> str:
        if pain_items:
            return self._pain_action(pain_items[0])
        if radar_items:
            return self._first_action(radar_items[0])
        if change_items:
            keyword = self._keyword(change_items[0])
            return f"今天在小红书和淘宝搜索“{keyword}”，记录 20 条评论痛点和可付费场景。"
        return "今天新增 3 个痛点类数据源，并记录 10 个真实问题标题。"

    def _understanding(self, item: IntelligenceItem) -> str:
        title = self._title_zh(item)
        trend = self._sentence(self._cognition(item).get("new"), "背后说明需求正在从泛泛关注转向可落地的工具、服务或内容。")
        domestic = self._domestic_value(item)
        avoid = "不要直接照搬海外平台、资本密集型项目或没有明确人群的概念。"
        return f"表面上看，这是“{title}”。{trend} 它现在出现，通常和成本下降、效率提升、平台规则变化或用户需求变得更具体有关。普通人真正能借鉴的是先找国内相似场景，再用低成本小样验证需求。{domestic} {avoid}"

    def _title_zh(self, item: IntelligenceItem) -> str:
        title = self._text(item.title)
        if re.search(r"[\u4e00-\u9fff]", title):
            return title[:80]
        summary = self._text(item.summary, "")
        if re.search(r"[\u4e00-\u9fff]", summary):
            return summary[:80]
        return self._english_title_to_chinese(title)

    def _english_title_to_chinese(self, title: str) -> str:
        lowered = title.lower()
        for keywords, translated in EN_TITLE_PATTERNS:
            if all(keyword in lowered for keyword in keywords):
                return translated
        words = re.findall(r"[A-Za-z][A-Za-z0-9+-]{2,}", title)
        if words:
            topic = " ".join(words[:3])
            return f"海外案例：{topic} 相关变化，先看国内迁移价值"
        return "海外案例：出现新的平台、工具或商业变化，先做趋势观察"

    def _pain_title(self, item: IntelligenceItem) -> str:
        pain = self._pain(item)
        value = pain.get("question") or pain.get("title") or item.summary or item.title
        return self._sentence(value, item.title)[:60]

    def _pain(self, item: IntelligenceItem) -> dict:
        value = item.analysis.get("pain_point")
        return value if isinstance(value, dict) else {}

    def _opportunity(self, item: IntelligenceItem) -> dict:
        value = item.analysis.get("opportunity")
        return value if isinstance(value, dict) else {}

    def _cognition(self, item: IntelligenceItem) -> dict:
        value = item.analysis.get("cognition")
        return value if isinstance(value, dict) else {}

    def _risk(self, item: IntelligenceItem) -> dict:
        value = item.analysis.get("risk")
        return value if isinstance(value, dict) else {}

    def _historical(self, item: IntelligenceItem) -> dict:
        value = item.analysis.get("historical_reference")
        return value if isinstance(value, dict) else {}

    def _breakthrough(self, item: IntelligenceItem) -> dict:
        value = item.analysis.get("cognitive_breakthrough")
        return value if isinstance(value, dict) else {}

    def _relationship_line(self, item: IntelligenceItem) -> str:
        rel = item.analysis.get("relationship")
        if isinstance(rel, dict):
            return rel.get("ai_efficiency") or rel.get("ecommerce") or rel.get("creators") or rel.get("ordinary_people") or FALLBACK
        return FALLBACK

    def _domestic_value(self, item: IntelligenceItem) -> str:
        mapping = item.analysis.get("domestic_mapping")
        if isinstance(mapping, dict) and self._valid(mapping.get("personal_value")):
            return self._text(mapping.get("personal_value"))
        platforms = self._platforms(item)
        if self._is_overseas(item):
            return f"不能照搬海外平台，但可迁移到{platforms}做需求验证。"
        return f"可在{platforms}做低成本验证。"

    def _platforms(self, item: IntelligenceItem) -> str:
        text = self._item_text(item).lower()
        platforms: list[str] = []
        if any(word in text for word in ["孩子", "育儿", "收纳", "宠物", "清洁", "做饭", "穿搭"]):
            platforms.extend(["小红书", "淘宝", "拼多多", "抖音"])
        if any(word in text for word in ["客服", "详情页", "主图", "选品", "电商", "商家", "客户", "ecommerce"]):
            platforms.extend(["淘宝", "拼多多", "抖音", "1688"])
        if any(word in text for word in ["内容", "选题", "播放量", "剪辑", "creator", "video"]):
            platforms.extend(["小红书", "抖音", "视频号", "公众号"])
        if any(word in text for word in ["ai", "prompt", "自动化", "办公", "效率", "workflow"]):
            platforms.extend(["企业服务", "公众号", "知识付费", "小红书"])
        if not platforms:
            platforms.extend(["小红书", "抖音", "淘宝", "公众号"])
        return " / ".join(dict.fromkeys(platforms))

    def _opportunity_name(self, item: IntelligenceItem) -> str:
        raw = self._opportunity(item).get("name")
        if self._valid(raw) and re.search(r"[\u4e00-\u9fff]", str(raw)):
            return self._sentence(raw, self._title_zh(item))[:60]
        return self._title_zh(item)[:60]

    def _radar_status(self, item: IntelligenceItem) -> str:
        if self._is_high_capital(item) or item.risk_score >= 8:
            return "不建议碰"
        if self._radar_criteria_count(item) >= 4:
            return "可测试"
        return "观察中"

    def _recommendation_index(self, item: IntelligenceItem) -> int:
        if self._radar_status(item) == "不建议碰":
            return 2
        raw = self._opportunity(item).get("recommendation_index")
        match = re.search(r"\d+", str(raw or ""))
        score = int(match.group(0)) if match else 3
        if self._radar_status(item) == "观察中":
            return max(1, min(3, score))
        return max(3, min(5, score))

    def _startup_cost(self, item: IntelligenceItem) -> str:
        text = self._item_text(item).lower()
        raw = str(self._opportunity(item).get("startup_cost") or "")
        if self._is_high_capital(item) or any(word in raw for word in ["高", "重", "大"]):
            return "高"
        if "中" in raw:
            return "中"
        return "低"

    def _risk_level(self, item: IntelligenceItem) -> str:
        raw = str(self._opportunity(item).get("risk_level") or "")
        if item.risk_score >= 7 or "高" in raw:
            return "高"
        if item.risk_score >= 4 or "中" in raw:
            return "中"
        return "低"

    def _first_action(self, item: IntelligenceItem) -> str:
        raw = self._opportunity(item).get("first_action") or self._opportunity(item).get("first_step")
        if self._valid_action(raw) and "相关关键词" not in str(raw) and "保存来源链接" not in str(raw):
            return self._text(raw)
        keyword = self._keyword(item)
        return f"今天在小红书、淘宝、抖音分别搜索“{keyword}”，记录 20 条笔记/商品/视频的价格、评论痛点和成交形式。"

    def _three_day_action(self, item: IntelligenceItem) -> str:
        raw = self._opportunity(item).get("three_day_action")
        if self._valid_action(raw) and "相关关键词" not in str(raw):
            return self._text(raw)
        keyword = self._keyword(item)
        return f"第 1 天整理 20 条需求，第 2 天做 1 个一页纸小样，第 3 天找 3 个目标用户验证“{keyword}”是否愿意付费。"

    def _pain_action(self, item: IntelligenceItem) -> str:
        raw = self._pain(item).get("seven_day_action")
        if self._valid_action(raw) and "相关关键词" not in str(raw):
            return self._text(raw)
        keyword = self._keyword(item)
        return f"今天在小红书、淘宝、拼多多搜索“{keyword}”，记录前 20 个结果的价格、差评痛点和卖点，判断能否做一个低价小样。"

    def _pain_need(self, item: IntelligenceItem) -> str:
        return f"目标人群想更省时间、更省心或更低成本地解决“{self._keyword(item)}”相关问题。"

    def _pain_product(self, item: IntelligenceItem) -> str:
        return f"围绕“{self._keyword(item)}”做低价小商品、资料包或模板。"

    def _pain_service(self, item: IntelligenceItem) -> str:
        return f"提供诊断、整理、代设置、陪跑或一对一解决服务。"

    def _pain_content(self, item: IntelligenceItem) -> str:
        return f"做小红书/抖音系列内容：真实问题、对比方案、避坑清单。"

    def _pain_tool(self, item: IntelligenceItem) -> str:
        return f"做表格、清单、模板、计算器或流程化工具。"

    def _pain_ai(self, item: IntelligenceItem) -> str:
        return f"用 AI 做问答助手、自动回复、文案生成、资料整理或流程自动化。"

    def _pain_platforms(self, item: IntelligenceItem) -> str:
        return self._platforms(item)

    def _historical_field(self, item: IntelligenceItem, key: str) -> str:
        historical = self._historical(item)
        if self._valid(historical.get(key)) and not self._is_generic_reference(historical.get(key)):
            return self._sentence(historical.get(key), FALLBACK)
        fallback = self._historical_fallback(item)
        return fallback[key]

    def _historical_fallback(self, item: IntelligenceItem) -> dict[str, str]:
        text = self._item_text(item).lower()
        title = self._title_zh(item)
        if any(word in text for word in ["audiobook", "podcast", "spotify", "音频", "有声书", "播客"]):
            return {
                "comparable_case": "欧美有声书、播客和订阅内容市场曾把长内容拆成音频、短视频、课程和社群。",
                "period": "大致在 2010 年代后期到 2020 年代初逐步成熟。",
                "opportunities": "当时出现了播客制作、音频剪辑、内容再分发、会员订阅和创作者赞助服务。",
                "china_stage": "中国内容平台也在把图文、直播、短视频和音频重新组合，但付费习惯仍需验证。",
                "insight": "普通人的机会不是复制 Spotify，而是帮已有内容资产做音频化和多平台再加工。",
            }
        if any(word in text for word in ["creator", "remix", "cover", "版权", "二创", "翻唱", "混音"]):
            return {
                "comparable_case": "美国 creator economy 里，Patreon、Substack、YouTube 等平台把创作、授权和粉丝付费逐步工具化。",
                "period": "大致在 2010 年代中后期开始加速。",
                "opportunities": "后来出现了创作者经纪、版权清理、素材授权、粉丝会员和内容再加工服务。",
                "china_stage": "中国也在经历内容从流量分发走向版权、IP 和多形态变现的阶段。",
                "insight": "提前看清规则边界，比盲目追热点更重要；能合规处理素材的人会更有价值。",
            }
        if any(word in text for word in ["search", "google", "搜索"]):
            return {
                "comparable_case": "美国互联网经历过从门户到 Google，再到垂直搜索和 AI 搜索的入口迁移。",
                "period": "门户到搜索发生在 2000 年前后，垂直搜索和 AI 搜索在 2020 年代继续分化。",
                "opportunities": "每次入口变化都会催生 SEO、内容站、垂直数据库、导购和问答服务。",
                "china_stage": "中国也在从通用搜索转向小红书、抖音、微信、淘宝站内搜索和 AI 问答并存。",
                "insight": "普通人要观察用户开始去哪里提问，而不是只盯一个平台的流量规则。",
            }
        if any(word in text for word in ["kids", "screen time", "孩子", "育儿", "儿童"]):
            return {
                "comparable_case": "欧美和日本较早出现儿童内容分级、家长控制、家庭任务卡和可打印育儿工具。",
                "period": "2010 年代移动互联网普及后，儿童屏幕管理和家庭教育工具快速增加。",
                "opportunities": "后来出现了儿童内容 App、家长控制工具、行为奖励表、亲子任务卡和低价资料包。",
                "china_stage": "中国家庭也在从焦虑式买课转向更低压力、可执行的家庭工具。",
                "insight": "机会不是制造焦虑，而是把育儿建议变成今晚就能用的小工具。",
            }
        if any(word in text for word in ["收纳", "衣架", "宠物", "做饭", "清洁", "小户型"]):
            return {
                "comparable_case": "日本收纳经济和欧美家居小物市场很早把大品类按人群、尺寸和场景切细。",
                "period": "日本在长期小户型和消费精细化阶段逐步成熟。",
                "opportunities": "催生了儿童尺寸、旅行尺寸、厨房细分工具、宠物清洁和空间管理类小商品。",
                "china_stage": "中国小户型、育儿、宠物和懒人家务场景正在出现类似细分需求。",
                "insight": "小商品机会常常不是发明新品，而是把成人用品按儿童、老人、宠物、小户型重新切细。",
            }
        if any(word in text for word in ["saas", "automation", "workflow", "自动化", "客服", "详情页", "ai工具", "ai 工具"]):
            return {
                "comparable_case": "美国中小企业 SaaS 曾把客服、营销、表单、协作和自动化逐步做成订阅工具。",
                "period": "大致从 2010 年代云服务普及后加速。",
                "opportunities": "出现了垂直 SaaS、自动化顾问、模板市场、代配置服务和工作流外包。",
                "china_stage": "中国很多小商家还未系统购买 SaaS，但愿意为具体问题的代配置和低价工具付费。",
                "insight": "普通人不一定要做软件平台，先做一套能交付结果的模板和代配置服务更现实。",
            }
        return {
            "comparable_case": "暂无明确历史类比，但可以从产业逻辑上理解为一次成本、效率或分发方式的变化。",
            "period": "时间阶段不明确，先不要硬套发达国家案例。",
            "opportunities": "只有当它能降低成本、扩大分发或形成新服务对象时，才可能出现可验证机会。",
            "china_stage": "中国是否类似还需要看平台规则、用户付费和合规边界。",
            "insight": f"先把“{title}”当作趋势信号观察，再用国内真实需求验证，而不是直接照搬。",
        }

    def _breakthrough_field(self, item: IntelligenceItem, key: str) -> str:
        breakthrough = self._breakthrough(item)
        if self._valid(breakthrough.get(key)):
            return self._sentence(breakthrough.get(key), FALLBACK)
        fallback = self._breakthrough_fallback(item)
        return fallback[key]

    def _breakthrough_fallback(self, item: IntelligenceItem) -> dict[str, str]:
        text = self._item_text(item).lower()
        title = self._title_zh(item)
        if any(word in text for word in ["audiobook", "podcast", "spotify", "音频", "有声书", "播客"]):
            return {
                "common_misread": "大多数人会把它看成某个平台的新功能。",
                "high_level_view": "更关键的是内容生产链条被压缩，文字、配音、剪辑和分发开始变成一个工作流。",
                "new_judgment": "我应该从“做内容”转向“帮别人把已有内容资产多次转化”。",
                "three_year_view": "3 年后，图文转音频、短视频、课程和私域产品可能会变成标准内容服务。",
            }
        if any(word in text for word in ["creator", "remix", "cover", "版权", "二创", "翻唱", "混音"]):
            return {
                "common_misread": "大多数人只看到 AI 二创更好玩。",
                "high_level_view": "高认知的人会先看授权、分账和合规工具，因为规则变化决定谁能长期赚钱。",
                "new_judgment": "我应该把素材合规、版权边界和再加工流程当成服务能力。",
                "three_year_view": "3 年后，AI 内容二创可能从野路子变成平台内的授权生意。",
            }
        if any(word in text for word in ["search", "google", "搜索"]):
            return {
                "common_misread": "大多数人会以为只是换一个搜索工具。",
                "high_level_view": "真正变化是用户提问入口分散，内容被发现的路径正在重写。",
                "new_judgment": "我应该研究用户在哪些平台搜索具体问题，而不是只研究传统 SEO。",
                "three_year_view": "3 年后，垂直内容库、问答资产和 AI 可读取资料可能成为新的流量基础设施。",
            }
        if any(word in text for word in ["kids", "screen time", "孩子", "育儿", "儿童"]):
            return {
                "common_misread": "大多数人会把它理解成又一个儿童内容产品。",
                "high_level_view": "更深层是家长需要低压力、可执行、能立刻降低家庭摩擦的工具。",
                "new_judgment": "我应该少做焦虑叙事，多做家长今晚能用的清单、卡片和流程。",
                "three_year_view": "3 年后，育儿内容可能更像工具包和陪伴服务，而不是单纯课程。",
            }
        if any(word in text for word in ["收纳", "衣架", "宠物", "做饭", "清洁", "小户型"]):
            return {
                "common_misread": "大多数人会觉得这是太小的生活问题。",
                "high_level_view": "高认知的人会看到人群、尺寸、场景被重新细分后，小商品也能形成稳定需求。",
                "new_judgment": "我应该从大品类里找儿童、老人、宠物、小户型等细分场景。",
                "three_year_view": "3 年后，更多普通用品会按细分人群重新设计和售卖。",
            }
        if any(word in text for word in ["saas", "automation", "workflow", "自动化", "客服", "详情页", "ai工具", "ai 工具"]):
            return {
                "common_misread": "大多数人会以为机会是开发一个完整软件。",
                "high_level_view": "更现实的切口是把一个具体工作流做成模板、代配置和轻服务。",
                "new_judgment": "我应该先卖结果和流程，再考虑产品化。",
                "three_year_view": "3 年后，小商家的 AI 自动化可能像现在的代运营一样常见。",
            }
        return {
            "common_misread": "大多数人会只看标题热度。",
            "high_level_view": "高认知的人会先判断它是否改变成本、效率、分发或信任结构。",
            "new_judgment": f"我应该把“{title}”拆成可验证的人群、场景和第一动作。",
            "three_year_view": "如果趋势持续，它可能变成某个行业的标准工作流，而不只是今天的新闻。",
        }

    def _pain_mature_market(self, item: IntelligenceItem) -> str:
        pain = self._pain(item)
        if self._valid(pain.get("mature_market_reference")) and not self._is_generic_reference(pain.get("mature_market_reference")):
            return self._sentence(pain.get("mature_market_reference"), FALLBACK)
        text = self._pain_signal_text(item).lower()
        if any(word in text for word in ["孩子", "育儿", "宝宝", "家长"]):
            return "欧美和日本家庭教育里常见 reward chart、behavior chart、chores chart、routine cards、printable parenting tools。"
        if any(word in text for word in ["衣架", "收纳", "小户型", "清洁", "厨房"]):
            return "日本和欧美家居收纳市场有大量儿童尺寸、旅行尺寸、分龄尺寸和小户型场景的小物。"
        if any(word in text for word in ["宠物"]):
            return "欧美和日本宠物市场已有宠物清洁、掉毛处理、出行收纳和训练工具等细分产品。"
        if any(word in text for word in ["ai工具", "ai 工具", "ai tool", "ai tools", "prompt", "自动化", "人工智能"]):
            return "海外 AI 工具正在从玩具变成工作流基础设施，围绕模板、自动化和行业落地出现服务市场。"
        if any(word in text for word in ["客服", "详情页", "主图", "淘宝", "商家", "电商"]):
            return "美国中小企业 SaaS 和电商服务市场已有客服自动化、页面优化、素材模板和代运营工具。"
        if any(word in text for word in ["小红书", "抖音", "播放量", "选题", "剪辑", "内容"]):
            return "美国 creator economy 已形成选题工具、剪辑服务、会员订阅、素材模板和创作者顾问服务。"
        return "暂无明确成熟市场参照，但可以先从人群、场景、频次和付费意愿判断是否值得验证。"

    def _pain_breakthrough(self, item: IntelligenceItem) -> str:
        pain = self._pain(item)
        if self._valid(pain.get("cognitive_breakthrough")) and not self._is_generic_reference(pain.get("cognitive_breakthrough")):
            return self._sentence(pain.get("cognitive_breakthrough"), FALLBACK)
        text = self._pain_signal_text(item).lower()
        if any(word in text for word in ["孩子", "育儿", "宝宝", "家长"]):
            return "很多人以为育儿机会只能做课程，其实更低门槛的是可打印、可执行、低价工具包；家长缺的往往不是大道理，而是今晚就能用的工具。"
        if any(word in text for word in ["衣架", "收纳", "小户型", "清洁", "厨房"]):
            return "小商品机会往往不是创造新需求，而是把一个大品类按人群、尺寸、空间和使用场景重新切细。"
        if any(word in text for word in ["ai工具", "ai 工具", "ai tool", "ai tools", "prompt", "自动化", "人工智能"]):
            return "AI 机会不在工具数量本身，而在把混乱工具变成某个行业可复用的工作流。"
        if any(word in text for word in ["客服", "详情页", "主图", "淘宝", "商家", "电商"]):
            return "小商家不一定愿意买复杂系统，但愿意为一个立刻改善转化或节省时间的具体交付付费。"
        if any(word in text for word in ["小红书", "抖音", "播放量", "选题", "剪辑", "内容"]):
            return "内容创作者缺的常常不是更多技巧，而是能持续产出、复盘和转化的低摩擦流程。"
        return "真正的机会不是问题被很多人讨论，而是它能被做成低成本、可交付、可验证的商品、内容或服务。"

    def _is_generic_reference(self, value) -> bool:
        text = str(value or "")
        generic_markers = [
            "暂无明确历史类比",
            "暂无明确成熟市场参照",
            "时间阶段不明确",
            "产业逻辑上理解",
            "真正的机会不是问题被很多人讨论",
        ]
        return any(marker in text for marker in generic_markers)

    def _pain_signal_text(self, item: IntelligenceItem) -> str:
        pain = self._pain(item)
        return " ".join(
            [
                str(item.title or ""),
                str(item.source or ""),
                str(item.category or ""),
                str(pain.get("question") or ""),
                str(pain.get("audience") or ""),
            ]
        )

    def _target_audience(self, item: IntelligenceItem) -> str:
        text = self._item_text(item)
        if any(word in text for word in ["孩子", "宝宝", "育儿", "家长", "学生"]):
            return "宝妈、家长、老师或学生"
        if any(word in text for word in ["淘宝", "电商", "客服", "详情页", "主图", "商家", "客户"]):
            return "淘宝/拼多多/抖音电商卖家"
        if any(word in text for word in ["内容", "小红书", "抖音", "creator", "video"]):
            return "内容创作者和小商家"
        if any(word in text for word in ["AI", "prompt", "自动化", "办公"]):
            return "想用 AI 提效的职场人、小团队或个体户"
        return "有具体生活、工作或经营问题的人群"

    def _audience(self, item: IntelligenceItem) -> str:
        raw = self._pain(item).get("audience")
        generic_values = {
            "有具体生活、工作或经营问题的人群",
            "所有人",
            "普通人",
            FALLBACK,
        }
        if self._valid(raw) and str(raw).strip() not in generic_values:
            return self._text(raw)
        return self._target_audience(item)

    def _difficulty(self, item: IntelligenceItem) -> str:
        if self._startup_cost(item) == "高":
            return "高"
        if self._risk_level(item) == "中":
            return "中"
        return "低"

    def _fit_me(self, item: IntelligenceItem) -> str:
        text = self._item_text(item)
        if any(word.lower() in text.lower() for word in ["ai", "自动化", "电商", "淘宝", "内容", "小红书", "抖音", "creator"]):
            return "适合你围绕 AI、自动化、电商或内容变现做低成本验证。"
        return "可作为需求观察，暂不作为优先方向。"

    def _has_clear_service_object(self, item: IntelligenceItem) -> bool:
        value = self._opportunity(item).get("suitable_for") or self._pain(item).get("audience")
        generic = ["所有人", "普通人", "有相关行业经验", "能低成本验证", "机会寻找者"]
        if self._valid(value) and not any(word in str(value) for word in generic):
            return True
        return self._has_ordinary_relevance(item)

    def _has_executable_first_step(self, item: IntelligenceItem) -> bool:
        return self._valid_action(self._first_action(item))

    def _can_migrate_to_china(self, item: IntelligenceItem) -> bool:
        return bool(self._platforms(item))

    def _depends_on_overseas_restriction(self, item: IntelligenceItem) -> bool:
        text = self._item_text(item).lower()
        return any(word in text for word in ["yc", "y combinator", "us only", "stripe", "海外账号", "美国账号"])

    def _is_high_capital(self, item: IntelligenceItem) -> bool:
        text = self._filter_text(item).lower()
        return self._contains_any_keyword(text, HIGH_CAPITAL_KEYWORDS)

    def _is_non_ordinary_opportunity(self, item: IntelligenceItem) -> bool:
        text = self._filter_text(item).lower()
        return self._contains_any_keyword(text, NON_ORDINARY_OPPORTUNITY_KEYWORDS)

    def _contains_any_keyword(self, text: str, keywords: list[str]) -> bool:
        return any(self._contains_keyword(text, keyword) for keyword in keywords)

    def _contains_keyword(self, text: str, keyword: str) -> bool:
        needle = keyword.lower()
        if re.fullmatch(r"[a-z0-9][a-z0-9 +&'’.-]*", needle):
            pattern = rf"(?<![a-z0-9]){re.escape(needle)}(?![a-z0-9])"
            return bool(re.search(pattern, text))
        return needle in text

    def _is_overseas(self, item: IntelligenceItem) -> bool:
        domain = urlparse(item.url or "").netloc.lower()
        if domain.endswith(".cn") or "gov.cn" in domain:
            return False
        return not re.search(r"[\u4e00-\u9fff]", item.title or "")

    def _keyword(self, item: IntelligenceItem) -> str:
        if item.source_type == "pain_keywords":
            return self._text(item.title)[:40]
        text = f"{item.title} {item.summary}"
        chinese = re.findall(r"[\u4e00-\u9fff]{2,}", text)
        if chinese:
            return " ".join(chinese[:3])
        title = self._title_zh(item)
        if re.search(r"[\u4e00-\u9fff]", title):
            return title.replace("海外案例：", "").split("：", 1)[0][:40]
        return "AI 自动化 电商提效"

    def _risk_title(self, item: IntelligenceItem) -> str:
        return self._opportunity_name(item)

    def _item_text(self, item: IntelligenceItem) -> str:
        return " ".join(
            [
                str(item.title or ""),
                str(item.summary or ""),
                str(item.content or ""),
                str(item.source or ""),
                str(item.category or ""),
                str(item.analysis or ""),
            ]
        )

    def _filter_text(self, item: IntelligenceItem) -> str:
        analysis = item.analysis if isinstance(item.analysis, dict) else {}
        parts = [
            str(item.title or ""),
            str(item.summary or ""),
            str(item.content or ""),
            str(item.source or ""),
            str(item.category or ""),
            str(analysis.get("what_happened") or ""),
            str(analysis.get("summary") or ""),
        ]
        pain = analysis.get("pain_point")
        source_text = f"{item.source or ''} {item.source_type or ''} {item.category or ''}"
        is_real_pain_source = item.source_type == "pain_keywords" or item.category == "痛点机会" or "痛点" in source_text
        if is_real_pain_source and isinstance(pain, dict):
            parts.extend(str(pain.get(key) or "") for key in ["question", "audience", "real_need", "why_need"])
        opportunity = analysis.get("opportunity")
        if isinstance(opportunity, dict):
            parts.extend(str(opportunity.get(key) or "") for key in ["name"])
        return " ".join(parts)

    def _sentence(self, value, fallback: str) -> str:
        text = self._text(value, fallback)
        text = re.sub(r"\s+", " ", text).strip()
        if "。" in text:
            text = text.split("。", 1)[0] + "。"
        return text[:140]

    def _text(self, value, fallback: str = FALLBACK) -> str:
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
        return bool(text) and text not in {"无", "/", "\\", "-", "N/A", "n/a", "None", "none", "暂无", "无。", "/。"}

    def _valid_action(self, value) -> bool:
        if not self._valid(value):
            return False
        text = str(value).strip()
        if text in FORBIDDEN_ACTIONS:
            return False
        if len(text) < 18:
            return False
        return any(word in text for word in ["搜索", "记录", "找", "做", "整理", "验证", "表格", "小样", "平台"])

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
            if phrase not in replacements:
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

        forbidden = SECTION_HEADINGS[2:]
        first_area = report[report.index(SECTION_HEADINGS[1]) : report.index(SECTION_HEADINGS[2])]
        for heading in forbidden:
            if heading in first_area:
                raise ValueError(f"Report structure invalid: {heading} appears inside change item area")

        for marker in ["：无", "：/", ": /", ": 无"]:
            if marker in report:
                raise ValueError(f"Report structure invalid: empty marker found {marker!r}")

        change_area = report[report.index(SECTION_HEADINGS[1]) : report.index(SECTION_HEADINGS[2])]
        change_blocks = re.findall(r"(?ms)^### \d+\. .*?(?=^### \d+\.|^## 二、|\Z)", change_area)
        for block in change_blocks:
            required = [
                "#### 我的理解",
                "#### 历史类比 / 发达国家参照",
                "- 可比案例：",
                "- 发生时期：",
                "- 当时带来的机会：",
                "- 中国现在是否类似：",
                "- 对普通人的启发：",
                "#### 认知破界",
                "- 大多数人的误解：",
                "- 高认知视角：",
                "- 我应该更新的判断：",
                "- 3 年后可能变成：",
                "#### 可执行动作",
            ]
            missing = [item for item in required if item not in block]
            if missing:
                title = block.splitlines()[0] if block.splitlines() else "unknown"
                raise ValueError(f"Report structure invalid: {title} missing {missing}")

        pain_area = report[report.index(SECTION_HEADINGS[3]) : report.index(SECTION_HEADINGS[4])]
        pain_blocks = re.findall(r"(?ms)^### 痛点 \d+：.*?(?=^### 痛点 \d+：|^## 四、|\Z)", pain_area)
        for block in pain_blocks:
            required = ["- 发达国家/成熟市场是否已有类似产品或服务：", "- 认知破界："]
            missing = [item for item in required if item not in block]
            if missing:
                title = block.splitlines()[0] if block.splitlines() else "unknown"
                raise ValueError(f"Report structure invalid: {title} missing {missing}")
