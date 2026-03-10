"""AgentHub — 管理所有反向连接的设备。

接收设备主动发起的 WebSocket 连接，完成 agent.register 握手后
创建 RemoteDeviceClient 并注册到 DeviceManager。
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import TYPE_CHECKING, Any

from autotest.core.config import ServerConfig
from autotest.device.remote_client import RemoteDeviceClient

if TYPE_CHECKING:
    from starlette.websockets import WebSocket
    from autotest.device.manager import DeviceManager

logger = logging.getLogger(__name__)


class AgentHub:
    """管理所有通过反向 WebSocket 连接的设备。"""

    def __init__(self, manager: DeviceManager, config: ServerConfig | None = None):
        self.manager = manager
        self.config = config or ServerConfig()
        self._clients: dict[str, RemoteDeviceClient] = {}

    @property
    def remote_devices(self) -> list[dict[str, Any]]:
        """返回所有反向连接设备的基本信息。"""
        return [
            {"serial": serial, "connected": client.is_connected, "mode": "reverse"}
            for serial, client in self._clients.items()
        ]

    async def handle_agent_connection(self, websocket: WebSocket) -> None:
        """处理一条设备反向连接。

        流程:
        1. Accept WebSocket
        2. 等待 agent.register 消息（超时 = registration_timeout）
        3. 验证 deviceId
        4. 回复 agent.registered
        5. 创建 RemoteDeviceClient → 注册到 manager
        6. 等待连接断开 → 注销
        """
        await websocket.accept()
        serial: str | None = None

        try:
            # ---- 等待注册握手 ----
            register_msg = await asyncio.wait_for(
                websocket.receive_text(),
                timeout=self.config.registration_timeout,
            )
            data = json.loads(register_msg)

            method = data.get("method")
            if method != "agent.register":
                logger.warning("Expected agent.register, got: %s", method)
                await websocket.close(code=1002, reason="Expected agent.register")
                return

            params = data.get("params", {})
            device_id = params.get("deviceId", "")
            if not device_id:
                logger.warning("agent.register missing deviceId")
                await websocket.close(code=1002, reason="Missing deviceId")
                return

            serial = device_id
            logger.info(
                "Device registered: id=%s, protocol=%s, agent=%s",
                device_id,
                params.get("protocolVersion", "?"),
                params.get("agentVersion", "?"),
            )

            # ---- 回复确认 ----
            ack = json.dumps({
                "type": "response",
                "method": "agent.registered",
                "result": {"status": "ok", "serverVersion": "1.0.0"},
                "timestamp": int(time.time() * 1000),
            })
            await websocket.send_text(ack)

            # ---- 创建客户端并注册 ----
            client = RemoteDeviceClient(serial=serial, websocket=websocket)
            self._clients[serial] = client
            self.manager.register_remote(serial, client)
            client.start_listening()

            logger.info("Remote device %s connected and registered", serial)

            # ---- 保持连接直到断开 ----
            # _listen 任务会持续运行，这里等待它结束
            if client._listen_task:
                await client._listen_task

        except asyncio.TimeoutError:
            logger.warning("Registration timeout — closing connection")
            await websocket.close(code=1002, reason="Registration timeout")
        except Exception as e:
            logger.warning("Agent connection error: %s", e)
        finally:
            if serial:
                self._clients.pop(serial, None)
                self.manager.unregister_remote(serial)
                logger.info("Remote device %s unregistered", serial)
