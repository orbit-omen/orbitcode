"""Plugin system for OrbitCode."""
import importlib.util
import logging
from pathlib import Path
from typing import Optional

from orbitcode.config import get_settings
from orbitcode.tools.registry import ToolRegistry
from orbitcode.tools.base import Tool

logger = logging.getLogger(__name__)


class Plugin:
    """Base class for plugins."""

    name: str = ""
    version: str = "0.1.0"
    description: str = ""

    def __init__(self, settings=None):
        self.settings = settings or get_settings()
        self.tools: list[Tool] = []

    def register_tools(self, registry: ToolRegistry):
        """Register tools provided by this plugin."""
        for tool in self.tools:
            registry.register(tool)
            logger.info(f"Plugin {self.name}: registered tool {tool.name}")

    async def initialize(self):
        """Initialize the plugin (async setup)."""
        pass

    async def shutdown(self):
        """Cleanup on shutdown."""
        pass


class PluginManager:
    """Manages plugin discovery and loading."""

    def __init__(self, settings=None):
        self.settings = settings or get_settings()
        self.plugins: dict[str, Plugin] = {}
        self._load_plugins()

    def _load_plugins(self):
        """Load plugins from the plugins directory."""
        plugins_dir = self.settings.plugins_dir
        if not plugins_dir.exists():
            return

        for plugin_dir in plugins_dir.iterdir():
            if not plugin_dir.is_dir():
                continue
            if plugin_dir.name.startswith(".") or plugin_dir.name == "__pycache__":
                continue

            # Check if plugin is enabled
            if self.settings.enabled_plugins and plugin_dir.name not in self.settings.enabled_plugins:
                continue

            self._load_plugin(plugin_dir)

    def _load_plugin(self, plugin_dir: Path):
        """Load a single plugin from a directory."""
        # Look for plugin.py or __init__.py with Plugin class
        plugin_file = plugin_dir / "plugin.py"
        if not plugin_file.exists():
            plugin_file = plugin_dir / "__init__.py"
        if not plugin_file.exists():
            return

        try:
            spec = importlib.util.spec_from_file_location(f"orbitcode_plugin_{plugin_dir.name}", plugin_file)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)

            # Find Plugin subclass
            for attr_name in dir(module):
                attr = getattr(module, attr_name)
                if isinstance(attr, type) and issubclass(attr, Plugin) and attr is not Plugin:
                    plugin = attr(self.settings)
                    self.plugins[plugin_dir.name] = plugin
                    logger.info(f"Loaded plugin: {plugin_dir.name} ({plugin.name})")
                    break
        except Exception as e:
            logger.error(f"Failed to load plugin {plugin_dir.name}: {e}")

    def register_all(self, registry: ToolRegistry):
        """Register all plugin tools with the registry."""
        for plugin in self.plugins.values():
            plugin.register_tools(registry)

    async def initialize_all(self):
        """Initialize all plugins."""
        for plugin in self.plugins.values():
            try:
                await plugin.initialize()
            except Exception as e:
                logger.error(f"Plugin {plugin.name} initialization failed: {e}")

    async def shutdown_all(self):
        """Shutdown all plugins."""
        for plugin in self.plugins.values():
            try:
                await plugin.shutdown()
            except Exception as e:
                logger.error(f"Plugin {plugin.name} shutdown failed: {e}")

    def list_plugins(self) -> list[dict]:
        """List loaded plugins."""
        return [
            {"name": p.name, "version": p.version, "description": p.description, "tools": [t.name for t in p.tools]}
            for p in self.plugins.values()
        ]

    def get_plugin(self, name: str) -> Optional[Plugin]:
        """Get a plugin by name."""
        return self.plugins.get(name)