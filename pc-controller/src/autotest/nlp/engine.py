"""自然语言命令引擎 — 通过 LLM 将自然语言翻译为设备操作步骤并执行。

复用 OCR 插件的 httpx + OpenAI 兼容 API 模式，支持带截图的上下文理解。
"""

from __future__ import annotations

import base64
import json
import logging
import os
import re
from dataclasses import dataclass, field
from typing import Any

from autotest.core.config import AutoTestConfig

logger = logging.getLogger(__name__)


@dataclass
class NLStep:
    """单个操作步骤。"""

    method: str  # 如 "ui.click"
    params: dict[str, Any]  # 如 {"selector": {"text": "登录"}}
    description: str  # 如 "点击登录按钮"


@dataclass
class NLResult:
    """自然语言命令的完整执行结果。"""

    steps: list[NLStep] = field(default_factory=list)
    executed: list[dict[str, Any]] = field(default_factory=list)  # 每步执行结果
    screenshot: str = ""  # 执行后截图 base64


# 系统提示词：指导 LLM 生成结构化操作步骤
_SYSTEM_PROMPT = """\
你是一个 Android 设备自动化助手。用户会用自然语言描述想要在手机上执行的操作，\
你需要将其翻译为结构化的操作步骤列表。

可用的操作方法（method）及其参数（params）:

【应用操作】
- app.launch: {"packageName": "com.example.app"} — 启动应用
- app.stop: {"packageName": "com.example.app"} — 停止应用
- app.clear: {"packageName": "com.example.app"} — 清除应用数据

【UI 操作】
- ui.click: {"selector": {...}} — 点击元素
- ui.longClick: {"selector": {...}} — 长按元素
- ui.type: {"selector": {...}, "text": "内容"} — 在输入框输入文字
- ui.swipe: {"startX": 500, "startY": 1500, "endX": 500, "endY": 500, "duration": 300} — 滑动
- ui.find: {"selector": {...}} — 查找元素
- ui.waitFor: {"selector": {...}, "timeout": 5000} — 等待元素出现

selector 支持的字段: text（文字）、resourceId（资源ID）、className（类名）、\
description（描述）、clickable（可点击）、index（索引）

【设备操作】
- device.screenshot: {} — 截图
- device.shell: {"command": "命令"} — 执行 Shell 命令
- device.info: {} — 获取设备信息
- device.wake: {} — 唤醒屏幕
- device.keyEvent: {"keyCode": 数字} — 发送按键（3=Home, 4=Back, 26=Power, 82=Menu）

【性能操作】
- perf.start: {"packageName": "com.example.app", "metrics": ["cpu", "memory", "fps"]} — 开始性能监测
- perf.snapshot: {} — 获取性能快照
- perf.stop: {} — 停止性能监测

请以 JSON 数组格式返回操作步骤，每个元素包含:
- "method": 操作方法名
- "params": 参数对象
- "description": 这一步的中文描述

示例输入: "打开微信并搜索张三"
示例输出:
[
  {"method": "app.launch", "params": {"packageName": "com.tencent.mm"}, "description": "启动微信"},
  {"method": "ui.waitFor", "params": {"selector": {"text": "搜索"}, "timeout": 5000}, "description": "等待搜索按钮出现"},
  {"method": "ui.click", "params": {"selector": {"text": "搜索"}}, "description": "点击搜索按钮"},
  {"method": "ui.type", "params": {"selector": {"className": "android.widget.EditText"}, "text": "张三"}, "description": "输入搜索关键词"}
]

只返回 JSON 数组，不要包含 markdown 代码块标记或其他内容。\
"""

_SYSTEM_PROMPT_WITH_SCREENSHOT = _SYSTEM_PROMPT + """

用户同时提供了当前屏幕截图，请结合截图内容理解当前状态，生成更精准的操作步骤。\
例如如果截图显示已经在某个页面，就不需要再导航到该页面。\
"""


def _resolve_env(value: str) -> str:
    """解析 ${ENV_VAR} 格式的环境变量引用。"""
    if value.startswith("${") and value.endswith("}"):
        env_name = value[2:-1]
        return os.environ.get(env_name, "")
    return value


