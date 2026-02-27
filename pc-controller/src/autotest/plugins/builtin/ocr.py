"""OCR (Optical Character Recognition) plugin for text-based element detection.

支持多种 OCR 后端：
- 在线 AI 大模型 Vision API（Deepseek / 豆包 / OpenAI / 通义千问等）
- 本地 PaddleOCR 引擎
- 本地 Tesseract 引擎

运行时自动检测可用后端，也可通过配置指定。
"""

from __future__ import annotations

import base64
import io
import json
import logging
import os
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from autotest.core.types import Rect
from autotest.plugins.base import Plugin, PluginContext, PluginInfo

logger = logging.getLogger(__name__)


@dataclass
class OcrResult:
    """单条 OCR 识别结果。"""
    text: str
    bounds: Rect
    confidence: float


# ---------------------------------------------------------------------------
# 后端抽象基类
# ---------------------------------------------------------------------------

class OcrBackend(ABC):
    """OCR 后端接口。"""

    @property
    @abstractmethod
    def name(self) -> str: ...

    @abstractmethod
    async def recognize(self, image: bytes) -> list[OcrResult]:
        """识别图片中的所有文字。"""
        ...

    async def find_text(
        self, image: bytes, target: str, threshold: float = 0.6
    ) -> list[OcrResult]:
        """在图片中查找指定文字，返回匹配结果列表。"""
        all_results = await self.recognize(image)
        matched: list[OcrResult] = []
        for r in all_results:
            if target in r.text and r.confidence >= threshold:
                matched.append(r)
        return matched


# ---------------------------------------------------------------------------
# 在线 AI 大模型 Vision API 后端
# ---------------------------------------------------------------------------

_ONLINE_SYSTEM_PROMPT = (
    "你是一个精确的 OCR 引擎。用户会发送一张手机截图，你需要识别其中所有可见文字。\n"
    "以 JSON 数组格式返回结果，每个元素包含:\n"
    '- "text": 识别到的文字内容（单个按钮/标签/标题为一个元素）\n'
    '- "bounds": {"left": 像素x起点, "top": 像素y起点, "right": 像素x终点, "bottom": 像素y终点}\n'
    '- "confidence": 置信度(0到1之间的小数)\n'
    "请尽量精确地估算每个文字在图片中的像素坐标。\n"
    "只返回 JSON 数组，不要包含 markdown 代码块标记或其他内容。"
)


class OnlineOcrBackend(OcrBackend):
    """通过 OpenAI 兼容的 Vision API 调用 AI 大模型进行 OCR。

    兼容 Deepseek / 豆包（火山引擎）/ OpenAI / 通义千问 / Moonshot 等。
    """

    def __init__(
        self,
        api_base: str,
        api_key: str,
        model: str,
        timeout: float = 60.0,
    ):
        self._api_base = api_base.rstrip("/")
        self._api_key = api_key
        self._model = model
        self._timeout = timeout

    @property
    def name(self) -> str:
        return f"online({self._model})"

    async def recognize(self, image: bytes) -> list[OcrResult]:
        try:
            import httpx
        except ImportError:
            raise RuntimeError("httpx 未安装。运行: pip install httpx")

        b64_image = base64.b64encode(image).decode("utf-8")

        # 检测图片格式
        media_type = "image/png"
        if image[:3] == b"\xff\xd8\xff":
            media_type = "image/jpeg"
        elif image[:4] == b"RIFF":
            media_type = "image/webp"

        payload = {
            "model": self._model,
            "messages": [
                {"role": "system", "content": _ONLINE_SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:{media_type};base64,{b64_image}",
                            },
                        },
                        {
                            "type": "text",
                            "text": "请识别这张截图中的所有文字及其像素坐标位置。",
                        },
                    ],
                },
            ],
            "max_tokens": 4096,
            "temperature": 0.1,
        }

        url = f"{self._api_base}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }

        async with httpx.AsyncClient(timeout=self._timeout) as client:
            resp = await client.post(url, json=payload, headers=headers)
            resp.raise_for_status()
            data = resp.json()

        content = data["choices"][0]["message"]["content"]
        return self._parse_response(content)

    @staticmethod
    def _parse_response(content: str) -> list[OcrResult]:
        """解析大模型返回的 JSON 文字列表。"""
        # 去除可能的 markdown 代码块标记
        content = content.strip()
        if content.startswith("```"):
            content = re.sub(r"^```(?:json)?\s*", "", content)
            content = re.sub(r"\s*```$", "", content)
        content = content.strip()

        try:
            items = json.loads(content)
        except json.JSONDecodeError:
            logger.warning("在线 OCR 返回内容无法解析为 JSON: %s", content[:200])
            return []

        if not isinstance(items, list):
            items = [items]

        results: list[OcrResult] = []
        for item in items:
            if not isinstance(item, dict):
                continue
            text = item.get("text", "")
            bounds_data = item.get("bounds", {})
            confidence = float(item.get("confidence", 0.8))
            if text and bounds_data:
                results.append(OcrResult(
                    text=text,
                    bounds=Rect(
                        left=int(bounds_data.get("left", 0)),
                        top=int(bounds_data.get("top", 0)),
                        right=int(bounds_data.get("right", 0)),
                        bottom=int(bounds_data.get("bottom", 0)),
                    ),
                    confidence=confidence,
                ))
        return results


