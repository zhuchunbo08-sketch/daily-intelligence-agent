# Ubuntu 云服务器部署说明

推荐 Ubuntu 22.04 或 24.04，最低 1C1G，建议 2C2G。

## 1. 安装 Docker

```bash
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER
```

重新登录服务器后检查：

```bash
docker version
docker compose version
```

## 2. 上传项目

把项目上传到服务器，例如：

```bash
cd /opt
git clone <your-repo-url> daily-intelligence-agent
cd daily-intelligence-agent
```

如果不是 Git 仓库，也可以直接上传整个目录。

## 3. 配置环境变量

```bash
cp .env.example .env
nano .env
```

至少配置：

```env
APP_TIMEZONE=Asia/Shanghai
DAILY_RUN_HOUR=7
DAILY_RUN_MINUTE=0
AI_BASE_URL=https://api.deepseek.com
AI_API_KEY=你的 DeepSeek API Key
AI_MODEL=deepseek-v4-flash
FEISHU_WEBHOOK=你的飞书机器人 Webhook
```

也可以换成 DeepSeek 或通义千问，见 [CONFIG.md](CONFIG.md)。

## 4. 设置服务器时区

```bash
sudo timedatectl set-timezone Asia/Shanghai
timedatectl
```

应用内部也会读取：

```env
APP_TIMEZONE=Asia/Shanghai
```

## 5. 启动服务

```bash
docker compose up --build -d
```

查看服务：

```bash
docker compose ps
docker compose logs -f backend
```

健康检查：

```bash
curl http://127.0.0.1:8000/health
```

打开后台：

```text
http://服务器IP:8000/admin
```

## 6. 手动生成一次日报

```bash
curl -X POST http://127.0.0.1:8000/api/runs/daily
```

成功后查看：

```bash
curl http://127.0.0.1:8000/api/reports/latest
```

## 7. 定时任务确认

容器启动后，APScheduler 会注册每天北京时间 07:00 的任务。

确认配置：

```bash
curl http://127.0.0.1:8000/api/settings
```

查看是否运行过：

```bash
curl http://127.0.0.1:8000/api/runs
```

运行窗口固定为：

```text
昨天 07:00 <= event_time < 今天 07:00
```

时间不明确的内容不会进入分析流程。

## 8. 持久化目录

Docker Compose 挂载：

- `./data`：SQLite 数据库。
- `./logs`：日志。
- `./backend/config`：数据源配置。

Docker Compose 会把数据库写到：

```text
./data/daily_intelligence.db
```

## 9. 更新项目

```bash
docker compose down
git pull
docker compose up --build -d
```

如果是手动上传代码，重新上传后执行：

```bash
docker compose down
docker compose up --build -d
```

## 10. 安全建议

第一版后台没有登录系统。如果部署到公网，建议：

- 只对自己的 IP 开放 8000 端口。
- 或者用 Nginx Basic Auth 保护。
- 或者不要暴露 8000，只通过 SSH 隧道访问。
