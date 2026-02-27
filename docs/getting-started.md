# AutoTest 快速入门指南

## 1. 环境要求

### PC 端
- Python 3.10+
- ADB 工具（Android SDK Platform-Tools）
- pip 或 hatch 包管理器

### 设备端
- Android 7.0+ (API 24+)
- USB 调试已启用
- （可选）Root 权限 — 可解锁更多能力

---

## 2. 安装

### 2.1 安装 PC 端控制器

```bash
cd pc-controller

# 基础安装
pip install -e .

# 安装完整功能（含 Web Dashboard、报告生成、OCR）
pip install -e ".[web,report,ocr]"
```

### 2.2 构建设备端 Agent

```bash
# 在项目根目录
./gradlew :agent-app:assembleDebug

# APK 生成位置
# agent-app/build/outputs/apk/debug/agent-app-debug.apk
```

### 2.3 安装 Agent 到设备

```bash
adb install agent-app/build/outputs/apk/debug/agent-app-debug.apk
```

---

## 3. 设备配置

### 3.1 启动 Agent

1. 在设备上打开 **AutoTest Agent** 应用
2. 点击 **Start Agent** 按钮启动服务
3. 状态栏会显示「Agent Running」通知

### 3.2 启用无障碍服务（非 Root 模式必需）

1. 进入设备 **设置 → 辅助功能 → 已安装的服务**
2. 找到 **AutoTest Agent** 并开启
3. 确认授权对话框

### 3.3 Root 模式（可选）

如果设备已 Root，Agent 会自动检测并启用 Root 增强能力。无需额外配置。

---

## 4. 基本使用

### 4.1 检查设备连接

```bash
autotest devices
```

输出示例：
```
┌──────────────────────────────┐
│     Connected Devices        │
├──────────┬────────┬──────────┤
│ Serial   │ State  │ Model    │
├──────────┼────────┼──────────┤
│ emulator │ device │ Pixel_6  │
│ abc123   │ device │ SM-G990B │
└──────────┴────────┴──────────┘
```

### 4.2 查看设备详情

```bash
autotest info <serial>
```

### 4.3 运行测试

```bash
# 运行指定目录下的所有测试
autotest run tests/

# 运行指定文件
autotest run tests/test_login.py

# 按标签过滤
autotest run tests/ --tags smoke --tags login

# 指定设备
autotest run tests/ --device abc123

# 多设备并行
autotest run tests/ --parallel

# 自定义报告格式和输出目录
autotest run tests/ --formats html --formats junit --output ./my-reports
```

### 4.4 生成报告

```bash
# 从已保存的结果重新生成报告
autotest report ./reports --formats html --formats allure
```

### 4.5 启动 Web Dashboard

```bash
autotest dashboard --port 8080
```

浏览器访问 `http://localhost:8080` 查看实时监控面板。

---

## 5. 编写测试用例

### 5.1 基本测试

```python
from autotest.automation.decorators import test_case
from autotest.automation.dsl import Device

@test_case(name="应用启动测试", tags=["smoke"])
async def test_app_launch(device: Device):
    """测试应用是否能正常启动"""
    await device.app("com.example.myapp").launch()

    # 等待主界面出现
    title = await device.ui(text="首页").wait_for(timeout=10)
    assert title.exists, "应用启动失败：未找到首页标题"
```

### 5.2 登录流程测试

```python
@test_case(name="登录流程测试", tags=["smoke", "login"], priority=1)
async def test_login(device: Device):
    await device.app("com.example.myapp").launch(clear_state=True)

    # 输入用户名和密码
    await device.ui(resource_id="et_username").type("admin")
    await device.ui(resource_id="et_password").type("password123")

    # 点击登录按钮
    await device.ui(text="登录").click()

    # 验证登录成功
    welcome = await device.ui(text_contains="欢迎").wait_for(timeout=10)
    assert welcome.exists, "登录失败：未出现欢迎页面"

    # 截图留证
    await device.screenshot(tag="login_success")
```

### 5.3 性能测试

```python
import asyncio

@test_case(name="应用性能基线", tags=["perf"])
async def test_performance(device: Device):
    # 启动性能采集
    perf = await device.perf.start(
        package="com.example.myapp",
        metrics=["cpu", "memory", "fps"]
    )

    # 执行操作
    await device.app("com.example.myapp").launch()
    await asyncio.sleep(30)  # 运行 30 秒

    # 停止采集并获取报告
    report = await perf.stop()

    # 断言性能指标
    assert report.avg_cpu < 30, f"CPU 使用率过高: {report.avg_cpu}%"
    assert report.avg_memory < 200, f"内存占用过高: {report.avg_memory}MB"
    assert report.avg_fps > 55, f"FPS 过低: {report.avg_fps}"
```

### 5.4 带重试的测试

```python
@test_case(
    name="不稳定网络测试",
    tags=["network"],
    retry=3,           # 最多重试 3 次
    timeout=60,        # 超时 60 秒
)
async def test_network_request(device: Device):
    await device.app("com.example.myapp").launch()
    await device.ui(text="刷新").click()
    data_view = await device.ui(resource_id="rv_data").wait_for(timeout=15)
    assert data_view.exists, "数据加载失败"
```

---

## 6. 选择器 API

支持多种方式定位 UI 控件：

```python
# 按文本
device.ui(text="登录")
device.ui(text_contains="欢迎")
device.ui(text_starts_with="第")

# 按资源 ID
device.ui(resource_id="btn_submit")

# 按类名
device.ui(class_name="android.widget.Button")

# 按 content-description
device.ui(description="返回按钮")

# 组合选择器
device.ui(class_name="android.widget.EditText", resource_id="et_username")

# 按索引
device.ui(text="选项", index=2)

# 按属性
device.ui(clickable=True, enabled=True)
```

---

## 7. 配置文件

默认配置文件位于 `pc-controller/configs/default.yaml`：

```yaml
device:
  adb_path: "adb"
  control_port: 18900
  binary_port: 18901
  event_port: 18902
  connection_timeout: 10.0
  command_timeout: 30.0

runner:
  default_timeout: 30.0
  retry_count: 0
  screenshot_on_failure: true
  parallel: false

reporter:
  output_dir: "./reports"
  formats:
    - html
  include_screenshots: true
  include_logs: true
```

可通过环境变量或命令行参数覆盖配置。

---

## 8. 项目结构（测试项目）

推荐的测试项目目录结构：

```
my-test-project/
├── tests/
│   ├── test_login.py         # 登录相关测试
│   ├── test_navigation.py    # 导航测试
│   ├── test_performance.py   # 性能测试
│   └── test_stability.py     # 稳定性测试
├── configs/
│   └── default.yaml          # 测试配置
├── baselines/                # 视觉回归基线图
├── reports/                  # 测试报告输出
└── requirements.txt
```

---

## 9. 常见问题

### Q: 设备连不上怎么办？

1. 确认 USB 调试已启用
2. 运行 `adb devices` 检查设备是否识别
3. 确认 Agent App 已安装并启动
4. 检查端口是否被占用

### Q: 非 Root 模式下哪些功能不可用？

主要限制：
- 无法静默安装 APK
- 无法清除应用数据
- 无法全局抓取 Logcat
- 截图需要用户授权一次（MediaProjection）
- 无法授予运行时权限

### Q: 如何同时在多台设备上运行测试？

```bash
autotest run tests/ --parallel
```

这会自动检测所有已连接设备，使用 round-robin 策略分配测试用例，并行执行。

### Q: 测试报告在哪里？

默认输出到 `./reports/` 目录。可通过 `--output` 参数或配置文件修改。