# ---------------------------------------------------------------------------
# PaddleOCR 本地后端
# ---------------------------------------------------------------------------

class PaddleOcrBackend(OcrBackend):
    """使用 PaddleOCR 本地引擎进行文字识别。"""

    def __init__(self, lang: str = "ch", use_gpu: bool = False):
        self._lang = lang
        self._use_gpu = use_gpu
        self._ocr: Any = None

    @property
    def name(self) -> str:
        return "paddleocr"

    def _get_engine(self) -> Any:
        if self._ocr is None:
            from paddleocr import PaddleOCR
            self._ocr = PaddleOCR(
                use_angle_cls=True,
                lang=self._lang,
                use_gpu=self._use_gpu,
                show_log=False,
            )
        return self._ocr

    async def recognize(self, image: bytes) -> list[OcrResult]:
        import asyncio
        import numpy as np
        from PIL import Image

        img = Image.open(io.BytesIO(image)).convert("RGB")
        img_array = np.array(img)

        loop = asyncio.get_event_loop()
        ocr = self._get_engine()
        raw_results = await loop.run_in_executor(None, ocr.ocr, img_array, True)

        results: list[OcrResult] = []
        if not raw_results:
            return results

        for line in raw_results:
            if not line:
                continue
            for item in line:
                box, (text, confidence) = item[0], item[1]
                # box 是 4 个角的坐标 [[x1,y1],[x2,y2],[x3,y3],[x4,y4]]
                xs = [p[0] for p in box]
                ys = [p[1] for p in box]
                results.append(OcrResult(
                    text=text,
                    bounds=Rect(
                        left=int(min(xs)),
                        top=int(min(ys)),
                        right=int(max(xs)),
                        bottom=int(max(ys)),
                    ),
                    confidence=float(confidence),
                ))
        return results


# ---------------------------------------------------------------------------
# Tesseract 本地后端
# ---------------------------------------------------------------------------

class TesseractBackend(OcrBackend):
    """使用 pytesseract（Tesseract OCR）进行文字识别。"""

    def __init__(self, lang: str = "chi_sim+eng"):
        self._lang = lang

    @property
    def name(self) -> str:
        return "tesseract"

    async def recognize(self, image: bytes) -> list[OcrResult]:
        import asyncio
        from PIL import Image

        try:
            import pytesseract
        except ImportError:
            raise RuntimeError("pytesseract 未安装。运行: pip install pytesseract")

        img = Image.open(io.BytesIO(image))
        loop = asyncio.get_event_loop()

        # 使用 image_to_data 获取文字和坐标
        raw = await loop.run_in_executor(
            None,
            lambda: pytesseract.image_to_data(img, lang=self._lang, output_type=pytesseract.Output.DICT),
        )

        results: list[OcrResult] = []
        n = len(raw["text"])
        for i in range(n):
            text = raw["text"][i].strip()
            conf = int(raw["conf"][i])
            if not text or conf < 0:
                continue
            results.append(OcrResult(
                text=text,
                bounds=Rect(
                    left=raw["left"][i],
                    top=raw["top"][i],
                    right=raw["left"][i] + raw["width"][i],
                    bottom=raw["top"][i] + raw["height"][i],
                ),
                confidence=conf / 100.0,
            ))
        return results


# ---------------------------------------------------------------------------
# OCR 插件主体
# ---------------------------------------------------------------------------

def _resolve_env(value: str) -> str:
    """解析 ${ENV_VAR} 格式的环境变量引用。"""
    if value.startswith("${") and value.endswith("}"):
        env_name = value[2:-1]
        return os.environ.get(env_name, "")
    return value


