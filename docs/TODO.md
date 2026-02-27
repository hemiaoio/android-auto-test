# 待办事项：Agent 命令处理器实现

## 背景

协议层 (`agent-protocol/Methods.kt`) 定义了 **60+ 个方法**，但设备端 Agent 目前仅实现了 **5 个处理器**。
PC 端测试框架（DSL / TestRunner）在调用未实现的方法时会收到 `Unknown method` 错误。

### 当前已实现

| 方法 | 模块 | 说明 |
|------|------|------|
| `system.capabilities` | agent-core (AgentEngine) | 返回设备能力信息 |
| `system.heartbeat` | agent-core (AgentEngine) | 心跳 / 健康检查 |
| `perf.start` | agent-performance | 启动性能监控会话 |
| `perf.stop` | agent-performance | 停止并返回性能数据 |
| `perf.snapshot` | agent-performance | 获取当前性能快照 |

### 基础设施已就绪

以下接口/策略已定义，处理器实现可直接委托：

- `DeviceController` — 统一设备操作接口（点击、滑动、输入、截图、Shell、App 管理）
- `InputStrategy` — Root (`input` 命令) / 非 Root (AccessibilityService) 输入策略
- `ScreenCaptureStrategy` — Root (`screencap`) / 非 Root (MediaProjection) 截图策略
- `HierarchyStrategy` — Root (`uiautomator dump`) / 非 Root (A11y NodeInfo) 控件树策略
- `ShellExecutor` — Shell 命令执行器
- `CommandHandler` — 命令处理器接口（`method` + `handle()` + `validate()`）
- `CommandRouter` — 命令路由器（通过 `register()` 注册处理器）

---

## Phase 1：核心命令（OCR 测试链路必需）

> 优先级：**P0** — 不实现则无法运行任何测试

### 1.1 App 命令处理器

新建 `agent-core/src/main/kotlin/com/auto/agent/core/handlers/AppHandlers.kt`

| 方法 | 处理器类 | 说明 | 委托目标 |
|------|---------|------|---------|
| `app.launch` | `AppLaunchHandler` | 启动应用，返回启动耗时(ms) | `DeviceController.launchApp()` |
| `app.stop` | `AppStopHandler` | 停止应用（`am force-stop`） | `DeviceController.stopApp()` |
| `app.info` | `AppInfoHandler` | 获取应用信息（是否运行等） | `ShellExecutor.execute("dumpsys ...")` |

**参数与返回值：**

```
app.launch:
  params: { packageName: String, activity: String?, clearState: Boolean, waitForIdle: Boolean }
  result: { launchTimeMs: Long }

app.stop:
  params: { packageName: String, force: Boolean }
  result: { success: Boolean }

app.info:
  params: { packageName: String }
  result: { packageName, versionName, versionCode, isRunning, ... }
```

### 1.2 Device 命令处理器

新建 `agent-core/src/main/kotlin/com/auto/agent/core/handlers/DeviceHandlers.kt`

| 方法 | 处理器类 | 说明 | 委托目标 |
|------|---------|------|---------|
| `device.info` | `DeviceInfoHandler` | 设备信息（型号/系统/分辨率） | `DeviceController.getDeviceInfo()` |
| `device.screenshot` | `ScreenshotHandler` | 截图，返回 Base64 PNG | `ScreenCaptureStrategy.capture()` |
| `device.shell` | `ShellHandler` | 执行 Shell 命令 | `ShellExecutor.execute()` |
| `device.inputKey` | `InputKeyHandler` | 发送按键事件 | `InputStrategy.keyEvent()` |
| `device.wake` | `WakeHandler` | 唤醒屏幕 | `ShellExecutor.execute("input keyevent KEYCODE_WAKEUP")` |

**参数与返回值：**

```
device.screenshot:
  params: { quality: Int?, scale: Float? }
  result: { data: String(base64), width: Int, height: Int, format: "png" }

device.shell:
  params: { command: String, asRoot: Boolean? }
  result: { exitCode: Int, stdout: String, stderr: String }

device.inputKey:
  params: { keyCode: Int }
  result: { success: Boolean }
```

### 1.3 UI 命令处理器

新建 `agent-core/src/main/kotlin/com/auto/agent/core/handlers/UiHandlers.kt`

