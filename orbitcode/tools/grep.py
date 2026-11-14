"""Grep tool for searching file contents."""
from pathlib import Path
import re

from orbitcode.tools.base import Tool, ToolResult, ToolContext


class GrepTool(Tool):
    """Search for patterns in files."""

    name: ClassVar[str] = "grep"
    description: ClassVar[str] = "Search for a regex pattern in files within the working directory."
    parameters: ClassVar[dict] = {
        "type": "object",
        "properties": {
            "pattern": {"type": "string", "description": "Regex pattern to search for"},
            "path": {"type": "string", "description": "Directory or file to search (relative to working dir)", "default": "."},
            "include": {"type": "string", "description": "Glob pattern for files to include (e.g., *.py)", "default": "**/*"},
            "max_results": {"type": "integer", "description": "Maximum number of matches to return", "default": 100},
        },
        "required": ["pattern"],
    }

    async def execute(self, ctx: ToolContext, pattern: str, path: str = ".", include: str = "**/*", max_results: int = 100) -> ToolResult:
        working_dir = ctx.working_dir
        search_path = (working_dir / path).resolve()

        try:
            search_path.relative_to(working_dir.resolve())
        except ValueError:
            return ToolResult(success=False, error="Path traversal not allowed")

        if not search_path.exists():
            return ToolResult(success=False, error=f"Path not found: {path}")

        try:
            regex = re.compile(pattern)
        except re.error as e:
            return ToolResult(success=False, error=f"Invalid regex: {e}")

        matches = []
        try:
            if search_path.is_file():
                files = [search_path]
            else:
                files = list(search_path.rglob(include))
                files = [f for f in files if f.is_file()]

            for file_path in files:
                if len(matches) >= max_results:
                    break
                try:
                    content = file_path.read_text(encoding="utf-8", errors="replace")
                    for i, line in enumerate(content.splitlines(), 1):
                        if regex.search(line):
                            rel_path = file_path.relative_to(working_dir)
                            matches.append({
                                "file": str(rel_path),
                                "line": i,
                                "content": line.strip(),
                            })
                            if len(matches) >= max_results:
                                break
                except Exception:
                    continue  # Skip unreadable files

            return ToolResult(
                success=True,
                output=matches,
                metadata={"pattern": pattern, "path": path, "include": include, "count": len(matches)},
            )
        except Exception as e:
            return ToolResult(success=False, error=f"Grep error: {e}")