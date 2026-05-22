# 配置说明

复制 `.env.example` 为 `.env` 后修改。

```bash
cp .env.example .env
```

## 基础配置

```env
APP_TIMEZONE=Asia/Shanghai
DAILY_RUN_HOUR=7
DAILY_RUN_MINUTE=0
DATABASE_URL=sqlite:///./daily_intelligence.db
```

本地直接运行时，数据库会写到当前工作目录的 `daily_intelligence.db`。

Docker Compose 部署时会覆盖为：

```env
DATABASE_URL=sqlite:///./data/daily_intelligence.db
```

这样数据库会持久化到宿主机 `./data`。

## AI 模型

系统统一使用 OpenAI-compatible AI Client。推荐只配置：

```env
AI_BASE_URL=https://api.deepseek.com
AI_API_KEY=你的 key
AI_MODEL=deepseek-v4-flash
```

分类、摘要、风险识别、深度理解、认知升级和日报生成都会走同一个 AI Client。

没有配置任何 AI Key 时，系统仍会运行，并退回本地启发式分析和模板日报。

### DeepSeek

```env
AI_BASE_URL=https://api.deepseek.com
AI_API_KEY=你的 DeepSeek API Key
AI_MODEL=deepseek-v4-flash
```

兼容快捷变量：

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

兼容快捷变量：

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

兼容快捷变量：

```env
OPENAI_API_KEY=sk-xxxx
OPENAI_MODEL=gpt-4.1-mini
```

优先级：

1. `AI_API_KEY`
2. `DEEPSEEK_API_KEY`
3. `QWEN_API_KEY`
4. `OPENAI_API_KEY`

## 飞书机器人

在飞书群里添加自定义机器人，复制 Webhook：

```env
FEISHU_WEBHOOK=https://open.feishu.cn/open-apis/bot/v2/hook/xxx
```

兼容旧变量：

```env
FEISHU_WEBHOOK_URL=https://open.feishu.cn/open-apis/bot/v2/hook/xxx
```

日报过长会按这个长度拆分：

```env
FEISHU_MAX_MESSAGE_CHARS=3500
```

## 飞书签名

如果飞书机器人开启了“签名校验”，填写：

```env
FEISHU_SECRET=xxxx
```

系统会自动按飞书规则生成 timestamp 和 sign。

## 邮件备用通道

飞书推送失败时会尝试邮件：

```env
EMAIL_HOST=smtp.example.com
EMAIL_PORT=587
EMAIL_USER=your@example.com
EMAIL_PASSWORD=邮箱授权码
EMAIL_TO=receiver@example.com
```

兼容旧变量：

```env
SMTP_HOST=smtp.example.com
SMTP_PORT=587
SMTP_USERNAME=your@example.com
SMTP_PASSWORD=邮箱授权码
SMTP_FROM=your@example.com
SMTP_TO=receiver@example.com
SMTP_USE_TLS=true
```

## 代理

如果服务器访问 AI、飞书或 GDELT 不稳定：

```env
PROXY_URL=http://127.0.0.1:7890
```

## 数据源

数据源配置在：

```text
backend/config/sources.json
```

支持：

- `rss`
- `gdelt`

新增 RSS 示例：

```json
{
  "name": "Example RSS",
  "type": "rss",
  "url": "https://example.com/feed.xml",
  "category_hint": "科技",
  "enabled": true
}
```

新增后同步：

```bash
curl -X POST http://127.0.0.1:8000/api/sources/sync
```
