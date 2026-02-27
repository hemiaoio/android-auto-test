"""OCR 截图识别点击 — 完整示例。

展示三种场景：
1. 基本用法：截图 → OCR 识别文字 → 点击
2. 高级用法：手动截图 + OCR 查找 + 坐标点击
3. 使用在线 AI 大模型 OCR 后端

运行前准备：
    # 安装 OCR 依赖
    pip install -e ".[ocr]"

    # 如需在线 OCR，设置 API Key
    export AUTOTEST_OCR_API_KEY="your-api-key"

运行命令：
    autotest run tests/test_ocr_click.py --tags ocr
"""

import asyncio
import os

from autotest.automation.decorators import test_case
from autotest.automation.dsl import Device
from autotest.plugins.builtin.ocr import OcrPlugin, OnlineOcrBackend, OcrResult


# ---------------------------------------------------------------------------
# 示例 1：一行代码完成「截图 → OCR → 点击」
# ---------------------------------------------------------------------------

@test_case(name="OCR 点击基本示例", tags=["ocr", "smoke"])
async def test_ocr_click_basic(device: Device):
    """最简用法：直接通过文字点击屏幕上的按钮。

    内部流程:
        1. 自动截屏
        2. 调用 OCR 引擎识别所有文字
        3. 查找包含目标文字的区域
        4. 点击该区域的中心坐标
    """
    # 启动目标应用
    await device.app("com.android.settings").launch()
    await asyncio.sleep(2)  # 等待界面稳定

    # 一行完成: 截图 → OCR 识别 "设置" → 点击
    result = await device.ocr_click("WLAN", timeout=15)

    print(f"已点击文字: '{result.text}'")
    print(f"点击坐标: ({result.click_x}, {result.click_y})")
    print(f"识别置信度: {result.confidence:.2f}")
    print(f"文字区域: {result.bounds}")

    # 验证点击后进入了 WLAN 页面
    await asyncio.sleep(1)
    wlan_result = await device.ocr_find("已连接")
    # 如果找到 "已连接" 说明成功进入了 WLAN 设置页面


# ---------------------------------------------------------------------------
# 示例 2：手动控制每一步（高级用法）
# ---------------------------------------------------------------------------

@test_case(name="OCR 手动流程示例", tags=["ocr", "advanced"])
async def test_ocr_manual_flow(device: Device):
    """手动控制截图、识别、点击每个步骤。

    适用于需要对 OCR 结果做自定义处理的场景。
    """
    await device.app("com.android.settings").launch()
    await asyncio.sleep(2)

    # 第 1 步：截图
    screenshot = await device.screenshot(tag="settings_main")
    print(f"截图大小: {len(screenshot)} bytes")

    # 第 2 步：OCR 识别所有文字
    all_texts = await device.ocr.recognize_screen(screenshot)
    print(f"识别到 {len(all_texts)} 个文字区域:")
    for item in all_texts:
        print(f"  '{item.text}' @ ({item.bounds.left},{item.bounds.top})-"
              f"({item.bounds.right},{item.bounds.bottom}) "
              f"conf={item.confidence:.2f}")

    # 第 3 步：查找目标文字
    targets = await device.ocr_find("蓝牙", screenshot=screenshot)
    assert len(targets) > 0, "未找到 '蓝牙' 文字"

    target = targets[0]
    print(f"\n找到目标: '{target.text}' "
          f"中心=({target.bounds.center_x}, {target.bounds.center_y})")

    # 第 4 步：点击坐标
    await device._client.send("ui.click", {
        "x": target.bounds.center_x,
        "y": target.bounds.center_y,
    })
    print(f"已点击 ({target.bounds.center_x}, {target.bounds.center_y})")


# ---------------------------------------------------------------------------
# 示例 3：使用在线 AI 大模型 OCR
# ---------------------------------------------------------------------------

@test_case(name="在线大模型 OCR 示例", tags=["ocr", "online"])
async def test_ocr_online_model(device: Device):
    """使用在线 AI 大模型（Deepseek/豆包等）进行 OCR。

    需要设置环境变量 AUTOTEST_OCR_API_KEY。
    """
    api_key = os.environ.get("AUTOTEST_OCR_API_KEY", "")
    if not api_key:
        print("跳过: 未设置 AUTOTEST_OCR_API_KEY 环境变量")
        return

    # 动态切换到在线后端
    device.ocr.create_online_backend(
        api_base="https://api.deepseek.com/v1",  # 替换为你的 API 地址
        api_key=api_key,
        model="deepseek-chat",                    # 替换为你的模型名称
    )

    await device.app("com.android.settings").launch()
    await asyncio.sleep(2)

    # 截图并用大模型识别
    screenshot = await device.screenshot()
    results = await device.ocr.recognize_screen(screenshot)

    print(f"大模型识别到 {len(results)} 个文字区域:")
    for r in results:
        print(f"  '{r.text}' conf={r.confidence:.2f} "
              f"@ ({r.bounds.left},{r.bounds.top})-({r.bounds.right},{r.bounds.bottom})")

    # 点击 "显示" 设置项
    result = await device.ocr_click("显示", timeout=5)
    print(f"已通过大模型 OCR 点击: '{result.text}' @ ({result.click_x}, {result.click_y})")


# ---------------------------------------------------------------------------
# 示例 4：OCR + 断言 的实战测试
# ---------------------------------------------------------------------------

@test_case(name="OCR 登录流程验证", tags=["ocr", "login"])
async def test_ocr_login_verification(device: Device):
    """用 OCR 验证登录后的欢迎页面文字。

    展示 OCR 在测试断言中的实际应用。
    """
    await device.app("com.example.app").launch(clear_state=True)
    await asyncio.sleep(2)

    # 用传统方式操作已知控件
    await device.ui(resource_id="et_username").type("admin")
    await device.ui(resource_id="et_password").type("password123")
    await device.ui(resource_id="btn_login").click()
    await asyncio.sleep(3)

    # 用 OCR 验证登录成功 — 适用于自定义绘制的欢迎文字
    screenshot = await device.screenshot(tag="after_login")
    welcome_texts = await device.ocr_find("欢迎", screenshot=screenshot)

    assert len(welcome_texts) > 0, "登录后未找到 '欢迎' 文字，登录可能失败"
    print(f"验证通过: 找到 '{welcome_texts[0].text}' "
          f"置信度 {welcome_texts[0].confidence:.2f}")


# ---------------------------------------------------------------------------
# 示例 5：多后端配置演示（独立脚本用法）
# ---------------------------------------------------------------------------

async def standalone_demo():
    """独立脚本示例 — 不依赖 @test_case 装饰器。

    可直接运行: python tests/test_ocr_click.py
    """
    from autotest.device.client import DeviceClient
    from autotest.plugins.base import PluginContext

    # 1. 初始化 OCR 插件
    ocr = OcrPlugin()
    await ocr.on_init(PluginContext(config={
        "ocr": {
            "backend": "online",
            "online": {
                "api_base": "https://api.deepseek.com/v1",
                "api_key": os.environ.get("AUTOTEST_OCR_API_KEY", ""),
                "model": "deepseek-chat",
            },
        },
    }))

    # 2. 连接设备
    async with DeviceClient(serial="emulator-5554") as client:
        device = Device(client, ocr_plugin=ocr)

        # 3. 截图 → OCR → 点击
        result = await device.ocr_click("设置")
        print(f"点击完成: {result.text} @ ({result.click_x}, {result.click_y})")


if __name__ == "__main__":
    asyncio.run(standalone_demo())
