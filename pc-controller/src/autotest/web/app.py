"""FastAPI Web Dashboard for real-time monitoring and report viewing."""

from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path
from typing import Any

from autotest.core.events import Event, EventBus

logger = logging.getLogger(__name__)

# Lazy imports to avoid requiring fastapi unless web extras are installed
_app = None


def create_app(event_bus: EventBus | None = None, report_dir: str = "./reports") -> Any:
    """Create and configure the FastAPI application."""
    try:
        from fastapi import FastAPI, WebSocket, WebSocketDisconnect
        from fastapi.responses import HTMLResponse, FileResponse
        from fastapi.staticfiles import StaticFiles
    except ImportError:
        raise RuntimeError(
            "FastAPI not installed. Run: pip install autotest[web]"
        )

    app = FastAPI(title="AutoTest Dashboard", version="1.0.0")
    bus = event_bus or EventBus()

    # Connected WebSocket clients for live updates
    ws_clients: list[WebSocket] = []

    # Forward events to WebSocket clients
    async def broadcast_event(event: Event) -> None:
        data = json.dumps({
            "type": event.type,
            "source": event.source,
            "data": event.data,
            "timestamp": event.timestamp,
        })
        for ws in list(ws_clients):
            try:
                await ws.send_text(data)
            except Exception:
                ws_clients.remove(ws)

    bus.on_all(broadcast_event)

    @app.get("/", response_class=HTMLResponse)
    async def dashboard() -> str:
        return DASHBOARD_HTML

    @app.get("/api/status")
    async def status() -> dict[str, Any]:
        return {
            "status": "running",
            "ws_clients": len(ws_clients),
        }

    @app.get("/api/reports")
    async def list_reports() -> list[dict[str, Any]]:
        report_path = Path(report_dir)
        if not report_path.exists():
            return []
        reports = []
        for f in sorted(report_path.glob("*"), key=lambda p: p.stat().st_mtime, reverse=True):
            if f.is_file():
                reports.append({
                    "name": f.name,
                    "size": f.stat().st_size,
                    "modified": f.stat().st_mtime,
                    "url": f"/api/reports/{f.name}",
                })
        return reports

    @app.get("/api/reports/{filename}")
    async def get_report(filename: str) -> FileResponse:
        path = Path(report_dir) / filename
        if not path.exists():
            from fastapi import HTTPException
            raise HTTPException(404, "Report not found")
        return FileResponse(str(path))

    @app.websocket("/ws")
    async def websocket_endpoint(websocket: WebSocket) -> None:
        await websocket.accept()
        ws_clients.append(websocket)
        try:
            while True:
                # Keep alive, receive client messages
                data = await websocket.receive_text()
                # Client can send commands here in the future
        except WebSocketDisconnect:
            ws_clients.remove(websocket)

    return app


def run_dashboard(
    event_bus: EventBus | None = None,
    host: str = "0.0.0.0",
    port: int = 8080,
    report_dir: str = "./reports",
) -> None:
    """Start the web dashboard server."""
    try:
        import uvicorn
    except ImportError:
        raise RuntimeError("uvicorn not installed. Run: pip install autotest[web]")

    app = create_app(event_bus, report_dir)
    uvicorn.run(app, host=host, port=port, log_level="info")


DASHBOARD_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>AutoTest Dashboard</title>
<style>
* { margin:0; padding:0; box-sizing:border-box; }
body { font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif; background:#1a1a2e; color:#eee; }
.header { background:#16213e; padding:16px 24px; display:flex; align-items:center; gap:16px; }
.header h1 { font-size:20px; color:#0f3460; }
.header h1 { color:#e94560; }
.container { max-width:1400px; margin:0 auto; padding:24px; }
.grid { display:grid; grid-template-columns:repeat(auto-fit,minmax(300px,1fr)); gap:16px; margin-bottom:24px; }
.card { background:#16213e; border-radius:12px; padding:20px; }
.card h3 { font-size:14px; color:#888; text-transform:uppercase; margin-bottom:12px; }
.stat { font-size:36px; font-weight:700; }
.stat.green { color:#4CAF50; }
.stat.red { color:#f44336; }
.stat.blue { color:#2196F3; }
.log-container { background:#0f0f23; border-radius:8px; padding:16px; font-family:monospace; font-size:12px; max-height:400px; overflow-y:auto; }
.log-entry { padding:2px 0; border-bottom:1px solid #1a1a2e; }
.log-entry .time { color:#666; }
.log-entry .type { font-weight:600; }
.log-entry .type.test { color:#2196F3; }
.log-entry .type.pass { color:#4CAF50; }
.log-entry .type.fail { color:#f44336; }
.status-dot { width:8px; height:8px; border-radius:50%; display:inline-block; margin-right:6px; }
.status-dot.online { background:#4CAF50; }
.status-dot.offline { background:#666; }
#reports-list a { color:#64b5f6; text-decoration:none; }
#reports-list a:hover { text-decoration:underline; }
</style>
</head>
<body>
<div class="header"><h1>AutoTest Dashboard</h1></div>
<div class="container">
  <div class="grid">
    <div class="card"><h3>Total Tests</h3><div class="stat blue" id="total">0</div></div>
    <div class="card"><h3>Passed</h3><div class="stat green" id="passed">0</div></div>
    <div class="card"><h3>Failed</h3><div class="stat red" id="failed">0</div></div>
    <div class="card"><h3>Connected Devices</h3><div class="stat" id="devices">0</div></div>
  </div>

  <div class="grid">
    <div class="card" style="grid-column:1/-1">
      <h3>Live Events</h3>
      <div class="log-container" id="log"></div>
    </div>
  </div>

  <div class="card">
    <h3>Reports</h3>
    <div id="reports-list">Loading...</div>
  </div>
</div>

<script>
let total=0, passed=0, failed=0;

const ws = new WebSocket(`ws://${location.host}/ws`);
ws.onmessage = (e) => {
  const event = JSON.parse(e.data);
  addLog(event);

  if (event.type === 'test.completed') {
    total++;
    if (event.data.status === 'passed') passed++;
    else if (event.data.status === 'failed' || event.data.status === 'error') failed++;
    updateStats();
  }
  if (event.type === 'execution.started') {
    document.getElementById('devices').textContent = event.data.device_count || 0;
  }
};

function addLog(event) {
  const log = document.getElementById('log');
  const time = new Date(event.timestamp * 1000).toLocaleTimeString();
  let typeClass = 'test';
  if (event.data?.status === 'passed') typeClass = 'pass';
  if (event.data?.status === 'failed' || event.data?.status === 'error') typeClass = 'fail';

  log.innerHTML += `<div class="log-entry"><span class="time">[${time}]</span> <span class="type ${typeClass}">${event.type}</span> ${JSON.stringify(event.data||{})}</div>`;
  log.scrollTop = log.scrollHeight;
}

function updateStats() {
  document.getElementById('total').textContent = total;
  document.getElementById('passed').textContent = passed;
  document.getElementById('failed').textContent = failed;
}

fetch('/api/reports').then(r=>r.json()).then(reports => {
  const el = document.getElementById('reports-list');
  if (!reports.length) { el.textContent = 'No reports yet'; return; }
  el.innerHTML = reports.map(r => `<div><a href="${r.url}" target="_blank">${r.name}</a> (${(r.size/1024).toFixed(1)}KB)</div>`).join('');
});
</script>
</body>
</html>"""
