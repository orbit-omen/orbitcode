"""File writing tool."""
from pathlib import Path

from orbitcode.tools.base import Tool, ToolResult, ToolContext


class WriteTool(Tool):
    """Write content to a file."""

    name: ClassVar[str] = "write"
    description: ClassVar[str] = "Write content to a file. Creates parent directories if needed. Overwrites existing files."
    parameters: ClassVar[dict] = {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Path to the file (relative to working directory)"},
            "content": {"type": "string", "description": "Content to write"},
        },
        "required": ["path", "content"],
    }

    async def execute(self, ctx: ToolContext, path: str, content: str) -> ToolResult:
        working_dir = ctx.working_dir
        file_path = (working_dir / path).resolve()

        # Security: ensure path is within working directory
        try:
            file_path.relative_to(working_dir.resolve())
        except ValueError:
            return ToolResult(success=False, error="Path traversal not allowed")

        try:
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_text(content, encoding="utf-8")

            return ToolResult(
                success=True,
                output=f"Written {len(content)} bytes to {path}",
                metadata={"path": str(file_path), "bytes": len(content)},
            )
        except Exception as e:
            return ToolResult(success=False, error=f"Write error: {e}")