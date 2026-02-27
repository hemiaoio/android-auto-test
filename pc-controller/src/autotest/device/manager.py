"""Multi-device connection pool and management."""

from __future__ import annotations

import asyncio
import logging
from typing import AsyncIterator

from autotest.core.config import DeviceConfig
from autotest.core.exceptions import DeviceOfflineError
from autotest.device.adb import AdbClient, AdbDevice
from autotest.device.client import DeviceClient

logger = logging.getLogger(__name__)


class DeviceManager:
    """Manages multiple device connections with automatic discovery."""

    def __init__(self, config: DeviceConfig | None = None, adb: AdbClient | None = None):
        self.config = config or DeviceConfig()
        self.adb = adb or AdbClient()
        self._clients: dict[str, DeviceClient] = {}
        self._port_map: dict[str, int] = {}
        self._next_local_port = 28900  # Local ports start from here

    async def discover(self) -> list[AdbDevice]:
        """Discover all connected ADB devices."""
        devices = await self.adb.devices()
        online = [d for d in devices if d.state == "device"]
        logger.info("Discovered %d online devices", len(online))
        return online

    async def connect(self, serial: str) -> DeviceClient:
        """Connect to a specific device by serial number."""
        if serial in self._clients and self._clients[serial].is_connected:
            return self._clients[serial]

        # Set up ADB port forwarding
        local_port = self._next_local_port
        self._next_local_port += 3  # Reserve 3 ports per device

        for offset, remote_port in enumerate([
            self.config.control_port,
            self.config.binary_port,
            self.config.event_port,
        ]):
            ok = await self.adb.forward(serial, local_port + offset, remote_port)
            if not ok:
                raise DeviceOfflineError(f"Failed to set up port forwarding for {serial}")

        # Create client with forwarded ports
        client_config = DeviceConfig(
            control_port=local_port,
            binary_port=local_port + 1,
            event_port=local_port + 2,
            connect_timeout=self.config.connect_timeout,
            command_timeout=self.config.command_timeout,
        )
        client = DeviceClient(serial=serial, config=client_config)
        await client.connect()

        self._clients[serial] = client
        self._port_map[serial] = local_port
        logger.info("Connected to device %s via ports %d-%d", serial, local_port, local_port + 2)
        return client

    async def connect_all(self) -> list[DeviceClient]:
        """Discover and connect to all available devices."""
        devices = await self.discover()
        clients = []
        for device in devices:
            try:
                client = await self.connect(device.serial)
                clients.append(client)
            except Exception as e:
                logger.warning("Failed to connect to %s: %s", device.serial, e)
        return clients

    async def disconnect(self, serial: str) -> None:
        """Disconnect from a specific device."""
        client = self._clients.pop(serial, None)
        if client:
            await client.disconnect()

        local_port = self._port_map.pop(serial, None)
        if local_port:
            for offset in range(3):
                await self.adb.forward_remove(serial, local_port + offset)

    async def disconnect_all(self) -> None:
        """Disconnect from all devices."""
        for serial in list(self._clients.keys()):
            await self.disconnect(serial)

    def get_client(self, serial: str) -> DeviceClient | None:
        """Get an existing client by serial."""
        return self._clients.get(serial)

    @property
    def connected_devices(self) -> list[str]:
        """List of connected device serials."""
        return [s for s, c in self._clients.items() if c.is_connected]

    async def __aenter__(self) -> DeviceManager:
        return self

    async def __aexit__(self, *args: object) -> None:
        await self.disconnect_all()
