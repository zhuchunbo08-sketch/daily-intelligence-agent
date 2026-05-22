# 数据库表结构说明

默认数据库是 SQLite。

本地直接运行时，`.env.example` 默认：

```env
DATABASE_URL=sqlite:///./daily_intelligence.db
```

Docker Compose 部署时会覆盖为：

```env
DATABASE_URL=sqlite:///./data/daily_intelligence.db
```

这样数据库会保存在宿主机 `./data` 目录。

## sources

数据源表，由 `backend/config/sources.json` 同步而来。

字段：

- `id`：主键。
- `name`：数据源名称，唯一。
- `source_type`：数据源类型，目前支持 `rss`、`gdelt`。
- `url`：抓取地址。
- `query`：搜索查询语句，主要给 GDELT 使用。
- `category_hint`：默认分类提示。
- `enabled`：是否启用。
- `created_at`：创建时间。
- `updated_at`：更新时间。

## intelligence_items

资讯主表。每条资讯必须保存的核心字段都在这里。

字段：

- `id`：主键。
- `title`：标题。
- `url`：来源链接，唯一。
- `source`：来源名称。
- `source_type`：来源类型。
- `category`：AI 分类，政治政策 / 科技 / 商业 / 经济 / 赚钱机会。
- `published_at`：发布时间。
- `event_time`：事件时间，时间过滤主要使用这个字段。
- `collected_at`：采集时间。
- `summary`：摘要。
- `content`：清洗后的正文或摘要正文。
- `content_hash`：内容 hash，唯一，用于内容去重。
- `semantic_hash`：语义 hash，用于近似语义去重。
- `freshness_score`：新鲜度。
- `money_score`：赚钱相关度。
- `trend_score`：趋势价值。
- `cognition_score`：认知升级价值。
- `actionability_score`：可行动性。
- `risk_score`：风险程度。
- `final_score`：最终分数。
- `pushed_at`：被推送时间。
- `credibility`：可信度，高 / 中 / 低。
- `freshness_label`：新鲜度判断。
- `is_fresh`：是否是时间窗口内新内容。
- `is_duplicate`：是否重复。
- `is_trustworthy`：是否可信。
- `has_money_opportunity`：是否包含赚钱机会。
- `has_cognition_value`：是否有认知升级价值。
- `has_cutting_risk`：是否有割韭菜风险。
- `worth_pushing`：是否值得推送。
- `analysis_json`：AI 完整分析结果。

## reports

日报表。

字段：

- `id`：主键。
- `report_date`：日报日期。
- `window_start`：覆盖时间开始。
- `window_end`：覆盖时间结束。
- `title`：日报标题。
- `content`：Markdown 日报正文。
- `item_count`：推送进入日报的重点资讯数量。
- `pushed_at`：推送时间。
- `created_at`：生成时间。

## run_logs

任务运行记录。

字段：

- `id`：主键。
- `job_name`：任务名称。
- `status`：running / success / failed。
- `window_start`：本次任务时间窗口开始。
- `window_end`：本次任务时间窗口结束。
- `started_at`：开始时间。
- `finished_at`：结束时间。
- `message`：统计信息。
- `error`：异常堆栈。

## push_logs

推送记录。

字段：

- `id`：主键。
- `report_id`：日报 ID。
- `channel`：feishu / email / dry_run。
- `status`：success / failed / failure_alert_sent。
- `message`：说明。
- `error`：错误信息。
- `created_at`：记录时间。
