"""External AI Harness Adapters - Integrate Claude Code, Codex, Aider, Opencode, Agy, etc."""
import asyncio
import json
import os
import shlex
import subprocess
import tempfile
from pathlib import Path
from typing import Optional, List, Dict, Any, AsyncGenerator
from dataclasses import dataclass
from abc import ABC, abstractmethod

from orbitcode.config import get_settings, HarnessConfig, Settings


@dataclass
class HarnessResult:
    """Result from external harness execution."""
    success: bool
    output: str
    error: Optional[str] = None
    files_changed: List[str] = None
    cost_usd: float = 0.0
    tokens_used: int = 0


class HarnessAdapter(ABC):
    """Base class for external AI harness adapters."""

    def __init__(self, config: HarnessConfig, settings: Settings):
        self.config = config
        self.settings = settings
        self.working_dir = Path(config.working_dir) if config.working_dir else Path.cwd()

    @abstractmethod
    async def execute(self, prompt: str, context_files: List[str] = None) -> HarnessResult:
        """Execute the harness with a prompt."""
        pass

    @abstractmethod
    def is_available(self) -> bool:
        """Check if harness is installed and configured."""
        pass

    def _prepare_context(self, context_files: List[str] = None) -> str:
        """Prepare context from files."""
        if not context_files:
            return ""

        parts = ["## Context Files:"]
        for f in context_files[:10]:  # Limit context
            path = Path(f)
            if path.exists() and path.is_file():
                try:
                    content = path.read_text(encoding="utf-8", errors="replace")
                    parts.append(f"\n### {path.relative_to(self.working_dir) if path.is_relative_to(self.working_dir) else path}\n```\n{content[:2000]}\n```")
                except Exception:
                    pass
        return "\n".join(parts)

    def _format_prompt(self, prompt: str, context: str) -> str:
        """Format the full prompt using custom template or default."""
        if self.config.prompt_template:
            return self.config.prompt_template.format(context=context, prompt=prompt)
        return f"{context}\n\n## Task:\n{prompt}"

    async def _run_command(self, cmd: List[str], input_data: str = None, env: Dict = None) -> tuple:
        """Run command and return (stdout, stderr, returncode)."""
        full_env = os.environ.copy()
        if self.config.env:
            full_env.update(self.config.env)
        if env:
            full_env.update(env)

        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdin=asyncio.subprocess.PIPE if input_data else None,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=self.working_dir,
            env=full_env,
        )

        stdout, stderr = await proc.communicate(input=input_data.encode() if input_data else None)
        return stdout.decode(), stderr.decode(), proc.returncode

    def _get_version_cmd(self) -> List[str]:
        """Get the version check command."""
        if self.config.version_flag:
            return [self.config.command, self.config.version_flag]
        return [self.config.command, "--version"]

    def _build_execute_cmd(self, prompt: str) -> List[str]:
        """Build the execute command with custom command support."""
        # Use custom command if provided (e.g., fcc-claude instead of claude)
        command = self.config.custom_command or self.config.command
        args = self.config.args.copy()

        if self.config.use_stdin:
            # Prompt will be passed via stdin
            return [command] + args

        return [command] + args + ["-p", prompt]


class ClaudeCodeAdapter(HarnessAdapter):
    """Claude Code CLI adapter - supports fcc-claude and custom wrappers."""

    def is_available(self) -> bool:
        try:
            result = subprocess.run(
                self._get_version_cmd(),
                capture_output=True,
                timeout=5
            )
            return result.returncode == 0
        except Exception:
            return False

    async def execute(self, prompt: str, context_files: List[str] = None) -> HarnessResult:
        context = self._prepare_context(context_files)
        full_prompt = self._format_prompt(prompt, context)

        cmd = self._build_execute_cmd(full_prompt)

        stdout, stderr, rc = await self._run_command(cmd)

        if rc == 0:
            return HarnessResult(success=True, output=stdout)
        else:
            return HarnessResult(success=False, output=stdout, error=stderr)


class CodexAdapter(HarnessAdapter):
    """OpenAI Codex CLI adapter - supports custom wrappers."""

    def is_available(self) -> bool:
        try:
            result = subprocess.run(
                self._get_version_cmd(),
                capture_output=True,
                timeout=5
            )
            return result.returncode == 0
        except Exception:
            return False

    async def execute(self, prompt: str, context_files: List[str] = None) -> HarnessResult:
        context = self._prepare_context(context_files)
        full_prompt = self._format_prompt(prompt, context)

        command = self.config.custom_command or self.config.command
        cmd = [command] + self.config.args + ["exec", full_prompt]

        stdout, stderr, rc = await self._run_command(cmd)

        if rc == 0:
            return HarnessResult(success=True, output=stdout)
        else:
            return HarnessResult(success=False, output=stdout, error=stderr)


