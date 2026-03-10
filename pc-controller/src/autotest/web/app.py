"""FastAPI Web Dashboard — 设备管理、NL 命令、实时监控。"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from autotest.core.config import AutoTestConfig, load_dotenv
from autotest.core.events import Event, EventBus

logger = logging.getLogger(__name__)

_app = None


def create_app(
    event_bus: EventBus | None = None,
    report_dir: str = "./reports",
    config: AutoTestConfig | None = None,
) -> Any:
    """创建并配置 FastAPI 应用。"""
    try:
        from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
        from fastapi.responses import FileResponse, HTMLResponse
    except ImportError:
        raise RuntimeError("FastAPI 未安装。运行: pip install autotest[web]")

    load_dotenv()
    cfg = config or AutoTestConfig()

    app = FastAPI(title="AutoTest Dashboard", version="2.0.0")
    bus = event_bus or EventBus()

    # WebSocket 实时推送客户端
    ws_clients: list[WebSocket] = []

    # 设备管理器（延迟初始化）
    _manager_holder: dict[str, Any] = {}

    async def _get_manager() -> Any:
        if "mgr" not in _manager_holder:
            from autotest.device.manager import DeviceManager
            mgr = DeviceManager(config=cfg.device)
            _manager_holder["mgr"] = mgr
        return _manager_holder["mgr"]

    # AgentHub（延迟初始化，反向连接）
    _hub_holder: dict[str, Any] = {}

    async def _get_hub() -> Any:
        if "hub" not in _hub_holder:
            from autotest.device.agent_hub import AgentHub
            manager = await _get_manager()
            _hub_holder["hub"] = AgentHub(manager, config=cfg.server)
        return _hub_holder["hub"]

    # NL 引擎（延迟初始化）
    _nl_holder: dict[str, Any] = {}

    def _get_nl_engine() -> Any:
        if "engine" not in _nl_holder:
            from autotest.nlp.engine import NLCommandEngine
            _nl_holder["engine"] = NLCommandEngine(cfg)
        return _nl_holder["engine"]

    # 事件广播
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

    # -------------------------------------------------------------------------
    # 页面路由
    # -------------------------------------------------------------------------

    @app.get("/", response_class=HTMLResponse)
    async def dashboard() -> str:
        return DASHBOARD_HTML

    # -------------------------------------------------------------------------
    # 原有 API
    # -------------------------------------------------------------------------

    @app.get("/api/status")
    async def status() -> dict[str, Any]:
        manager = await _get_manager()
        return {
            "status": "running",
            "ws_clients": len(ws_clients),
            "connected_devices": manager.connected_devices,
        }

    @app.get("/api/reports")
    async def list_reports() -> list[dict[str, Any]]:
        report_path = Path(report_dir)
        if not report_path.exists():
            return []
        reports = []
        for f in sorted(
            report_path.glob("*"), key=lambda p: p.stat().st_mtime, reverse=True
        ):
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
            raise HTTPException(404, "报告文件不存在")
        return FileResponse(str(path))

    @app.websocket("/ws")
    async def websocket_endpoint(websocket: WebSocket) -> None:
        await websocket.accept()
        ws_clients.append(websocket)
        try:
            while True:
                await websocket.receive_text()
        except WebSocketDisconnect:
            ws_clients.remove(websocket)

    # -------------------------------------------------------------------------
    # 反向连接 — 设备主动连接 PC
    # -------------------------------------------------------------------------

    @app.websocket("/agent")
    async def agent_endpoint(websocket: WebSocket) -> None:
        """接收设备反向 WebSocket 连接。"""
        hub = await _get_hub()
        await hub.handle_agent_connection(websocket)

    @app.get("/api/remote-devices")
    async def list_remote_devices() -> list[dict[str, Any]]:
        """列出所有通过反向连接的远程设备。"""
        hub = await _get_hub()
        return hub.remote_devices

    # -------------------------------------------------------------------------
    # 设备管理 API
    # -------------------------------------------------------------------------

    @app.get("/api/devices")
    async def list_devices() -> list[dict[str, Any]]:
        """列出所有已发现设备及其连接状态。"""
        manager = await _get_manager()
        discovered = await manager.discover()
        connected = set(manager.connected_devices)
        devices = []
        for d in discovered:
            devices.append({
                "serial": d.serial,
                "state": d.state,
                "model": d.model,
                "connected": d.serial in connected,
            })
        return devices

    @app.post("/api/devices/{serial}/connect")
    async def connect_device(serial: str) -> dict[str, Any]:
        """连接指定设备。"""
        manager = await _get_manager()
        try:
            await manager.connect(serial)
            return {"serial": serial, "status": "connected"}
        except Exception as e:
            raise HTTPException(500, f"连接设备失败: {e}")

    @app.post("/api/devices/{serial}/disconnect")
    async def disconnect_device(serial: str) -> dict[str, Any]:
        """断开指定设备。"""
        manager = await _get_manager()
        await manager.disconnect(serial)
        return {"serial": serial, "status": "disconnected"}

    @app.get("/api/devices/{serial}/info")
    async def device_info(serial: str) -> dict[str, Any]:
        """获取设备详细信息。"""
        manager = await _get_manager()
        client = manager.get_client(serial)
        if not client or not client.is_connected:
            raise HTTPException(400, "设备未连接")
        try:
            resp = await client.send("device.info")
            return {"serial": serial, "info": resp.result}
        except Exception as e:
            raise HTTPException(500, f"获取设备信息失败: {e}")

    @app.get("/api/devices/{serial}/screenshot")
    async def device_screenshot(serial: str) -> dict[str, Any]:
        """获取设备实时截图（返回 base64 PNG）。"""
        manager = await _get_manager()
        client = manager.get_client(serial)
        if not client or not client.is_connected:
            raise HTTPException(400, "设备未连接")
        try:
            resp = await client.send("device.screenshot")
            data = ""
            if resp.result and isinstance(resp.result, dict):
                data = resp.result.get("data", "")
            return {"serial": serial, "screenshot": data}
        except Exception as e:
            raise HTTPException(500, f"截图失败: {e}")

    @app.post("/api/devices/{serial}/command")
    async def send_command(serial: str, body: dict[str, Any]) -> dict[str, Any]:
        """发送原始命令到设备。

        请求体: {"method": "ui.click", "params": {...}}
        """
        manager = await _get_manager()
        client = manager.get_client(serial)
        if not client or not client.is_connected:
            raise HTTPException(400, "设备未连接")
        method = body.get("method", "")
        params = body.get("params")
        if not method:
            raise HTTPException(400, "缺少 method 字段")
        try:
            resp = await client.send(method, params)
            return {
                "success": resp.is_success,
                "result": resp.result,
                "error": resp.error_message if not resp.is_success else None,
            }
        except Exception as e:
            return {"success": False, "result": None, "error": str(e)}

    @app.post("/api/devices/{serial}/nl")
    async def nl_command(serial: str, body: dict[str, Any]) -> dict[str, Any]:
        """发送自然语言命令。

        请求体: {"text": "打开设置", "with_screenshot": true}
        """
        engine = _get_nl_engine()
        if not engine.is_available:
            raise HTTPException(
                503, "NLP 引擎不可用，请检查 API Key 配置"
            )

        manager = await _get_manager()
        client = manager.get_client(serial)
        if not client or not client.is_connected:
            raise HTTPException(400, "设备未连接")

        text = body.get("text", "")
        with_screenshot = body.get("with_screenshot", False)
        if not text:
            raise HTTPException(400, "缺少 text 字段")

        try:
            result = await engine.execute(text, client, with_screenshot=with_screenshot)
            return {
                "steps": [
                    {"method": s.method, "params": s.params, "description": s.description}
                    for s in result.steps
                ],
                "executed": result.executed,
                "screenshot": result.screenshot,
            }
        except Exception as e:
            raise HTTPException(500, f"NL 命令执行失败: {e}")

    return app


def run_dashboard(
    event_bus: EventBus | None = None,
    host: str = "0.0.0.0",
    port: int = 8080,
    report_dir: str = "./reports",
    config: AutoTestConfig | None = None,
) -> None:
    """启动 Web Dashboard 服务器。"""
    try:
        import uvicorn
    except ImportError:
        raise RuntimeError("uvicorn 未安装。运行: pip install autotest[web]")

    app = create_app(event_bus, report_dir, config)
    uvicorn.run(app, host=host, port=port, log_level="info")


# ---------------------------------------------------------------------------
# 内嵌 HTML Dashboard
# ---------------------------------------------------------------------------

DASHBOARD_HTML = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>AutoTest Dashboard</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI','PingFang SC','Microsoft YaHei',sans-serif;background:#0f0f1a;color:#e0e0e0;min-height:100vh}

/* 头部 */
.header{background:#161628;padding:14px 24px;display:flex;align-items:center;justify-content:space-between;border-bottom:1px solid #2a2a4a}
.header h1{font-size:20px;color:#7c6ff7;letter-spacing:1px}
.header .status-badge{font-size:12px;padding:4px 12px;border-radius:12px;background:#1e3a2e;color:#4caf50}

/* 布局 */
.main{display:flex;height:calc(100vh - 52px)}
.sidebar{width:280px;background:#161628;border-right:1px solid #2a2a4a;display:flex;flex-direction:column;flex-shrink:0}
.content{flex:1;display:flex;flex-direction:column;overflow:hidden}

/* 侧边栏 - 设备列表 */
.sidebar-header{padding:16px;border-bottom:1px solid #2a2a4a;display:flex;align-items:center;justify-content:space-between}
.sidebar-header h3{font-size:13px;color:#888;text-transform:uppercase;letter-spacing:1px}
.btn-refresh{background:none;border:1px solid #3a3a5a;color:#888;padding:4px 10px;border-radius:6px;cursor:pointer;font-size:12px}
.btn-refresh:hover{border-color:#7c6ff7;color:#7c6ff7}
.device-list{flex:1;overflow-y:auto;padding:8px}
.device-card{background:#1e1e35;border:1px solid #2a2a4a;border-radius:10px;padding:12px;margin-bottom:8px;cursor:pointer;transition:all .2s}
.device-card:hover{border-color:#7c6ff7}
.device-card.active{border-color:#7c6ff7;background:#1e1e40}
.device-card .model{font-size:14px;font-weight:600;margin-bottom:4px}
.device-card .serial{font-size:11px;color:#666;font-family:monospace}
.device-card .badge{display:inline-block;font-size:10px;padding:2px 8px;border-radius:10px;margin-top:6px}
.badge.connected{background:#1e3a2e;color:#4caf50}
.badge.offline{background:#3a2020;color:#f44336}
.badge.connecting{background:#3a3020;color:#ff9800}
.btn-connect{margin-top:8px;width:100%;padding:6px;border:none;border-radius:6px;cursor:pointer;font-size:12px;font-weight:600}
.btn-connect.connect{background:#7c6ff7;color:#fff}
.btn-connect.disconnect{background:#3a2020;color:#f44336}
.btn-connect:hover{opacity:.85}

/* 内容区 - 上部 */
.content-top{display:flex;flex:1;overflow:hidden}

/* 截图区 */
.screenshot-panel{flex:1;display:flex;flex-direction:column;padding:16px;min-width:0}
.screenshot-header{display:flex;align-items:center;justify-content:space-between;margin-bottom:12px}
.screenshot-header h3{font-size:13px;color:#888;text-transform:uppercase;letter-spacing:1px}
.btn-screenshot{background:#7c6ff7;color:#fff;border:none;padding:6px 14px;border-radius:6px;cursor:pointer;font-size:12px}
.btn-screenshot:hover{opacity:.85}
.btn-screenshot:disabled{opacity:.4;cursor:not-allowed}
.screenshot-view{flex:1;background:#111;border-radius:10px;display:flex;align-items:center;justify-content:center;overflow:hidden;position:relative;min-height:300px}
.screenshot-view img{max-width:100%;max-height:100%;object-fit:contain}
.screenshot-view .placeholder{color:#444;font-size:14px}

/* 右侧面板 */
.right-panel{width:420px;border-left:1px solid #2a2a4a;display:flex;flex-direction:column;flex-shrink:0}

/* NL 命令区 */
.nl-panel{padding:16px;border-bottom:1px solid #2a2a4a}
.nl-panel h3{font-size:13px;color:#888;text-transform:uppercase;letter-spacing:1px;margin-bottom:10px}
.nl-input-row{display:flex;gap:8px}
.nl-input{flex:1;background:#1e1e35;border:1px solid #2a2a4a;border-radius:8px;padding:10px 14px;color:#e0e0e0;font-size:14px;outline:none;font-family:inherit}
.nl-input:focus{border-color:#7c6ff7}
.nl-input::placeholder{color:#555}
.btn-send{background:#7c6ff7;color:#fff;border:none;padding:10px 18px;border-radius:8px;cursor:pointer;font-size:14px;font-weight:600;white-space:nowrap}
.btn-send:hover{opacity:.85}
.btn-send:disabled{opacity:.4;cursor:not-allowed}
.nl-options{display:flex;gap:12px;margin-top:8px;align-items:center}
.nl-options label{font-size:12px;color:#888;display:flex;align-items:center;gap:4px;cursor:pointer}
.nl-options input[type=checkbox]{accent-color:#7c6ff7}

/* 命令历史 */
.history-panel{flex:1;overflow-y:auto;padding:16px}
.history-panel h3{font-size:13px;color:#888;text-transform:uppercase;letter-spacing:1px;margin-bottom:10px}
.history-item{background:#1e1e35;border-radius:8px;padding:12px;margin-bottom:8px;border:1px solid #2a2a4a}
.history-item .cmd{font-size:13px;color:#7c6ff7;margin-bottom:6px;font-weight:600}
.history-item .steps{font-size:12px;color:#aaa}
.history-item .step-row{padding:3px 0;border-bottom:1px solid #1a1a2e}
.history-item .step-row:last-child{border:none}
.step-ok{color:#4caf50}
.step-fail{color:#f44336}
.history-item .time{font-size:10px;color:#555;margin-top:4px}

/* 底部 - 统计 + 事件 */
.content-bottom{border-top:1px solid #2a2a4a;display:flex;height:200px;flex-shrink:0}
.stats-bar{display:flex;gap:0;border-right:1px solid #2a2a4a}
.stat-box{padding:16px 24px;text-align:center;min-width:120px;border-right:1px solid #2a2a4a}
.stat-box:last-child{border:none}
.stat-box .label{font-size:11px;color:#666;text-transform:uppercase;margin-bottom:6px}
.stat-box .value{font-size:28px;font-weight:700}
.stat-box .value.blue{color:#7c6ff7}
.stat-box .value.green{color:#4caf50}
.stat-box .value.red{color:#f44336}
.event-log{flex:1;overflow-y:auto;padding:12px 16px;font-family:'SF Mono',monospace;font-size:11px;background:#0a0a14}
.event-entry{padding:3px 0;color:#777}
.event-entry .ev-time{color:#444}
.event-entry .ev-type{font-weight:600}
.event-entry .ev-type.pass{color:#4caf50}
.event-entry .ev-type.fail{color:#f44336}
.event-entry .ev-type.info{color:#7c6ff7}

/* 报告面板（可切换） */
.tab-bar{display:flex;border-bottom:1px solid #2a2a4a}
.tab-bar .tab{padding:8px 16px;font-size:12px;color:#666;cursor:pointer;border-bottom:2px solid transparent}
.tab-bar .tab.active{color:#7c6ff7;border-color:#7c6ff7}
.reports-list{padding:12px 16px;font-size:12px}
.reports-list a{color:#64b5f6;text-decoration:none}
.reports-list a:hover{text-decoration:underline}

/* 加载动画 */
.spinner{display:inline-block;width:14px;height:14px;border:2px solid #444;border-top-color:#7c6ff7;border-radius:50%;animation:spin .6s linear infinite}
@keyframes spin{to{transform:rotate(360deg)}}

/* 滚动条 */
::-webkit-scrollbar{width:6px}
::-webkit-scrollbar-track{background:transparent}
::-webkit-scrollbar-thumb{background:#2a2a4a;border-radius:3px}
::-webkit-scrollbar-thumb:hover{background:#3a3a5a}
</style>
</head>
<body>

<div class="header">
  <h1>AutoTest Dashboard</h1>
  <span class="status-badge" id="statusBadge">● 运行中</span>
</div>

<div class="main">
  <!-- 侧边栏 -->
  <div class="sidebar">
    <div class="sidebar-header">
      <h3>设备</h3>
      <button class="btn-refresh" onclick="refreshDevices()">刷新</button>
    </div>
    <div class="device-list" id="deviceList">
      <div style="padding:20px;text-align:center;color:#555">加载中...</div>
    </div>
  </div>

  <!-- 内容区 -->
  <div class="content">
    <div class="content-top">
      <!-- 截图区 -->
      <div class="screenshot-panel">
        <div class="screenshot-header">
          <h3>实时截图</h3>
          <button class="btn-screenshot" id="btnScreenshot" onclick="takeScreenshot()" disabled>截图</button>
        </div>
        <div class="screenshot-view" id="screenshotView">
          <span class="placeholder">选择设备后查看截图</span>
        </div>
      </div>

      <!-- 右侧面板 -->
      <div class="right-panel">
        <!-- NL 命令输入 -->
        <div class="nl-panel">
          <h3>自然语言命令</h3>
          <div class="nl-input-row">
            <input class="nl-input" id="nlInput" type="text" placeholder="例如：打开设置、点击WiFi..."
                   onkeydown="if(event.key==='Enter')sendNL()" disabled>
            <button class="btn-send" id="btnSend" onclick="sendNL()" disabled>发送</button>
          </div>
          <div class="nl-options">
            <label><input type="checkbox" id="chkScreenshot" checked> 附带截图</label>
          </div>
        </div>

        <!-- 命令历史 -->
        <div class="history-panel" id="historyPanel">
          <h3>命令历史</h3>
          <div id="historyList" style="color:#555;font-size:12px;margin-top:8px">暂无命令记录</div>
        </div>
      </div>
    </div>

    <!-- 底部统计 + 事件 -->
    <div class="content-bottom">
      <div class="stats-bar">
        <div class="stat-box"><div class="label">设备数</div><div class="value blue" id="statDevices">0</div></div>
        <div class="stat-box"><div class="label">总测试</div><div class="value blue" id="statTotal">0</div></div>
        <div class="stat-box"><div class="label">通过</div><div class="value green" id="statPassed">0</div></div>
        <div class="stat-box"><div class="label">失败</div><div class="value red" id="statFailed">0</div></div>
      </div>
      <div>
        <div class="tab-bar">
          <div class="tab active" onclick="switchTab('events',this)">事件日志</div>
          <div class="tab" onclick="switchTab('reports',this)">测试报告</div>
        </div>
        <div class="event-log" id="eventLog" style="height:160px"></div>
        <div class="reports-list" id="reportsList" style="height:160px;overflow-y:auto;display:none">加载中...</div>
      </div>
    </div>
  </div>
</div>

<script>
// 状态
let selectedDevice = null;
let totalTests = 0, passedTests = 0, failedTests = 0;
let historyItems = [];

// ---- WebSocket 实时推送 ----
const ws = new WebSocket(`ws://${location.host}/ws`);
ws.onopen = () => {};
ws.onmessage = (e) => {
  const event = JSON.parse(e.data);
  addEvent(event);
  if (event.type === 'test.completed') {
    totalTests++;
    if (event.data?.status === 'passed') passedTests++;
    else if (event.data?.status === 'failed' || event.data?.status === 'error') failedTests++;
    updateStats();
  }
  if (event.type === 'execution.started') {
    document.getElementById('statDevices').textContent = event.data?.device_count || 0;
  }
};

function addEvent(event) {
  const el = document.getElementById('eventLog');
  const time = new Date(event.timestamp * 1000).toLocaleTimeString();
  let cls = 'info';
  if (event.data?.status === 'passed') cls = 'pass';
  if (event.data?.status === 'failed' || event.data?.status === 'error') cls = 'fail';
  el.innerHTML += `<div class="event-entry"><span class="ev-time">[${time}]</span> <span class="ev-type ${cls}">${event.type}</span> ${JSON.stringify(event.data||{}).slice(0,120)}</div>`;
  el.scrollTop = el.scrollHeight;
}

function updateStats() {
  document.getElementById('statTotal').textContent = totalTests;
  document.getElementById('statPassed').textContent = passedTests;
  document.getElementById('statFailed').textContent = failedTests;
}

// ---- Tab 切换 ----
function switchTab(name, tabEl) {
  document.querySelectorAll('.tab-bar .tab').forEach(t => t.classList.remove('active'));
  tabEl.classList.add('active');
  document.getElementById('eventLog').style.display = name === 'events' ? '' : 'none';
  document.getElementById('reportsList').style.display = name === 'reports' ? '' : 'none';
  if (name === 'reports') loadReports();
}

function loadReports() {
  fetch('/api/reports').then(r => r.json()).then(reports => {
    const el = document.getElementById('reportsList');
    if (!reports.length) { el.textContent = '暂无报告'; return; }
    el.innerHTML = reports.map(r =>
      `<div style="padding:4px 0"><a href="${r.url}" target="_blank">${r.name}</a> <span style="color:#555">(${(r.size/1024).toFixed(1)}KB)</span></div>`
    ).join('');
  });
}

// ---- 设备管理 ----
async function refreshDevices() {
  try {
    const [adbResp, remoteResp] = await Promise.all([
      fetch('/api/devices'),
      fetch('/api/remote-devices'),
    ]);
    const adbDevices = await adbResp.json();
    const remoteDevices = await remoteResp.json();
    // 标记 ADB 设备
    adbDevices.forEach(d => { if (!d.mode) d.mode = 'adb'; });
    const devices = [...adbDevices, ...remoteDevices];
    renderDevices(devices);
    document.getElementById('statDevices').textContent = devices.filter(d => d.connected).length;
  } catch (e) {
    document.getElementById('deviceList').innerHTML = '<div style="padding:20px;text-align:center;color:#f44336">加载失败</div>';
  }
}

function renderDevices(devices) {
  const el = document.getElementById('deviceList');
  if (!devices.length) {
    el.innerHTML = '<div style="padding:20px;text-align:center;color:#555">未发现设备</div>';
    return;
  }
  el.innerHTML = devices.map(d => {
    const isReverse = d.mode === 'reverse';
    const modeLabel = isReverse ? 'WiFi' : 'ADB';
    const modeColor = isReverse ? '#ff9800' : '#64b5f6';
    return `
    <div class="device-card ${selectedDevice === d.serial ? 'active' : ''}" onclick="selectDevice('${d.serial}')">
      <div class="model">${d.model || '未知设备'} <span style="font-size:10px;color:${modeColor};border:1px solid ${modeColor};border-radius:4px;padding:1px 5px;margin-left:4px">${modeLabel}</span></div>
      <div class="serial">${d.serial}</div>
      <span class="badge ${d.connected ? 'connected' : (d.state === 'device' ? 'offline' : 'offline')}">
        ${d.connected ? '已连接' : (d.state === 'device' ? '在线' : '离线')}
      </span>
      ${d.connected && !isReverse
        ? `<button class="btn-connect disconnect" onclick="event.stopPropagation();disconnectDevice('${d.serial}')">断开</button>`
        : (!d.connected && d.state === 'device' && !isReverse
          ? `<button class="btn-connect connect" onclick="event.stopPropagation();connectDevice('${d.serial}')">连接</button>`
          : '')
      }
    </div>`;
  }).join('');
}

async function connectDevice(serial) {
  try {
    await fetch(`/api/devices/${serial}/connect`, {method: 'POST'});
    await refreshDevices();
    selectDevice(serial);
  } catch (e) {
    alert('连接失败: ' + e.message);
  }
}

async function disconnectDevice(serial) {
  try {
    await fetch(`/api/devices/${serial}/disconnect`, {method: 'POST'});
    if (selectedDevice === serial) {
      selectedDevice = null;
      updateUIState();
    }
    await refreshDevices();
  } catch (e) {
    alert('断开失败: ' + e.message);
  }
}

function selectDevice(serial) {
  selectedDevice = serial;
  updateUIState();
  refreshDevices();
  takeScreenshot();
}

function updateUIState() {
  const hasDevice = !!selectedDevice;
  document.getElementById('btnScreenshot').disabled = !hasDevice;
  document.getElementById('nlInput').disabled = !hasDevice;
  document.getElementById('btnSend').disabled = !hasDevice;
  if (!hasDevice) {
    document.getElementById('screenshotView').innerHTML = '<span class="placeholder">选择设备后查看截图</span>';
  }
}

// ---- 截图 ----
async function takeScreenshot() {
  if (!selectedDevice) return;
  const view = document.getElementById('screenshotView');
  view.innerHTML = '<div class="spinner"></div>';
  try {
    const resp = await fetch(`/api/devices/${selectedDevice}/screenshot`);
    const data = await resp.json();
    if (data.screenshot) {
      view.innerHTML = `<img src="data:image/png;base64,${data.screenshot}" alt="screenshot">`;
    } else {
      view.innerHTML = '<span class="placeholder">截图为空</span>';
    }
  } catch (e) {
    view.innerHTML = '<span class="placeholder" style="color:#f44336">截图失败</span>';
  }
}

// ---- NL 命令 ----
async function sendNL() {
  const input = document.getElementById('nlInput');
  const text = input.value.trim();
  if (!text || !selectedDevice) return;

  const btn = document.getElementById('btnSend');
  btn.disabled = true;
  btn.innerHTML = '<span class="spinner"></span>';
  input.disabled = true;

  const withScreenshot = document.getElementById('chkScreenshot').checked;

  try {
    const resp = await fetch(`/api/devices/${selectedDevice}/nl`, {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({text, with_screenshot: withScreenshot}),
    });
    const data = await resp.json();

    if (resp.ok) {
      // 添加到历史
      addHistory(text, data);
      // 更新截图
      if (data.screenshot) {
        document.getElementById('screenshotView').innerHTML =
          `<img src="data:image/png;base64,${data.screenshot}" alt="screenshot">`;
      }
      input.value = '';
    } else {
      addHistory(text, {error: data.detail || '执行失败'});
    }
  } catch (e) {
    addHistory(text, {error: e.message});
  } finally {
    btn.disabled = false;
    btn.textContent = '发送';
    input.disabled = false;
    input.focus();
  }
}

function addHistory(text, data) {
  const el = document.getElementById('historyList');
  const time = new Date().toLocaleTimeString();

  let stepsHtml = '';
  if (data.error) {
    stepsHtml = `<div class="step-fail">${data.error}</div>`;
  } else if (data.executed) {
    stepsHtml = data.executed.map((s, i) =>
      `<div class="step-row"><span class="${s.success ? 'step-ok' : 'step-fail'}">${s.success ? '✓' : '✗'}</span> ${s.step || s.method}</div>`
    ).join('');
  }

  const item = `<div class="history-item">
    <div class="cmd">${text}</div>
    <div class="steps">${stepsHtml}</div>
    <div class="time">${time}</div>
  </div>`;

  // 移除"暂无"提示
  if (el.querySelector && !el.querySelector('.history-item')) {
    el.innerHTML = '';
  }
  el.insertAdjacentHTML('afterbegin', item);
}

// ---- 初始化 ----
refreshDevices();
loadReports();
</script>
</body>
</html>"""