def _auto_detect_backend(config: dict[str, Any]) -> OcrBackend | None:
    """根据配置和环境自动选择可用的 OCR 后端。"""
    backend_name = config.get("backend", "auto")

    if backend_name == "online" or (backend_name == "auto" and "online" in config):
        online_cfg = config.get("online", {})
        api_key = _resolve_env(online_cfg.get("api_key", ""))
        if not api_key:
            api_key = os.environ.get("AUTOTEST_OCR_API_KEY", "")
        if api_key:
            return OnlineOcrBackend(
                api_base=online_cfg.get("api_base", "https://api.deepseek.com/v1"),
                api_key=api_key,
                model=online_cfg.get("model", "deepseek-chat"),
                timeout=float(online_cfg.get("timeout", 60)),
            )
        if backend_name == "online":
            logger.warning("在线 OCR 已配置但未提供 API Key")

    if backend_name in ("paddleocr", "auto"):
        try:
            import paddleocr  # noqa: F401
            paddle_cfg = config.get("paddleocr", {})
            return PaddleOcrBackend(
                lang=paddle_cfg.get("lang", "ch"),
                use_gpu=paddle_cfg.get("use_gpu", False),
            )
        except ImportError:
            if backend_name == "paddleocr":
                logger.warning("PaddleOCR 未安装。运行: pip install paddleocr")

    if backend_name in ("tesseract", "auto"):
        try:
            import pytesseract  # noqa: F401
            tess_cfg = config.get("tesseract", {})
            return TesseractBackend(lang=tess_cfg.get("lang", "chi_sim+eng"))
        except ImportError:
            if backend_name == "tesseract":
                logger.warning("pytesseract 未安装。运行: pip install pytesseract")

    return None


class OcrPlugin(Plugin):
    """OCR 文字识别插件 — 支持在线大模型 / PaddleOCR / Tesseract 多后端。"""

    def __init__(self) -> None:
        self._context: PluginContext | None = None
        self._backend: OcrBackend | None = None

    def info(self) -> PluginInfo:
        return PluginInfo(
            id="builtin.ocr",
            name="OCR Text Recognition",
            version="2.0.0",
            description="多后端 OCR 文字识别 — 支持在线 AI 大模型 / PaddleOCR / Tesseract",
        )

    @property
    def backend(self) -> OcrBackend | None:
        return self._backend

    async def on_init(self, context: PluginContext) -> None:
        self._context = context
        ocr_config = context.config.get("ocr", {})
        self._backend = _auto_detect_backend(ocr_config)
        if self._backend:
            logger.info("OCR 后端已初始化: %s", self._backend.name)
        else:
            logger.warning("未找到可用的 OCR 后端。请安装 paddleocr / pytesseract 或配置在线 API。")

    def set_backend(self, backend: OcrBackend) -> None:
        """手动设置 OCR 后端（用于测试或动态切换）。"""
        self._backend = backend
        logger.info("OCR 后端已切换为: %s", backend.name)

    def create_online_backend(
        self,
        api_base: str,
        api_key: str,
        model: str = "deepseek-chat",
        timeout: float = 60.0,
    ) -> OnlineOcrBackend:
        """便捷方法：创建并设置在线 OCR 后端。"""
        backend = OnlineOcrBackend(api_base, api_key, model, timeout)
        self.set_backend(backend)
        return backend

    async def find_text(
        self,
        screenshot: bytes,
        target_text: str,
        threshold: float = 0.6,
    ) -> list[OcrResult]:
        """在截图中查找指定文字。

        Args:
            screenshot: PNG/JPEG 截图字节
            target_text: 要查找的目标文字
            threshold: 最低置信度阈值 (0-1)

        Returns:
            匹配的 OcrResult 列表，按置信度降序排列
        """
        if not self._backend:
            logger.error("无可用 OCR 后端")
            return []

        results = await self._backend.find_text(screenshot, target_text, threshold)
        results.sort(key=lambda r: r.confidence, reverse=True)
        return results

    async def recognize_screen(self, screenshot: bytes) -> list[OcrResult]:
        """识别截图中的所有文字。

        Args:
            screenshot: PNG/JPEG 截图字节

        Returns:
            所有识别到的 OcrResult 列表
        """
        if not self._backend:
            logger.error("无可用 OCR 后端")
            return []

        return await self._backend.recognize(screenshot)