class AiderAdapter(HarnessAdapter):
    """Aider adapter - supports custom wrappers."""

    def is_available(self) -> bool:
        try:
            result = subprocess.run(
                self._get_version_cmd(),
                capture_output=True,
                timeout=5
            )
            return result.returncode == 0
        except Exception:
            return False

    async def execute(self, prompt: str, context_files: List[str] = None) -> HarnessResult:
        # Aider works by modifying files in place
        # We'll create a temp file with the prompt and use --message
        context = self._prepare_context(context_files)
        full_prompt = self._format_prompt(prompt, context)

        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            f.write(full_prompt)
            prompt_file = f.name

        try:
            command = self.config.custom_command or self.config.command
            cmd = [command] + self.config.args + [
                "--message-file", prompt_file,
                "--yes",  # Auto-approve edits
            ]

            stdout, stderr, rc = await self._run_command(cmd)

            if rc == 0:
                return HarnessResult(success=True, output=stdout)
            else:
                return HarnessResult(success=False, output=stdout, error=stderr)
        finally:
            try:
                os.unlink(prompt_file)
            except Exception:
                pass


class OpencodeAdapter(HarnessAdapter):
    """Opencode adapter - supports custom wrappers."""

    def is_available(self) -> bool:
        try:
            result = subprocess.run(
                self._get_version_cmd(),
                capture_output=True,
                timeout=5
            )
            return result.returncode == 0
        except Exception:
            return False

    async def execute(self, prompt: str, context_files: List[str] = None) -> HarnessResult:
        context = self._prepare_context(context_files)
        full_prompt = self._format_prompt(prompt, context)

        command = self.config.custom_command or self.config.command
        cmd = [command] + self.config.args + ["run", full_prompt]

        stdout, stderr, rc = await self._run_command(cmd)

        if rc == 0:
            return HarnessResult(success=True, output=stdout)
        else:
            return HarnessResult(success=False, output=stdout, error=stderr)


class AgyAdapter(HarnessAdapter):
    """Agy adapter - supports custom wrappers."""

    def is_available(self) -> bool:
        try:
            result = subprocess.run(
                self._get_version_cmd(),
                capture_output=True,
                timeout=5
            )
            return result.returncode == 0
        except Exception:
            return False

    async def execute(self, prompt: str, context_files: List[str] = None) -> HarnessResult:
        context = self._prepare_context(context_files)
        full_prompt = self._format_prompt(prompt, context)

        command = self.config.custom_command or self.config.command
        cmd = [command] + self.config.args + ["ask", full_prompt]

        stdout, stderr, rc = await self._run_command(cmd)

        if rc == 0:
            return HarnessResult(success=True, output=stdout)
        else:
            return HarnessResult(success=False, output=stdout, error=stderr)


class GeminiCliAdapter(HarnessAdapter):
    """Google Gemini CLI adapter - supports custom wrappers."""

    def is_available(self) -> bool:
        try:
            result = subprocess.run(
                self._get_version_cmd(),
                capture_output=True,
                timeout=5
            )
            return result.returncode == 0
        except Exception:
            return False

    async def execute(self, prompt: str, context_files: List[str] = None) -> HarnessResult:
        context = self._prepare_context(context_files)
        full_prompt = self._format_prompt(prompt, context)

        command = self.config.custom_command or self.config.command
        cmd = [command] + self.config.args + ["-p", full_prompt]

        stdout, stderr, rc = await self._run_command(cmd)

        if rc == 0:
            return HarnessResult(success=True, output=stdout)
        else:
            return HarnessResult(success=False, output=stdout, error=stderr)


class CustomHarnessAdapter(HarnessAdapter):
    """Generic custom harness adapter - supports custom wrappers."""

    def is_available(self) -> bool:
        try:
            result = subprocess.run(
                self._get_version_cmd(),
                capture_output=True,
                timeout=5
            )
            return result.returncode == 0
        except Exception:
            return False

    async def execute(self, prompt: str, context_files: List[str] = None) -> HarnessResult:
        context = self._prepare_context(context_files)
        full_prompt = self._format_prompt(prompt, context)

        command = self.config.custom_command or self.config.command

        # Handle different input formats
        if self.config.use_stdin:
            if self.config.input_format == "json":
                input_data = json.dumps({"prompt": full_prompt})
            elif self.config.input_format == "markdown":
                input_data = f"# Task\n\n{full_prompt}"
            else:
                input_data = full_prompt
            cmd = [command] + self.config.args
            stdout, stderr, rc = await self._run_command(cmd, input_data=input_data)
        else:
            cmd = [command] + self.config.args + ["-p", full_prompt]
            stdout, stderr, rc = await self._run_command(cmd)

        # Parse output based on output_parser
        output = stdout
        if self.config.output_parser == "extract_code_blocks":
            output = self._extract_code_blocks(stdout)
        elif self.config.output_parser == "json":
            try:
                data = json.loads(stdout)
                output = data.get("response", data.get("output", stdout))
            except Exception:
                pass

        if rc == 0:
            return HarnessResult(success=True, output=output)
        else:
            return HarnessResult(success=False, output=output, error=stderr)

    def _extract_code_blocks(self, text: str) -> str:
        """Extract code blocks from markdown output."""
        import re
        blocks = re.findall(r'```(?:\w+)?\n(.*?)\n```', text, re.DOTALL)
        if blocks:
            return "\n\n".join(blocks)
        return text


