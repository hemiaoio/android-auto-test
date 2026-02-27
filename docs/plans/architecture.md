# AutoTest 架构设计文档

## 1. 概述

AutoTest 是一个工业级 Android App 自动化测试平台，采用 **Kotlin（设备端 Agent）+ Python（PC 端控制器）** 混合架构。支持 Root 和非 Root 双模式，覆盖 UI 自动化、性能监控、稳定性测试、批量设备管理等全场景。

设计理念参考腾讯 WeTest、字节跳动内部自动化工具等成熟工业平台。

---

## 2. 整体架构

```
┌─────────────────────────────────────────────────────────────────┐
│                    PC端 (Python 3.10+)                          │
│  ┌──────────┐ ┌────────────┐ ┌───────────┐ ┌───────────────┐   │
│  │ CLI工具   │ │ Web Dashboard│ │ CI/CD集成 │ │ 测试报告生成  │   │
│  └─────┬────┘ └──────┬─────┘ └─────┬─────┘ └───────┬───────┘   │
│        └──────────────┴─────────────┴───────────────┘           │
│                          │                                      │
│  ┌───────────────────────┴──────────────────────────────┐       │
│  │              Core Engine (autotest)                   │       │
│  │  DeviceManager │ TestRunner │ Scheduler │ PluginHost  │       │
│  └───────────────────────┬──────────────────────────────┘       │
│                          │ ADB Forward / WiFi                   │
│                     WebSocket x3                                │
│             (:18900 控制 / :18901 二进制 / :18902 事件)           │
└──────────────────────────┬──────────────────────────────────────┘
                           │
┌──────────────────────────┴──────────────────────────────────────┐
│                  设备端 Agent App (Kotlin)                       │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │                    AgentEngine                            │   │
│  │  ┌──────────────┐ ┌───────────────┐ ┌─────────────────┐  │   │
│  │  │ Accessibility │ │ Root Bridge   │ │ Performance     │  │   │
│  │  │ Bridge        │ │ (su shell)    │ │ Collector       │  │   │
│  │  └──────────────┘ └───────────────┘ └─────────────────┘  │   │
│  │  ┌──────────────┐ ┌───────────────┐ ┌─────────────────┐  │   │
│  │  │ Transport    │ │ Plugin Manager│ │ Task Executor   │  │   │
│  │  │ (WebSocket)  │ │ (DEX加载)     │ │ (协程调度)       │  │   │
│  │  └──────────────┘ └───────────────┘ └─────────────────┘  │   │
│  └──────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

---

## 3. 模块划分

### 3.1 设备端模块（Kotlin / Android）

| 模块 | 目录 | 职责 |
|------|------|------|
| `agent-protocol` | `agent-protocol/` | 通信协议定义：消息信封、方法常量、错误码、事件类型 |
| `agent-core` | `agent-core/` | 核心引擎：命令路由、策略解析、插件管理 |
| `agent-accessibility` | `agent-accessibility/` | 非 Root 自动化：AccessibilityService 实现 |
| `agent-root` | `agent-root/` | Root 自动化：su shell 执行器、Root 输入注入 |
| `agent-performance` | `agent-performance/` | 性能采集：CPU/内存/FPS/网络/电量 |
| `agent-transport` | `agent-transport/` | 传输层：Ktor WebSocket 服务端 |
| `agent-app` | `agent-app/` | App 壳工程：前台 Service、配置 UI |

### 3.2 PC 端模块（Python）

| 模块 | 目录 | 职责 |
|------|------|------|
| `core` | `pc-controller/src/autotest/core/` | 基础设施：事件总线、异常体系、配置、类型定义 |
| `device` | `pc-controller/src/autotest/device/` | 设备管理：ADB 封装、WebSocket 客户端、连接池 |
| `automation` | `pc-controller/src/autotest/automation/` | 自动化引擎：DSL API、装饰器、测试执行器 |
| `performance` | `pc-controller/src/autotest/performance/` | 性能分析：统计分析、图表生成 |
| `scheduler` | `pc-controller/src/autotest/scheduler/` | 任务调度：分配策略、并行执行器 |
| `reporter` | `pc-controller/src/autotest/reporter/` | 报告生成：HTML/JSON/JUnit/Allure |
| `plugins` | `pc-controller/src/autotest/plugins/` | 插件系统：OCR、图像匹配、视觉回归 |
| `cli` | `pc-controller/src/autotest/cli/` | 命令行工具：Typer CLI |
| `web` | `pc-controller/src/autotest/web/` | Web 控制台：FastAPI Dashboard |

---

## 4. 关键设计模式

### 4.1 策略模式 — CapabilityResolver

设备连接时自动检测能力，为每个操作选择最优实现策略：

```
Root → AccessibilityService → Shell Fallback
```

上层 API 完全透明，开发者无需关心底层实现差异。

```kotlin
class CapabilityResolver {
    fun resolveInputStrategy(): InputStrategy      // 输入注入策略
    fun resolveCaptureStrategy(): ScreenCaptureStrategy  // 截图策略
    fun resolveHierarchyStrategy(): HierarchyStrategy    // 控件树策略
}
```

### 4.2 命令路由 — CommandRouter

基于方法名的 ConcurrentHashMap 路由，支持动态注册和参数校验：

```kotlin
router.register("ui.click") { params -> /* 处理点击 */ }
router.register("perf.start") { params -> /* 开始采集 */ }
```

### 4.3 事件总线 — EventBus

Python 端异步事件总线，支持类型订阅和通配符监听：

```python
bus = EventBus()
bus.on("test.completed", handler)   # 精确订阅
bus.on_all(global_handler)          # 全局监听
await bus.emit(Event(type="test.completed", ...))
```

### 4.4 插件体系

- **设备端**: DexClassLoader 动态加载 APK/DEX 插件
- **PC 端**: Python entry_points + 目录扫描加载插件

---

## 5. Root vs 非 Root 能力矩阵

| 能力 | 非Root实现 | Root实现 | 策略 |
|------|-----------|---------|------|
| UI点击 | A11y `performAction` | `input tap` / InputManager | Root优先 |
| 文字输入 | A11y `ACTION_SET_TEXT` | `input text` via shell | Root优先 |
| 截图 | MediaProjection | `screencap -p` (静默) | Root优先 |
| 控件树 | A11y `AccessibilityNodeInfo` | `uiautomator dump` | A11y优先(实时) |
| App安装 | PackageInstaller (需确认) | `pm install` (静默) | Root优先 |
| 清除数据 | 不支持 | `pm clear` | Root专属 |
| 全局Logcat | 仅自身进程(API30+) | Root shell全进程 | Root增强 |
| 性能采集 | `Debug` API + 有限dumpsys | top/dumpsys/proc全量 | Root增强 |
| FPS监控 | Choreographer (前台) | `dumpsys SurfaceFlinger` | Root更精确 |
| 权限授予 | 不支持 | `pm grant` | Root专属 |

---

## 6. 技术选型

### 设备端 (Kotlin)

| 技术 | 选型 | 说明 |
|------|------|------|
| 最低 SDK | API 24 (Android 7.0) | 覆盖 95%+ 设备 |
| WebSocket | Ktor Server 2.3.7 | 轻量嵌入式服务端 |
| 异步 | Kotlin Coroutines 1.7.3 | 全异步协程 |
| 依赖注入 | Koin 3.5.3 | 轻量 DI 框架 |
| 序列化 | kotlinx.serialization 1.6.2 | JSON 编解码 |
| 插件加载 | DexClassLoader | 运行时 DEX 加载 |

### PC 端 (Python)

| 技术 | 选型 | 说明 |
|------|------|------|
| Python | 3.10+ | 类型注解支持 |
| WebSocket | websockets | 异步 WebSocket 客户端 |
| 异步 | asyncio | Python 原生异步 |
| CLI | Typer + Rich | 命令行交互 |
| Web | FastAPI + Uvicorn | Web Dashboard |
| 报告 | Jinja2 / Allure | 多格式报告 |
| 配置 | PyYAML | YAML 配置管理 |
| 打包 | hatch (pyproject.toml) | 现代 Python 打包 |

---

## 7. 数据流

### 7.1 测试执行流程

```
用户编写测试 → CLI/Runner 加载 → DeviceManager 连接设备
    → TestRunner 逐条执行 → DeviceClient 发送 WebSocket 命令
    → 设备 Agent 路由到 Handler → 执行操作 → 返回结果
    → Runner 收集结果 → ReportGenerator 生成报告
```

### 7.2 性能采集流程

```
perf.start 命令 → Agent 创建 PerfSession → 各 Collector 定时采集
    → 数据通过事件端口 (:18902) 实时推送 → PC 端 Analyzer 统计分析
    → perf.stop 命令 → 生成 PerfReport → 可视化图表
```

### 7.3 并行执行流程

```
TestPlanner 分配测试 → ParallelExecutor 创建 worker
    → asyncio.Semaphore 控制并发 → 每设备串行执行
    → asyncio.gather 收集结果 → 合并报告
```
