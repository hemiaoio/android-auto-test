# AutoTest Python API 参考

## 1. 测试装饰器

### `@test_case`

```python
from autotest.automation.decorators import test_case

@test_case(
    name="测试名称",           # 必填：显示名称
    tags=["smoke", "login"],  # 可选：标签列表，用于过滤
    priority=1,               # 可选：优先级（越高越先执行），默认 0
    devices=["serial1"],      # 可选：限定设备列表
    retry=0,                  # 可选：失败重试次数，默认 0
    timeout=30,               # 可选：超时时间（秒），默认 30
)
async def test_example(device: Device):
    pass
```

被装饰的函数自动注册到全局测试注册表，通过 `TestRunner.discover()` 发现。

---

## 2. Device — 设备操作门面

```python
from autotest.automation.dsl import Device
from autotest.device.client import DeviceClient

client = DeviceClient(serial="abc123", host="localhost", port=28900)
device = Device(client)
```

### 2.1 设备信息

```python
info = await device.info()
# 返回: DeviceInfo
#   .model: str           — 设备型号
#   .manufacturer: str    — 制造商
#   .android_version: str — Android 版本
#   .sdk_version: int     — SDK 版本
#   .screen_width: int    — 屏幕宽度
#   .screen_height: int   — 屏幕高度
#   .is_rooted: bool      — 是否 Root
#   .is_accessibility_enabled: bool — 无障碍是否启用
```

### 2.2 截图

```python
screenshot_bytes = await device.screenshot(tag="step_1")
# 返回: bytes (PNG)
# tag 参数会记录到测试报告中
```

### 2.3 Shell 命令

```python
result = await device.shell("pm list packages")
# 返回: ShellResult
#   .stdout: str
#   .stderr: str
#   .exit_code: int
```

---

## 3. AppController — 应用管理

```python
app = device.app("com.example.myapp")
```

### 方法

```python
await app.launch()                   # 启动应用
await app.launch(clear_state=True)   # 清除数据后启动
await app.stop()                     # 停止应用
await app.clear_data()               # 清除数据（需 Root）
await app.install("/path/to/app.apk") # 安装 APK
await app.uninstall()                # 卸载应用
```

---

## 4. UiSelector — UI 控件选择器

```python
selector = device.ui(
    text="登录",                    # 精确匹配文本
    text_contains="欢迎",           # 包含文本
    text_starts_with="第",          # 文本前缀
    resource_id="btn_submit",      # 资源 ID
    class_name="android.widget.Button",  # 类名
    description="返回",             # contentDescription
    package="com.example.app",     # 包名
    index=0,                       # 同类元素索引
    clickable=True,                # 可点击
    enabled=True,                  # 可用
    focusable=True,                # 可聚焦
    scrollable=False,              # 可滚动
    checkable=False,               # 可勾选
    checked=False,                 # 已勾选
)
```

**注意**: Python 端使用 `snake_case`，自动转换为协议要求的 `camelCase`。

### 4.1 操作方法

```python
# 点击
await selector.click()

# 长按
await selector.long_click()

# 输入文字
await selector.type("hello world")

# 清除文字
await selector.clear()

# 滑动
await selector.swipe(direction="up", distance=500)

# 获取文本
text = await selector.get_text()

# 获取属性
attrs = await selector.get_attrs()

# 检查是否存在
exists = await selector.exists()
```

### 4.2 等待

```python
# 等待控件出现
element = await selector.wait_for(timeout=10)
# 返回: UiElement（含 .exists 属性）

# 等待控件消失
await selector.wait_gone(timeout=10)
```

---

## 5. PerfController — 性能采集

```python
perf = device.perf
```

### 5.1 启动采集

```python
session = await perf.start(
    package="com.example.myapp",
    metrics=["cpu", "memory", "fps", "network", "battery"],
    interval=1000,  # 采集间隔（毫秒）
)
# 返回: PerfSession
```

### 5.2 停止采集

```python
report = await session.stop()
# 返回: PerfReport
#   .session_id: str
#   .duration_ms: float
#   .avg_cpu: float       — 平均 CPU 使用率 (%)
#   .avg_memory: float    — 平均内存使用 (MB)
#   .avg_fps: float       — 平均帧率
#   .data: dict           — 原始数据
```

### 5.3 单次快照

```python
snapshot = await perf.snapshot(
    package="com.example.myapp",
    metrics=["cpu", "memory"]
)
```

---

## 6. EventBus — 事件总线

