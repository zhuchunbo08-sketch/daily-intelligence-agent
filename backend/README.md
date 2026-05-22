# Backend

FastAPI 后端服务，负责抓取、过滤、分析、生成日报、推送和定时运行。

## 本地启动

```bash
python -m pip install -r requirements.txt
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

## 主要模块

- `app/collectors`：数据源抓取。
- `app/intelligence`：去重、分析、日报生成。
- `app/jobs`：每日任务主流程。
- `app/notifications`：飞书和邮件推送。
- `app/api`：管理接口。
- `app/prompts`：AI 分析提示词草稿。
