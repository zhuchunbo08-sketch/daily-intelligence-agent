from fastapi import APIRouter
from fastapi.responses import HTMLResponse

router = APIRouter(tags=["admin"])


@router.get("/admin", response_class=HTMLResponse)
def admin_page():
    return """
<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>每日破圈赚钱情报系统</title>
  <style>
    body { font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; margin: 24px; line-height: 1.5; }
    button { padding: 8px 12px; cursor: pointer; }
    pre { white-space: pre-wrap; background: #f6f6f6; padding: 12px; border: 1px solid #ddd; overflow: auto; }
    section { margin: 20px 0; }
  </style>
</head>
<body>
  <h1>每日破圈赚钱情报系统</h1>
  <section>
    <button onclick="triggerRun()">手动触发日报</button>
    <button onclick="loadRuns()">刷新运行记录</button>
    <button onclick="loadSources()">刷新数据源</button>
    <button onclick="loadReports()">查看历史日报</button>
    <button onclick="loadLatestReport()">查看最新日报</button>
    <button onclick="pushLatestReport()">补推最新日报</button>
  </section>
  <section>
    <h2>运行结果</h2>
    <pre id="output">等待操作...</pre>
  </section>
  <script>
    async function show(promise) {
      const output = document.getElementById('output');
      output.textContent = '加载中...';
      try {
        const res = await promise;
        const data = await res.json();
        output.textContent = typeof data.content === 'string' ? data.content : JSON.stringify(data, null, 2);
      } catch (err) {
        output.textContent = String(err);
      }
    }
    function triggerRun() { show(fetch('/api/runs/daily', { method: 'POST' })); }
    function loadRuns() { show(fetch('/api/runs')); }
    function loadSources() { show(fetch('/api/sources')); }
    function loadReports() { show(fetch('/api/reports')); }
    function loadLatestReport() { show(fetch('/api/reports/latest')); }
    async function pushLatestReport() {
      const latest = await fetch('/api/reports/latest');
      const data = await latest.json();
      show(fetch(`/api/reports/${data.id}/push`, { method: 'POST' }));
    }
  </script>
</body>
</html>
"""
