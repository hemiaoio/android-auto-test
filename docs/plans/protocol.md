# AutoTest 通信协议规范

## 1. 传输层设计

### 1.1 三端口架构

| 端口 | 用途 | 数据格式 | 说明 |
|------|------|---------|------|
| `:18900` | 命令控制 | JSON text frames | 请求-响应模式 |
| `:18901` | 二进制数据 | binary frames | 截图/文件传输 |
| `:18902` | 事件推送 | JSON text frames | 服务端主动推送 |

### 1.2 连接方式

- **USB 优先**: 通过 `adb forward` 转发端口
- **WiFi 备用**: mDNS 服务发现
- **自动重连**: 指数退避策略（1s → 2s → 4s → 8s → 16s → 30s max）

### 1.3 ADB 端口转发规则

PC 端为每台设备分配 3 个连续端口，起始端口 28900：

```
设备 0: 28900 → 18900, 28901 → 18901, 28902 → 18902
设备 1: 28903 → 18900, 28904 → 18901, 28905 → 18902
设备 N: 28900+N*3 → 18900, 28901+N*3 → 18901, 28902+N*3 → 18902
```

---

## 2. 消息信封

所有控制通道消息遵循统一的 JSON 信封格式：

```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "type": "request",
  "method": "ui.click",
  "params": {
    "selector": { "resourceId": "btn_login" }
  },
  "result": null,
  "error": null,
  "metadata": {
    "timeout": 10000,
    "traceId": "trace-xxx"
  },
  "timestamp": 1709251200000
}
```

### 2.1 字段说明

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `id` | string (UUID) | 是 | 消息唯一标识，用于请求-响应关联 |
| `type` | enum | 是 | `request` / `response` / `event` / `stream_data` |
| `method` | string | 条件 | 请求和事件时必填，格式 `domain.action` |
| `params` | object | 否 | 请求参数 |
| `result` | any | 否 | 响应数据 |
| `error` | object | 否 | 错误信息 |
| `metadata` | object | 否 | 附加元数据（超时、追踪ID等） |
| `timestamp` | long | 是 | 毫秒时间戳 |

### 2.2 消息类型

- **request**: PC → 设备的命令请求
- **response**: 设备 → PC 的命令响应（通过 id 关联到对应 request）
- **event**: 设备 → PC 的异步事件通知
- **stream_data**: 设备 → PC 的流式数据（性能指标等）

### 2.3 错误格式

```json
{
  "code": 4001,
  "category": "ELEMENT_NOT_FOUND",
  "message": "No element matching selector: {resourceId: btn_login}"
}
```

---

## 3. 二进制通道协议

二进制通道 (`:18901`) 使用自定义帧头：

```
┌──────────┬───────┬──────────────────┬──────┬────────┬─────────┐
│ Magic(1B)│Flags  │ RequestID (16B)  │ Type │ Length │ Payload │
│  0xA7    │ (1B)  │   UUID bytes     │ (1B) │ (4B)  │  (N B)  │
└──────────┴───────┴──────────────────┴──────┴────────┴─────────┘
```

### 3.1 字段说明

| 字段 | 大小 | 说明 |
|------|------|------|
| Magic | 1 byte | 固定值 `0xA7`，用于帧同步 |
| Flags | 1 byte | 标志位（保留） |
| RequestID | 16 bytes | 关联的请求 UUID |
| Type | 1 byte | 负载类型（见下表） |
| Length | 4 bytes | 负载长度（大端序） |
| Payload | N bytes | 实际数据 |

### 3.2 负载类型

| 值 | 类型 | 说明 |
|----|------|------|
| `0x01` | SCREENSHOT | PNG 截图数据 |
| `0x02` | FILE | 文件传输数据 |
| `0x03` | LOG | 日志数据 |
| `0x04` | CUSTOM | 自定义插件数据 |

---

## 4. 方法清单

### 4.1 设备操作 (device.*)

| 方法 | 说明 | 参数 | 返回 |
|------|------|------|------|
| `device.info` | 获取设备信息 | 无 | DeviceInfo |
| `device.screenshot` | 截屏 | `{format, quality, scale}` | 二进制通道返回 |
| `device.shell` | 执行 shell 命令 | `{command, timeout}` | `{stdout, stderr, exitCode}` |
| `device.reboot` | 重启设备 | `{mode}` | 无 |

### 4.2 UI 操作 (ui.*)

| 方法 | 说明 | 参数 | 返回 |
|------|------|------|------|
| `ui.find` | 查找控件 | `{selector}` | `UiElement[]` |
| `ui.click` | 点击 | `{selector}` / `{x, y}` | `{success}` |
| `ui.type` | 文字输入 | `{selector, text, append}` | `{success}` |
| `ui.swipe` | 滑动 | `{startX, startY, endX, endY, duration}` | `{success}` |
| `ui.scroll` | 滚动 | `{selector, direction, distance}` | `{success}` |
| `ui.dump` | 导出控件树 | `{format}` | 完整控件树 |
| `ui.waitFor` | 等待控件出现 | `{selector, timeout, interval}` | `UiElement` |
| `ui.gesture` | 复杂手势 | `{points[], duration}` | `{success}` |

