from datetime import datetime
import json
import logging
import traceback

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.collectors.source_registry import SourceRegistry
from app.core.config import get_settings
from app.core.time import daily_window, now_local
from app.db.models import IntelligenceItem, PushLog, Report, RunLog
from app.intelligence.analyzer import AnalysisService
from app.intelligence.dedupe import DedupeService
from app.intelligence.report_builder import ReportBuilder
from app.notifications.email import EmailNotifier
from app.notifications.feishu import FeishuNotifier

logger = logging.getLogger(__name__)


class DailyReportJob:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.registry = SourceRegistry()
        self.dedupe = DedupeService()
        self.analyzer = AnalysisService()
        self.report_builder = ReportBuilder()
        self.feishu = FeishuNotifier()
        self.email = EmailNotifier()

    async def run(self, db: Session, reference_time: datetime | None = None) -> dict:
        window_start, window_end = daily_window(reference_time)
        run_log = RunLog(
            job_name="daily_report",
            status="running",
            window_start=window_start,
            window_end=window_end,
            started_at=now_local(),
        )
        db.add(run_log)
        db.commit()
        db.refresh(run_log)

        try:
            logger.info("Daily report window: %s - %s", window_start, window_end)
            collected = self.registry.collect_all(db)
            fresh = [
                item
                for item in collected
                if self._is_fresh(item.event_time or item.published_at, window_start, window_end)
            ]
            logger.info("Fresh items: %s/%s", len(fresh), len(collected))

            deduped = self.dedupe.filter_new(db, fresh)
            saved_items: list[IntelligenceItem] = []

            for deduped_item in deduped:
                source_item = deduped_item.item
                event_time = source_item.event_time or source_item.published_at
                freshness_score = self._freshness_score(event_time, window_start, window_end)
                analysis = await self.analyzer.analyze(source_item, freshness_score)
                db_item = IntelligenceItem(
                    title=source_item.title,
                    url=source_item.url,
                    source=source_item.source,
                    source_type=source_item.source_type,
                    category=analysis.get("category"),
                    published_at=source_item.published_at,
                    event_time=event_time,
                    collected_at=now_local(),
                    summary=analysis.get("summary") or source_item.summary,
                    content=source_item.content,
                    content_hash=deduped_item.content_hash,
                    semantic_hash=deduped_item.semantic_hash,
                    freshness_score=analysis.get("freshness_score", freshness_score),
                    money_score=analysis.get("money_score", 0),
                    trend_score=analysis.get("trend_score", 0),
                    cognition_score=analysis.get("cognition_score", 0),
                    actionability_score=analysis.get("actionability_score", 0),
                    risk_score=analysis.get("risk_score", 0),
                    final_score=analysis.get("final_score", 0),
                    credibility=analysis.get("credibility"),
                    freshness_label=analysis.get("freshness_label"),
                    is_fresh=True,
                    is_duplicate=False,
                    is_trustworthy=bool(analysis.get("is_trustworthy")),
                    has_money_opportunity=bool(analysis.get("has_money_opportunity")),
                    has_cognition_value=bool(analysis.get("has_cognition_value")),
                    has_cutting_risk=bool(analysis.get("has_cutting_risk")),
                    worth_pushing=self._worth_pushing(analysis),
                    analysis_json=json.dumps(analysis, ensure_ascii=False),
                )
                db.add(db_item)
                try:
                    db.commit()
                    db.refresh(db_item)
                    saved_items.append(db_item)
                except IntegrityError:
                    db.rollback()
                    logger.info("Skipped duplicate during save: %s", source_item.url)

            window_items = (
                db.query(IntelligenceItem)
                .filter(
                    IntelligenceItem.event_time >= window_start,
                    IntelligenceItem.event_time < window_end,
                )
                .order_by(IntelligenceItem.final_score.desc())
                .all()
            )
            push_items = [
                item
                for item in window_items
                if item.worth_pushing and item.final_score >= self.settings.min_final_score
            ]
            report_date = window_end.strftime("%Y-%m-%d")
            report_content = await self.report_builder.build(
                report_date=report_date,
                window_start=window_start,
                window_end=window_end,
                items=push_items,
                observed_items=window_items,
            )
            report = Report(
                report_date=report_date,
                window_start=window_start,
                window_end=window_end,
                title=f"每日破圈赚钱情报 {report_date}",
                content=report_content,
                item_count=len(push_items),
            )
            db.add(report)
            db.commit()
            db.refresh(report)

            await self._push_report(db, report, push_items)

            run_log.status = "success"
            run_log.finished_at = now_local()
            run_log.message = (
                f"collected={len(collected)}, fresh={len(fresh)}, "
                f"deduped={len(deduped)}, saved={len(saved_items)}, "
                f"window_items={len(window_items)}, pushed={len(push_items)}"
            )
            db.commit()

            return {
                "run_id": run_log.id,
                "report_id": report.id,
                "status": "success",
                "window_start": window_start.isoformat(),
                "window_end": window_end.isoformat(),
                "collected": len(collected),
                "fresh": len(fresh),
                "deduped": len(deduped),
                "saved": len(saved_items),
                "window_items": len(window_items),
                "pushed": len(push_items),
            }
        except Exception as exc:
            logger.exception("Daily report job failed")
            run_log.status = "failed"
            run_log.finished_at = now_local()
            run_log.error = traceback.format_exc()
            db.commit()
            await self._send_failure_alert(db, str(exc), run_log.error)
            raise

    def _is_fresh(
        self, value: datetime | None, window_start: datetime, window_end: datetime
    ) -> bool:
        if value is None:
            return False
        return window_start <= value < window_end

    def _freshness_score(
        self, value: datetime | None, window_start: datetime, window_end: datetime
    ) -> float:
        if value is None or not self._is_fresh(value, window_start, window_end):
            return 0.0
        total_seconds = (window_end - window_start).total_seconds()
        age_seconds = (window_end - value).total_seconds()
        return round(max(6.0, min(10.0, 10 - (age_seconds / total_seconds) * 4)), 2)

    def _worth_pushing(self, analysis: dict) -> bool:
        if analysis.get("has_cutting_risk") or analysis.get("risk_score", 0) >= 8:
            return False
        return bool(analysis.get("worth_pushing")) and bool(analysis.get("is_trustworthy"))

    async def _push_report(
        self, db: Session, report: Report, push_items: list[IntelligenceItem]
    ) -> None:
        if self.settings.push_dry_run:
            pushed_at = now_local()
            report.pushed_at = pushed_at
            for item in push_items:
                item.pushed_at = pushed_at
            db.add(
                PushLog(
                    report_id=report.id,
                    channel="dry_run",
                    status="success",
                    message="Push skipped because PUSH_DRY_RUN=true",
                )
            )
            db.commit()
            return

        pushed = False
        try:
            await self.feishu.send_markdown(report.content)
            pushed = True
            db.add(PushLog(report_id=report.id, channel="feishu", status="success"))
        except Exception as exc:
            logger.exception("Feishu push failed")
            db.add(
                PushLog(
                    report_id=report.id,
                    channel="feishu",
                    status="failed",
                    error=str(exc),
                )
            )
            try:
                self.email.send(report.title, report.content)
                pushed = True
                db.add(PushLog(report_id=report.id, channel="email", status="success"))
            except Exception as email_exc:
                logger.exception("Email fallback failed")
                db.add(
                    PushLog(
                        report_id=report.id,
                        channel="email",
                        status="failed",
                        error=str(email_exc),
                    )
                )
                db.commit()
                raise

        if pushed:
            pushed_at = now_local()
            report.pushed_at = pushed_at
            for item in push_items:
                item.pushed_at = pushed_at
            db.commit()

    async def _send_failure_alert(self, db: Session, message: str, detail: str | None) -> None:
        hint = self._failure_hint(message, detail)
        detail_excerpt = (detail or "").strip()
        detail_line = f"- 详细信息：{detail_excerpt[:500]}\n\n" if detail_excerpt else ""
        content = (
            "# 每日破圈赚钱情报运行失败\n\n"
            f"- 时间：{now_local():%Y-%m-%d %H:%M:%S}\n"
            f"- 错误：{message}\n\n"
            f"{detail_line}"
            f"- 排查线索：{hint}\n\n"
            "请检查服务日志和数据源配置。"
        )
        try:
            await self.feishu.send_markdown(content)
            db.add(PushLog(report_id=None, channel="feishu", status="failure_alert_sent"))
        except Exception as exc:
            logger.exception("Feishu failure alert failed")
            db.add(PushLog(report_id=None, channel="feishu", status="failed", error=str(exc)))
            try:
                self.email.send("每日破圈赚钱情报运行失败", f"{content}\n\n{detail or ''}")
                db.add(PushLog(report_id=None, channel="email", status="failure_alert_sent"))
            except Exception as email_exc:
                db.add(
                    PushLog(
                        report_id=None,
                        channel="email",
                        status="failed",
                        error=str(email_exc),
                    )
                )
        finally:
            db.commit()

    def _failure_hint(self, message: str, detail: str | None) -> str:
        text = f"{message}\n{detail or ''}"
        if "Report structure invalid" in text:
            if "missing" in text:
                return "日报结构缺少必需模块，错误信息中通常包含具体标题和缺失字段。"
            if "empty marker" in text:
                return "日报中出现普通空值标记，请检查对应字段的 AI 输出或 fallback。"
            if "Feishu segment title" in text:
                return "飞书分段标题混入日报正文，请检查 report.content 和 Feishu 分段逻辑。"
            return "日报结构校验失败，请优先查看错误中的标题、字段或模块名称。"
        return "非结构校验错误，请检查采集、AI 分析、数据库和推送日志。"