```python
from autotest.core.events import EventBus, Event

bus = EventBus()

# 订阅特定事件
async def on_test_complete(event: Event):
    print(f"Test completed: {event.data}")

bus.on("test.completed", on_test_complete)

# 订阅所有事件
bus.on_all(lambda e: print(e.type))

# 发射事件
await bus.emit(Event(
    type="test.completed",
    source="runner",
    data={"name": "test_login", "status": "passed"}
))

# 取消订阅
bus.off("test.completed", on_test_complete)
```

---

## 7. DeviceManager — 多设备管理

```python
from autotest.device.manager import DeviceManager

async with DeviceManager() as manager:
    # 连接指定设备
    client = await manager.connect("abc123")

    # 连接所有设备
    clients = await manager.connect_all()

    # 获取已连接客户端
    client = manager.get_client("abc123")

    # 断开特定设备
    await manager.disconnect("abc123")
```

---

## 8. TestRunner — 测试执行器

```python
from autotest.automation.runner import TestRunner
from autotest.core.events import EventBus

event_bus = EventBus()
runner = TestRunner(event_bus)

# 发现测试
tests = runner.discover(["tests/"])

# 按标签过滤
tests = runner.filter_tests(tests, tags=["smoke"])

# 运行测试
results = await runner.run(tests, client)
# 返回: list[TestResult]
```

---

## 9. ParallelExecutor — 并行执行器

```python
from autotest.scheduler.executor import ParallelExecutor

executor = ParallelExecutor(
    device_manager=manager,
    event_bus=event_bus,
    max_workers=8,       # 最大并发设备数
)

result = await executor.execute(
    tests,
    strategy="round_robin",  # round_robin | capability_match | single_device | duplicate
)
# 返回: ExecutionResult
#   .results: list[TestResult]
#   .duration_ms: float
#   .device_count: int
#   .passed: int
#   .failed: int
#   .pass_rate: float
#   .is_success: bool
```

### 调度策略

| 策略 | 说明 |
|------|------|
| `round_robin` | 按优先级排序后轮流分配到各设备 |
| `capability_match` | 根据测试的 `devices` 字段匹配设备 |
| `single_device` | 所有测试运行在第一台设备上 |
| `duplicate` | 所有测试在每台设备上各运行一次（兼容性测试） |

---

## 10. ReportGenerator — 报告生成器

```python
from autotest.reporter.generator import ReportGenerator

generator = ReportGenerator(output_dir="./reports")

paths = generator.generate(
    results,                         # list[TestResult]
    formats=["html", "json", "junit", "allure"],
    perf_data=perf_report,          # 可选：性能数据
)
# 返回: list[str] — 生成的报告文件路径
```

### 支持的报告格式

| 格式 | 文件 | 说明 |
|------|------|------|
| `html` | `report.html` | 带样式的 HTML 报告，含图表和统计 |
| `json` | `report.json` | 结构化 JSON，可供其他工具消费 |
| `junit` | `report-junit.xml` | JUnit XML，兼容 Jenkins/GitHub Actions |
| `allure` | `allure-results/` | Allure 格式，可用 `allure serve` 查看 |

---

## 11. 配置管理

```python
from autotest.core.config import AutoTestConfig

# 从文件加载
config = AutoTestConfig.load("configs/default.yaml")

# 访问配置
config.device.adb_path        # "adb"
config.device.control_port    # 18900
config.runner.default_timeout # 30.0
config.reporter.output_dir    # "./reports"
config.reporter.formats       # ["html"]

# 保存配置
config.save("configs/my-config.yaml")
```

---

## 12. 异常体系

```python
from autotest.core.exceptions import (
    AutoTestError,          # 基础异常
    ConnectionError,        # 连接错误
    DeviceNotFoundError,    # 设备未找到
    TimeoutError,           # 操作超时
    ElementNotFoundError,   # 控件未找到
    RootRequiredError,      # 需要 Root
    ProtocolError,          # 协议错误
    PluginError,            # 插件错误
    ConfigurationError,     # 配置错误
)
```

所有自定义异常继承自 `AutoTestError`，便于统一捕获。

---

## 13. 插件系统

### 13.1 使用内置插件

```python
from autotest.plugins.host import PluginHost

host = PluginHost()
await host.discover()     # 发现插件
await host.start_all()    # 启动所有插件

# 获取插件实例
visual_diff = host.get_plugin("builtin.visual_diff")
result = await visual_diff.compare(actual_png, expected_png, threshold=0.01)
```

### 13.2 内置插件

| 插件 ID | 名称 | 功能 |
|---------|------|------|
| `builtin.ocr` | OCR 文字识别 | 从截图中识别文字 |
| `builtin.image_match` | 图像匹配 | 模板匹配定位控件 |
| `builtin.visual_diff` | 视觉回归 | 像素级截图对比 |

### 13.3 开发自定义插件

参见 [插件开发指南](./plugin-development.md)。
