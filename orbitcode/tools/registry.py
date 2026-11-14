"""Tool registry for managing and discovering tools."""
from typing import Optional
from collections.abc import Callable

from orbitcode.tools.base import Tool, ToolContext, ToolResult
from orbitcode.config import get_settings


class ToolRegistry:
    """Registry for all available tools."""

    def __init__(self, settings=None):
        self.settings = settings or get_settings()
        self._tools: dict[str, Tool] = {}
        self._tool_factories: dict[str, Callable[[], Tool]] = {}
        self._register_builtin_tools()

    def _register_builtin_tools(self):
        """Register all built-in tools."""
        from orbitcode.tools import (
            BashTool, ReadTool, WriteTool, EditTool,
            GlobTool, GrepTool, WebSearchTool, BrowserTool
        )

        tools = [
            BashTool(),
            ReadTool(),
            WriteTool(),
            EditTool(),
            GlobTool(),
            GrepTool(),
            WebSearchTool(),
            BrowserTool(),
        ]

        for tool in tools:
            self.register(tool)

    def register(self, tool: Tool):
        """Register a tool instance."""
        self._tools[tool.name] = tool

    def register_factory(self, name: str, factory: Callable[[], Tool]):
        """Register a tool factory for lazy loading."""
        self._tool_factories[name] = factory

    def get(self, name: str) -> Optional[Tool]:
        """Get a tool by name."""
        if name in self._tools:
            return self._tools[name]
        # Try factory
        if name in self._tool_factories:
            tool = self._tool_factories[name]()
            self._tools[name] = tool
            return tool
        return None

    def list_tools(self) -> list[Tool]:
        """List all registered tools."""
        return list(self._tools.values())

    def get_openai_functions(self) -> list[dict]:
        """Get all tools in OpenAI function format."""
        return [tool.to_openai_function() for tool in self._tools.values()]

    def get_tool_definitions(self) -> list[dict]:
        """Get all tool definitions for model prompt."""
        return [
            {
                "name": tool.name,
                "description": tool.description,
                "parameters": tool.get_parameters(),
            }
            for tool in self._tools.values()
        ]

    async def execute(self, name: str, ctx: ToolContext, **params) -> ToolResult:
        """Execute a tool by name."""
        tool = self.get(name)
        if not tool:
            return ToolResult(success=False, error=f"Tool not found: {name}")
        return await tool.execute(ctx, **params)

    async def close_all(self):
        """Close all tools that have close method."""
        for tool in self._tools.values():
            if hasattr(tool, "close") and callable(tool.close):
                try:
                    await tool.close()
                except Exception:
                    pass

    def get_plugin(self, name: str):
        """Get a plugin from tool context (if available)."""
        # This is a placeholder - the actual plugin access would be through the agent context
        # For now, tools can access plugins via context.registry.get_plugin if we pass the plugin manager
        return None


_registry: Optional[ToolRegistry] = None


def get_registry() -> ToolRegistry:
    """Get singleton tool registry."""
    global _registry
    if _registry is None:
        _registry = ToolRegistry()
    return _registry