# 运维说明

## 本地运行

```bash
cp .env.example .env
cd backend
python -m pip install -r requirements.txt
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

本地没有飞书时，可以设置：

```env
PUSH_DRY_RUN=true
```

## 常用地址

- 健康检查：http://127.0.0.1:8000/health
- 极简后台：http://127.0.0.1:8000/admin
- API 文档：http://127.0.0.1:8000/docs

## 手动运行一次日报

```bash
curl -X POST http://127.0.0.1:8000/api/runs/daily
```

这个接口会重新跑完整流程：

1. 抓取数据源。
2. 只保留昨天 07:00 到今天 07:00 的内容。
3. 去重。
4. AI 分析。
5. 生成日报。
6. 推送或干跑推送。
7. 写入日志。

## 查看日志

Docker：

```bash
docker compose logs -f backend
```

本地：

```bash
tail -f logs/app.log
```

Windows PowerShell：

```powershell
Get-Content backend\logs\app.log -Wait
```

## 确认每天早上 7 点会自动运行

查看当前配置：

```bash
curl http://127.0.0.1:8000/api/settings
```

确认返回：

```json
{
  "timezone": "Asia/Shanghai",
  "daily_run_hour": 7,
  "daily_run_minute": 0
}
```

查看运行记录：

```bash
curl http://127.0.0.1:8000/api/runs
```

## 修改推送时间

修改 `.env`：

```env
DAILY_RUN_HOUR=8
DAILY_RUN_MINUTE=30
```

重启服务：

```bash
docker compose restart backend
```

时间按 `APP_TIMEZONE=Asia/Shanghai` 解释。

## 查看历史日报

后台：

```text
http://127.0.0.1:8000/admin
```

接口：

```bash
curl http://127.0.0.1:8000/api/reports
curl http://127.0.0.1:8000/api/reports/latest
curl http://127.0.0.1:8000/api/reports/1
```

## 手动重新生成日报

```bash
curl -X POST http://127.0.0.1:8000/api/runs/daily
```

如果同一时间窗口的资讯已经保存过，系统不会重复保存，但会基于数据库里已有的窗口内资讯重新生成日报。

## 手动补推送

```bash
curl -X POST http://127.0.0.1:8000/api/reports/1/push
```

也可以在 `/admin` 点击“补推最新日报”。

## 新增数据源

编辑：

```text
backend/config/sources.json
```

然后同步：

```bash
curl -X POST http://127.0.0.1:8000/api/sources/sync
```

## 更换 AI 模型

修改 `.env` 后重启服务。

推荐使用统一变量：

```env
AI_BASE_URL=https://api.deepseek.com
AI_API_KEY=你的 key
AI_MODEL=deepseek-v4-flash
```

DeepSeek：

```env
AI_BASE_URL=https://api.deepseek.com
AI_API_KEY=你的 DeepSeek API Key
AI_MODEL=deepseek-v4-flash
```

通义千问：

```env
AI_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
AI_API_KEY=你的 DashScope API Key
AI_MODEL=qwen-plus
```

OpenAI：

```env
AI_BASE_URL=https://api.openai.com/v1
AI_API_KEY=你的 OpenAI API Key
AI_MODEL=gpt-4.1-mini
```

## 失败提醒

任务失败时：

1. 写入 `run_logs`。
2. 写入 `push_logs`。
3. 优先发送飞书失败提醒。
4. 飞书失败后尝试邮件提醒。

## 过滤规则

以下内容会被高风险处理或阻断推送：

- 资金盘
- 传销
- 博彩
- 灰产
- 刷单
- 虚假副业
- 割韭菜课程
- 夸大收益项目
- 需要拉人头项目
- 违法违规项目
- 擦边项目
- 没有真实案例的项目
- 过时旧闻
- 营销号重复洗稿
- 标题党内容
