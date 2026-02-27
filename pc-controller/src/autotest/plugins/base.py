"""Plugin interface and base classes."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class PluginInfo:
    id: str
    name: str
    version: str
    description: str = ""
    author: str = ""
    dependencies: list[str] = field(default_factory=list)


class Plugin(ABC):
    """Base class for all AutoTest plugins."""

    @abstractmethod
    def info(self) -> PluginInfo:
        """Return plugin metadata."""
        ...

    async def on_init(self, context: PluginContext) -> None:
        """Called when plugin is loaded."""
        pass

    async def on_start(self) -> None:
        """Called when plugin is started."""
        pass

    async def on_stop(self) -> None:
        """Called when plugin is stopped."""
        pass

    async def on_destroy(self) -> None:
        """Called when plugin is unloaded."""
        pass


class PluginContext:
    """Context provided to plugins for accessing framework capabilities."""

    def __init__(
        self,
        config: dict[str, Any] | None = None,
        data_dir: str = "./plugin_data",
    ):
        self.config = config or {}
        self.data_dir = data_dir

    async def get_device_client(self, serial: str) -> Any:
        """Get a device client by serial (lazy import to avoid circular deps)."""
        raise NotImplementedError("Provided by PluginHost at runtime")