| 方法 | 处理器类 | 说明 | 委托目标 |
|------|---------|------|---------|
| `ui.click` | `UiClickHandler` | 坐标点击或选择器点击 | `InputStrategy.click()` |
| `ui.find` | `UiFindHandler` | 查找 UI 元素 | `HierarchyStrategy.findElements()` |
| `ui.type` | `UiTypeHandler` | 输入文字 | `InputStrategy.type()` |
| `ui.dump` | `UiDumpHandler` | 导出控件树 | `HierarchyStrategy.dump()` |
| `ui.waitFor` | `UiWaitForHandler` | 等待元素出现/消失 | 轮询 `findElements()` |

**参数与返回值：**

```
ui.click:
  params: { x: Int, y: Int } 或 { selector: { text?, resourceId?, className?, ... } }
  result: { success: Boolean }

ui.find:
  params: { selector: { text?, resourceId?, className?, contentDesc?, ... } }
  result: { elements: [{ text, resourceId, className, bounds, ... }] }

ui.type:
  params: { text: String, selector?: ... }
  result: { success: Boolean }

ui.dump:
  params: {}
  result: { hierarchy: String(XML) 或 elements: [...] }

ui.waitFor:
  params: { selector: {...}, timeout: Long, condition: "exists"|"gone" }
  result: { found: Boolean, element?: {...} }
```

---

## Phase 2：扩展命令

> 优先级：**P1** — 完善体验，非阻塞

### 2.1 App 扩展

| 方法 | 说明 |
|------|------|
| `app.clear` | 清除应用数据（`pm clear`，需 Root） |
| `app.install` | 安装 APK（`pm install`） |
| `app.uninstall` | 卸载应用（`pm uninstall`） |
| `app.list` | 列出已安装应用 |
| `app.permissions` | 查询/授予应用权限 |

### 2.2 Device 扩展

| 方法 | 说明 |
|------|------|
| `device.reboot` | 重启设备 |
| `device.rotation` | 获取/设置屏幕方向 |
| `device.clipboard` | 读写剪贴板 |

### 2.3 UI 扩展

| 方法 | 说明 |
|------|------|
| `ui.longClick` | 长按 |
| `ui.doubleClick` | 双击 |
| `ui.swipe` | 滑动手势 |
| `ui.scroll` | 滚动 |
| `ui.toast` | Toast 检测 |
| `ui.gesture` | 自定义手势 |
| `ui.pinch` | 缩放手势 |

### 2.4 Log / File / Task

| 类别 | 方法 |
|------|------|
| Log | `log.start` / `log.stop` / `log.filter` / `log.dump` |
| File | `file.push` / `file.pull` / `file.list` / `file.delete` / `file.stat` / `file.mkdir` |
| Task | `task.execute` / `task.cancel` / `task.status` / `task.list` |

### 2.5 System 扩展

| 方法 | 说明 |
|------|------|
| `system.configure` | 运行时修改 Agent 配置 |
| `system.shutdown` | 远程关闭 Agent |
| `perf.stream` | 实时推送性能数据 |

---

## 实现指南

### 处理器代码结构

```kotlin
class AppLaunchHandler(
    private val controller: DeviceController
) : CommandHandler {
    override val method = Methods.App.LAUNCH

    override suspend fun handle(
        params: JsonObject?,
        context: RequestContext
    ): JsonElement {
        val packageName = params?.get("packageName")?.jsonPrimitive?.content
            ?: throw IllegalArgumentException("packageName is required")
        val activity = params["activity"]?.jsonPrimitive?.contentOrNull
        val clearState = params["clearState"]?.jsonPrimitive?.booleanOrNull ?: false

        val launchTimeMs = controller.launchApp(packageName, activity, clearState)
            .getOrThrow()

        return buildJsonObject {
            put("launchTimeMs", JsonPrimitive(launchTimeMs))
        }
    }
}
```

### 注册方式

在 `AgentEngine.start()` 或 Koin 模块中注册：

```kotlin
// AgentEngine.kt
private fun registerCoreHandlers() {
    val controller = deviceController  // 由 Koin 注入
    commandRouter.register(AppLaunchHandler(controller))
    commandRouter.register(AppStopHandler(controller))
    commandRouter.register(ScreenshotHandler(controller))
    commandRouter.register(UiClickHandler(controller))
    // ... 其他处理器
}
```

### 构建验证

```bash
./gradlew :agent-app:assembleDebug
adb install agent-app/build/outputs/apk/debug/agent-app-debug.apk
autotest run tests/ --tags ocr --device 127.0.0.1:58526
```
