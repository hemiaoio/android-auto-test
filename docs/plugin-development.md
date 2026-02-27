# AutoTest 插件开发指南

## 1. 概述

AutoTest 支持在设备端（Kotlin）和 PC 端（Python）两侧进行插件扩展。本文档覆盖两侧的插件开发流程。

---

## 2. Python 插件开发

### 2.1 插件接口

所有 Python 插件需继承 `Plugin` 抽象基类：

```python
from autotest.plugins.base import Plugin, PluginContext, PluginInfo

class MyPlugin(Plugin):
    """自定义插件示例"""

    def info(self) -> PluginInfo:
        return PluginInfo(
            id="my_org.my_plugin",
            name="My Custom Plugin",
            version="1.0.0",
            description="A custom plugin for AutoTest",
        )

    async def on_init(self, context: PluginContext) -> None:
        """插件初始化，接收上下文"""
        self.context = context
        self.data_dir = context.data_dir  # 插件数据目录

    async def on_start(self) -> None:
        """插件启动"""
        pass

    async def on_stop(self) -> None:
        """插件停止"""
        pass

    async def on_destroy(self) -> None:
        """插件销毁，释放资源"""
        pass
```

### 2.2 PluginInfo 字段

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | str | 全局唯一插件 ID，建议 `org.plugin_name` 格式 |
| `name` | str | 可读名称 |
| `version` | str | 语义化版本号 |
| `description` | str | 功能描述 |

### 2.3 PluginContext 字段

| 字段 | 类型 | 说明 |
|------|------|------|
| `data_dir` | str | 插件专属数据目录 |
| `config` | dict | 插件配置 |
| `event_bus` | EventBus | 事件总线实例 |

### 2.4 注册方式

#### 方式 1: Entry Points（推荐用于分发）

在你的 `pyproject.toml` 中：

```toml
[project.entry-points."autotest.plugins"]
my_plugin = "my_package.plugin:MyPlugin"
```

安装该包后，AutoTest 会自动发现并加载。

#### 方式 2: 目录加载

将插件文件放到指定目录（默认 `~/.autotest/plugins/`），PluginHost 会扫描目录中的 Python 文件并加载。

### 2.5 完整插件示例：自定义截图对比

```python
import io
from pathlib import Path
from autotest.plugins.base import Plugin, PluginContext, PluginInfo


class ScreenshotValidator(Plugin):
    """截图内容验证插件 — 检查特定区域是否包含预期颜色"""

    def __init__(self):
        self._context = None

    def info(self) -> PluginInfo:
        return PluginInfo(
            id="custom.screenshot_validator",
            name="Screenshot Validator",
            version="1.0.0",
            description="Validate screenshot regions for expected colors",
        )

    async def on_init(self, context: PluginContext) -> None:
        self._context = context

    async def on_start(self) -> None:
        pass

    async def on_stop(self) -> None:
        pass

    async def on_destroy(self) -> None:
        pass

    async def validate_region(
        self,
        screenshot: bytes,
        region: dict,
        expected_color: tuple[int, int, int],
        tolerance: int = 30,
    ) -> bool:
        """检查截图指定区域是否为预期颜色。

        Args:
            screenshot: PNG 截图字节
            region: {"left": int, "top": int, "right": int, "bottom": int}
            expected_color: (R, G, B) 期望颜色
            tolerance: 允许的颜色偏差

        Returns:
            是否匹配
        """
        from PIL import Image

        img = Image.open(io.BytesIO(screenshot)).convert("RGB")
        cropped = img.crop((
            region["left"], region["top"],
            region["right"], region["bottom"]
        ))

        pixels = list(cropped.getdata())
        match_count = 0
        for pixel in pixels:
            diff = sum(abs(a - b) for a, b in zip(pixel[:3], expected_color))
            if diff <= tolerance * 3:
                match_count += 1

        match_ratio = match_count / len(pixels) if pixels else 0
        return match_ratio > 0.8  # 80% 以上像素匹配即通过
```

---

## 3. Kotlin 插件开发（设备端）

### 3.1 插件接口

```kotlin
package com.auto.agent.core.plugin

interface AutoTestPlugin {
    val manifest: PluginManifest

    suspend fun onInit(context: PluginContext)
    suspend fun onStart()
    suspend fun onStop()
    suspend fun onDestroy()
    suspend fun handleCommand(method: String, params: Map<String, Any?>): Any?
}
```

