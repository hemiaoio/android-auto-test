"""WebSocket client for communicating with the device Agent."""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Callable, Coroutine

import websockets
from websockets.client import WebSocketClientProtocol

from autotest.core.config import DeviceConfig
from autotest.core.exceptions import ConnectionError, TimeoutError
from autotest.device.protocol import Message

logger = logging.getLogger(__name__)

EventCallback = Callable[[Message], Coroutine[Any, Any, None]]


class DeviceClient:
    """WebSocket client that connects to a device Agent on 3 channels."""

    def __init__(self, serial: str, host: str = "127.0.0.1", config: DeviceConfig | None = None):
        self.serial = serial
        self.host = host
        self.config = config or DeviceConfig()

        self._control_ws: WebSocketClientProtocol | None = None
        self._event_ws: WebSocketClientProtocol | None = None
        self._pending: dict[str, asyncio.Future[Message]] = {}
        self._event_handlers: list[EventCallback] = []
        self._event_listener_task: asyncio.Task[None] | None = None
        self._connected = False

    @property
    def is_connected(self) -> bool:
        return self._connected

    async def connect(self) -> None:
        """Establish WebSocket connections to the device Agent."""
        try:
            control_uri = f"ws://{self.host}:{self.config.control_port}/control"
            event_uri = f"ws://{self.host}:{self.config.event_port}/events"

            self._control_ws = await asyncio.wait_for(
                websockets.connect(control_uri),
                timeout=self.config.connect_timeout,
            )

            self._event_ws = await asyncio.wait_for(
                websockets.connect(event_uri),
                timeout=self.config.connect_timeout,
            )

            # Start listening for control responses
            self._event_listener_task = asyncio.create_task(self._listen_events())
            asyncio.create_task(self._listen_control())

            self._connected = True
            logger.info("Connected to device %s", self.serial)
        except Exception as e:
            raise ConnectionError(f"Failed to connect to device {self.serial}: {e}")

    async def disconnect(self) -> None:
        """Close all WebSocket connections."""
        self._connected = False
        if self._event_listener_task:
            self._event_listener_task.cancel()
        if self._control_ws:
            await self._control_ws.close()
        if self._event_ws:
            await self._event_ws.close()
        # Resolve all pending futures with errors
        for future in self._pending.values():
            if not future.done():
                future.set_exception(ConnectionError("Disconnected"))
        self._pending.clear()
        logger.info("Disconnected from device %s", self.serial)

    async def send(self, method: str, params: dict[str, Any] | None = None,
                   timeout: float | None = None) -> Message:
        """Send a request and wait for the response."""
        if not self._control_ws:
            raise ConnectionError("Not connected")

        timeout = timeout or self.config.command_timeout
        msg = Message.request(method, params, timeout)
        future: asyncio.Future[Message] = asyncio.get_event_loop().create_future()
        self._pending[msg.id] = future

        await self._control_ws.send(msg.to_json())

        try:
            response = await asyncio.wait_for(future, timeout=timeout)
        except asyncio.TimeoutError:
            self._pending.pop(msg.id, None)
            raise TimeoutError(f"Request {method} timed out after {timeout}s")

        if not response.is_success:
            from autotest.core.exceptions import AutoTestError
            raise AutoTestError(response.error_message, response.error_code)

        return response

    def on_event(self, handler: EventCallback) -> Callable[[], None]:
        """Register an event handler. Returns unsubscribe function."""
        self._event_handlers.append(handler)
        return lambda: self._event_handlers.remove(handler)

    async def _listen_control(self) -> None:
        """Listen for responses on the control channel."""
        if not self._control_ws:
            return
        try:
            async for raw in self._control_ws:
                msg = Message.from_json(str(raw))
                if msg.type == "response":
                    future = self._pending.pop(msg.id, None)
                    if future and not future.done():
                        future.set_result(msg)
        except websockets.exceptions.ConnectionClosed:
            self._connected = False

    async def _listen_events(self) -> None:
        """Listen for events on the event channel."""
        if not self._event_ws:
            return
        try:
            async for raw in self._event_ws:
                msg = Message.from_json(str(raw))
                for handler in self._event_handlers:
                    try:
                        await handler(msg)
                    except Exception:
                        pass
        except websockets.exceptions.ConnectionClosed:
            pass

    async def __aenter__(self) -> DeviceClient:
        await self.connect()
        return self

    async def __aexit__(self, *args: Any) -> None:
        await self.disconnect()
