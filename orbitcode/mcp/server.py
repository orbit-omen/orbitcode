"""MCP Server exposing OrbitCode tools (stub - requires MCP SDK compatibility)."""
import asyncio
import logging
from typing import Optional
from contextlib import asynccontextmanager
from pathlib import Path

# Note: MCP SDK API varies by version. This is a stub for future implementation.
# from mcp.server import Server
# from mcp.server.stdio import stdio_server
# from mcp.types import Tool as MCPTool, TextContent, CallToolResult

from orbitcode.tools.registry import get_registry
from orbitcode.tools.base import ToolContext
from orbitcode.config import get_settings
from orbitcode.core.session import SessionManager

logger = logging.getLogger(__name__)


class OrbitCodeMCPServer:
    """MCP Server that exposes OrbitCode tools (stub)."""

    def __init__(self, working_dir=None, settings=None):
        self.settings = settings or get_settings()
        self.working_dir = working_dir or Path.cwd()
        self.tool_registry = get_registry()
        self.session_manager = SessionManager(self.settings)

    async def run_stdio(self):
        """Run the MCP server over stdio (not implemented)."""
        logger.warning("MCP server not fully implemented - requires compatible MCP SDK version")
        # Placeholder for future implementation
        await asyncio.sleep(3600)  # Keep alive

    @asynccontextmanager
    async def lifespan(self):
        """Lifespan context manager."""
        try:
            yield
        finally:
            await self.tool_registry.close_all()


def create_mcp_server(working_dir=None, settings=None) -> OrbitCodeMCPServer:
    """Create an MCP server instance."""
    return OrbitCodeMCPServer(working_dir, settings)


# CLI entry point for MCP server
async def main():
    import sys
    working_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else Path.cwd()
    server = create_mcp_server(working_dir)
    async with server.lifespan():
        await server.run_stdio()


if __name__ == "__main__":
    asyncio.run(main())