### 3.2 PluginManifest

```kotlin
data class PluginManifest(
    val id: String,          // 全局唯一 ID
    val name: String,        // 可读名称
    val version: String,     // 版本
    val description: String, // 描述
    val author: String = "",
    val methods: List<String> = emptyList(),  // 注册的命令方法
    val permissions: List<String> = emptyList(),  // 需要的权限
)
```

### 3.3 创建插件 APK/DEX

1. 创建一个 Android Library 模块
2. 实现 `AutoTestPlugin` 接口
3. 在 `META-INF/autotest-plugin.json` 中声明：

```json
{
  "pluginClass": "com.example.myplugin.MyPlugin",
  "manifest": {
    "id": "com.example.myplugin",
    "name": "My Device Plugin",
    "version": "1.0.0",
    "methods": ["myplugin.doSomething"]
  }
}
```

4. 构建为 APK 或 DEX 文件

### 3.4 加载方式

将插件 DEX/APK 推送到设备指定目录：

```bash
adb push my-plugin.apk /data/local/tmp/autotest/plugins/
```

Agent 启动时会通过 `PluginManager` 使用 `DexClassLoader` 动态加载。

### 3.5 插件间通信

使用 `PluginEventBus`（基于 Kotlin SharedFlow）：

```kotlin
// 发布事件
pluginEventBus.emit("my_event_type", mapOf("key" to "value"))

// 订阅事件
pluginEventBus.on("my_event_type") { data ->
    // 处理事件
}

// 通配符订阅
pluginEventBus.onAll { type, data ->
    // 处理所有事件
}
```

---

## 4. 内置插件说明

### 4.1 OCR 插件 (`builtin.ocr`)

基于 OCR 引擎从截图中识别文字。

```python
ocr = host.get_plugin("builtin.ocr")
texts = await ocr.recognize(screenshot_bytes)
# 返回: list[OcrResult]
#   .text: str — 识别的文字
#   .confidence: float — 置信度 (0-1)
#   .bounds: dict — 文字区域坐标
```

**依赖**: 需要安装 `pillow` 和可选的 `pytesseract` 或 `paddleocr`。

### 4.2 图像匹配插件 (`builtin.image_match`)

在截图中查找目标图像的位置。

```python
matcher = host.get_plugin("builtin.image_match")
result = await matcher.find(
    screenshot_bytes,   # 完整截图
    template_bytes,     # 要查找的模板图像
    threshold=0.8,      # 匹配阈值
)
# 返回: MatchResult
#   .found: bool
#   .confidence: float
#   .location: dict — {"left", "top", "right", "bottom"}
```

### 4.3 视觉回归插件 (`builtin.visual_diff`)

像素级截图对比，用于检测 UI 回归。

```python
diff = host.get_plugin("builtin.visual_diff")

# 对比两张截图
result = await diff.compare(
    actual_bytes,
    expected_bytes,
    threshold=0.01,         # 最大允许差异百分比
    ignore_regions=[        # 忽略区域（如状态栏）
        {"left": 0, "top": 0, "right": 1080, "bottom": 50}
    ],
)
# 返回: DiffResult
#   .is_match: bool
#   .diff_percentage: float
#   .diff_pixel_count: int
#   .diff_image: bytes | None  — 差异可视化图像

# 基线管理
await diff.save_baseline("login_page", screenshot)
result = await diff.compare_with_baseline("login_page", new_screenshot)
```

---

## 5. 插件生命周期

```
discover() → on_init(context) → on_start() → [运行中] → on_stop() → on_destroy()
```

| 阶段 | 说明 |
|------|------|
| `discover` | 扫描发现插件（entry points / 目录） |
| `on_init` | 初始化，接收上下文（数据目录、配置、事件总线） |
| `on_start` | 启动，开始工作 |
| `on_stop` | 停止，暂停工作 |
| `on_destroy` | 销毁，释放所有资源 |

---

## 6. 最佳实践

1. **唯一 ID**: 插件 ID 使用反向域名格式，避免冲突
2. **版本管理**: 遵循语义化版本规范（SemVer）
3. **资源清理**: 在 `on_destroy` 中释放所有资源（文件句柄、网络连接等）
4. **异常处理**: 插件内部异常不应影响宿主稳定性
5. **异步优先**: 耗时操作使用异步方法，避免阻塞主循环
6. **最小依赖**: 避免引入不必要的第三方依赖
