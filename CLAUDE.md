# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 语言规则

- **所有回答和对话必须使用中文**
- **所有文档（Markdown、注释说明等）必须使用中文**
- 代码标识符（变量名、函数名、类名）保持英文

## Project Overview

AutoTest is an industrial-grade Android app automation testing platform using a **Kotlin (device-side Agent) + Python (PC-side controller)** hybrid architecture. It supports both Root and non-Root modes via a strategy pattern (CapabilityResolver) that transparently selects the best implementation for each operation.

## Build & Run Commands

### Android Agent (Kotlin/Gradle)

```bash
./gradlew :agent-app:assembleDebug          # Build debug APK
./gradlew clean                              # Clean all builds
```

The APK outputs to `agent-app/build/outputs/apk/debug/agent-app-debug.apk`.

### PC Controller (Python)

```bash
cd pc-controller
pip install -e .                   # Basic install
pip install -e ".[all]"            # All features (web, report, ocr)
pip install -e ".[dev]"            # Dev tools (pytest, ruff, mypy)
```

### Running Tests

```bash
cd pc-controller
pytest                                          # Run all Python unit tests
pytest tests/test_example.py                    # Run single test file
autotest run tests/ --tags smoke                # Run automation tests by tag
autotest run tests/ --parallel --device abc123  # Target specific device
```

### Linting & Type Checking

```bash
cd pc-controller
ruff check src/                    # Lint (line-length: 100, target: py310)
mypy src/                          # Type check (strict mode)
```

### CLI Commands

```bash
autotest devices                   # List connected devices
autotest info <serial>             # Device details
autotest run <paths> [options]     # Run tests (--tags, --device, --parallel, --formats, --output)
autotest report <dir> --formats html  # Regenerate reports from saved results
autotest dashboard --port 8080     # Start FastAPI web dashboard
```

## Architecture

### Two-Tier Design

**Device side** (7 Gradle modules): An Android app running a Ktor WebSocket server on 3 ports — control (:18900, JSON), binary (:18901, screenshots/files), events (:18902, push). The `AgentEngine` routes commands through `CommandRouter` to handlers that use either Root (su shell) or AccessibilityService strategies, resolved automatically by `CapabilityResolver`.

**PC side** (Python package `autotest`, 9 sub-packages): Connects to devices via ADB port forwarding. The `DeviceClient` (WebSocket) correlates requests/responses by UUID. User-facing API is the async DSL in `automation/dsl.py` — `Device`, `UiSelector`, `AppController`, `PerfController`.

### Module Dependency Chain (Kotlin)

```
agent-app → agent-core → agent-protocol
                       → agent-accessibility
                       → agent-root
                       → agent-performance
                       → agent-transport → agent-protocol
```

### Key Python Packages

| Package | Role |
|---------|------|
| `core/` | EventBus (async pub/sub), exception hierarchy, YAML config, shared types |
| `device/` | ADB wrapper, WebSocket client with future-based request correlation, multi-device connection pool |
| `automation/` | `@test_case` decorator with registry, `Device` facade (DSL entry point), `TestRunner` |
| `scheduler/` | `TestPlanner` (4 distribution strategies) + `ParallelExecutor` (asyncio.Semaphore bounded concurrency) |
| `reporter/` | Multi-format output: HTML (embedded SVG charts), JSON, JUnit XML, Allure |
| `plugins/` | Plugin base class + host; builtins: OCR, image matching, visual diff (pixel-level comparison) |

### Communication Protocol

Messages use a JSON envelope with `{id, type, method, params, result, error, metadata, timestamp}`. The `type` field is one of: `request`, `response`, `event`, `stream_data`. Binary frames on port 18901 use a custom header (magic byte 0xA7 + UUID + payload type + length).

Method naming: `domain.action` — e.g., `ui.click`, `perf.start`, `device.screenshot`, `app.launch`.

### Dual-Mode Strategy

`CapabilityResolver` auto-detects Root availability and registers the best strategy for each operation type (`InputStrategy`, `ScreenCaptureStrategy`, `HierarchyStrategy`). Root is preferred for input/screenshots; AccessibilityService is preferred for real-time UI hierarchy. The `automation/dsl.py` `UiSelector` automatically converts Python snake_case params to protocol camelCase.

## Configuration

Default config: `pc-controller/configs/default.yaml`. Device ports start at 18900 (agent-side), PC maps them via ADB forward starting at 28900 (3 ports per device).

## Key Conventions

- All Python async code uses `asyncio`; test functions decorated with `@test_case` are async and receive a `Device` parameter
- Kotlin uses coroutines throughout; all command handlers are `suspend` functions
- Error codes are namespaced by range: 1000s=transport, 2000s=device, 3000s=app, 4000s=UI, 5000s=perf, 6000s=file, 7000s=plugin, 9000s=internal
- pytest configured with `asyncio_mode = "auto"` — async test functions run automatically
- The project language is mixed Chinese/English — documentation is in Chinese, code identifiers and comments are in English
