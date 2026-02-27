# AutoTest 文档中心

**AutoTest** — 工业级 Android App 自动化测试平台

采用 Kotlin（设备端）+ Python（PC 端）混合架构，支持 Root / 非 Root 双模式。

---

## 文档目录

### 入门

| 文档 | 说明 |
|------|------|
| [快速入门](./getting-started.md) | 安装、配置、基本使用、编写第一个测试 |

### 设计 & 计划

| 文档 | 说明 |
|------|------|
| [架构设计](./plans/architecture.md) | 整体架构、模块划分、关键设计模式、技术选型 |
| [通信协议](./plans/protocol.md) | WebSocket 三端口协议、消息信封、方法清单、错误码 |
| [实施阶段](./plans/implementation-phases.md) | 6 个实施阶段的详细任务和验证标准 |

### API & 开发

| 文档 | 说明 |
|------|------|
| [Python API 参考](./api-reference.md) | 完整的 Python DSL API、测试装饰器、各模块接口 |
| [插件开发指南](./plugin-development.md) | Python 和 Kotlin 两端的插件开发流程 |

### 部署 & 集成

| 文档 | 说明 |
|------|------|
| [CI/CD 集成](./ci-cd-integration.md) | GitHub Actions、Jenkins、GitLab CI 集成模板 |

### 项目管理

| 文档 | 说明 |
|------|------|
| [待办事项](./TODO.md) | Agent 命令处理器实现进度、优先级、详细设计 |

---

## 项目结构

```
auto-test/
├── agent-app/              # Android Agent APK 主应用
├── agent-core/             # 核心引擎模块
├── agent-accessibility/    # AccessibilityService 模块（非Root）
├── agent-root/             # Root 操作模块
├── agent-performance/      # 性能采集模块
├── agent-transport/        # WebSocket 传输层
├── agent-protocol/         # 通信协议定义
├── pc-controller/          # PC 端 Python 控制器
│   └── src/autotest/
│       ├── core/           # 基础设施
│       ├── device/         # 设备管理
│       ├── automation/     # 自动化 DSL
│       ├── performance/    # 性能分析
│       ├── scheduler/      # 任务调度
│       ├── reporter/       # 报告生成
│       ├── plugins/        # 插件系统
│       ├── cli/            # 命令行工具
│       └── web/            # Web Dashboard
└── docs/                   # 本文档
```

---

## 核心能力

| 能力 | Root 模式 | 非 Root 模式 |
|------|-----------|-------------|
| UI 点击/输入/滑动 | input 命令注入 | AccessibilityService |
| 截图 | screencap 静默 | MediaProjection |
| 控件树获取 | uiautomator dump | A11y NodeInfo |
| App 安装 | pm install 静默 | PackageInstaller |
| 清除数据 | pm clear | 不支持 |
| 性能采集 | /proc + dumpsys 全量 | 有限 API |
| 全局 Logcat | Root shell 全进程 | 仅自身进程 |
| 权限授予 | pm grant | 不支持 |

---

## 快速开始

```bash
# 1. 安装 PC 端
cd pc-controller && pip install -e ".[web,report]"

# 2. 构建并安装 Agent
./gradlew :agent-app:assembleDebug
adb install agent-app/build/outputs/apk/debug/agent-app-debug.apk

# 3. 启动 Agent（在设备上打开 App 并点击 Start）

# 4. 查看设备
autotest devices

# 5. 运行测试
autotest run tests/ --tags smoke

# 6. 查看 Dashboard
autotest dashboard --port 8080
```
