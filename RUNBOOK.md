# RUNBOOK

## 项目

每日商业观察系统：FastAPI + SQLite + APScheduler + 飞书机器人 Webhook 的公开资讯日报系统。

## 启动

```powershell
cd "C:\Users\Administrator\Documents\tigaorenzhi"
cd backend
python -m pip install -r requirements.txt
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

访问：

- 健康检查：http://127.0.0.1:8000/health
- 后台：http://127.0.0.1:8000/admin
- API 文档：http://127.0.0.1:8000/docs

## 安全运行

- 不读取 `.env`，如需推送测试，优先使用 `.env.example` 的字段说明。
- 没有用户确认前，不配置真实飞书 Webhook、不发真实群消息、不连接生产数据库。
- 可使用 `PUSH_DRY_RUN=true` 做本地演练。

## 验证

```powershell
cd "C:\Users\Administrator\Documents\tigaorenzhi\backend"
python -m compileall app
python -m pytest -q
```

当前已验证命令：

```powershell
cd "C:\Users\Administrator\Documents\tigaorenzhi"
python -m compileall backend/app
pytest -q
```

本地 dry-run 日报验证：

```powershell
cd "C:\Users\Administrator\Documents\tigaorenzhi\backend"
$env:DATABASE_URL='sqlite:///./data/quality_consolidation_dryrun.db'
$env:PUSH_DRY_RUN='true'
$env:AI_API_KEY=''
$env:OPENAI_API_KEY=''
$env:DEEPSEEK_API_KEY=''
$env:QWEN_API_KEY=''
$env:SOURCES_CONFIG_PATH='./config/sources.json'
python -m uvicorn app.main:app --host 127.0.0.1 --port 8037
```

另开终端触发：

```powershell
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8037/api/runs/daily
```

dry-run 结束后删除临时库：

```powershell
Remove-Item .\data\quality_consolidation_dryrun.db -Force
```

## 质量验收重点

- `report.content` 只允许开头出现 `# 每日商业观察`，正文中间不能再出现单独标题或 `(2/3)` 分段标题。
- 飞书 markdown payload 正文字段不能包含分段标题；标题只能作为卡片 header。
- 固定的是目标，不是结构：不要强制输出机会雷达、历史类比、国内映射、赚钱机会、三天行动或风险提醒。
- 每天只保留真正有价值的动态段落；没有价值的段落不输出。
- 当天没有高价值内容时，只输出“今天没有发现值得占用你时间的重要变化。”。
- 选题来自全球真实变化；用户历史信息只能用于解释案例、判断相关性和提供落地角度，不能用于选新闻或强行制造机会。
- `/api/trends` 应记录高价值变化，作为长期世界变化数据库的复盘基础。

## 继续规则

1. 读 `progress.md`、`TODO_AI.md`、`error_log.md`。
2. 优先做 P0 中最小的安全任务。
3. 修改后运行相关验证。
4. 更新 `progress.md`；失败写入 `error_log.md`。
