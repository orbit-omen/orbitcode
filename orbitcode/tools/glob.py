"""Glob pattern file finding tool."""
from pathlib import Path
import fnmatch

from orbitcode.tools.base import Tool, ToolResult, ToolContext


class GlobTool(Tool):
    """Find files matching a glob pattern."""

    name: ClassVar[str] = "glob"
    description: ClassVar[str] = "Find files matching a glob pattern (e.g., **/*.py, src/**/*.ts)."
    parameters: ClassVar[dict] = {
        "type": "object",
        "properties": {
            "pattern": {"type": "string", "description": "Glob pattern to match"},
            "root": {"type": "string", "description": "Root directory (relative to working dir)", "default": "."},
        },
        "required": ["pattern"],
    }

    async def execute(self, ctx: ToolContext, pattern: str, root: str = ".") -> ToolResult:
        working_dir = ctx.working_dir
        root_path = (working_dir / root).resolve()

        try:
            root_path.relative_to(working_dir.resolve())
        except ValueError:
            return ToolResult(success=False, error="Path traversal not allowed")

        if not root_path.exists():
            return ToolResult(success=False, error=f"Root directory not found: {root}")

        try:
            matches = []
            for file_path in root_path.rglob("*"):
                if file_path.is_file():
                    rel_path = file_path.relative_to(root_path)
                    if fnmatch.fnmatch(str(rel_path), pattern) or fnmatch.fnmatch(file_path.name, pattern):
                        matches.append(str(rel_path))

            matches.sort()
            return ToolResult(
                success=True,
                output=matches,
                metadata={"pattern": pattern, "root": str(root_path), "count": len(matches)},
            )
        except Exception as e:
            return ToolResult(success=False, error=f"Glob error: {e}")