# Pre-defined harness templates for popular tools
HARNESS_TEMPLATES = {
    "claude_code": {
        "command": "claude",
        "args": [],
        "version_flag": "--version",
        "prompt_template": "{context}\n\n## Task:\n{prompt}",
        "custom_command": None,  # Can be overridden to "fcc-claude" or similar
    },
    "claude_code_fcc": {
        "command": "fcc-claude",
        "args": [],
        "version_flag": "--version",
        "prompt_template": "{context}\n\n## Task:\n{prompt}",
    },
    "codex": {
        "command": "codex",
        "args": [],
        "version_flag": "--version",
        "prompt_template": "{context}\n\n## Task:\n{prompt}",
    },
    "codex_custom": {
        "command": "codex",
        "args": ["--model", "gpt-4o"],
        "version_flag": "--version",
        "prompt_template": "{context}\n\n## Task:\n{prompt}",
    },
    "aider": {
        "command": "aider",
        "args": ["--no-git", "--yes"],
        "version_flag": "--version",
        "prompt_template": "{context}\n\n## Task:\n{prompt}",
    },
    "opencode": {
        "command": "opencode",
        "args": [],
        "version_flag": "--version",
        "prompt_template": "{context}\n\n## Task:\n{prompt}",
    },
    "agy": {
        "command": "agy",
        "args": [],
        "version_flag": "--version",
        "prompt_template": "{context}\n\n## Task:\n{prompt}",
    },
    "gemini": {
        "command": "gemini",
        "args": [],
        "version_flag": "--version",
        "prompt_template": "{context}\n\n## Task:\n{prompt}",
    },
    "custom_stdin": {
        "command": "my-ai-tool",
        "args": [],
        "version_flag": "--version",
        "use_stdin": True,
        "input_format": "json",
        "prompt_template": "{prompt}",
    },
}


# Adapter registry
ADAPTER_CLASSES = {
    "claude_code": ClaudeCodeAdapter,
    "codex": CodexAdapter,
    "aider": AiderAdapter,
    "opencode": OpencodeAdapter,
    "agy": AgyAdapter,
    "gemini": GeminiCliAdapter,
    "custom": CustomHarnessAdapter,
}

# Harness templates for quick setup
HARNESS_TEMPLATES = {
    "claude_code": {
        "command": "claude",
        "args": [],
        "version_flag": "--version",
        "prompt_template": "{context}\n\n## Task:\n{prompt}",
        "custom_command": None,  # Can be overridden to "fcc-claude" or similar
    },
    "claude_code_fcc": {
        "command": "fcc-claude",
        "args": [],
        "version_flag": "--version",
        "prompt_template": "{context}\n\n## Task:\n{prompt}",
    },
    "codex": {
        "command": "codex",
        "args": [],
        "version_flag": "--version",
        "prompt_template": "{context}\n\n## Task:\n{prompt}",
    },
    "codex_custom": {
        "command": "codex",
        "args": ["--model", "gpt-4o"],
        "version_flag": "--version",
        "prompt_template": "{context}\n\n## Task:\n{prompt}",
    },
    "aider": {
        "command": "aider",
        "args": ["--no-git", "--yes"],
        "version_flag": "--version",
        "prompt_template": "{context}\n\n## Task:\n{prompt}",
    },
    "opencode": {
        "command": "opencode",
        "args": [],
        "version_flag": "--version",
        "prompt_template": "{context}\n\n## Task:\n{prompt}",
    },
    "agy": {
        "command": "agy",
        "args": [],
        "version_flag": "--version",
        "prompt_template": "{context}\n\n## Task:\n{prompt}",
    },
    "gemini": {
        "command": "gemini",
        "args": [],
        "version_flag": "--version",
        "prompt_template": "{context}\n\n## Task:\n{prompt}",
    },
    "custom_stdin": {
        "command": "my-ai-tool",
        "args": [],
        "version_flag": "--version",
        "use_stdin": True,
        "input_format": "json",
        "prompt_template": "{prompt}",
    },
}


