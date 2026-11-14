"""OrbitCode Agent - Main agent loop with streaming, tool execution, session management, and learning integration."""
import asyncio
import logging
import uuid
from pathlib import Path
from typing import Optional, List, Dict, Any, AsyncGenerator
from dataclasses import dataclass, field
from datetime import datetime

from orbitcode.config import get_settings, Settings
from orbitcode.core.model_router import ModelRouter, ChatMessage, ChatResponse, ModelError
from orbitcode.core.session import SessionManager, Session
from orbitcode.tools.registry import ToolRegistry, get_registry
from orbitcode.tools.base import ToolResult
from orbitcode.core.learning import get_learning_engine, LearningEngine
from orbitcode.plugins import PluginManager

logger = logging.getLogger(__name__)


@dataclass
class AgentContext:
    """Runtime context for the agent."""
    working_dir: Path
    session: Session
    model_router: ModelRouter
    tool_registry: ToolRegistry
    session_manager: SessionManager
    settings: Settings
    learning_engine: LearningEngine
    plugin_manager: PluginManager
    current_mode: str = "smart"  # ask, auto_edit, plan, yolo, smart
    tokens_used: int = 0
    tokens_saved: int = 0
    turn_count: int = 0


class Agent:
    """Main OrbitCode agent with streaming, tools, learning, and session persistence."""

    def __init__(self, ctx: AgentContext):
        self.ctx = ctx
        self._running = False
        self._pending_approval: Optional[Dict] = None

    @classmethod
    async def create(
        cls,
        working_dir: Path,
        session_manager: SessionManager,
        model_router: ModelRouter,
        tool_registry: ToolRegistry,
        settings: Settings,
        plugin_manager: PluginManager,
        resume: bool = False,
    ) -> "Agent":
        """Create and initialize agent with new or resumed session."""
        learning_engine = get_learning_engine()

        if resume:
            session = session_manager.get_latest_session(working_dir)
            if not session:
                session = session_manager.create_session(working_dir)
        else:
            session = session_manager.create_session(working_dir)

        session_manager.set_current(session)

        ctx = AgentContext(
            working_dir=working_dir,
            session=session,
            model_router=model_router,
            tool_registry=tool_registry,
            session_manager=session_manager,
            settings=settings,
            learning_engine=learning_engine,
            plugin_manager=plugin_manager,
            current_mode=settings.permission_mode,
        )

        agent = cls(ctx)
        await agent._initialize()
        return agent

    async def _initialize(self) -> None:
        """Initialize agent components."""
        # Load project playbook if exists
        playbook = self.ctx.learning_engine.generate_playbook_markdown(str(self.ctx.working_dir))
        if playbook:
            self.ctx.session.metadata["playbook"] = playbook

        # Initialize plugins
        await self.ctx.plugin_manager.initialize_all()

        # Register plugin tools
        self.ctx.plugin_manager.register_all(self.ctx.tool_registry)

    def _build_system_prompt(self) -> str:
        """Build the system prompt with all context, lessons, and instructions."""
        settings = self.ctx.settings
        working_dir = self.ctx.working_dir

        # Base system prompt
        prompt_parts = [
            f"You are {settings.app_name}, an AI coding agent made by {settings.maker}.",
            f"Working directory: {working_dir}",
            f"Current mode: {self.ctx.current_mode}",
            "",
            "## Capabilities",
            "- Read, write, edit files in the workspace",
            "- Execute bash commands",
            "- Search code with glob/grep",
            "- Search the web for factual information (Google Search + Grounding)",
            "- Browse websites for documentation",
            "- Plan multi-step tasks",
            "- Git operations",
            "- Learn from mistakes and adapt",
            "",
            "## Tool Use Guidelines",
            "- Use tools efficiently; batch related operations",
            "- Prefer targeted reads (read_lines) over full file reads",
            "- Use google_search for factual queries (versions, docs, errors)",
            "- Use bash for file ops, git, running tests/commands",
            "- Always verify changes work (run tests, lint, typecheck)",
            "",
        ]

        # Add permission mode instructions
        mode_instructions = {
            "ask": "ASK before every tool use. Wait for user confirmation.",
            "auto_edit": "Auto-execute file edits. ASK for bash commands, git push, destructive ops.",
            "plan": "Create plan first. Ask for confirmation before executing.",
            "yolo": "Execute everything automatically. No confirmations.",
            "smart": "Auto-execute most things. ASK for: destructive commands, large file changes (>100 lines), "
                     "external API calls that cost money, git push/force push, long test runs (>30s), "
                     "commits without message review, package installs.",
        }
        prompt_parts.append(f"## Permission Mode: {self.ctx.current_mode}")
        prompt_parts.append(mode_instructions.get(self.ctx.current_mode, mode_instructions["smart"]))
        prompt_parts.append("")

        # Add negative constraints (never rules)
        negative_rules = self.ctx.learning_engine.get_all_negative_rules()
        if negative_rules:
            prompt_parts.append("## NEVER DO THESE (Hard Constraints):")
            for rule in negative_rules:
                prompt_parts.append(f"- {rule.rule}")
            prompt_parts.append("")

        # Add relevant lessons from learning engine
        if settings.learning_enabled and settings.auto_inject_lessons:
            # We'll inject lessons per-tool based on context
            pass

        # Add repo playbook
        playbook = self.ctx.session.metadata.get("playbook")
        if playbook:
            prompt_parts.append("## Project Playbook (Learned Conventions):")
            prompt_parts.append(playbook[:3000])  # Limit size
            prompt_parts.append("")

        # Add tool descriptions
        tools = self.ctx.tool_registry.get_tool_definitions()
        if tools:
            prompt_parts.append("## Available Tools:")
            for tool in tools:
                prompt_parts.append(f"- **{tool['name']}**: {tool['description']}")
            prompt_parts.append("")

        # Add current git status
        try:
            from orbitcode.core.git import GitIntegration
            git = GitIntegration(working_dir)
            if git.is_repo():
                status = git.get_status()
                prompt_parts.append(f"## Git Status: Branch={status.branch}, Dirty={status.dirty}")
                if status.staged_files:
                    prompt_parts.append(f"  Staged: {', '.join(status.staged_files[:5])}")
                if status.unstaged_files:
                    prompt_parts.append(f"  Unstaged: {', '.join(status.unstaged_files[:5])}")
        except Exception:
            pass

        prompt_parts.append("---")
        prompt_parts.append("Respond naturally. Use tools when needed. Think step by step.")

        return "\n".join(prompt_parts)

    def _get_lessons_for_tool(self, tool_name: str, file_path: str = "") -> str:
        """Get relevant lessons for a specific tool and file context."""
        if not self.ctx.settings.learning_enabled or not self.ctx.settings.auto_inject_lessons:
            return ""

        file_ext = Path(file_path).suffix if file_path else ""
        lessons = self.ctx.learning_engine.get_relevant_lessons(
            tool_name, file_ext, "", self.ctx.settings.max_lessons_per_prompt
        )

        if lessons:
            return self.ctx.learning_engine.format_lessons_for_prompt(lessons)
        return ""

    async def run_stream(self, user_input: str) -> AsyncGenerator[str, None]:
        """Run agent with streaming response."""
        self._running = True
        self.ctx.turn_count += 1

        try:
            # Add user message to session
            self.ctx.session.add_message("user", user_input)

            # Build messages for model
            messages = self._build_messages(user_input)

            # Stream response
            full_response = ""
            tool_calls_made = []

            async for chunk in self._stream_chat(messages):
                if isinstance(chunk, str):
                    full_response += chunk
                    yield chunk
                elif isinstance(chunk, dict) and chunk.get("type") == "tool_call":
                    # Tool call executed, result will be streamed
                    tool_calls_made.append(chunk)
                    yield f"\n[Tool: {chunk['tool']}] {chunk.get('result', '')[:200]}...\n"

            # Add assistant response to session
            self.ctx.session.add_message("assistant", full_response, tool_calls=tool_calls_made)

            # Auto-save session
            self.ctx.session_manager.save_current()

            # Generate playbook at session end (periodic)
            if self.ctx.settings.auto_playbook and self.ctx.turn_count % 10 == 0:
                playbook = self.ctx.learning_engine.generate_playbook_markdown(str(self.ctx.working_dir))
                if playbook:
                    self.ctx.session.metadata["playbook"] = playbook
                    playbook_path = self.ctx.working_dir / ".orbitcode" / "PLAYBOOK.md"
                    playbook_path.parent.mkdir(exist_ok=True)
                    playbook_path.write_text(playbook)

        finally:
            self._running = False

    def _build_messages(self, user_input: str) -> List[ChatMessage]:
        """Build message list for model."""
        messages = [
            ChatMessage(role="system", content=self._build_system_prompt()),
        ]

        # Add conversation history (last 20 messages)
        history = self.ctx.session.messages[-20:]
        for msg in history:
            if msg.role in ("user", "assistant"):
                messages.append(ChatMessage(role=msg.role, content=msg.content))

        # Add current user input
        messages.append(ChatMessage(role="user", content=user_input))

        return messages

    async def _stream_chat(self, messages: List[ChatMessage]) -> AsyncGenerator[Any, None]:
        """Stream chat with tool execution loop."""
        max_turns = 10
        turn = 0

        while turn < max_turns:
            turn += 1

            # Get tools for model
            tools = self.ctx.tool_registry.get_tool_definitions()

            try:
                # Stream from model
                async for content_delta, tool_calls, model_name, is_final in self.ctx.model_router.chat_stream(
                    messages, tools, task_type="coding"
                ):
                    if content_delta:
                        yield content_delta

                    if tool_calls:
                        # Execute tool calls
                        for tc in tool_calls:
                            yield await self._execute_tool_call(tc, messages)

                        # After tool execution, continue the loop to let model respond
                        break

                if is_final:
                    break

            except ModelError as e:
                yield f"\n[Error: All models failed - {e}]\n"
                break
            except Exception as e:
                logger.error(f"Chat stream error: {e}")
                yield f"\n[Error: {e}]\n"
                break

    async def _execute_tool_call(self, tool_call: dict, messages: List[ChatMessage]) -> Dict[str, Any]:
        """Execute a single tool call with permission checking and learning."""
        tool_name = tool_call.get("function", {}).get("name")
        arguments = tool_call.get("function", {}).get("arguments", {})
        tool_call_id = tool_call.get("id")

        if isinstance(arguments, str):
            import json
            arguments = json.loads(arguments)

        # Check negative rules
        violations = self.ctx.learning_engine.check_negative_rules(tool_name, "execute", arguments)
        if violations and self.ctx.settings.negative_rules_strict:
            result = f"BLOCKED by negative rule: {'; '.join(violations)}"
            return {"type": "tool_call", "tool": tool_name, "result": result, "blocked": True}

        # Permission check based on mode
        if not self._check_permission(tool_name, arguments):
            result = await self._request_permission(tool_name, arguments)
            if not result:
                return {"type": "tool_call", "tool": tool_name, "result": "Cancelled by user", "cancelled": True}

        # Execute tool
        tool = self.ctx.tool_registry.get_tool(tool_name)
        if not tool:
            result = f"Tool not found: {tool_name}"
        else:
            try:
                # Add learning context for this tool
                file_path = arguments.get("path") or arguments.get("file_path") or ""
                lessons = self._get_lessons_for_tool(tool_name, file_path)
                if lessons and hasattr(tool, 'set_learning_context'):
                    tool.set_learning_context(lessons)

                tool_result = await tool.execute(**arguments)
                result = tool_result.output if tool_result.success else f"Error: {tool_result.output}"

                # Log error for learning if failed
                if not tool_result.success:
                    error_event_id = self.ctx.learning_engine.log_error(
                        Exception(result), tool_name, file_path, str(arguments)
                    )
                    # Store event ID for potential resolution tracking
                    if not hasattr(self, '_pending_errors'):
                        self._pending_errors = {}
                    self._pending_errors[tool_call_id] = error_event_id

            except Exception as e:
                result = f"Tool execution error: {e}"
                self.ctx.learning_engine.log_error(e, tool_name, file_path, str(arguments))

        # Add tool result to messages
        messages.append(ChatMessage(
            role="tool",
            content=result,
            tool_call_id=tool_call_id
        ))

        return {"type": "tool_call", "tool": tool_name, "result": result}

    def _check_permission(self, tool_name: str, arguments: dict) -> bool:
        """Check if tool execution is allowed in current mode."""
        mode = self.ctx.current_mode

        if mode == "yolo":
            return True

        if mode == "ask":
            return False

        if mode == "auto_edit":
            # Allow file edits, ask for bash/git/destructive
            if tool_name in ("bash", "git", "write", "edit"):
                # Check for destructive patterns
                if tool_name == "bash":
                    cmd = arguments.get("command", "")
                    if any(p in cmd for p in self.ctx.settings.destructive_patterns):
                        return False
                return True
            return False

        if mode == "plan":
            return False  # Plan mode doesn't execute

        if mode == "smart":
            # Smart mode: auto for most, ask for triggers
            triggers = self.ctx.settings.smart_mode_triggers

            if tool_name == "bash":
                cmd = arguments.get("command", "")
                if any(p in cmd for p in self.ctx.settings.destructive_patterns):
                    return "destructive_command" not in triggers  # Ask if trigger enabled
                # Check for package installs
                if any(p in cmd for p in ["npm install", "pip install", "cargo add", "go get"]):
                    return "install_packages" not in triggers

            if tool_name in ("write", "edit"):
                # Check for large changes (would need preview)
                if "large_file_change" in triggers:
                    return False  # Ask for large changes

            if tool_name == "git":
                action = arguments.get("action", "")
                if action == "push":
                    return "git_push" not in triggers

            return True  # Default allow in smart mode

        return False

    async def _request_permission(self, tool_name: str, arguments: dict) -> bool:
        """Request user permission for tool execution."""
        # This would integrate with TUI/CLI for interactive approval
        # For now, return True in non-interactive contexts
        return True

    def set_mode(self, mode: str) -> None:
        """Set permission mode."""
        valid_modes = {"ask", "auto_edit", "plan", "yolo", "smart"}
        if mode in valid_modes:
            self.ctx.current_mode = mode
            self.ctx.settings.permission_mode = mode

    def get_stats(self) -> dict:
        """Get agent statistics."""
        return {
            "turn_count": self.ctx.turn_count,
            "tokens_used": self.ctx.tokens_used,
            "tokens_saved": self.ctx.tokens_saved,
            "session_id": self.ctx.session.id[:8],
            "mode": self.ctx.current_mode,
            "learning_stats": self.ctx.learning_engine.get_stats(),
        }


async def create_agent(
    working_dir: Path,
    session_manager: SessionManager,
    model_router: ModelRouter,
    tool_registry: ToolRegistry,
    settings: Settings,
    plugin_manager: PluginManager,
    resume: bool = False,
) -> Agent:
    """Factory function to create agent."""
    return await Agent.create(
        working_dir=working_dir,
        session_manager=session_manager,
        model_router=model_router,
        tool_registry=tool_registry,
        settings=settings,
        plugin_manager=plugin_manager,
        resume=resume,
    )