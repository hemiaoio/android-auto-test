# AutoTest — 工业级 Android 自动化测试平台

采用 **Kotlin（设备端 Agent）+ Python（PC 端控制器）** 混合架构，支持 Root / 非 Root 双模式，覆盖 UI 自动化、性能监控、稳定性测试、批量设备管理等全场景。

设计参考腾讯 WeTest、字节跳动内部自动化工具。

## 架构概览

```
┌──────────────────── PC 端 (Python 3.10+) ────────────────────┐
│  CLI  │  Web Dashboard  │  CI/CD 集成  │  测试报告生成        │
│                          │                                    │
│   DeviceManager │ TestRunner │ Scheduler │ PluginHost          │
└──────────────────── WebSocket x3 ────────────────────────────┘
                  :18900 控制 / :18901 二进制 / :18902 事件
┌──────────────────── 设备端 Agent (Kotlin) ───────────────────┐
│  AccessibilityService  │  Root Bridge  │  性能采集            │
│  WebSocket Server (Ktor)  │  插件管理 (DEX)  │  协程调度      │
└──────────────────────────────────────────────────────────────┘
```

## 核心能力

| 能力 | Root 模式 | 非 Root 模式 |
|------|-----------|-------------|
| UI 点击/输入/滑动 | `input` 命令注入 | AccessibilityService |
| 截图 | `screencap` 静默 | MediaProjection |
| 控件树获取 | `uiautomator dump` | A11y NodeInfo |
| App 安装 | `pm install` 静默 | PackageInstaller |
| 清除数据 | `pm clear` | 不支持 |
| 性能采集 | `/proc` + `dumpsys` 全量 | 有限 API |
| 全局 Logcat | Root shell 全进程 | 仅自身进程 |
| OCR 文字识别 | 在线大模型 / PaddleOCR / Tesseract | 同左 |

## 快速开始

### 1. 克隆并初始化

```bash
git clone git@github.com:hemiaoio/android-auto-test.git
cd android-auto-test

# 安装 Git Hooks（拉取代码后自动检查 skills）
bash scripts/setup-hooks.sh
```

### 2. 安装 PC 端

```bash
cd pc-controller

# 基础安装
pip install -e .

# 完整功能（Web Dashboard + 报告 + OCR）
pip install -e ".[all]"
```

### 3. 配置 OCR（可选）

```bash
# 复制环境变量模板
cp .env.example .env

# 编辑 .env，填入 Deepseek / 豆包 / 通义千问等 API Key
# AUTOTEST_OCR_API_KEY=sk-your-key-here
```

### 4. 构建并安装 Agent

```bash
cd ..
./gradlew :agent-app:assembleDebug
adb install agent-app/build/outputs/apk/debug/agent-app-debug.apk
```

### 5. 在设备上启动 Agent

打开 **AutoTest Agent** 应用 → 点击 **Start Agent**，并在系统设置中启用无障碍服务（非 Root 模式必需）。

### 6. 验证连接

```bash
autotest devices
```

## 编写测试

```python
from autotest.automation.decorators import test_case
from autotest.automation.dsl import Device

@test_case(name="登录流程测试", tags=["smoke", "login"])
async def test_login(device: Device):
    await device.app("com.example.app").launch(clear_state=True)

    await device.ui(resource_id="et_username").type("admin")
    await device.ui(resource_id="et_password").type("pass123")
    await device.ui(text="登录").click()

    welcome = await device.ui(text_contains="欢迎").wait_for(timeout=10)
    assert welcome.exists, "登录失败"
```

### OCR 点击（无障碍树无法覆盖时）

```python
@test_case(name="OCR 点击示例", tags=["ocr"])
async def test_ocr(device: Device):
    await device.app("com.android.settings").launch()

    # 一行完成：截图 → OCR 识别 → 点击文字
    result = await device.ocr_click("WLAN", timeout=15)
    print(f"已点击 '{result.text}' @ ({result.click_x}, {result.click_y})")
```

## 运行测试

```bash
# 运行所有冒烟测试
autotest run tests/ --tags smoke

# 指定设备
autotest run tests/ --device abc123

# 多设备并行
autotest run tests/ --parallel

# 指定报告格式和输出目录
autotest run tests/ --formats html --formats junit --output ./reports
```

## CLI 命令

| 命令 | 说明 |
|------|------|
| `autotest devices` | 列出已连接设备 |
| `autotest info <serial>` | 设备详情 |
| `autotest run <path> [选项]` | 运行测试（`--tags` `--device` `--parallel` `--formats` `--output`） |
| `autotest report <dir>` | 从已有结果重新生成报告 |
| `autotest dashboard` | 启动 Web 实时监控面板（默认 `:8080`） |

## 项目结构

```
android-auto-test/
├── agent-app/              # Android Agent APK 主应用
├── agent-core/             # 核心引擎：命令路由、策略解析、插件管理
├── agent-accessibility/    # AccessibilityService 模块（非 Root）
├── agent-root/             # Root 模块：su shell、输入注入、截图
├── agent-performance/      # 性能采集：CPU / 内存 / FPS / 网络 / 电量
├── agent-transport/        # Ktor WebSocket 传输层
├── agent-protocol/         # 通信协议：消息信封、方法常量、错误码
├── pc-controller/          # PC 端 Python 控制器
│   ├── src/autotest/
│   │   ├── core/           # 事件总线、异常、配置、类型
│   │   ├── device/         # ADB 封装、WebSocket 客户端、多设备连接池
│   │   ├── automation/     # DSL API、@test_case 装饰器、测试引擎
│   │   ├── performance/    # 性能统计分析、SVG 图表
│   │   ├── scheduler/      # 多设备并行调度（4 种分配策略）
│   │   ├── reporter/       # 报告生成（HTML / JSON / JUnit / Allure）
│   │   ├── plugins/        # 插件系统（OCR / 图像匹配 / 视觉回归）
│   │   ├── cli/            # Typer 命令行工具
│   │   └── web/            # FastAPI Web Dashboard
│   ├── tests/              # 测试用例示例
│   └── configs/            # 默认配置
├── scripts/                # 工具脚本（hooks 安装、skills 检查）
└── docs/                   # 文档
```

## 技术栈

| 层 | 技术 |
|----|------|
| 设备端 | Kotlin · Ktor · Coroutines · Koin · kotlinx.serialization · Min SDK 24 |
| PC 端 | Python 3.10+ · asyncio · websockets · Typer · Rich · FastAPI · Pydantic |
| OCR | Deepseek / 豆包 / 通义千问 Vision API · PaddleOCR · Tesseract |
| 报告 | HTML（内嵌 SVG 图表）· JSON · JUnit XML · Allure |
| 构建 | Gradle 8.2 (Android) · Hatch (Python) |

## 文档

| 文档 | 说明 |
|------|------|
| [快速入门](docs/getting-started.md) | 安装配置、编写第一个测试 |
| [架构设计](docs/plans/architecture.md) | 整体架构、模块划分、设计模式 |
| [通信协议](docs/plans/protocol.md) | WebSocket 三端口协议、60+ 方法清单、错误码 |
| [Python API 参考](docs/api-reference.md) | DSL API、装饰器、各模块接口 |
| [插件开发指南](docs/plugin-development.md) | Python / Kotlin 双端插件开发 |
| [CI/CD 集成](docs/ci-cd-integration.md) | GitHub Actions / Jenkins / GitLab CI 模板 |

## 许可证

MIT
