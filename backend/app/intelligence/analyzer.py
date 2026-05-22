import json
import logging
import re

from app.collectors.base import CollectedItem
from app.intelligence.text import BLOCKED_PHRASES, contains_blocked_phrase
from app.llm.client import LLMClient

logger = logging.getLogger(__name__)

CATEGORIES = ["政治政策", "科技", "商业", "经济", "赚钱机会", "痛点机会"]


class AnalysisService:
    def __init__(self) -> None:
        self.llm = LLMClient()

    async def analyze(self, item: CollectedItem, freshness_score: float) -> dict:
        text = f"{item.title}\n{item.summary}\n{item.content}"[:6000]
        if self.llm.enabled:
            try:
                result = await self._analyze_with_llm(item, text, freshness_score)
                return self._normalize_result(result, item, freshness_score)
            except Exception:
                logger.exception("LLM analysis failed, using heuristic fallback: %s", item.title)
        return self._heuristic(item, text, freshness_score)

    async def _analyze_with_llm(self, item: CollectedItem, text: str, freshness_score: float) -> dict:
        system_prompt = """
你是一个谨慎的 AI 情报分析员，任务是从公开资讯中识别真实变化、赚钱机会、风险和认知升级点。
必须遵守：
1. 不编造来源、案例、数据。
2. 不把不确定机会说成确定赚钱。
3. 对资金盘、传销、博彩、刷单、灰产、虚假副业、割韭菜课程、夸大收益项目、拉人头项目、违法违规项目、擦边项目必须高风险处理。
4. 禁止输出这些表达：轻松月入过万、零基础暴富、稳赚不赔、躺赚、无脑复制。
5. 可信度不足但像机会的内容，只能标为“观察中”。
只返回 JSON，不要 Markdown。
"""
        user_prompt = f"""
请分析这条资讯，返回 JSON。

标题：{item.title}
来源：{item.source}
来源类型：{item.source_type}
时间：{item.published_at or item.event_time}
内容：
{text}

JSON 字段：
category: 政治政策/科技/商业/经济/赚钱机会/痛点机会
summary: 80-160字摘要
credibility: 高/中/低
freshness_label: 确认是过去24小时内/疑似旧闻翻新/时间不明确
is_trustworthy: boolean
has_money_opportunity: boolean
has_cognition_value: boolean
has_cutting_risk: boolean
worth_pushing: boolean
money_score: 0-10
trend_score: 0-10
cognition_score: 0-10
actionability_score: 0-10
risk_score: 0-10
what_happened: string
why_important: string
affected_industries: string
plain_language: string
deep_insight: string
relationship: object，字段包含 ordinary_people, small_business, ecommerce, creators, ai_efficiency, opportunity_seekers
domestic_mapping: object，字段包含 similar_scene, direct_use, migration_target, platforms, personal_value。海外平台新闻必须强制填写中国落地价值。
opportunity: object，字段包含 status(是/否/观察中), name, source, suitable_for, not_suitable_for, monetization, required_skills, startup_cost, path, first_action, three_day_action, risk_level, recommendation_index, mainland_fit, fit_me
cognition: object，字段包含 old, new, judgment_change, long_term_meaning
risk: object，字段包含 packaging_risk, traps, warning_words
historical_reference: object，字段包含 comparable_case, period, changes, opportunities, china_stage, insight。不要硬套历史类比；没有明确案例时 comparable_case 必须写“暂无明确历史类比，但可以从产业逻辑上理解为……”
cognitive_breakthrough: object，字段包含 common_misread, high_level_view, underestimated, old_belief_broken, new_belief, new_judgment, three_year_view。每项要简短、具体、能改变判断，不能写“AI很重要”“趋势很大”。
pain_point: object，字段包含 question, category(生活痛点/工作痛点/生意痛点/内容创作痛点/AI使用痛点/育儿教育痛点), audience, real_need, why_need, current_gap, product, service, content, tool, ai_automation, platforms, mature_market_reference, cognitive_breakthrough, seven_day_action, demand_score, money_score, action_score, trend_score, risk_score

推荐指数必须是 1-5 的整数。字段不能填“无”或“/”，没有明确价值时填“暂无明确价值，但可作为趋势观察”。
如果机会需要融资、硬件研发、专业化学、气候科学、AI底层模型、巨额资本，只能标为观察中或不建议碰。

已知新鲜度分：{freshness_score}
"""
        return await self.llm.analyze_json(system_prompt, user_prompt)

    def _normalize_result(self, result: dict, item: CollectedItem, freshness_score: float) -> dict:
        result["category"] = result.get("category") if result.get("category") in CATEGORIES else self._guess_category(item)
        result["freshness_score"] = freshness_score
        for field in [
            "money_score",
            "trend_score",
            "cognition_score",
            "actionability_score",
            "risk_score",
        ]:
            result[field] = self._score(result.get(field, 0))

        if contains_blocked_phrase(json.dumps(result, ensure_ascii=False)):
            result["risk_score"] = max(result["risk_score"], 8)
            result["has_cutting_risk"] = True
            result["worth_pushing"] = False

        result["final_score"] = self._final_score(result)
        if result["risk_score"] >= 8:
            result["worth_pushing"] = False
        return result

    def _heuristic(self, item: CollectedItem, text: str, freshness_score: float) -> dict:
        lowered = text.lower()
        pain_keywords = [
            "怎么",
            "怎么办",
            "不会",
            "太难",
            "痛点",
            "问题",
            "差评",
            "评论",
            "客服",
            "详情页",
            "主图",
            "选题",
            "播放量",
            "收纳",
            "清洁",
            "育儿",
            "孩子",
            "宠物",
            "老人",
            "prompt",
            "how to",
            "problem",
            "struggling",
            "pain point",
        ]
        money_keywords = ["商业", "收入", "电商", "广告", "平台", "变现", "startup", "saas", "commerce", "marketplace", "付费", "卖", "服务", "工具", "课程", "资料包"]
        trend_keywords = ["发布", "推出", "增长", "监管", "融资", "ai", "人工智能", "自动化", "政策"]
        cognition_keywords = ["变化", "趋势", "转型", "效率", "门槛", "需求", "监管", "成本", "痛点"]
        risk_keywords = BLOCKED_PHRASES + ["课程", "暴富", "副业", "收益", "返利"]

        pain_score = self._keyword_score(lowered, pain_keywords)
        money_score = self._keyword_score(lowered, money_keywords)
        trend_score = self._keyword_score(lowered, trend_keywords)
        cognition_score = self._keyword_score(lowered, cognition_keywords)
        actionability_score = min(8, (money_score + cognition_score + pain_score) / 3)
        risk_score = self._keyword_score(lowered, risk_keywords)
        category = self._guess_category(item)
        if pain_score >= 4 or item.category_hint == "痛点机会":
            category = "痛点机会"
        has_risk = risk_score >= 5 or contains_blocked_phrase(text)
        result = {
            "category": category,
            "summary": item.summary or item.content[:160] or item.title,
            "credibility": "中",
            "freshness_label": "确认是过去24小时内",
            "is_trustworthy": not has_risk,
            "has_money_opportunity": money_score >= 5 or (category == "痛点机会" and pain_score >= 4),
            "has_cognition_value": cognition_score >= 5,
            "has_cutting_risk": has_risk,
            "worth_pushing": not has_risk,
            "freshness_score": freshness_score,
            "money_score": money_score,
            "trend_score": trend_score,
            "cognition_score": cognition_score,
            "actionability_score": actionability_score,
            "risk_score": risk_score,
            "what_happened": item.title,
            "why_important": "这条信息可能代表平台、技术、政策或商业环境中的新变化，需要结合来源继续验证。",
            "affected_industries": category,
            "plain_language": f"简单说，就是：{item.title}",
            "deep_insight": "目前信息有限，先作为公开信号观察。真正值得关注的是它是否降低了成本、改变了流量分配，或让小团队获得新的切入口。",
            "relationship": {
                "ordinary_people": "适合作为信息观察，不建议直接投入资金。",
                "small_business": "可观察是否影响获客、供应链或服务交付。",
                "ecommerce": "若涉及平台规则或消费变化，需要关注店铺和内容策略。",
                "creators": "可观察是否出现新选题、新工具或新分发入口。",
                "ai_efficiency": "如果能自动化重复工作，可进一步验证工具价值。",
                "opportunity_seekers": "先记录信号，再找真实案例验证。",
            },
            "domestic_mapping": {
                "similar_scene": "有，可对照抖音、小红书、淘宝、视频号、公众号、知识付费或企业服务场景。",
                "direct_use": "不能直接照搬，需要先做国内平台、账号、支付和合规迁移。",
                "migration_target": "迁移到国内内容平台、电商平台、私域服务或企业自动化服务。",
                "platforms": "抖音 / 小红书 / 淘宝 / 视频号 / 公众号 / 知识付费 / 企业服务",
                "personal_value": "有观察价值，尤其适合判断 AI、自动化、电商运营和内容变现是否出现新需求。",
            },
            "historical_reference": {
                "comparable_case": "暂无明确历史类比，但可以从产业逻辑上理解为一次成本、效率或分发方式的变化。",
                "period": "时间阶段不明确，先不要硬套发达国家案例。",
                "changes": "需要继续观察它是否真的改变了成本、效率、分发或信任结构。",
                "opportunities": "只有当它能降低成本、扩大分发或形成新服务对象时，才可能出现可验证机会。",
                "china_stage": "中国是否类似还需要看平台规则、用户付费和合规边界。",
                "insight": "先当作趋势信号观察，再用国内真实需求验证，而不是直接照搬。",
            },
            "cognitive_breakthrough": {
                "common_misread": "大多数人会只看标题热度。",
                "high_level_view": "高认知的人会先判断它是否改变成本、效率、分发或信任结构。",
                "underestimated": "过去容易低估小团队把趋势翻译成具体服务的能力。",
                "old_belief_broken": "旧认知是看到新技术就急着找大机会。",
                "new_belief": "新认知是先拆成人群、场景、付费理由和第一动作。",
                "new_judgment": "先判断它能否形成可验证的人群、场景和第一动作。",
                "three_year_view": "如果趋势持续，它可能变成某个行业的标准工作流，而不只是今天的新闻。",
            },
            "pain_point": {
                "question": item.title,
                "category": self._guess_pain_category(text),
                "audience": self._guess_audience(text),
                "real_need": "用户想更省时间、更省心或更低成本地解决这个具体问题。",
                "why_need": "它对应重复出现的生活、工作、生意或内容创作问题，具备被商品、服务、内容或工具承接的可能。",
                "current_gap": "现有方案往往太泛，不够场景化，用户不知道该买什么、怎么做、找谁解决。",
                "product": "可以做低价小商品、资料包、模板或清单。",
                "service": "可以做诊断、代设置、陪跑、整理或一对一解决服务。",
                "content": "可以做小红书/抖音系列内容：真实问题、对比方案、避坑清单。",
                "tool": "可以做表格、清单、计算器、流程模板或轻量工具。",
                "ai_automation": "可以用 AI 做问答助手、自动回复、文案生成、资料整理或流程自动化。",
                "platforms": "小红书 / 抖音 / 淘宝 / 拼多多 / 公众号 / 1688",
                "mature_market_reference": "暂无明确成熟市场参照，但可以先从人群、场景、频次和付费意愿判断是否值得验证。",
                "cognitive_breakthrough": "真正的机会不是问题被很多人讨论，而是它能被做成低成本、可交付、可验证的商品、内容或服务。",
                "seven_day_action": "今天在小红书、淘宝、拼多多搜索相关关键词，记录前 20 个结果的价格、差评痛点和卖点。",
                "demand_score": min(10, pain_score + 2),
                "money_score": money_score,
                "action_score": actionability_score,
                "trend_score": trend_score,
                "risk_score": risk_score,
            },
            "opportunity": {
                "status": "观察中" if money_score >= 5 else "否",
                "name": item.title[:60],
                "source": item.source,
                "suitable_for": "有相关行业经验或能低成本验证的人",
                "not_suitable_for": "不适合没有时间验证、只想直接复制收益的人。",
                "monetization": "先做服务、内容或工具验证，不建议重资产投入。",
                "required_skills": "信息验证、客户访谈、基础自动化能力",
                "startup_cost": "低到中，取决于验证方式",
                "path": "收集案例 -> 找痛点 -> 做小样本验证 -> 再考虑放大",
                "first_action": "保存来源链接，找 3 个真实用户或商家验证需求。",
                "three_day_action": "第 1 天收集 10 条需求，第 2 天做 1 页服务说明，第 3 天找 3 个潜在用户验证。",
                "risk_level": "高" if has_risk else "中",
                "recommendation_index": 2,
                "mainland_fit": "可作为中国大陆普通人的趋势观察，不建议直接照搬。",
                "fit_me": "适合作为 AI、自动化、电商或内容变现方向的观察素材。",
            },
            "cognition": {
                "old": "只看新闻标题判断机会。",
                "new": "先判断变化是否真实，再判断它是否带来成本、效率或流量结构变化。",
                "judgment_change": "不因热度直接行动，先验证信号质量。",
                "long_term_meaning": "持续记录信号，能逐步形成自己的行业雷达。",
            },
            "risk": {
                "packaging_risk": "可能被包装成夸大收益项目，需要警惕。",
                "traps": "不要只看收益承诺，要看真实客户、真实交付和合规性。",
                "warning_words": "、".join(BLOCKED_PHRASES),
            },
        }
        result["final_score"] = self._final_score(result)
        if result["risk_score"] >= 8:
            result["worth_pushing"] = False
        return result

    def _guess_category(self, item: CollectedItem) -> str:
        text = f"{item.category_hint or ''} {item.title}".lower()
        if any(word in text for word in ["政策", "监管", "政府", "politic"]):
            return "政治政策"
        if any(word in text for word in ["ai", "科技", "模型", "软件", "tech"]):
            return "科技"
        if any(word in text for word in ["经济", "利率", "消费", "gdp"]):
            return "经济"
        if any(word in text for word in ["赚钱", "变现", "副业", "opportunity"]):
            return "赚钱机会"
        if any(word in text for word in ["痛点", "问题", "怎么", "怎么办", "how to", "struggling", "pain point"]):
            return "痛点机会"
        return item.category_hint or "商业"

    def _guess_pain_category(self, text: str) -> str:
        lowered = text.lower()
        if any(word in lowered for word in ["孩子", "宝宝", "育儿", "作业", "parent", "kid"]):
            return "育儿教育痛点"
        if any(word in lowered for word in ["淘宝", "客服", "详情页", "主图", "选品", "ecommerce", "shop"]):
            return "生意痛点"
        if any(word in lowered for word in ["小红书", "抖音", "播放量", "剪辑", "creator", "video"]):
            return "内容创作痛点"
        if any(word in lowered for word in ["ai", "prompt", "自动化", "workflow"]):
            return "AI使用痛点"
        if any(word in lowered for word in ["办公", "效率", "表格", "资料", "工作"]):
            return "工作痛点"
        return "生活痛点"

    def _guess_audience(self, text: str) -> str:
        lowered = text.lower()
        if any(word in lowered for word in ["孩子", "宝宝", "育儿", "parent", "kid"]):
            return "宝妈、家长、老师或学生"
        if any(word in lowered for word in ["淘宝", "客服", "电商", "ecommerce", "shop"]):
            return "淘宝/拼多多/抖音电商卖家"
        if any(word in lowered for word in ["creator", "video", "小红书", "抖音"]):
            return "内容创作者和小商家"
        if any(word in lowered for word in ["ai", "prompt", "workflow", "自动化"]):
            return "想用 AI 提效的职场人、小团队或个体户"
        return "有具体生活、工作或经营问题的人群"

    def _keyword_score(self, text: str, keywords: list[str]) -> float:
        hits = sum(1 for keyword in keywords if keyword.lower() in text)
        return min(10.0, hits * 2.0)

    def _score(self, value) -> float:
        try:
            return max(0.0, min(10.0, float(value)))
        except (TypeError, ValueError):
            return 0.0

    def _final_score(self, result: dict) -> float:
        return round(
            result["freshness_score"] * 0.2
            + result["money_score"] * 0.3
            + result["trend_score"] * 0.2
            + result["cognition_score"] * 0.2
            + result["actionability_score"] * 0.1
            - result["risk_score"] * 0.3,
            2,
        )
