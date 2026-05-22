# 每日破圈赚钱情报系统

《每日破圈赚钱情报系统》是一个长期运行的 AI 情报自动化项目。第一版使用 FastAPI + SQLite + APScheduler + 飞书机器人 Webhook，每天北京时间 07:00 自动抓取昨天 07:00 到今天 07:00 的公开资讯，去重、过滤、分析后生成日报并推送到飞书。

第一版不做微信外挂、不读 Cookie、不模拟点击、不绕过平台风控。

## 已实现能力

- FastAPI 后端服务。
- SQLite 数据库。
- JSON 数据源配置。
- APScheduler 定时任务，每天北京时间 07:00 运行。
- 手动触发日报接口。
- 严格按昨天 07:00 到今天 07:00 的时间窗口处理。
- URL 去重、标题相似度去重、内容 hash 去重、语义 hash 去重。
- AI 分类、机会识别、风险识别、深度理解、认知升级提炼。
- 政治政策、科技、商业、经济、赚钱机会分类。
- 明显割韭菜内容过滤。
- 固定格式 Markdown 日报。
- 飞书机器人 Webhook 推送。
- 飞书签名支持。
- 飞书消息过长自动分段。
- 邮件备用通道。
- 失败日志和失败提醒。
- 极简后台查看历史日报和手动操作。
- Docker Compose 部署。

## 项目结构

```text
daily-intelligence-agent/
├── backend/
│   ├── app/
│   │   ├── main.py
│   │   ├── api/
│   │   ├── collectors/
│   │   ├── core/
│   │   ├── db/
│   │   ├── intelligence/
│   │   ├── jobs/
│   │   ├── llm/
│   │   ├── notifications/
│   │   └── prompts/
│   ├── config/sources.json
│   ├── Dockerfile
│   ├── README.md
│   └── requirements.txt
├── docs/
├── docker-compose.yml
├── .env.example
└── README.md
```

## 本地运行

```bash
cp .env.example .env
cd backend
python -m pip install -r requirements.txt
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

打开：

- 健康检查：http://127.0.0.1:8000/health
- 极简后台：http://127.0.0.1:8000/admin
- API 文档：http://127.0.0.1:8000/docs

如果暂时没有飞书机器人，可以在 `.env` 设置：

```env
PUSH_DRY_RUN=true
```

这样会生成日报和记录日志，但不会真实推送。

## Docker Compose 运行

```bash
cp .env.example .env
docker compose up --build -d
docker compose logs -f backend
```

手动触发一次：

```bash
curl -X POST http://127.0.0.1:8000/api/runs/daily
```

## 核心配置

`.env.example` 已包含所有必需配置，最少需要关注：

```env
APP_TIMEZONE=Asia/Shanghai
DAILY_RUN_HOUR=7
DAILY_RUN_MINUTE=0
DATABASE_URL=sqlite:///./daily_intelligence.db
AI_BASE_URL=https://api.deepseek.com
AI_API_KEY=
AI_MODEL=deepseek-v4-flash

# Optional compatibility aliases
OPENAI_API_KEY=
OPENAI_MODEL=gpt-4.1-mini
FEISHU_WEBHOOK=
FEISHU_SECRET=
EMAIL_HOST=
EMAIL_PORT=587
EMAIL_USER=
EMAIL_PASSWORD=
EMAIL_TO=
PROXY_URL=
```

## 飞书机器人配置

1. 在飞书群里添加“自定义机器人”。
2. 复制 Webhook 到 `.env`：

```env
FEISHU_WEBHOOK=https://open.feishu.cn/open-apis/bot/v2/hook/xxxx
```

3. 如果机器人开启“签名校验”，复制 Secret：

```env
FEISHU_SECRET=xxxx
```

系统会自动按飞书规则生成签名。日报过长时会按 `FEISHU_MAX_MESSAGE_CHARS` 自动拆分。

## 邮件备用通道

飞书失败时，系统会尝试邮件备用：

```env
EMAIL_HOST=smtp.example.com
EMAIL_PORT=587
EMAIL_USER=your@example.com
EMAIL_PASSWORD=邮箱授权码
EMAIL_TO=receiver@example.com
```

## 常用接口

- `POST /api/runs/daily`：手动生成今日情报。
- `GET /api/runs`：查看运行记录。
- `GET /api/reports`：查看历史日报列表。
- `GET /api/reports/latest`：查看最新日报。
- `GET /api/reports/{report_id}`：查看指定日报。
- `POST /api/reports/{report_id}/push`：手动补推送指定日报。
- `GET /api/reports/{report_id}/items`：查看日报时间窗口内的资讯。
- `GET /api/sources`：查看数据源。
- `POST /api/sources/sync`：同步数据源配置。
- `GET /api/opportunities`：查看机会列表。
- `GET /api/settings`：查看非敏感运行配置。

## 修改推送时间

修改 `.env`：

```env
DAILY_RUN_HOUR=7
DAILY_RUN_MINUTE=0
```

重启服务后生效。时间按 `APP_TIMEZONE=Asia/Shanghai` 解释。

## 新增数据源

编辑 [backend/config/sources.json](backend/config/sources.json)：

```json
{
  "name": "Example RSS",
  "type": "rss",
  "url": "https://example.com/feed.xml",
  "category_hint": "科技",
  "enabled": true
}
```

保存后重启，或调用：

```bash
curl -X POST http://127.0.0.1:8000/api/sources/sync
```

## 更换 AI 模型

系统统一使用 OpenAI-compatible AI Client。推荐优先配置这三个变量：

```env
AI_BASE_URL=https://api.deepseek.com
AI_API_KEY=你的 key
AI_MODEL=deepseek-v4-flash
```

分类、摘要、风险识别、深度理解、认知升级和日报生成都会走同一个 AI Client。

如果不配置任何 AI Key，系统仍会运行，并退回到本地启发式分析和模板日报，只是质量会弱一些。

### DeepSeek

```env
AI_BASE_URL=https://api.deepseek.com
AI_API_KEY=你的 DeepSeek API Key
AI_MODEL=deepseek-v4-flash
```

也可以使用兼容变量：

```env
DEEPSEEK_API_KEY=你的 DeepSeek API Key
DEEPSEEK_MODEL=deepseek-v4-flash
```

### 通义千问

```env
AI_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
AI_API_KEY=你的 DashScope API Key
AI_MODEL=qwen-plus
```

也可以使用兼容变量：

```env
QWEN_API_KEY=你的 DashScope API Key
QWEN_MODEL=qwen-plus
```

### OpenAI

```env
AI_BASE_URL=https://api.openai.com/v1
AI_API_KEY=你的 OpenAI API Key
AI_MODEL=gpt-4.1-mini
```

也可以使用兼容变量：

```env
OPENAI_API_KEY=你的 OpenAI API Key
OPENAI_MODEL=gpt-4.1-mini
```

优先级：

1. `AI_API_KEY`
2. `DEEPSEEK_API_KEY`
3. `QWEN_API_KEY`
4. `OPENAI_API_KEY`

## 日志

Docker：

```bash
docker compose logs -f backend
```

本地文件：

```bash
tail -f logs/app.log
```

## 云服务器部署

完整说明见 [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md)。

## 数据库表结构

完整说明见 [docs/DATABASE.md](docs/DATABASE.md)。

## 常见报错

完整说明见 [docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md)。
