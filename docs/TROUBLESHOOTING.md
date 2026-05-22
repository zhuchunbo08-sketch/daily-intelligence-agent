# 常见报错处理

## 1. `FEISHU_WEBHOOK_URL is not configured`

原因：没有配置飞书 Webhook，且没有打开干跑模式。

处理：

```env
FEISHU_WEBHOOK=https://open.feishu.cn/open-apis/bot/v2/hook/xxxx
```

本地测试可以先设置：

```env
PUSH_DRY_RUN=true
```

## 2. 飞书返回签名错误

原因：飞书机器人开启了签名校验，但 `.env` 的 `FEISHU_SECRET` 不正确。

处理：

1. 打开飞书机器人设置。
2. 复制“签名校验”的 Secret。
3. 写入：

```env
FEISHU_SECRET=xxxx
```

## 3. 日报为空

可能原因：

- 过去 24 小时内没有数据源内容。
- 数据源发布时间不明确，被严格过滤。
- 内容低于 `MIN_FINAL_SCORE`。
- 内容被判定为重复或高风险。

处理：

```bash
curl http://127.0.0.1:8000/api/runs
curl http://127.0.0.1:8000/api/reports/latest
curl http://127.0.0.1:8000/api/reports/1/items
```

如果只是想降低第一版筛选强度，可以调低：

```env
MIN_FINAL_SCORE=3.5
```

## 4. AI 没有生效

原因：没有配置 `AI_API_KEY` 或兼容快捷变量，系统会退回启发式分析。

推荐配置 DeepSeek：

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

## 5. 访问外网超时

如果服务器访问 AI、GDELT 或飞书网络不稳定，可以配置：

```env
PROXY_URL=http://127.0.0.1:7890
```

## 6. 每天 7 点没有运行

检查：

```bash
curl http://127.0.0.1:8000/api/settings
curl http://127.0.0.1:8000/api/runs
docker compose logs -f backend
```

确认：

```env
APP_TIMEZONE=Asia/Shanghai
DAILY_RUN_HOUR=7
DAILY_RUN_MINUTE=0
```

修改后需要重启服务。

## 7. Docker 命令不存在

原因：服务器或本机没有安装 Docker。

Ubuntu 安装：

```bash
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER
```

重新登录后再执行：

```bash
docker compose version
```