class NLCommandEngine:
    """自然语言命令引擎 — 翻译 + 执行。"""

    def __init__(self, config: AutoTestConfig) -> None:
        self._config = config
        nlp = config.nlp
        ocr_online = config.ocr.online

        # 复用 OCR 在线配置作为默认值
        self._api_base = (
            _resolve_env(nlp.api_base) or _resolve_env(ocr_online.api_base)
        ).rstrip("/")
        self._api_key = (
            _resolve_env(nlp.api_key)
            or _resolve_env(ocr_online.api_key)
            or os.environ.get("AUTOTEST_OCR_API_KEY", "")
        )
        self._model = nlp.model or ocr_online.model
        self._timeout = nlp.timeout
        self._max_steps = nlp.max_steps

    @property
    def is_available(self) -> bool:
        """检查引擎是否可用（有 API Key 且已启用）。"""
        return bool(self._api_key) and self._config.nlp.enabled

    async def translate(
        self,
        text: str,
        screenshot: bytes | None = None,
    ) -> list[NLStep]:
        """将自然语言翻译为操作步骤列表。

        Args:
            text: 用户自然语言命令
            screenshot: 可选的当前屏幕截图（PNG/JPEG 字节）

        Returns:
            操作步骤列表
        """
        try:
            import httpx
        except ImportError:
            raise RuntimeError("httpx 未安装。运行: pip install httpx")

        if not self._api_key:
            raise RuntimeError("未配置 NLP API Key，请设置 nlp.api_key 或 ocr.online.api_key")

        # 构造消息
        system_prompt = (
            _SYSTEM_PROMPT_WITH_SCREENSHOT if screenshot else _SYSTEM_PROMPT
        )

        user_content: list[dict[str, Any]] = []
        if screenshot:
            b64_image = base64.b64encode(screenshot).decode("utf-8")
            media_type = "image/png"
            if screenshot[:3] == b"\xff\xd8\xff":
                media_type = "image/jpeg"
            user_content.append({
                "type": "image_url",
                "image_url": {"url": f"data:{media_type};base64,{b64_image}"},
            })
        user_content.append({"type": "text", "text": text})

        payload = {
            "model": self._model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content},
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
        return self._parse_steps(content)

    def _parse_steps(self, content: str) -> list[NLStep]:
        """解析 LLM 返回的 JSON 步骤列表。"""
        content = content.strip()
        if content.startswith("```"):
            content = re.sub(r"^```(?:json)?\s*", "", content)
            content = re.sub(r"\s*```$", "", content)
        content = content.strip()

        try:
            items = json.loads(content)
        except json.JSONDecodeError:
            logger.warning("NLP 返回内容无法解析为 JSON: %s", content[:200])
            return []

        if not isinstance(items, list):
            items = [items]

        steps: list[NLStep] = []
        for item in items[: self._max_steps]:
            if not isinstance(item, dict):
                continue
            method = item.get("method", "")
            params = item.get("params", {})
            description = item.get("description", "")
            if method:
                steps.append(NLStep(method=method, params=params, description=description))
        return steps

    async def execute(
        self,
        text: str,
        client: Any,
        with_screenshot: bool = False,
    ) -> NLResult:
        """翻译自然语言命令并在设备上执行。

        Args:
            text: 用户自然语言命令
            client: DeviceClient 实例
            with_screenshot: 是否先截图提供给 LLM 理解上下文

        Returns:
            包含步骤、执行结果和最终截图的 NLResult
        """
        screenshot_bytes: bytes | None = None
        if with_screenshot:
            try:
                resp = await client.send("device.screenshot")
                if resp.result and isinstance(resp.result, dict):
                    b64 = resp.result.get("data", "")
                    if b64:
                        screenshot_bytes = base64.b64decode(b64)
            except Exception as e:
                logger.warning("截图失败，继续执行不带截图模式: %s", e)

        # 翻译
        steps = await self.translate(text, screenshot_bytes)
        if not steps:
            return NLResult(steps=[], executed=[], screenshot="")

        # 逐步执行
        executed: list[dict[str, Any]] = []
        for step in steps:
            try:
                resp = await client.send(step.method, step.params)
                executed.append({
                    "step": step.description,
                    "method": step.method,
                    "success": resp.is_success,
                    "result": resp.result,
                })
            except Exception as e:
                executed.append({
                    "step": step.description,
                    "method": step.method,
                    "success": False,
                    "error": str(e),
                })

        # 执行完成后截图
        final_screenshot = ""
        try:
            resp = await client.send("device.screenshot")
            if resp.result and isinstance(resp.result, dict):
                final_screenshot = resp.result.get("data", "")
        except Exception as e:
            logger.warning("最终截图失败: %s", e)

        return NLResult(steps=steps, executed=executed, screenshot=final_screenshot)
