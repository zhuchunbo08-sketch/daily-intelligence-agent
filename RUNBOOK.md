# RUNBOOK

## 项目

每日破圈赚钱情报系统：FastAPI + SQLite + APScheduler + 飞书机器人 Webhook 的公开资讯日报系统。

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

- `report.content` 只允许开头出现 `# 每日破圈赚钱情报`，正文中间不能再出现单独标题或 `(2/3)` 分段标题。
- 飞书 markdown payload 正文字段不能包含分段标题；标题只能作为卡片 header。
- 今日赚钱机会雷达最多 3 条，宁可少，不凑数。
- 今日行动建议最多 1 条；没有高质量机会时写“今天不建议行动，只观察趋势。”
- 反割韭菜提醒最多 2 条，风险概念和判断方法不能跨新闻串台。
- 痛点、机会雷达、行动建议、商业模式、认知模块必须围绕同一个主机会保持一致。
- 观察中新闻必须短，不给 3 天动作，不进入机会雷达。

## 继续规则

1. 读 `progress.md`、`TODO_AI.md`、`error_log.md`。
2. 优先做 P0 中最小的安全任务。
3. 修改后运行相关验证。
4. 更新 `progress.md`；失败写入 `error_log.md`。
