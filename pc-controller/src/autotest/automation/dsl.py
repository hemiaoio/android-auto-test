"""Fluent automation DSL for writing device test scripts.

Usage:
    @test_case(name="Login Test")
    async def test_login(device: Device):
        await device.app("com.example").launch()
        await device.ui(text="Login").click()
        assert await device.ui(text="Welcome").wait_for(timeout=10)
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import Any

from autotest.core.exceptions import ElementNotFoundError
from autotest.core.types import DeviceInfo, Rect, ShellResult, UiElement
from autotest.device.client import DeviceClient
from autotest.plugins.builtin.ocr import OcrPlugin, OcrResult


@dataclass
class OcrClickResult:
    """ocr_click 操作的返回结果。"""
    text: str
    bounds: Rect
    click_x: int
    click_y: int
    confidence: float
    all_matches: list[OcrResult]


class Device:
    """High-level device facade wrapping DeviceClient with a fluent API."""

    def __init__(self, client: DeviceClient, ocr_plugin: OcrPlugin | None = None):
        self._client = client
        self._ocr = ocr_plugin or OcrPlugin()
        self.perf = PerfController(client)

    @property
    def serial(self) -> str:
        return self._client.serial

    async def info(self) -> DeviceInfo:
        resp = await self._client.send("device.info")
        data = resp.result or {}
        return DeviceInfo(**data)

    async def screenshot(self, tag: str = "", format: str = "png", quality: int = 90) -> bytes:
        resp = await self._client.send("device.screenshot", {
            "format": format, "quality": quality, "tag": tag,
        })
        import base64
        return base64.b64decode(resp.result.get("data", "")) if resp.result else b""

    async def shell(self, command: str, as_root: bool = False) -> ShellResult:
        resp = await self._client.send("device.shell", {
            "command": command, "asRoot": as_root,
        })
        data = resp.result or {}
        return ShellResult(
            exit_code=data.get("exitCode", -1),
            stdout=data.get("stdout", ""),
            stderr=data.get("stderr", ""),
        )

    def app(self, package_name: str) -> AppController:
        return AppController(self._client, package_name)

    def ui(self, **selector: Any) -> UiSelector:
        return UiSelector(self._client, selector)

    async def wake(self) -> None:
        await self._client.send("device.wake")

    async def key(self, keycode: int) -> None:
        await self._client.send("device.inputKey", {"keyCode": keycode})

    async def press_back(self) -> None:
        await self.key(4)

    async def press_home(self) -> None:
        await self.key(3)

    @property
    def ocr(self) -> OcrPlugin:
        """获取 OCR 插件实例，用于高级用法。"""
        return self._ocr

    async def ocr_find(
        self,
        text: str,
        threshold: float = 0.6,
        screenshot: bytes | None = None,
    ) -> list[OcrResult]:
        """通过 OCR 在当前屏幕中查找指定文字。

        Args:
            text: 要查找的目标文字
            threshold: 最低置信度阈值 (0-1)
            screenshot: 可选，传入已有截图；不传则自动截屏

        Returns:
            匹配的 OcrResult 列表
        """
        if screenshot is None:
            screenshot = await self.screenshot()
        return await self._ocr.find_text(screenshot, text, threshold)

    async def ocr_click(
        self,
        text: str,
        index: int = 0,
        threshold: float = 0.6,
        timeout: float = 10,
        poll_interval: float = 1.0,
    ) -> OcrClickResult:
        """通过 OCR 识别屏幕上的文字并点击。

        完整流程: 截图 → OCR 识别 → 定位目标文字 → 点击中心坐标

        Args:
            text: 要点击的目标文字
            index: 当有多个匹配时，点击第几个（0 开始）
            threshold: 最低置信度阈值 (0-1)
            timeout: 最长等待时间（秒），会重试直到找到文字或超时
            poll_interval: 重试间隔（秒）

        Returns:
            OcrClickResult 包含识别结果和点击坐标

        Raises:
            ElementNotFoundError: 超时后仍未找到目标文字
        """
        logger = logging.getLogger(__name__)
        deadline = asyncio.get_event_loop().time() + timeout

        while True:
            screenshot = await self.screenshot()
            matches = await self._ocr.find_text(screenshot, text, threshold)

            if matches and len(matches) > index:
                target = matches[index]
                click_x = target.bounds.center_x
                click_y = target.bounds.center_y

                logger.info(
                    "OCR 找到文字 '%s' 于 (%d, %d)，置信度 %.2f，执行点击",
                    text, click_x, click_y, target.confidence,
                )

                # 通过坐标点击
                await self._client.send("ui.click", {
                    "x": click_x, "y": click_y,
                })

                return OcrClickResult(
                    text=target.text,
                    bounds=target.bounds,
                    click_x=click_x,
                    click_y=click_y,
                    confidence=target.confidence,
                    all_matches=matches,
                )

            if asyncio.get_event_loop().time() >= deadline:
                raise ElementNotFoundError(
                    f"OCR 未找到文字 '{text}'（超时 {timeout}s，阈值 {threshold}）"
                )

            logger.debug("OCR 未找到 '%s'，%.1f 秒后重试", text, poll_interval)
            await asyncio.sleep(poll_interval)


class AppController:
    """Controls a specific app on the device."""

    def __init__(self, client: DeviceClient, package_name: str):
        self._client = client
        self.package_name = package_name

    async def launch(
        self, activity: str | None = None, clear_state: bool = False, wait: bool = True
    ) -> float:
        """Launch the app. Returns launch time in milliseconds."""
        resp = await self._client.send("app.launch", {
            "packageName": self.package_name,
            "activity": activity,
            "clearState": clear_state,
            "waitForIdle": wait,
        })
        return (resp.result or {}).get("launchTimeMs", 0)

    async def stop(self, force: bool = True) -> None:
        await self._client.send("app.stop", {
            "packageName": self.package_name, "force": force,
        })

    async def clear(self) -> None:
        await self._client.send("app.clear", {"packageName": self.package_name})

    async def install(self, path: str, replace: bool = True) -> None:
        await self._client.send("app.install", {
            "path": path, "replace": replace, "grantPermissions": True,
        })

    async def uninstall(self) -> None:
        await self._client.send("app.uninstall", {"packageName": self.package_name})

    async def is_running(self) -> bool:
        resp = await self._client.send("app.info", {"packageName": self.package_name})
        return (resp.result or {}).get("running", False)


class UiSelector:
    """Lazy UI element selector. Operations are sent to the device when called."""

    def __init__(self, client: DeviceClient, selector: dict[str, Any]):
        self._client = client
        self._selector = self._normalize_selector(selector)

    @staticmethod
    def _normalize_selector(sel: dict[str, Any]) -> dict[str, Any]:
        """Convert Python snake_case keys to protocol camelCase."""
        mapping = {
            "resource_id": "resourceId",
            "text_contains": "textContains",
            "text_matches": "textMatches",
            "class_name": "className",
            "package_name": "packageName",
            "content_description": "description",
            "description_contains": "descriptionContains",
        }
        return {mapping.get(k, k): v for k, v in sel.items()}

    async def find(self, timeout: float = 10) -> list[UiElement]:
        """Find all matching elements."""
        resp = await self._client.send("ui.find", {
            "selector": self._selector, "timeout": int(timeout * 1000),
        })
        elements_data = (resp.result or {}).get("elements", [])
        return [self._parse_element(e) for e in elements_data]

    async def find_one(self, timeout: float = 10) -> UiElement:
        """Find exactly one matching element or raise."""
        elements = await self.find(timeout)
        if not elements:
            raise ElementNotFoundError(f"Element not found: {self._selector}")
        return elements[0]

    async def exists(self, timeout: float = 5) -> bool:
        """Check if the element exists."""
        try:
            elements = await self.find(timeout)
            return len(elements) > 0
        except Exception:
            return False

    async def click(self, timeout: float = 10) -> None:
        """Find and click the element."""
        await self._client.send("ui.click", {
            "selector": self._selector, "timeout": int(timeout * 1000),
        })

    async def long_click(self, duration_ms: int = 500, timeout: float = 10) -> None:
        await self._client.send("ui.longClick", {
            "selector": self._selector, "durationMs": duration_ms,
            "timeout": int(timeout * 1000),
        })

    async def type(self, text: str, clear_first: bool = True, timeout: float = 10) -> None:
        """Type text into the element."""
        await self._client.send("ui.type", {
            "selector": self._selector, "text": text,
            "clearFirst": clear_first, "timeout": int(timeout * 1000),
        })

    async def swipe(self, direction: str = "up", amount: float = 0.5, timeout: float = 10) -> None:
        await self._client.send("ui.scroll", {
            "selector": self._selector, "direction": direction,
            "amount": amount, "timeout": int(timeout * 1000),
        })

    async def wait_for(
        self, condition: str = "exists", timeout: float = 10, poll_interval: float = 0.5
    ) -> UiSelectorResult:
        """Wait for a condition to be met."""
        resp = await self._client.send("ui.waitFor", {
            "selector": self._selector,
            "condition": condition,
            "timeout": int(timeout * 1000),
            "pollInterval": int(poll_interval * 1000),
        })
        data = resp.result or {}
        return UiSelectorResult(
            found=data.get("found", False),
            elapsed_ms=data.get("elapsed", 0),
        )

    async def get_text(self, timeout: float = 10) -> str:
        """Get the text content of the element."""
        element = await self.find_one(timeout)
        return element.text or ""

    @staticmethod
    def _parse_element(data: dict[str, Any]) -> UiElement:
        bounds_data = data.get("bounds", {})
        return UiElement(
            id=data.get("id", ""),
            class_name=data.get("className", ""),
            bounds=Rect(
                left=bounds_data.get("left", 0),
                top=bounds_data.get("top", 0),
                right=bounds_data.get("right", 0),
                bottom=bounds_data.get("bottom", 0),
            ),
            resource_id=data.get("resourceId"),
            text=data.get("text"),
            content_description=data.get("contentDescription"),
            package_name=data.get("packageName"),
            is_clickable=data.get("isClickable", False),
            is_enabled=data.get("isEnabled", True),
            is_scrollable=data.get("isScrollable", False),
        )


class UiSelectorResult:
    """Result of a wait_for operation."""

    def __init__(self, found: bool, elapsed_ms: float = 0):
        self.found = found
        self.elapsed_ms = elapsed_ms
        self.exists = found  # Alias

    def __bool__(self) -> bool:
        return self.found


class PerfController:
    """Performance monitoring controller."""

    def __init__(self, client: DeviceClient):
        self._client = client

    async def start(
        self,
        package: str,
        metrics: list[str] | None = None,
        interval_ms: int = 1000,
    ) -> PerfSession:
        metrics = metrics or ["cpu", "memory", "fps"]
        resp = await self._client.send("perf.start", {
            "packageName": package,
            "metrics": metrics,
            "intervalMs": interval_ms,
        })
        session_id = (resp.result or {}).get("sessionId", "")
        return PerfSession(self._client, session_id)


class PerfSession:
    """Active performance monitoring session."""

    def __init__(self, client: DeviceClient, session_id: str):
        self._client = client
        self.session_id = session_id

    async def snapshot(self) -> dict[str, Any]:
        resp = await self._client.send("perf.snapshot", {"sessionId": self.session_id})
        return resp.result or {}

    async def stop(self) -> PerfReport:
        resp = await self._client.send("perf.stop", {"sessionId": self.session_id})
        data = resp.result or {}
        return PerfReport(data)


class PerfReport:
    """Performance report data."""

    def __init__(self, data: dict[str, Any]):
        self.raw = data
        summary = data.get("summary", {})
        self.avg_cpu: float = summary.get("avgCpu", 0)
        self.max_cpu: float = summary.get("maxCpu", 0)
        self.avg_memory: float = summary.get("avgMemory", 0)
        self.max_memory: float = summary.get("maxMemory", 0)
        self.avg_fps: float = summary.get("avgFps", 0)
        self.jank_count: int = summary.get("jankCount", 0)
        self.data_points: list[dict[str, Any]] = data.get("dataPoints", [])
