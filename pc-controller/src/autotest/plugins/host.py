"""Plugin host - discovers, loads, and manages plugin lifecycle."""

from __future__ import annotations

import importlib
import logging
from pathlib import Path
from typing import Any

from autotest.plugins.base import Plugin, PluginContext, PluginInfo

logger = logging.getLogger(__name__)


class PluginHost:
    """Manages plugin lifecycle: discovery, loading, starting, stopping."""

    def __init__(self, context: PluginContext | None = None):
        self.context = context or PluginContext()
        self._plugins: dict[str, _PluginEntry] = {}

    async def load_builtin(self) -> None:
        """Load all built-in plugins."""
        builtin_plugins = [
            "autotest.plugins.builtin.ocr:OcrPlugin",
            "autotest.plugins.builtin.image_match:ImageMatchPlugin",
            "autotest.plugins.builtin.visual_diff:VisualDiffPlugin",
        ]
        for entry_point in builtin_plugins:
            try:
                await self.load_from_entry_point(entry_point)
            except Exception as e:
                logger.debug("Skipped builtin plugin %s: %s", entry_point, e)

    async def load_from_entry_point(self, entry_point: str) -> Plugin | None:
        """Load a plugin from 'module:ClassName' format."""
        module_path, class_name = entry_point.rsplit(":", 1)
        try:
            module = importlib.import_module(module_path)
            plugin_class = getattr(module, class_name)
            plugin: Plugin = plugin_class()
            return await self._register(plugin)
        except Exception as e:
            logger.warning("Failed to load plugin %s: %s", entry_point, e)
            return None

    async def load_from_directory(self, directory: str | Path) -> list[Plugin]:
        """Discover and load plugins from a directory."""
        dir_path = Path(directory)
        loaded = []
        if not dir_path.exists():
            return loaded

        for py_file in dir_path.glob("*.py"):
            if py_file.name.startswith("_"):
                continue
            try:
                spec = importlib.util.spec_from_file_location(py_file.stem, str(py_file))
                if spec and spec.loader:
                    module = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(module)
                    for attr_name in dir(module):
                        attr = getattr(module, attr_name)
                        if (
                            isinstance(attr, type)
                            and issubclass(attr, Plugin)
                            and attr is not Plugin
                        ):
                            plugin = attr()
                            result = await self._register(plugin)
                            if result:
                                loaded.append(result)
            except Exception as e:
                logger.warning("Failed to load plugin from %s: %s", py_file, e)

        return loaded

    async def _register(self, plugin: Plugin) -> Plugin:
        info = plugin.info()
        await plugin.on_init(self.context)
        await plugin.on_start()
        self._plugins[info.id] = _PluginEntry(plugin=plugin, info=info, state="running")
        logger.info("Plugin loaded: %s v%s", info.name, info.version)
        return plugin

    async def unload(self, plugin_id: str) -> None:
        entry = self._plugins.pop(plugin_id, None)
        if entry:
            await entry.plugin.on_stop()
            await entry.plugin.on_destroy()
            logger.info("Plugin unloaded: %s", plugin_id)

    async def unload_all(self) -> None:
        for plugin_id in list(self._plugins.keys()):
            await self.unload(plugin_id)

    def get_plugin(self, plugin_id: str) -> Plugin | None:
        entry = self._plugins.get(plugin_id)
        return entry.plugin if entry else None

    def list_plugins(self) -> list[PluginInfo]:
        return [e.info for e in self._plugins.values()]


class _PluginEntry:
    def __init__(self, plugin: Plugin, info: PluginInfo, state: str = "loaded"):
        self.plugin = plugin
        self.info = info
        self.state = state
