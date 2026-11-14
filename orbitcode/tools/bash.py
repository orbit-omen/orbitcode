"""Bash command execution tool."""
import asyncio
import shlex
import os
from pathlib import Path
from typing import Optional

from orbitcode.tools.base import Tool, ToolResult, ToolContext


class BashTool(Tool):
    """Execute bash commands in the working directory."""

    name: ClassVar[str] = "bash"
    description: ClassVar[str] = "Execute a bash command in the working directory. Use for running commands, scripts, builds, tests, etc."
    parameters: ClassVar[dict] = {
        "type": "object",
        "properties": {
            "command": {"type": "string", "description": "The bash command to execute"},
            "timeout": {"type": "number", "description": "Timeout in seconds (default: 60)", "default": 60},
            "description": {"type": "string", "description": "Brief description of what the command does"},
        },
        "required": ["command", "description"],
    }

    async def execute(self, ctx: ToolContext, command: str, timeout: float = 60, description: str = "") -> ToolResult:
        # Security: check against blocked commands
        settings = ctx.settings
        for blocked in settings.blocked_commands:
            if blocked in command:
                return ToolResult(success=False, error=f"Blocked command pattern: {blocked}")

        # Security: check if command starts with allowed prefix (optional strict mode)
        # For now, allow all commands but log them

        working_dir = ctx.working_dir

        try:
            # Run command
            proc = await asyncio.create_subprocess_shell(
                command,
                cwd=working_dir,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env={**os.environ, "TERM": "dumb"},  # Clean env
            )

            try:
                stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
            except asyncio.TimeoutError:
                proc.kill()
                await proc.wait()
                return ToolResult(
                    success=False,
                    error=f"Command timed out after {timeout}s",
                    output={"stdout": "", "stderr": "TIMEOUT", "returncode": -1},
                )

            output = {
                "stdout": stdout.decode("utf-8", errors="replace"),
                "stderr": stderr.decode("utf-8", errors="replace"),
                "returncode": proc.returncode,
            }

            success = proc.returncode == 0
            return ToolResult(
                success=success,
                output=output,
                error=output["stderr"] if not success else None,
                metadata={"command": command, "description": description},
            )

        except Exception as e:
            return ToolResult(success=False, error=f"Execution error: {e}")