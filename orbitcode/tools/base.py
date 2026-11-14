"""Base classes for OrbitCode tools."""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Optional, ClassVar
from pathlib import Path
from pydantic import BaseModel, Field


@dataclass
class ToolContext:
    """Context provided to tools during execution."""
    working_dir: Path
    session_id: str
    settings: Any  # Settings object
    # Runtime state
    allowed_commands: list[str] = None
    blocked_commands: list[str] = None

    def __post_init__(self):
        if self.allowed_commands is None:
            self.allowed_commands = []
        if self.blocked_commands is None:
            self.blocked_commands = []


class ToolResult(BaseModel):
    """Result of a tool execution."""
    success: bool
    output: Any = None
    error: Optional[str] = None
    metadata: dict = Field(default_factory=dict)

    def __bool__(self) -> bool:
        return self.success

    def __str__(self) -> str:
        if self.success:
            return str(self.output) if self.output else "OK"
        return f"Error: {self.error}"


class Tool(BaseModel, ABC):
    """Base class for all tools."""

    name: ClassVar[str]
    description: ClassVar[str]
    parameters: ClassVar[dict]  # JSON Schema for parameters

    model_config = {"arbitrary_types_allowed": True}

    @classmethod
    def get_parameters(cls) -> dict:
        """Get parameters schema for this tool."""
        return getattr(cls, 'parameters', {})

    @abstractmethod
    async def execute(self, ctx: ToolContext, **params) -> ToolResult:
        """Execute the tool with given parameters."""
        pass

    def to_openai_function(self) -> dict:
        """Convert to OpenAI function format."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.get_parameters(),
            },
        }

    def validate_params(self, params: dict) -> dict:
        """Validate and coerce parameters. Override for custom validation."""
        return params