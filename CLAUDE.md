# CLAUDE.md

本文件为 Claude Code (claude.ai/code) 在本仓库中工作时提供指引。

## 语言规则

- **所有回答和对话必须使用中文**
- **所有文档（Markdown、注释说明等）必须使用中文**
- 代码标识符（变量名、函数名、类名）保持英文

## 项目概述

AutoTest 是工业级 Android App 自动化测试平台，采用 **Kotlin（设备端 Agent）+ Python（PC 端控制器）** 混合架构。通过策略模式（CapabilityResolver）自动选择 Root 或 AccessibilityService 实现，上层 API 完全透明。

## 构建与运行命令

### 设备端 Agent（Kotlin/Gradle）

```bash
./gradlew :agent-app:assembleDebug          # 构建 Debug APK
./gradlew clean                              # 清理构建产物
```

APK 输出路径：`agent-app/build/outputs/apk/debug/agent-app-debug.apk`

### PC 端控制器（Python）

```bash
cd pc-controller
pip install -e .                   # 基础安装
pip install -e ".[all]"            # 全部功能（Web、报告、OCR）
pip install -e ".[dev]"            # 开发工具（pytest、ruff、mypy）
```

### 运行测试

```bash
cd pc-controller
pytest                                          # 运行所有 Python 单元测试
pytest tests/test_example.py                    # 运行单个测试文件
autotest run tests/ --tags smoke                # 按标签运行自动化测试
autotest run tests/ --parallel --device abc123  # 指定设备并行
```

### 代码检查

```bash
cd pc-controller
ruff check src/                    # 代码风格检查（行宽 100，目标 py310）
mypy src/                          # 类型检查（严格模式）
```

### CLI 命令

```bash
autotest devices                   # 列出已连接设备
autotest info <serial>             # 设备详情
autotest run <paths> [选项]        # 运行测试（--tags、--device、--parallel、--formats、--output）
autotest report <dir> --formats html  # 从已有结果重新生成报告
autotest dashboard --port 8080     # 启动 FastAPI Web 监控面板
```

## 架构

### 双层设计

**设备端**（7 个 Gradle 模块）：Android App 内嵌 Ktor WebSocket 服务，开放 3 个端口 — 控制通道（:18900，JSON）、二进制通道（:18901，截图/文件）、事件通道（:18902，推送）。`AgentEngine` 通过 `CommandRouter` 路由命令到处理器，由 `CapabilityResolver` 自动选择 Root 或 AccessibilityService 策略。

**PC 端**（Python 包 `autotest`，9 个子包）：通过 ADB 端口转发连接设备。`DeviceClient`（WebSocket）通过 UUID 关联请求/响应。面向用户的 API 为 `automation/dsl.py` 中的异步 DSL — `Device`、`UiSelector`、`AppController`、`PerfController`。

### 模块依赖链（Kotlin）

```
agent-app → agent-core → agent-protocol
                       → agent-accessibility
                       → agent-root
                       → agent-performance
                       → agent-transport → agent-protocol
```

### Python 核心包

| 包 | 职责 |
|----|------|
| `core/` | 事件总线（异步发布/订阅）、异常体系、YAML 配置、共享类型 |
| `device/` | ADB 封装、WebSocket 客户端（Future 关联请求响应）、多设备连接池 |
| `automation/` | `@test_case` 装饰器与注册表、`Device` 门面（DSL 入口）、测试执行器 |
| `scheduler/` | `TestPlanner`（4 种分配策略）+ `ParallelExecutor`（asyncio.Semaphore 并发控制） |
| `reporter/` | 多格式输出：HTML（内嵌 SVG 图表）、JSON、JUnit XML、Allure |
| `plugins/` | 插件基类 + 宿主；内置：OCR（多后端）、图像匹配、视觉回归（像素级对比） |

### 通信协议

消息使用 JSON 信封格式 `{id, type, method, params, result, error, metadata, timestamp}`。`type` 取值：`request`、`response`、`event`、`stream_data`。二进制通道（端口 18901）使用自定义帧头（魔数 0xA7 + UUID + 负载类型 + 长度）。

方法命名：`域.动作` — 如 `ui.click`、`perf.start`、`device.screenshot`、`app.launch`。

### 双模式策略

`CapabilityResolver` 自动检测 Root 可用性，为每类操作注册最优策略（`InputStrategy`、`ScreenCaptureStrategy`、`HierarchyStrategy`）。输入/截图优先 Root；实时控件树优先 AccessibilityService。`automation/dsl.py` 中的 `UiSelector` 自动将 Python snake_case 参数转换为协议 camelCase。

## 配置

默认配置文件：`pc-controller/configs/default.yaml`。设备端口从 18900 起，PC 端通过 ADB forward 从 28900 起映射（每台设备占 3 个端口）。

环境变量通过 `pc-controller/.env` 管理（含 OCR API Key 等敏感信息，已被 .gitignore 排除）。

## 关键约定

- Python 异步代码统一使用 `asyncio`；`@test_case` 装饰的测试函数为 async，接收 `Device` 参数
- Kotlin 全面使用协程；所有命令处理器为 `suspend` 函数
- 错误码按范围分域：1000 传输、2000 设备、3000 应用、4000 UI、5000 性能、6000 文件、7000 插件、9000 内部
- pytest 配置 `asyncio_mode = "auto"` — 异步测试函数自动运行
- 文档使用中文，代码标识符使用英文