### 4.3 性能采集 (perf.*)

| 方法 | 说明 | 参数 | 返回 |
|------|------|------|------|
| `perf.start` | 开始采集 | `{package, metrics[], interval}` | `{sessionId}` |
| `perf.stop` | 停止采集 | `{sessionId}` | 完整性能报告 |
| `perf.snapshot` | 单次快照 | `{package, metrics[]}` | 当前指标 |
| `perf.stream` | 实时流推送 | `{sessionId}` | 通过事件通道推送 |

### 4.4 应用管理 (app.*)

| 方法 | 说明 | 参数 | 返回 |
|------|------|------|------|
| `app.launch` | 启动应用 | `{package, activity, clearState}` | `{success}` |
| `app.stop` | 停止应用 | `{package}` | `{success}` |
| `app.clear` | 清除数据 | `{package}` | `{success}` (需 Root) |
| `app.install` | 安装 APK | `{path}` | `{success}` |
| `app.uninstall` | 卸载 | `{package}` | `{success}` |
| `app.permissions` | 权限管理 | `{package, permissions[], action}` | `{success}` (需 Root) |

### 4.5 日志 (log.*)

| 方法 | 说明 | 参数 | 返回 |
|------|------|------|------|
| `log.start` | 开始抓取 | `{filters[], level}` | `{sessionId}` |
| `log.stop` | 停止抓取 | `{sessionId}` | 日志内容 |
| `log.filter` | 设置过滤 | `{sessionId, filters[]}` | `{success}` |
| `log.dump` | 导出日志 | `{lines, level}` | 日志内容 |

### 4.6 文件操作 (file.*)

| 方法 | 说明 | 参数 | 返回 |
|------|------|------|------|
| `file.push` | 推送文件 | `{remotePath}` + 二进制通道 | `{success}` |
| `file.pull` | 拉取文件 | `{remotePath}` | 二进制通道返回 |
| `file.list` | 列出文件 | `{path, recursive}` | 文件列表 |
| `file.delete` | 删除文件 | `{path}` | `{success}` |

### 4.7 系统 (system.*)

| 方法 | 说明 | 参数 | 返回 |
|------|------|------|------|
| `system.capabilities` | 查询能力 | 无 | 能力清单 |
| `system.heartbeat` | 心跳检测 | 无 | `{alive, uptime}` |
| `system.configure` | 动态配置 | `{key, value}` | `{success}` |

---

## 5. 错误码体系

| 范围 | 分类 | 说明 |
|------|------|------|
| 1000-1999 | TRANSPORT | 传输层错误 |
| 2000-2999 | DEVICE | 设备操作错误 |
| 3000-3999 | APP | 应用管理错误 |
| 4000-4999 | UI | UI 操作错误 |
| 5000-5999 | PERFORMANCE | 性能采集错误 |
| 6000-6999 | FILE | 文件操作错误 |
| 7000-7999 | PLUGIN | 插件错误 |
| 9000-9999 | INTERNAL | 内部错误 |

### 常用错误码

| 代码 | 名称 | 可恢复 | 说明 |
|------|------|--------|------|
| 1001 | CONNECTION_FAILED | 是 | 连接失败 |
| 1002 | TIMEOUT | 是 | 请求超时 |
| 1003 | AUTH_FAILED | 否 | 认证失败 |
| 2001 | DEVICE_NOT_FOUND | 否 | 设备未找到 |
| 2003 | ROOT_REQUIRED | 否 | 需要 Root 权限 |
| 4001 | ELEMENT_NOT_FOUND | 是 | 控件未找到 |
| 4002 | ELEMENT_NOT_VISIBLE | 是 | 控件不可见 |
| 4005 | GESTURE_FAILED | 是 | 手势执行失败 |

---

## 6. 事件类型

### 连接事件
- `connection.established` — 连接建立
- `connection.lost` — 连接断开
- `connection.reconnecting` — 重连中

### 测试事件
- `task.started` — 测试任务开始
- `task.completed` — 测试任务完成
- `task.failed` — 测试任务失败

### 性能事件
- `perf.data` — 性能数据点
- `perf.alert` — 性能告警

### 设备事件
- `device.connected` — 设备连接
- `device.disconnected` — 设备断开
- `app.crashed` — 应用崩溃

---

## 7. 认证机制

采用 Token 认证：

1. PC 端在连接时携带 Token
2. Agent 端验证 Token 并创建 Session
3. Session 关联到 WebSocket 连接
4. Token 可配置或自动生成

```json
// 认证请求（首条消息）
{
  "type": "request",
  "method": "system.auth",
  "params": { "token": "your-secret-token" }
}
```
