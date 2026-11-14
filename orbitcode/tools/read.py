"""File reading tool."""
from pathlib import Path
from typing import Optional

from orbitcode.tools.base import Tool, ToolResult, ToolContext


class ReadTool(Tool):
    """Read file contents."""

    name: ClassVar[str] = "read"
    description: ClassVar[str] = "Read the contents of a file. Supports text files with optional line range."
    parameters: ClassVar[dict] = {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Path to the file (relative to working directory)"},
            "offset": {"type": "integer", "description": "Starting line number (0-indexed)", "default": 0},
            "limit": {"type": "integer", "description": "Number of lines to read (0 = all)", "default": 0},
        },
        "required": ["path"],
    }

    async def execute(self, ctx: ToolContext, path: str, offset: int = 0, limit: int = 0) -> ToolResult:
        working_dir = ctx.working_dir
        file_path = (working_dir / path).resolve()

        # Security: ensure path is within working directory
        try:
            file_path.relative_to(working_dir.resolve())
        except ValueError:
            return ToolResult(success=False, error="Path traversal not allowed")

        if not file_path.exists():
            return ToolResult(success=False, error=f"File not found: {path}")

        if not file_path.is_file():
            return ToolResult(success=False, error=f"Not a file: {path}")

        # Check file size
        max_size = ctx.settings.max_file_size
        if file_path.stat().st_size > max_size:
            return ToolResult(success=False, error=f"File too large (> {max_size} bytes)")

        try:
            content = file_path.read_text(encoding="utf-8", errors="replace")
            lines = content.splitlines()

            if offset < 0:
                offset = 0
            if offset >= len(lines):
                return ToolResult(success=True, output="", metadata={"total_lines": len(lines)})

            end = offset + limit if limit > 0 else len(lines)
            selected = lines[offset:end]

            return ToolResult(
                success=True,
                output="\n".join(selected),
                metadata={
                    "total_lines": len(lines),
                    "offset": offset,
                    "limit": limit,
                    "path": str(file_path),
                },
            )
        except Exception as e:
            return ToolResult(success=False, error=f"Read error: {e}")