"""File editing tool (string replacement)."""
from pathlib import Path

from orbitcode.tools.base import Tool, ToolResult, ToolContext


class EditTool(Tool):
    """Edit a file by replacing a specific string."""

    name: ClassVar[str] = "edit"
    description: ClassVar[str] = "Edit a file by replacing a specific string with another. Use for precise edits."
    parameters: ClassVar[dict] = {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Path to the file (relative to working directory)"},
            "old_string": {"type": "string", "description": "The exact string to replace (must be unique in file)"},
            "new_string": {"type": "string", "description": "The string to replace it with"},
            "replace_all": {"type": "boolean", "description": "Replace all occurrences (default: false)", "default": False},
        },
        "required": ["path", "old_string", "new_string"],
    }

    async def execute(self, ctx: ToolContext, path: str, old_string: str, new_string: str, replace_all: bool = False) -> ToolResult:
        working_dir = ctx.working_dir
        file_path = (working_dir / path).resolve()

        try:
            file_path.relative_to(working_dir.resolve())
        except ValueError:
            return ToolResult(success=False, error="Path traversal not allowed")

        if not file_path.exists():
            return ToolResult(success=False, error=f"File not found: {path}")

        try:
            content = file_path.read_text(encoding="utf-8", errors="replace")

            if old_string not in content:
                return ToolResult(success=False, error="old_string not found in file")

            if not replace_all and content.count(old_string) > 1:
                return ToolResult(success=False, error="old_string appears multiple times; use replace_all=true or be more specific")

            if replace_all:
                new_content = content.replace(old_string, new_string)
                count = content.count(old_string)
            else:
                new_content = content.replace(old_string, new_string, 1)
                count = 1

            file_path.write_text(new_content, encoding="utf-8")

            return ToolResult(
                success=True,
                output=f"Replaced {count} occurrence(s) in {path}",
                metadata={"path": str(file_path), "replacements": count},
            )
        except Exception as e:
            return ToolResult(success=False, error=f"Edit error: {e}")