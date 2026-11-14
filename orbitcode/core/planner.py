"""Planning mode for OrbitCode - breaks tasks into steps with confirmation."""
import json
from typing import Optional
from dataclasses import dataclass, field, asdict
from pathlib import Path

from orbitcode.core.model_router import ModelRouter, ChatMessage
from orbitcode.tools.registry import get_registry
from orbitcode.tools.base import ToolContext
from orbitcode.config import get_settings


@dataclass
class PlanStep:
    """A single step in a plan."""
    id: str
    description: str
    tool: Optional[str] = None
    params: dict = field(default_factory=dict)
    depends_on: list[str] = field(default_factory=list)
    status: str = "pending"  # pending, running, done, failed
    result: Optional[str] = None


@dataclass
class Plan:
    """A complete plan with multiple steps."""
    id: str
    goal: str
    steps: list[PlanStep] = field(default_factory=list)
    created_at: str = ""
    status: str = "draft"  # draft, approved, executing, done, failed


PLANNING_SYSTEM_PROMPT = """You are OrbitCode's planner. Break down the user's goal into a clear, ordered list of steps.

Each step should be:
- Specific and actionable
- Small enough to complete in one tool call (or a few)
- Ordered by dependencies

Available tools:
{tools}

Output a JSON object with this structure:
{{
  "goal": "User's original goal",
  "steps": [
    {{"id": "1", "description": "Step description", "tool": "tool_name", "params": {{}}, "depends_on": []}},
    ...
  ]
}}

Rules:
- Use only the tools listed above
- Include realistic parameters for each tool
- Steps should be in dependency order
- Max 10 steps for a typical task
- If no tool needed, use tool: "none" (for thinking/analysis steps)
"""


class Planner:
    """Creates and manages execution plans."""

    def __init__(self, model_router: ModelRouter, tool_registry, working_dir: Path, settings):
        self.model_router = model_router
        self.tool_registry = tool_registry
        self.working_dir = working_dir
        self.settings = settings
        self.tool_ctx = ToolContext(
            working_dir=working_dir,
            session_id="planner",
            settings=settings,
        )

    def _get_tool_descriptions(self) -> str:
        """Get formatted tool descriptions for the prompt."""
        tools = self.tool_registry.list_tools()
        lines = []
        for t in tools:
            params = t.parameters.get("properties", {})
            param_str = ", ".join(params.keys()) if params else "none"
            lines.append(f"  - {t.name}: {t.description} (params: {param_str})")
        return "\n".join(lines)

    async def create_plan(self, goal: str) -> Plan:
        """Create a plan for the given goal."""
        import uuid
        from datetime import datetime

        tools_desc = self._get_tool_descriptions()
        system_prompt = PLANNING_SYSTEM_PROMPT.format(tools=tools_desc)

        messages = [
            ChatMessage(role="system", content=system_prompt),
            ChatMessage(role="user", content=f"Create a plan for: {goal}"),
        ]

        response = await self.model_router.chat(messages)

        try:
            plan_data = json.loads(response.content)
        except json.JSONDecodeError:
            # Fallback: try to extract JSON from markdown
            import re
            match = re.search(r'```json\n(.*?)\n```', response.content, re.DOTALL)
            if match:
                plan_data = json.loads(match.group(1))
            else:
                raise ValueError(f"Failed to parse plan: {response.content}")

        steps = []
        for step_data in plan_data.get("steps", []):
            steps.append(PlanStep(
                id=step_data["id"],
                description=step_data["description"],
                tool=step_data.get("tool"),
                params=step_data.get("params", {}),
                depends_on=step_data.get("depends_on", []),
            ))

        plan = Plan(
            id=str(uuid.uuid4())[:8],
            goal=plan_data.get("goal", goal),
            steps=steps,
            created_at=datetime.utcnow().isoformat(),
        )
        return plan

    def format_plan(self, plan: Plan) -> str:
        """Format plan for display."""
        lines = [
            f"\n📋 Plan: {plan.goal}",
            f"   ID: {plan.id}  |  Steps: {len(plan.steps)}",
            "",
        ]
        for i, step in enumerate(plan.steps, 1):
            status_icon = {"pending": "⏳", "running": "▶️", "done": "✅", "failed": "❌"}.get(step.status, "⏳")
            tool_info = f" [{step.tool}]" if step.tool and step.tool != "none" else ""
            deps = f" ← {', '.join(step.depends_on)}" if step.depends_on else ""
            lines.append(f"  {i}. {status_icon} {step.description}{tool_info}{deps}")
        return "\n".join(lines)

    async def execute_plan(self, plan: Plan, confirm_each: bool = True) -> Plan:
        """Execute a plan step by step."""
        from rich.console import Console
        from rich.prompt import Confirm
        console = Console()

        plan.status = "executing"

        for step in plan.steps:
            # Check dependencies
            for dep_id in step.depends_on:
                dep_step = next((s for s in plan.steps if s.id == dep_id), None)
                if dep_step and dep_step.status != "done":
                    step.status = "failed"
                    step.result = f"Dependency {dep_id} not completed"
                    continue

            step.status = "running"
            console.print(f"\n[cyan]▶ Step {step.id}:[/cyan] {step.description}")

            if step.tool and step.tool != "none":
                if confirm_each:
                    if not Confirm.ask(f"  Run {step.tool} with params {step.params}?"):
                        console.print("  [yellow]Skipped[/yellow]")
                        step.status = "pending"
                        continue

                try:
                    result = await self.tool_registry.execute(step.tool, self.tool_ctx, **step.params)
                    if result.success:
                        step.status = "done"
                        step.result = str(result.output)[:500]
                        console.print(f"  [green]✓[/green] {step.result[:100]}...")
                    else:
                        step.status = "failed"
                        step.result = result.error
                        console.print(f"  [red]✗[/red] {step.result}")
                        if not Confirm.ask("  Continue despite failure?"):
                            break
                except Exception as e:
                    step.status = "failed"
                    step.result = str(e)
                    console.print(f"  [red]✗[/red] {e}")
            else:
                # Thinking step - just mark done
                step.status = "done"
                step.result = "Analysis complete"

        plan.status = "done" if all(s.status == "done" for s in plan.steps) else "failed"
        return plan