class HarnessManager:
    """Manages external AI harness adapters."""

    def __init__(self, settings: Optional[Settings] = None):
        self.settings = settings or get_settings()
        self.adapters: Dict[str, HarnessAdapter] = {}
        self._initialize_adapters()

    def _initialize_adapters(self):
        """Initialize adapters from settings."""
        for name, config in self.settings.get_all_harnesses().items():
            adapter_class = ADAPTER_CLASSES.get(config.input_format if config.input_format in ADAPTER_CLASSES else "custom")
            # Check for specific adapter
            for key, cls in ADAPTER_CLASSES.items():
                if key in name.lower():
                    adapter_class = cls
                    break

            try:
                adapter = adapter_class(config, self.settings)
                if adapter.is_available():
                    self.adapters[name] = adapter
            except Exception as e:
                pass  # Silently skip unavailable adapters

    def get_adapter(self, name: str) -> Optional[HarnessAdapter]:
        """Get adapter by name."""
        return self.adapters.get(name)

    def list_adapters(self) -> List[Dict[str, Any]]:
        """List all available adapters."""
        return [
            {"name": name, "command": adapter.config.command, "available": True}
            for name, adapter in self.adapters.items()
        ]

    async def execute(
        self,
        harness_name: str,
        prompt: str,
        context_files: List[str] = None
    ) -> HarnessResult:
        """Execute a harness."""
        adapter = self.adapters.get(harness_name)
        if not adapter:
            return HarnessResult(
                success=False,
                output="",
                error=f"Harness '{harness_name}' not found or not available"
            )

        return await adapter.execute(prompt, context_files)

    async def race(
        self,
        harness_names: List[str],
        prompt: str,
        context_files: List[str] = None
    ) -> Dict[str, HarnessResult]:
        """Run multiple harnesses in parallel and return all results."""
        tasks = [
            self.execute(name, prompt, context_files)
            for name in harness_names
            if name in self.adapters
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        return {
            name: result if isinstance(result, HarnessResult) else HarnessResult(
                success=False, output="", error=str(result)
            )
            for name, result in zip(harness_names, results)
            if name in self.adapters
        }

    async def chain(
        self,
        steps: List[Dict[str, Any]],
        initial_prompt: str,
        context_files: List[str] = None
    ) -> List[HarnessResult]:
        """Chain multiple harnesses: each step feeds into the next."""
        results = []
        current_prompt = initial_prompt

        for step in steps:
            harness_name = step.get("harness")
            transform = step.get("transform", "passthrough")  # passthrough, extract_code, summarize

            result = await self.execute(harness_name, current_prompt, context_files)
            results.append(result)

            if result.success:
                if transform == "extract_code":
                    current_prompt = self._extract_code(result.output)
                elif transform == "summarize":
                    current_prompt = f"Previous result summary:\n{result.output[:2000]}"
                else:
                    current_prompt = result.output
            else:
                break

        return results

    def _extract_code(self, text: str) -> str:
        """Extract code blocks from text."""
        import re
        blocks = re.findall(r'```(?:\w+)?\n(.*?)\n```', text, re.DOTALL)
        return "\n\n".join(blocks) if blocks else text


def get_harness_manager(settings: Optional[Settings] = None) -> HarnessManager:
    """Get singleton harness manager."""
    return HarnessManager(settings)


def add_harness_from_template(
    name: str,
    template_name: str,
    settings: Optional[Settings] = None,
    **overrides
) -> HarnessConfig:
    """Add a harness from a predefined template with optional overrides."""
    s = settings or get_settings()

    if template_name not in HARNESS_TEMPLATES:
        raise ValueError(f"Unknown template: {template_name}. Available: {list(HARNESS_TEMPLATES.keys())}")

    template = HARNESS_TEMPLATES[template_name].copy()
    template.update(overrides)

    config = HarnessConfig(**template)
    s.harnesses[name] = config

    # Save to config
    _save_harnesses_to_config(s)

    return config


def _save_harnesses_to_config(settings: Settings):
    """Save harnesses to config.toml"""
    import tomli_w

    config_dir = Path.home() / ".orbitcode"
    config_path = config_dir / "config.toml"

    if config_path.exists():
        import tomli
        with open(config_path, "rb") as f:
            config_data = tomli.load(f)
    else:
        config_data = {}

    harness_list = {}
    for name, h in settings.harnesses.items():
        harness_list[name] = {
            "command": h.command,
            "args": h.args,
            "env": h.env,
            "input_format": h.input_format,
            "output_parser": h.output_parser,
            "enabled": h.enabled,
            "working_dir": h.working_dir,
            "prompt_template": h.prompt_template,
            "context_template": h.context_template,
            "version_flag": h.version_flag,
            "use_stdin": h.use_stdin,
            "timeout": h.timeout,
            "custom_command": h.custom_command,
        }

    config_data["harnesses"] = harness_list
    config_path.write_text(tomli_w.dumps(config_data))