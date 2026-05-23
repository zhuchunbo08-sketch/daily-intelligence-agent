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
    "## 七、今日商业模式拆解",
    "## 八、今日一个反常识判断",
    "## 九、今日认知边界扩展",
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
NO_HISTORY_REFERENCE = "暂无明确可比历史阶段，本条更适合作为趋势观察。"
NO_ACTION = "暂不建议行动，本条只做趋势观察。"
NO_THREE_DAY_ACTION = "不建议做 3 天动作，本条只做趋势观察。"


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
        report = self.sanitize_report_content(report)
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
        pain_items = self._pain_items(observed_items)
        change_items = self._change_items(observed_items)
        radar_items = self._radar_items(observed_items, pain_items)
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
            f"- 今天最值得看的机会：{self._opportunity_headline(radar_items, pain_items)}",
            f"- 今天最值得关注的痛点：{self._pain_headline(pain_items)}",
            f"- 今天最值得避开的坑：{self._risk_headline(risk_items)}",
            f"- 今天我建议你做的一件事：{self._conclusion_action(pain_items, radar_items, change_items)}",
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

        lines.extend(["", "## 七、今日商业模式拆解", ""])
        lines.extend(self._render_business_model(pain_items, radar_items, change_items))

        lines.extend(["", "## 八、今日一个反常识判断", ""])
        lines.extend(self._render_counterintuitive_judgment(pain_items, radar_items, change_items))

        lines.extend(["", "## 九、今日认知边界扩展", ""])
        lines.extend(self._render_boundary_expansion(pain_items, radar_items, change_items))

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
            "#### 历史类比 / 成熟市场参照",
            *self._render_historical_reference(item),
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
            return ["今天没有筛出足够具体、低成本、7 天内可验证的机会，宁可不推，不凑数。"]
        lines: list[str] = []
        for item in items[:3]:
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
        primary = self._best_action_item(pain_items, radar_items)
        if primary:
            action = self._three_day_action(primary) if primary in radar_items else self._pain_action(primary)
            if action != NO_ACTION and action != NO_THREE_DAY_ACTION:
                actions.append(f"1. 今天先验证“{self._action_theme(primary)}”这个痛点：\n{action}")
        elif change_items and self._should_generate_action(change_items[0]):
            action = self._first_action(change_items[0])
            if action != NO_ACTION:
                actions.append(f"1. {action}")
        if not actions:
            actions.append("1. 今天用 30 分钟整理 3 个真实痛点问题，只记录人群、场景、现有方案和是否有人付费，不急着行动。")
        return self._dedupe_lines(actions)[:2]

    def _render_business_model(
        self,
        pain_items: list[IntelligenceItem],
        radar_items: list[IntelligenceItem],
        change_items: list[IntelligenceItem],
    ) -> list[str]:
        item = self._best_commercial_learning_item(pain_items, radar_items, change_items)
        if not item:
            return ["今天没有足够具体、贴近真实交易的商业模式可拆，宁可空过，不硬写。"]
        model = self._business_model_profile(item)
        return [
            f"- 模式名称：{model['name']}",
            f"- 谁在付钱：{model['payer']}",
            f"- 为什么愿意付钱：{model['reason']}",
            f"- 核心交付是什么：{model['delivery']}",
            f"- 真正赚钱的环节在哪里：{model['profit_point']}",
            f"- 最大成本是什么：{model['cost']}",
            f"- 为什么这个模式能长期存在：{model['durability']}",
            f"- 普通人能不能切进去：{model['entry_possible']}",
            f"- 最低成本切入口：{model['entry']}",
            f"- 最大坑：{model['trap']}",
            f"- 我今天应该记住的一句话：{model['one_sentence']}",
        ]

    def _render_counterintuitive_judgment(
        self,
        pain_items: list[IntelligenceItem],
        radar_items: list[IntelligenceItem],
        change_items: list[IntelligenceItem],
    ) -> list[str]:
        item = self._best_commercial_learning_item(pain_items, radar_items, change_items)
        if not item:
            return ["今天没有足够扎实的反常识判断，先不硬凑。"]
        judgment = self._counterintuitive_profile(item)
        return [
            f"- 大多数人的直觉：{judgment['intuition']}",
            f"- 更高层的真实规律：{judgment['law']}",
            f"- 为什么很多人会看错：{judgment['why_wrong']}",
            f"- 现实案例：{judgment['case']}",
            f"- 对普通人的意义：{judgment['meaning']}",
            f"- 我今天应该更新的判断：{judgment['update']}",
        ]

    def _render_boundary_expansion(
        self,
        pain_items: list[IntelligenceItem],
        radar_items: list[IntelligenceItem],
        change_items: list[IntelligenceItem],
    ) -> list[str]:
        item = self._best_commercial_learning_item(pain_items, radar_items, change_items)
        if not item:
            return ["今天没有足够高质量的认知边界扩展材料，先不输出。"]
        boundary = self._boundary_profile(item)
        return [
            f"- 今日破界主题：{boundary['topic']}",
            f"- 原来的常见认知：{boundary['old']}",
            f"- 更高一层的认知：{boundary['new']}",
            f"- 现实案例：{boundary['case']}",
            f"- 中国是否正在出现类似变化：{boundary['china']}",
            f"- 对普通人的机会：{boundary['opportunity']}",
            f"- 最容易踩的坑：{boundary['trap']}",
            f"- 我今天应该记住的一句话：{boundary['one_sentence']}",
        ]

    def _change_items(self, items: list[IntelligenceItem]) -> list[IntelligenceItem]:
        candidates: list[IntelligenceItem] = []
        for item in sorted(items, key=lambda x: x.final_score, reverse=True):
            reason = self._change_filter_reason(item)
            if reason:
                self.last_filtered_news.append({"title": item.title, "reason": reason})
                continue
            candidates.append(item)
        return candidates[:3]

    def _radar_items(self, items: list[IntelligenceItem], pain_items: list[IntelligenceItem] | None = None) -> list[IntelligenceItem]:
        selected: list[IntelligenceItem] = []
        seen_opportunities: set[str] = set()
        has_quality_pain = bool(pain_items)
        for item in sorted(items, key=lambda x: (self._radar_priority(x), x.final_score), reverse=True):
            if self._is_pain_item(item):
                if self._pain_filter_reason(item):
                    continue
            elif self._change_filter_reason(item):
                continue
            if self._is_high_capital(item) or self._is_non_ordinary_opportunity(item) or item.risk_score >= 7:
                continue
            if not self._should_generate_action(item):
                continue
            if self._is_vague_trend_opportunity(item):
                continue
            if not self._is_pain_item(item) and not self._has_concrete_radar_offer(item):
                continue
            if not has_quality_pain and not self._is_pain_item(item) and not self._is_strong_concrete_service(item):
                continue
            if self._radar_criteria_count(item) < 6:
                continue
            key = self._radar_dedupe_key(item)
            if key in seen_opportunities:
                continue
            seen_opportunities.add(key)
            selected.append(item)
        return selected[:3]

    def _radar_priority(self, item: IntelligenceItem) -> int:
        if self._is_pain_item(item):
            return 10 + self._pain_priority(item)
        if self._is_service_or_tool_opportunity(item):
            return 4
        if any(word in self._item_text(item).lower() for word in ["商品", "收纳", "宠物", "厨房", "衣架", "1688"]):
            return 3
        if any(word in self._item_text(item).lower() for word in ["内容", "资料包", "模板", "课程"]):
            return 2
        return 1

    def _radar_dedupe_key(self, item: IntelligenceItem) -> str:
        return re.sub(r"\s+", "", self._opportunity_name(item).lower())

    def _pain_items(self, items: list[IntelligenceItem]) -> list[IntelligenceItem]:
        selected: list[IntelligenceItem] = []
        for item in sorted(items, key=lambda x: (self._pain_priority(x), x.final_score), reverse=True):
            if not self._is_pain_item(item):
                continue
            reason = self._pain_filter_reason(item)
            if reason:
                self.last_filtered_pain_points.append({"title": item.title, "reason": reason})
                continue
            selected.append(item)
        return selected[:3]

    def _pain_priority(self, item: IntelligenceItem) -> int:
        text = self._raw_item_text(item).lower()
        if any(word in text for word in ["客户老问", "重复问题", "客服", "自动回复", "知识库", "回复太慢"]):
            return 5
        if any(word in text for word in ["详情页", "主图", "店铺", "商家"]):
            return 4
        if any(word in text for word in ["ai工具", "ai 工具", "prompt", "自动化"]):
            return 3
        if any(word in text for word in ["孩子", "育儿", "家长"]):
            return 2
        return 1

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
        return self._brief(self._title_zh(items[0]), fallback)

    def _opportunity_headline(self, radar_items: list[IntelligenceItem], pain_items: list[IntelligenceItem]) -> str:
        source = next((item for item in radar_items if self._is_pain_item(item)), None) or self._best_action_item(pain_items, radar_items)
        if not source:
            return "没有发现普通人 7 天内能验证的明确机会"
        return self._brief(self._opportunity_name(source), "没有发现普通人 7 天内能验证的明确机会")

    def _pain_headline(self, items: list[IntelligenceItem]) -> str:
        if not items:
            return "没有筛出足够具体、可变现的高频痛点"
        return self._brief(self._pain_title(items[0]), "没有筛出足够具体、可变现的高频痛点")

    def _risk_headline(self, items: list[IntelligenceItem]) -> str:
        if not items:
            return "高收益副业包装、刷单、拉人头和不透明代运营"
        return self._brief(self._risk_title(items[0]), "高收益副业包装、刷单、拉人头和不透明代运营")

    def _one_action(
        self,
        pain_items: list[IntelligenceItem],
        radar_items: list[IntelligenceItem],
        change_items: list[IntelligenceItem],
    ) -> str:
        if pain_items:
            return self._specific_first_action(pain_items[0])
        if radar_items:
            return self._first_action(radar_items[0])
        if change_items:
            keyword = self._keyword(change_items[0])
            return f"今天在小红书和淘宝搜索“{keyword}”，记录 20 条评论痛点和可付费场景。"
        return "今天新增 3 个痛点类数据源，并记录 10 个真实问题标题。"

    def _conclusion_action(
        self,
        pain_items: list[IntelligenceItem],
        radar_items: list[IntelligenceItem],
        change_items: list[IntelligenceItem],
    ) -> str:
        item = self._best_action_item(pain_items, radar_items)
        if item:
            theme = self._action_theme(item)
            return self._brief(
                f"先验证“{theme}”：搜价格差评，做飞书表格小样，找 3 个商家问付费意愿。",
                f"今天先验证“{theme}”这个痛点。",
            )
        if change_items and self._should_generate_action(change_items[0]):
            return self._brief(self._first_action(change_items[0]), "今天只做一个低成本验证动作")
        return "今天只整理真实痛点，不急着追海外趋势或复杂项目"

    def _best_action_item(self, pain_items: list[IntelligenceItem], radar_items: list[IntelligenceItem]) -> IntelligenceItem | None:
        candidates = [item for item in pain_items if self._should_generate_action(item)]
        if not candidates:
            candidates = [item for item in radar_items if self._should_generate_action(item)]
        if not candidates:
            return None
        def score(item: IntelligenceItem) -> tuple[int, float]:
            text = self._raw_item_text(item).lower()
            priority = 3 if any(word in text for word in ["客户老问", "重复问题", "客服", "自动回复", "知识库", "回复太慢"]) else 0
            return (priority, item.final_score)
        return sorted(candidates, key=score, reverse=True)[0]

    def _best_commercial_learning_item(
        self,
        pain_items: list[IntelligenceItem],
        radar_items: list[IntelligenceItem],
        change_items: list[IntelligenceItem],
    ) -> IntelligenceItem | None:
        candidates = [item for item in pain_items + radar_items if self._is_commercial_learning_source(item)]
        if not candidates:
            candidates = [item for item in change_items if self._is_commercial_learning_source(item)]
        if not candidates:
            return None

        def score(item: IntelligenceItem) -> tuple[int, float]:
            text = self._item_text(item).lower()
            priority = 0
            if self._is_ai_customer_service_opportunity(item):
                priority += 6
            if self._is_pain_item(item):
                priority += 4
            if self._has_concrete_radar_offer(item):
                priority += 3
            if any(word in text for word in ["客服", "详情页", "自动回复", "知识库", "商家", "店铺"]):
                priority += 2
            return (priority, item.final_score)

        return sorted(candidates, key=score, reverse=True)[0]

    def _is_commercial_learning_source(self, item: IntelligenceItem) -> bool:
        if self._is_high_capital(item) or self._is_non_ordinary_opportunity(item):
            return False
        if self._has_complex_rights_risk(item) and not self._has_concrete_radar_offer(item):
            return False
        text = self._item_text(item).lower()
        return self._is_pain_item(item) or self._has_concrete_radar_offer(item) or any(
            word in text
            for word in [
                "商业模式",
                "变现",
                "付费",
                "订阅",
                "服务",
                "模板",
                "工具",
                "电商",
                "小商家",
                "创作者",
                "小商品",
            ]
        )

    def _action_theme(self, item: IntelligenceItem) -> str:
        text = self._raw_item_text(item).lower()
        if any(word in text for word in ["客户老问", "重复问题", "客服", "自动回复", "知识库", "回复太慢"]):
            return "AI客服自动回复"
        if "详情页" in text:
            return "详情页诊断"
        if any(word in text for word in ["ai工具", "ai 工具", "prompt", "自动化"]):
            return "AI工作流模板"
        return self._brief(self._pain_title(item), "低成本痛点验证", min_len=8, max_len=24)

    def _business_model_profile(self, item: IntelligenceItem) -> dict[str, str]:
        text = self._item_text(item).lower()
        if self._is_ai_customer_service_opportunity(item) or any(word in text for word in ["客服", "自动回复", "知识库", "客户老问"]):
            return {
                "name": "AI客服话术库和自动回复配置服务",
                "payer": "淘宝、拼多多、抖音小店商家和本地小老板。",
                "reason": "客服重复回答耗时间，新人培训慢，错答还会影响转化和售后。",
                "delivery": "行业高频问答库、标准话术、自动回复规则和一份可维护的飞书表格。",
                "profit_point": "不是卖 AI 概念，而是卖已经整理好的行业知识和配置结果。",
                "cost": "前期跑真实店铺场景、整理问答、持续补充新问题。",
                "durability": "每个行业都有自己的客户问法，商家也一直有降本和提转化需求。",
                "entry_possible": "可以，但要先从一个垂直行业切进去。",
                "entry": "先做母婴店、女装店或本地家政店的 30 条客服问答模板。",
                "trap": "只卖通用模板，不懂真实业务，商家很快会觉得没用。",
                "one_sentence": "很多人买的不是工具，而是已经帮他整理好的结果。",
            }
        if any(word in text for word in ["详情页", "主图", "店铺", "转化率"]):
            return {
                "name": "电商详情页诊断和改版清单服务",
                "payer": "有流量但转化差的淘宝、拼多多和抖音小店商家。",
                "reason": "他们不一定懂设计和文案，但能感受到点击、咨询和成交变少。",
                "delivery": "一页问题诊断、竞品对照、主图/详情页改版建议和可直接外包的修改清单。",
                "profit_point": "赚钱点在把模糊的“页面不好”翻译成商家能执行的改法。",
                "cost": "看店铺、看竞品、积累类目经验和真实转化案例。",
                "durability": "平台规则和用户审美会变，但商家提高转化的需求长期存在。",
                "entry_possible": "可以，从一个小类目开始更现实。",
                "entry": "选一个母婴、服饰或家居小类目，做 3 个免费诊断样本换反馈。",
                "trap": "只做漂亮设计，不看商品卖点、评价痛点和真实成交路径。",
                "one_sentence": "小商家愿意为能直接提高转化的具体改法付钱。",
            }
        if any(word in text for word in ["孩子", "育儿", "家长", "任务卡", "奖励表"]):
            return {
                "name": "低价育儿工具包",
                "payer": "被作业、习惯和亲子沟通反复困扰的家长。",
                "reason": "家长不缺大道理，缺的是今晚就能拿来用的表格、卡片和流程。",
                "delivery": "行为奖励表、作息打卡表、亲子任务卡和使用说明。",
                "profit_point": "赚钱点在把育儿建议做成低压力、可打印、可执行的小工具。",
                "cost": "理解真实家庭场景，避免夸大效果和制造焦虑。",
                "durability": "家庭管理问题会反复出现，低价工具比大课更容易试错。",
                "entry_possible": "可以，但要克制承诺。",
                "entry": "先做一页孩子作息打卡表，在小红书找 3 位家长试用。",
                "trap": "把工具包装成万能教育方法，反而变成焦虑生意。",
                "one_sentence": "育儿小生意的低门槛切口，是把建议变成能立刻用的工具。",
            }
        if any(word in text for word in ["收纳", "衣架", "宠物", "清洁", "厨房", "小商品"]):
            return {
                "name": "场景细分小商品",
                "payer": "被尺寸、收纳、清洁或宠物问题反复困扰的家庭用户。",
                "reason": "小问题出现频率高，用户愿意为省心和更贴合场景的小物付钱。",
                "delivery": "一个按人群、尺寸或场景重新定义的小商品，加上清楚的使用场景内容。",
                "profit_point": "赚钱点在选品、差异化卖点和内容场景，而不只是低价进货。",
                "cost": "找货源、测质量、看差评、拍内容和处理售后。",
                "durability": "家庭空间和生活方式越细分，小商品需求越容易持续出现。",
                "entry_possible": "可以，从差评集中且货源成熟的品类切入。",
                "entry": "先在淘宝、拼多多、1688 找 20 条差评，倒推出 3 个差异化卖点。",
                "trap": "只看销量不看差评，最后卖成无差异低价货。",
                "one_sentence": "小商品机会常常不是发明新品，而是把老品类按场景切细。",
            }
        if any(word in text for word in ["内容", "小红书", "抖音", "选题", "剪辑", "创作者"]):
            return {
                "name": "内容创作者选题和复盘服务",
                "payer": "有产品或账号但不会稳定产出内容的小商家和创作者。",
                "reason": "他们缺的不是平台口号，而是持续选题、标题、脚本和复盘流程。",
                "delivery": "选题库、标题模板、内容日历、复盘表和一轮账号诊断。",
                "profit_point": "赚钱点在把平台经验变成可重复执行的内容流程。",
                "cost": "持续研究账号案例、平台规则和转化结果。",
                "durability": "只要平台靠内容分发，商家和创作者就会需要更稳定的产出方法。",
                "entry_possible": "可以，但最好选一个细分行业。",
                "entry": "先做一个本地生活或电商账号的 10 条选题样本。",
                "trap": "只卖爆款标题，不看用户需求和成交路径。",
                "one_sentence": "内容服务不是卖灵感，而是卖可持续生产和复盘的流程。",
            }
        return {
            "name": "低成本问题诊断服务",
            "payer": f"{self._audience(item)}。",
            "reason": "他们已经感到麻烦，但不知道问题该怎么拆、先做哪一步。",
            "delivery": "问题诊断、可执行清单、模板小样和一次验证建议。",
            "profit_point": "赚钱点在把模糊问题拆成用户能马上执行的下一步。",
            "cost": "理解真实场景，积累案例，避免泛泛而谈。",
            "durability": "只要信息过载和执行门槛存在，用户就会为明确答案付费。",
            "entry_possible": "可以，但必须从具体人群和具体场景开始。",
            "entry": "先选一个明确问题，做 1 页诊断样本给 3 个真实用户看。",
            "trap": "把诊断写成空话，没有交付物，也没有验证结果。",
            "one_sentence": "普通人能切的小生意，往往是把复杂问题变成清楚下一步。",
        }

    def _counterintuitive_profile(self, item: IntelligenceItem) -> dict[str, str]:
        text = self._item_text(item).lower()
        if self._is_ai_customer_service_opportunity(item) or any(word in text for word in ["客服", "自动回复", "知识库"]):
            return {
                "intuition": "很多人以为 AI 服务的核心是会用最新工具。",
                "law": "客户真正付钱的，常常是行业知识被整理成可直接使用的结果。",
                "why_wrong": "工具看起来更高级，但小商家最缺的是能马上减少重复沟通的交付物。",
                "case": "AI 客服话术库、常见问题知识库、自动回复配置，比单纯教工具更容易成交。",
                "meaning": "普通人不必追模型本身，可以从一个行业的重复问题切入。",
                "update": "能赚钱的不是会说 AI，而是能把 AI 变成具体行业的省时结果。",
            }
        if any(word in text for word in ["收纳", "衣架", "宠物", "清洁", "厨房", "小商品"]):
            return {
                "intuition": "很多人觉得小商品太普通，没什么商业认知可讲。",
                "law": "越具体、越高频、越能被差评描述的小问题，反而越容易验证。",
                "why_wrong": "大趋势更容易让人兴奋，小需求看起来不高级。",
                "case": "儿童衣架、宠物除毛、厨房收纳、小户型清洁工具，都靠具体场景长期卖货。",
                "meaning": "普通人可以先从差评和搜索词找需求，而不是先想宏大项目。",
                "update": "痛点越具体，越容易验证；概念越宏大，越容易空转。",
            }
        if any(word in text for word in ["孩子", "育儿", "家长"]):
            return {
                "intuition": "很多人以为育儿变现就是卖课和专家建议。",
                "law": "更低门槛的付费，往往来自简单、低价、今晚就能用的家庭工具。",
                "why_wrong": "课程显得更完整，但家长在高压场景里先要一个能马上执行的办法。",
                "case": "奖励表、作息卡、亲子任务卡和可打印资料包，比长课更容易低价测试。",
                "meaning": "做育儿机会时，先解决一个家庭小摩擦，不要制造焦虑。",
                "update": "用户不一定缺知识，很多时候缺一个能立刻落地的工具。",
            }
        return {
            "intuition": "大多数人会先问这是不是风口。",
            "law": "普通人更应该问：谁正在为这个具体麻烦付钱，交付物是什么。",
            "why_wrong": "风口给人确定感，但真实交易发生在具体人群和具体结果之间。",
            "case": self._opportunity_name(item),
            "meaning": "先把趋势翻译成一个小样、一个模板或一次服务，再判断值不值得做。",
            "update": "不要追最大概念，先找最小可付费场景。",
        }

    def _boundary_profile(self, item: IntelligenceItem) -> dict[str, str]:
        text = self._item_text(item).lower()
        if self._is_ai_customer_service_opportunity(item) or any(word in text for word in ["客服", "自动回复", "知识库", "自动化"]):
            return {
                "topic": "AI 从工具使用进入行业工作流交付。",
                "old": "以前以为会用 AI 工具就能形成优势。",
                "new": "更高一层是把 AI 嵌进某个行业的固定流程，让客户买到结果而不是教程。",
                "case": "小商家客服问答库、自动回复规则、飞书表格知识库，就是比泛 AI 培训更具体的交付。",
                "china": "正在出现，尤其是电商、本地生活和小团队办公场景。",
                "opportunity": "先做垂直行业模板和代配置服务，再根据重复交付沉淀产品。",
                "trap": "把 AI 包装成万能课，忽略客户真实业务和维护成本。",
                "one_sentence": "AI 的普通人机会，不在模型，而在把模型接进具体工作流。",
            }
        if any(word in text for word in ["收纳", "衣架", "宠物", "清洁", "厨房", "小商品"]):
            return {
                "topic": "小痛点经济和场景细分商品。",
                "old": "以前以为只有大品类、大品牌才值得做。",
                "new": "成熟市场里很多生意来自把一个大品类按人群、尺寸、空间和场景切得更细。",
                "case": "日本收纳经济、儿童尺寸家居小物、宠物清洁用品，都是具体场景推动的长期需求。",
                "china": "正在出现，小户型、宠物、育儿和懒人家务场景都在细分。",
                "opportunity": "从搜索词、差评和使用场景里找微创新，而不是凭空发明需求。",
                "trap": "只做低价搬运，不做质量、场景和内容表达。",
                "one_sentence": "商业地图里，小需求不是小价值，关键看频次和付费意愿。",
            }
        if any(word in text for word in ["孩子", "育儿", "家长"]):
            return {
                "topic": "家庭工具化需求。",
                "old": "以前以为教育和育儿只能靠课程、专家和长期陪跑。",
                "new": "很多家庭问题首先需要低压力、短链路、可执行的日常工具。",
                "case": "欧美和日本常见 reward chart、routine cards、printable parenting tools。",
                "china": "正在出现，家长从焦虑买课转向寻找更具体的家庭管理方法。",
                "opportunity": "做可打印工具、亲子任务卡、习惯表和低价资料包。",
                "trap": "夸大效果，暗示工具能解决所有教育问题。",
                "one_sentence": "好的育儿小生意，是降低家庭摩擦，不是放大家长焦虑。",
            }
        return {
            "topic": "从热点判断转向交易判断。",
            "old": "以前容易把热度当成机会。",
            "new": "真正的商业判断要看谁付钱、为什么付、交付什么、能否重复。",
            "case": self._opportunity_name(item),
            "china": "中国很多平台变化和消费需求，都需要先落到具体场景才能判断。",
            "opportunity": "把今天看到的趋势拆成一个人群、一个痛点、一个交付物。",
            "trap": "只记新闻标题，不验证真实需求。",
            "one_sentence": "商业认知不是知道更多新闻，而是更快看清交易结构。",
        }


    def _understanding(self, item: IntelligenceItem) -> str:
        title = self._title_zh(item)
        trend = self._sentence(self._cognition(item).get("new"), "背后说明需求正在从泛泛关注转向可落地的工具、服务或内容。")
        domestic = self._domestic_value(item)
        avoid = "不要直接照搬海外平台、资本密集型项目或没有明确人群的概念。"
        if self._should_generate_action(item):
            ordinary = "普通人真正能借鉴的是找到具体人群、具体场景和一个低成本小样。"
        else:
            ordinary = "普通人暂时不必急着行动，先判断它是否真的改变平台规则、成本结构或用户需求。"
        return f"表面上看，这是“{title}”。{trend} 它现在出现，通常和成本下降、效率提升、平台规则变化或用户需求变得更具体有关。{ordinary}{domestic} {avoid}"

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
        if (
            isinstance(mapping, dict)
            and self._valid(mapping.get("personal_value"))
            and not self._is_generic_domestic_mapping(mapping.get("personal_value"))
        ):
            return self._text(mapping.get("personal_value"))
        if self._is_overseas(item) and not self._should_generate_action(item):
            return "国内暂无直接迁移平台，先作为趋势观察。"
        platforms = self._platforms(item)
        if not platforms:
            return "国内暂无直接迁移平台，先作为趋势观察。"
        if self._is_overseas(item):
            return f"不能照搬海外平台，但可迁移到{platforms}做需求验证。"
        return f"可在{platforms}做低成本验证。"

    def _platforms(self, item: IntelligenceItem) -> str:
        text = (self._pain_signal_text(item) if self._is_pain_item(item) else self._raw_item_text(item)).lower()
        platforms: list[str] = []
        if self._depends_on_overseas_restriction(item) or (self._is_overseas(item) and not self._has_ordinary_relevance(item)):
            return ""
        if any(word in text for word in ["衣架", "收纳", "宠物", "清洁", "厨房", "做饭", "穿搭", "小商品", "货源"]):
            platforms.extend(["淘宝", "拼多多", "1688", "小红书测评", "抖音带货"])
        if any(word in text for word in ["孩子", "育儿", "家长", "内容", "选题", "播放量", "剪辑", "creator", "video", "知识"]):
            platforms.extend(["小红书", "抖音", "视频号", "公众号", "B站"])
        if any(word in text for word in ["客服", "详情页", "主图", "选品", "电商", "商家", "客户", "代运营", "诊断", "服务", "ecommerce"]):
            platforms.extend(["微信私域", "飞书", "淘宝服务市场", "本地生活", "公众号"])
        if any(word in text for word in ["ai", "ai工具", "prompt", "自动化", "办公", "效率", "workflow", "表格", "知识库"]):
            platforms.extend(["SaaS", "小程序", "飞书多维表格", "Notion 模板", "浏览器插件", "企业服务"])
        return " / ".join(dict.fromkeys(platforms))

    def _opportunity_name(self, item: IntelligenceItem) -> str:
        if self._is_ai_customer_service_opportunity(item):
            return "为小商家做 AI 客服话术库和自动回复配置服务"
        raw = self._opportunity(item).get("name")
        if self._valid(raw) and re.search(r"[\u4e00-\u9fff]", str(raw)):
            return self._sentence(raw, self._title_zh(item))[:60]
        return self._title_zh(item)[:60]

    def _radar_status(self, item: IntelligenceItem) -> str:
        if self._is_high_capital(item) or self._is_non_ordinary_opportunity(item) or item.risk_score >= 8:
            return "不建议碰"
        if not self._should_generate_action(item):
            return "观察中"
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
        if not self._should_generate_action(item):
            return NO_ACTION
        raw = self._opportunity(item).get("first_action") or self._opportunity(item).get("first_step")
        if self._valid_action(raw) and not self._is_generic_action(raw):
            return self._text(raw)
        return self._specific_first_action(item)

    def _three_day_action(self, item: IntelligenceItem) -> str:
        if not self._should_generate_action(item):
            return NO_THREE_DAY_ACTION
        raw = self._opportunity(item).get("three_day_action")
        if self._valid_action(raw) and not self._is_generic_action(raw):
            return self._text(raw)
        return self._specific_three_day_action(item)

    def _pain_action(self, item: IntelligenceItem) -> str:
        if not self._should_generate_action(item):
            return NO_ACTION
        raw = self._pain(item).get("seven_day_action")
        if self._valid_action(raw) and not self._is_generic_action(raw):
            return self._text(raw)
        return self._specific_three_day_action(item)

    def _should_generate_action(self, item: IntelligenceItem) -> bool:
        if self._startup_cost(item) == "高" or self._risk_level(item) == "高":
            return False
        if self._is_high_capital(item) or self._is_non_ordinary_opportunity(item):
            return False
        if self._depends_on_overseas_restriction(item) or self._has_complex_rights_risk(item):
            return False
        if not self._platforms(item):
            return False
        if self._is_pain_item(item):
            return self._has_clear_service_object(item) and item.money_score >= 2
        status = str(self._opportunity(item).get("status") or "")
        if "否" in status or "不建议" in status:
            return False
        return self._has_ordinary_relevance(item) and self._has_clear_service_object(item) and self._has_concrete_radar_offer(item)

    def _specific_first_action(self, item: IntelligenceItem) -> str:
        action = self._specific_three_day_action(item)
        if action in {NO_ACTION, NO_THREE_DAY_ACTION}:
            return NO_ACTION
        return action.split("\n\n", 1)[0].replace("第 1 天：\n", "").strip()

    def _specific_three_day_action(self, item: IntelligenceItem) -> str:
        if not self._should_generate_action(item):
            return NO_THREE_DAY_ACTION
        text = (self._pain_signal_text(item) if self._is_pain_item(item) else self._item_text(item)).lower()
        if self._is_ai_customer_service_opportunity(item) or any(word in text for word in ["客户老问", "重复问题", "客服", "自动回复", "知识库"]):
            return (
                "第 1 天：在淘宝、小红书、抖音搜索“AI客服自动回复 / 客服话术模板 / 店铺自动回复 / 常见问题知识库”，记录 20 个商品或服务的价格、差评和卖点。\n\n"
                "第 2 天：选一个细分场景，比如淘宝女装客服、母婴店客服或本地家政客服，整理 30 条常见问答，做成一个飞书表格或文档小样。\n\n"
                "第 3 天：找 3 个淘宝商家或小老板看样品，问是否愿意付 99-299 元买一套客服话术库或自动回复配置服务。"
            )
        if any(word in text for word in ["宠物掉毛", "猫毛", "除毛", "粘毛"]):
            return (
                "第 1 天：在淘宝、拼多多、小红书搜索“宠物掉毛怎么办 / 猫毛清理神器 / 宠物除毛刷 / 粘毛器测评”，记录价格、销量和差评。\n\n"
                "第 2 天：找 3 个差评集中点，比如不耐用、清不干净、伤宠物或不好收纳，整理成选品表。\n\n"
                "第 3 天：在 1688 找 3 个候选货源，做一个小红书测评选题或淘宝商品差异化卖点草稿。"
            )
        if any(word in text for word in ["详情页", "主图", "选品", "店铺", "商家"]):
            return (
                "第 1 天：在淘宝服务市场、小红书和抖音搜索“详情页诊断 / 主图优化 / 店铺转化率”，记录 20 个服务的价格、交付内容和差评。\n\n"
                "第 2 天：选一个细分店铺类型，整理 3 个详情页问题和 1 页改版建议小样。\n\n"
                "第 3 天：找 3 个小商家看样品，验证是否愿意为 99-299 元的诊断或改版清单付费。"
            )
        if any(word in text for word in ["ai工具", "ai 工具", "prompt", "自动化", "工作流"]):
            return (
                "第 1 天：在小红书、公众号和飞书模板库搜索“AI工作流 / Prompt 模板 / 自动化表格”，记录 20 个具体场景和付费形式。\n\n"
                "第 2 天：选一个场景，比如客服回复、选题整理或商品评论分析，做一个飞书多维表格或 Notion 模板小样。\n\n"
                "第 3 天：找 3 个职场人或小老板试用，问是否愿意为模板配置或代搭建服务付费。"
            )
        if any(word in text for word in ["孩子", "育儿", "家长", "作业", "习惯"]):
            return (
                "第 1 天：在小红书和淘宝搜索“行为奖励表 / 亲子任务卡 / 作息打卡表 / 孩子习惯养成”，记录 20 个笔记或商品的价格、评论和痛点。\n\n"
                "第 2 天：做一页可打印家庭任务卡或奖励表小样，避免制造家长焦虑。\n\n"
                "第 3 天：找 3 位家长试用，问是否愿意为 9.9-29.9 元资料包付费。"
            )
        if any(word in text for word in ["收纳", "衣架", "小户型", "厨房", "清洁", "做饭"]):
            return (
                "第 1 天：在淘宝、拼多多、1688 和小红书搜索对应小商品关键词，记录价格、销量、差评和使用场景。\n\n"
                "第 2 天：把差评按尺寸、耐用、收纳、颜值和场景分类，找 3 个可差异化卖点。\n\n"
                "第 3 天：选 3 个候选货源，写一版小红书测评选题和淘宝商品卖点草稿。"
            )
        if any(word in text for word in ["小红书", "抖音", "播放量", "选题", "剪辑", "内容"]):
            return (
                "第 1 天：在小红书、抖音和 B 站搜索同类账号诊断、选题库和剪辑模板，记录 20 个付费服务或模板。\n\n"
                "第 2 天：选一个垂直人群，做 10 个选题标题和 1 个内容日历小样。\n\n"
                "第 3 天：找 3 个创作者看样品，验证是否愿意为选题诊断或内容模板付费。"
            )
        platforms = self._platforms(item)
        keyword = self._keyword(item)
        if not platforms:
            return NO_THREE_DAY_ACTION
        return f"第 1 天：在{platforms}搜索“{keyword}”相关真实商品、服务或内容，记录 20 条价格、评论痛点和交付形式。\n\n第 2 天：整理一个 1 页小样或服务说明，只保留目标人群、痛点和交付结果。\n\n第 3 天：找 3 个目标用户验证是否愿意付费。"

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
        return self._platforms(item) or "暂不建议绑定具体平台，先观察需求是否真实。"

    def _render_historical_reference(self, item: IntelligenceItem) -> list[str]:
        if not self._should_render_historical_reference(item):
            return [self._historical_observation_line(item)]
        return [
            f"- 可比阶段：{self._historical_field(item, 'comparable_case')}",
            f"- 当时带来的机会：{self._historical_field(item, 'opportunities')}",
            f"- 中国是否类似：{self._historical_field(item, 'china_stage')}",
            f"- 对普通人的启发：{self._historical_field(item, 'insight')}",
        ]

    def _should_render_historical_reference(self, item: IntelligenceItem) -> bool:
        historical = self._historical(item)
        if self._valid(historical.get("comparable_case")) and not self._is_generic_reference(historical.get("comparable_case")):
            return self._historical_match_kind(item) is not None or self._has_actionable_stage_signal(item)
        return self._historical_match_kind(item) is not None

    def _historical_match_kind(self, item: IntelligenceItem) -> str | None:
        text = self._raw_item_text(item).lower()
        if self._is_high_capital(item) or self._is_non_ordinary_opportunity(item) or self._has_complex_rights_risk(item):
            return None
        if any(word in text for word in ["audiobook", "podcast", "elevenlabs", "有声书", "播客", "音频"]):
            return "audio_content"
        if any(word in text for word in ["收纳", "衣架", "小户型", "厨房小物", "家居小物"]):
            return "home_goods"
        if any(word in text for word in ["reward chart", "routine cards", "behavior chart", "孩子不好管", "家庭任务卡", "行为奖励表"]):
            return "parenting_tools"
        if any(word in text for word in ["客服", "详情页", "主图", "shopify", "saas", "知识库", "自动回复"]):
            return "smb_saas"
        if any(word in text for word in ["search", "google", "搜索入口", "ai 搜索", "垂直搜索"]):
            return "search_entry"
        return None

    def _has_actionable_stage_signal(self, item: IntelligenceItem) -> bool:
        text = self._raw_item_text(item).lower()
        return any(word in text for word in ["阶段", "生态", "插件", "订阅", "工作流", "工具化", "细分品类"])

    def _historical_observation_line(self, item: IntelligenceItem) -> str:
        if self._is_overseas(item) and not self._can_migrate_to_china(item):
            return "暂无必要类比，本条主要看海外平台规则变化。"
        return NO_HISTORY_REFERENCE

    def _historical_field(self, item: IntelligenceItem, key: str) -> str:
        historical = self._historical(item)
        if (
            self._valid(historical.get(key))
            and not self._is_generic_reference(historical.get(key))
            and not self._is_generic_reference(historical.get("comparable_case"))
        ):
            return self._sentence(historical.get(key), FALLBACK)
        fallback = self._historical_fallback(item)
        return fallback[key]

    def _historical_fallback(self, item: IntelligenceItem) -> dict[str, str]:
        text = self._raw_item_text(item).lower()
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
        text = self._raw_item_text(item).lower()
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
            "暂无明确可比历史阶段",
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
        text = self._item_text(item).lower()
        return any(
            word in text
            for word in [
                "商家",
                "卖家",
                "小老板",
                "门店",
                "企业",
                "客户",
                "客服",
                "家长",
                "宝妈",
                "宠物主",
                "创作者",
                "店铺",
                "职场人",
            ]
        )

    def _has_executable_first_step(self, item: IntelligenceItem) -> bool:
        raw = self._opportunity(item).get("first_action") or self._pain(item).get("seven_day_action")
        return self._should_generate_action(item) and (self._valid_action(raw) or bool(self._platforms(item)))

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

    def _is_service_or_tool_opportunity(self, item: IntelligenceItem) -> bool:
        text = (self._pain_signal_text(item) if self._is_pain_item(item) else self._raw_item_text(item)).lower()
        return any(
            word in text
            for word in [
                "客服",
                "详情页",
                "主图",
                "自动回复",
                "知识库",
                "ai工具",
                "ai 工具",
                "prompt",
                "自动化",
                "工作流",
                "模板",
                "诊断",
                "服务",
            ]
        )

    def _has_concrete_radar_offer(self, item: IntelligenceItem) -> bool:
        text = self._item_text(item).lower()
        if self._is_ai_customer_service_opportunity(item):
            return True
        concrete_terms = [
            "话术库",
            "自动回复配置",
            "自动回复",
            "知识库",
            "飞书表格",
            "多维表格",
            "notion",
            "模板",
            "清单",
            "资料包",
            "诊断",
            "代配置",
            "代搭建",
            "选品表",
            "详情页诊断",
            "主图优化",
            "评论分析",
            "客服",
        ]
        vague_only_terms = ["策展", "过滤工具", "社区运营", "forum", "论坛", "创作者/社区"]
        if any(term in text for term in vague_only_terms) and not any(term in text for term in concrete_terms):
            return False
        return any(term in text for term in concrete_terms)

    def _is_strong_concrete_service(self, item: IntelligenceItem) -> bool:
        return (
            self._has_concrete_radar_offer(item)
            and self._has_clear_service_object(item)
            and self._startup_cost(item) in {"低", "中"}
            and self._risk_level(item) != "高"
            and self._platforms(item) != ""
        )

    def _is_vague_trend_opportunity(self, item: IntelligenceItem) -> bool:
        text = self._item_text(item).lower()
        if self._is_ai_customer_service_opportunity(item):
            return False
        vague_patterns = [
            "音频内容策展",
            "内容策展与过滤",
            "过滤工具",
            "forum内容创作者",
            "forum 内容创作者",
            "社区运营",
            "海外新应用",
            "新应用趋势",
            "平台趋势",
        ]
        if any(pattern in text for pattern in vague_patterns):
            return True
        if "forum" in text and not self._has_concrete_radar_offer(item):
            return True
        if any(word in text for word in ["spotify", "hark", "环球音乐", "版权", "分成", "翻唱", "混音"]):
            return True
        return False

    def _is_ai_customer_service_opportunity(self, item: IntelligenceItem) -> bool:
        text = self._item_text(item).lower()
        has_ai = any(word in text for word in ["ai", "人工智能", "自动化", "自动回复", "知识库", "training", "培训"])
        has_customer_service = any(
            word in text
            for word in [
                "客服",
                "客户老问",
                "重复问题",
                "话术",
                "小商家",
                "商家",
                "卖家",
                "店铺",
                "small business",
                "小企业",
                "小老板",
            ]
        )
        return has_ai and has_customer_service

    def _has_complex_rights_risk(self, item: IntelligenceItem) -> bool:
        text = self._raw_item_text(item).lower()
        return any(word in text for word in ["版权", "授权", "分成", "universal music", "环球音乐", "remix", "cover", "翻唱", "混音"])

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

    def _raw_item_text(self, item: IntelligenceItem) -> str:
        return " ".join(
            [
                str(item.title or ""),
                str(item.summary or ""),
                str(item.content or ""),
                str(item.source or ""),
                str(item.category or ""),
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

    def _brief(self, value, fallback: str, min_len: int = 35, max_len: int = 60) -> str:
        text = re.sub(r"\s+", " ", self._text(value, fallback)).strip()
        if len(text) <= max_len:
            return text
        candidates: list[str] = []
        for marker in ["。", "；", ";", "，", ",", "：", ":"]:
            pos = text.rfind(marker, 0, max_len + 1)
            if pos >= min_len:
                candidates.append(text[: pos + 1])
        if candidates:
            return max(candidates, key=len).rstrip("，,：:；;")
        words = text[:max_len].split()
        if len(words) > 1:
            return " ".join(words[:-1]).rstrip("，,：:；;")
        return text[:max_len].rstrip("，,：:；;")

    def _dedupe_lines(self, values: list[str]) -> list[str]:
        result: list[str] = []
        seen: set[str] = set()
        for value in values:
            normalized = re.sub(r"\s+", " ", value).strip()
            if normalized in seen:
                continue
            seen.add(normalized)
            result.append(value)
        return result

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
        if "不建议" in text or "暂不建议" in text or "只做趋势观察" in text:
            return False
        if len(text) < 18:
            return False
        return any(word in text for word in ["搜索", "记录", "找", "做", "整理", "验证", "表格", "小样", "平台"])

    def _is_generic_action(self, value) -> bool:
        text = str(value or "")
        generic_markers = [
            "相关关键词",
            "保存来源链接",
            "找 3 个真实用户或商家验证需求",
            "收集 10 条需求",
            "做 1 页服务说明",
            "与环球音乐达成协议",
            "允许订阅用户使用",
            "暂不建议行动",
            "不建议做 3 天动作",
            "只做趋势观察",
        ]
        return any(marker in text for marker in generic_markers)

    def _is_generic_domestic_mapping(self, value) -> bool:
        text = str(value or "")
        generic_markers = [
            "抖音、小红书、淘宝、视频号",
            "国内内容平台、电商平台、私域服务",
            "AI、自动化、电商运营和内容变现",
            "有观察价值",
            "不能直接照搬",
            "国内暂无直接迁移平台",
        ]
        return any(marker in text for marker in generic_markers)

    def _sanitize(self, content: str) -> str:
        content = re.sub(r"(?m)^#?\s*每日破圈赚钱情报\s+\(\d+/\d+\)\s*$\n?", "", content)
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
        return self.sanitize_report_content(content)

    def sanitize_report_content(self, content: str) -> str:
        content = re.sub(r"(?m)^#?\s*每日破圈赚钱情报\s+\(\d+/\d+\)\s*$\n?", "", content)
        content = re.sub(r"每日破圈赚钱情报\s+\(\d+/\d+\)", "", content)
        field_fallbacks = {
            "风险提醒": "暂无明显风险，但仍需核实来源、真实案例和交付能力。",
            "风险": "暂无明显风险，但仍需核实来源、真实案例和交付能力。",
            "历史类比": "暂无明确可比历史阶段，本条更适合作为趋势观察。",
            "历史类比 / 成熟市场参照": "暂无明确可比历史阶段，本条更适合作为趋势观察。",
            "中国落地价值": "暂无直接落地路径，先作为趋势观察。",
            "可执行动作": "暂不建议行动，本条只做趋势观察。",
            "第一行动": "暂不建议行动，本条只做趋势观察。",
            "3 天内动作": "不建议做 3 天动作，本条只做趋势观察。",
            "7 天内验证动作": "暂不建议行动，本条只做趋势观察。",
            "机会判断": "观察中。",
        }
        empty_values = r"(?:无|/|\\|N/A|n/a|None|none|暂无)\s*[。.]?"

        def replace_field(match: re.Match) -> str:
            prefix = match.group("prefix")
            field = match.group("field").strip()
            fallback = field_fallbacks.get(field, "暂无明确价值，先作为趋势观察。")
            return f"{prefix}{field}：{fallback}"

        field_names = sorted(field_fallbacks, key=len, reverse=True)
        field_pattern = re.compile(
            rf"(?m)^(?P<prefix>\s*(?:(?:[-*]|\#+)\s*)?)(?P<field>{'|'.join(re.escape(k) for k in field_names)})\s*[：:]\s*{empty_values}\s*$"
        )
        content = field_pattern.sub(replace_field, content)

        default_fallback = "暂无明确价值，先作为趋势观察。"
        content = re.sub(rf"(?m)([：:])\s*(?:无|/|\\|N/A|n/a|None|none)\s*[。.]?(?=\s*$)", rf"\1{default_fallback}", content)
        content = re.sub(r"(?m)([：:])\s*暂无\s*[。.]?(?=\s*$)", rf"\1{default_fallback}", content)
        return content

    def _remaining_empty_markers(self, content: str) -> list[str]:
        patterns = [
            r"：\s*无\s*[。.]?(?=\s*$)",
            r"：\s*/\s*[。.]?(?=\s*$)",
            r"：\s*N/A\s*[。.]?(?=\s*$)",
            r":\s*无\s*[。.]?(?=\s*$)",
            r":\s*/\s*[。.]?(?=\s*$)",
            r":\s*N/A\s*[。.]?(?=\s*$)",
        ]
        matches: list[str] = []
        for pattern in patterns:
            matches.extend(match.group(0).strip() for match in re.finditer(pattern, content, re.M))
        return matches

    def _validate_report_structure(self, report: str) -> None:
        if "每日破圈赚钱情报 (" in report:
            raise ValueError("Report structure invalid: Feishu segment title leaked into report content")
        remaining_markers = self._remaining_empty_markers(report)
        if remaining_markers:
            raise ValueError(f"Report structure invalid after sanitize: empty markers remain {remaining_markers[:5]}")
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

        change_area = report[report.index(SECTION_HEADINGS[1]) : report.index(SECTION_HEADINGS[2])]
        change_blocks = re.findall(r"(?ms)^### \d+\. .*?(?=^### \d+\.|^## 二、|\Z)", change_area)
        for block in change_blocks:
            required = [
                "#### 我的理解",
                "#### 历史类比 / 成熟市场参照",
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
            has_structured_history = all(
                marker in block
                for marker in ["- 可比阶段：", "- 当时带来的机会：", "- 中国是否类似：", "- 对普通人的启发："]
            )
            has_observation_history = NO_HISTORY_REFERENCE in block or "暂无必要类比" in block
            if not has_structured_history and not has_observation_history:
                title = block.splitlines()[0] if block.splitlines() else "unknown"
                raise ValueError(f"Report structure invalid: {title} has invalid history section")

        pain_area = report[report.index(SECTION_HEADINGS[3]) : report.index(SECTION_HEADINGS[4])]
        pain_blocks = re.findall(r"(?ms)^### 痛点 \d+：.*?(?=^### 痛点 \d+：|^## 四、|\Z)", pain_area)
        for block in pain_blocks:
            required = ["- 发达国家/成熟市场是否已有类似产品或服务：", "- 认知破界："]
            missing = [item for item in required if item not in block]
            if missing:
                title = block.splitlines()[0] if block.splitlines() else "unknown"
                raise ValueError(f"Report structure invalid: {title} missing {missing}")
