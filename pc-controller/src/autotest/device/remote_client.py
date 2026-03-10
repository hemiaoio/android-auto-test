"""远程设备客户端 — 封装通过反向 WebSocket 连接的设备。

接口与 DeviceClient 完全一致，上层代码（DSL、NLP、Runner）无需区分。
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Callable, Coroutine

from starlette.websockets import WebSocket

from autotest.device.protocol import Message

logger = logging.getLogger(__name__)

EventCallback = Callable[[Message], Coroutine[Any, Any, None]]


class RemoteDeviceClient:
    """包装一条已建立的 WebSocket 连接（设备主动连上来的）。

    消息路由：
    - PC 发 request → 通过 WebSocket 发给设备 → 设备返回 response → 匹配 Future
    - 设备发 event → 分发给 event handlers
    """

    def __init__(self, serial: str, websocket: WebSocket):
        self.serial = serial
        self._ws = websocket
        self._pending: dict[str, asyncio.Future[Message]] = {}
        self._event_handlers: list[EventCallback] = []
        self._connected = True
        self._listen_task: asyncio.Task[None] | None = None

    @property
    def is_connected(self) -> bool:
        return self._connected

    def start_listening(self) -> None:
        """启动异步消息循环（在 AgentHub 中调用）。"""
        self._listen_task = asyncio.create_task(self._listen())

    async def send(
        self,
        method: str,
        params: dict[str, Any] | None = None,
        timeout: float | None = None,
    ) -> Message:
        """发送请求并等待响应，与 DeviceClient.send() 接口一致。"""
        if not self._connected:
            from autotest.core.exceptions import ConnectionError
            raise ConnectionError("Remote device not connected")

        timeout = timeout or 30.0
        msg = Message.request(method, params, timeout)
        future: asyncio.Future[Message] = asyncio.get_event_loop().create_future()
        self._pending[msg.id] = future

        await self._ws.send_text(msg.to_json())

        try:
            response = await asyncio.wait_for(future, timeout=timeout)
        except asyncio.TimeoutError:
            self._pending.pop(msg.id, None)
            from autotest.core.exceptions import TimeoutError
            raise TimeoutError(f"Request {method} timed out after {timeout}s")

        if not response.is_success:
            from autotest.core.exceptions import AutoTestError
            raise AutoTestError(response.error_message, response.error_code)

        return response

    def on_event(self, handler: EventCallback) -> Callable[[], None]:
        """注册事件处理器，返回取消订阅函数。"""
        self._event_handlers.append(handler)
        return lambda: self._event_handlers.remove(handler)

    async def disconnect(self) -> None:
        """关闭连接。"""
        self._connected = False
        if self._listen_task:
            self._listen_task.cancel()
        for future in self._pending.values():
            if not future.done():
                from autotest.core.exceptions import ConnectionError
                future.set_exception(ConnectionError("Disconnected"))
        self._pending.clear()
        try:
            await self._ws.close()
        except Exception:
            pass
        logger.info("Remote device %s disconnected", self.serial)

    async def _listen(self) -> None:
        """监听 WebSocket 消息：response 匹配 Future，event 分发给 handler。"""
        try:
            while self._connected:
                raw = await self._ws.receive_text()
                msg = Message.from_json(raw)
                if msg.type == "response":
                    future = self._pending.pop(msg.id, None)
                    if future and not future.done():
                        future.set_result(msg)
                elif msg.type == "event":
                    for handler in self._event_handlers:
                        try:
                            await handler(msg)
                        except Exception:
                            pass
        except Exception:
            self._connected = False
