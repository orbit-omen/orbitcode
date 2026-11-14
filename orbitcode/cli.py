"""CLI entry point for OrbitCode."""
import asyncio
import logging
import sys
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.markdown import Markdown
from rich.prompt import Prompt, Confirm

from orbitcode.config import reload_settings, load_or_wizard, is_first_run
from orbitcode.config.customise import run_customise
from orbitcode.core.model_router import ModelRouter
from orbitcode.core.session import SessionManager
from orbitcode.core.agent import Agent, create_agent
from orbitcode.core.planner import Planner
from orbitcode.core.indexer import CodeIndexer
from orbitcode.core.git import GitIntegration
from orbitcode.core.tui import launch_tui
from orbitcode.tools.registry import get_registry
from orbitcode.plugins import PluginManager
from orbitcode.mcp import create_mcp_server

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

app = typer.Typer(
    name="orbitcode",
    help="OrbitCode - AI coding agent with model failover, MCP, plugins, and session persistence",
    add_completion=False,
    no_args_is_help=False,
)
console = Console()


def print_banner():
    """Print the OrbitCode banner."""
    banner = """
╔══════════════════════════════════════════════════════════════╗
║  ██████╗ ███████╗██████╗ ██████╗ ███████╗███████╗██╗  ██╗     ║
║  ██╔══██╗██╔════╝██╔══██╗██╔══██╗██╔════╝██╔════╝██║  ██║     ║
║  ██████╔╝█████╗  ██████╔╝██████╔╝█████╗  ███████╗███████║     ║
║  ██╔═══╝ ██╔══╝  ██╔══██╗██╔══██╗██╔══╝  ╚════██║██╔══██║     ║
║  ██║     ███████╗██║  ██║██║  ██║███████╗███████║██║  ██║     ║
║  ╚═╝     ╚══════╝╚═╝  ╚═╝╚═╝  ╚═╝╚══════╝╚══════╝╚═╝  ╚═╝     ║
║                                                              ║
║   AI Coding Agent  •  Model Failover  •  MCP  •  Plugins    ║
║   Made by OrbitOmen                                          ║
╚══════════════════════════════════════════════════════════════╝
"""
    console.print(banner, style="bold cyan")


@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    working_dir: Optional[Path] = typer.Option(None, "--dir", "-d", help="Working directory (default: current)"),
    resume: bool = typer.Option(False, "--resume", "-r", help="Resume latest session"),
    model: Optional[str] = typer.Option(None, "--model", "-m", help="Preferred model to use first"),
    mcp: bool = typer.Option(False, "--mcp", help="Run as MCP server"),
    version: bool = typer.Option(False, "--version", "-v", help="Show version"),
    setup: bool = typer.Option(False, "--setup", help="Run setup wizard"),
):
    """OrbitCode - AI Coding Agent"""
    # Handle version before wizard (doesn't need config)
    if version:
        # Load minimal settings for version
        from orbitcode.config import Settings
        s = Settings()
        console.print(f"OrbitCode v{s.app_version}")
        raise typer.Exit()

    # Run wizard if first run or explicitly requested
    if setup or is_first_run():
        settings = load_or_wizard()
    else:
        settings = reload_settings()

    if mcp:
        # Run MCP server
        asyncio.run(run_mcp_server(working_dir or Path.cwd()))
        raise typer.Exit()

    # Only run interactive if no subcommand was invoked
    if ctx.invoked_subcommand is None:
        asyncio.run(run_interactive(working_dir or Path.cwd(), resume, model))


async def run_mcp_server(working_dir: Path):
    """Run the MCP server."""
    server = create_mcp_server(working_dir)
    async with server.lifespan():
        await server.run_stdio()


async def run_interactive(working_dir: Path, resume: bool, preferred_model: Optional[str]):
    """Run the interactive agent loop."""
    print_banner()

    console.print(f"[dim]Working directory: {working_dir}[/dim]")
    if resume:
        console.print("[dim]Resuming latest session...[/dim]")

    # Initialize components
    settings = reload_settings()
    model_router = ModelRouter(settings)
    session_manager = SessionManager(settings)
    tool_registry = get_registry()
    plugin_manager = PluginManager(settings)

    # Register plugin tools
    plugin_manager.register_all(tool_registry)
    await plugin_manager.initialize_all()

    # Create agent
    agent = await create_agent(
        working_dir=working_dir,
        session_manager=session_manager,
        model_router=model_router,
        tool_registry=tool_registry,
        settings=settings,
        resume=resume,
        plugin_manager=plugin_manager,
    )

    console.print(Panel.fit(
        "[bold green]OrbitCode ready![/bold green]\n"
        "Type your request or use commands:\n"
        "  /help     - Show help\n"
        "  /sessions - List sessions\n"
        "  /plugins  - List plugins\n"
        "  /models   - Show model chain\n"
        "  /clear    - Clear screen\n"
        "  /exit     - Exit",
        title="Commands",
        border_style="cyan",
    ))

    try:
        while True:
            try:
                user_input = Prompt.ask("\n[bold cyan]orbitcode>[/bold cyan]").strip()
            except (EOFError, KeyboardInterrupt):
                console.print("\n[yellow]Goodbye![/yellow]")
                break

            if not user_input:
                continue

            # Handle commands
            if user_input.startswith("/"):
                await handle_command(user_input, agent, session_manager, plugin_manager, model_router, settings)
                continue

            # Run agent
            console.print()  # spacing
            async for chunk in agent.run_stream(user_input):
                console.print(chunk, end="", highlight=False)
            console.print()  # newline after response

    finally:
        # Cleanup
        await plugin_manager.shutdown_all()
        await model_router.close()
        await tool_registry.close_all()


async def handle_command(cmd: str, agent: Agent, session_manager: SessionManager,
                         plugin_manager: PluginManager, model_router: ModelRouter, settings):
    """Handle slash commands."""
    parts = cmd.split()
    command = parts[0].lower()

    if command in ("/help", "/?"):
        console.print(Panel(
            "Available commands:\n"
            "  /help, /?       - Show this help\n"
            "  /sessions       - List recent sessions\n"
            "  /session <id>   - Switch to session\n"
            "  /new            - Start new session\n"
            "  /plugins        - List loaded plugins\n"
            "  /models         - Show model failover chain\n"
            "  /model <name>   - Set preferred model\n"
            "  /clear          - Clear screen\n"
            "  /exit, /quit    - Exit OrbitCode",
            title="Help",
            border_style="cyan",
        ))

    elif command == "/sessions":
        sessions = session_manager.list_sessions(agent.ctx.working_dir)
        if not sessions:
            console.print("[dim]No sessions found[/dim]")
        else:
            for s in sessions:
                current = "← current" if s.id == agent.ctx.session.id else ""
                console.print(f"  [cyan]{s.id[:8]}[/cyan]  {len(s.messages)} msgs  {s.updated_at.strftime('%Y-%m-%d %H:%M')}  {current}")

    elif command == "/session" and len(parts) > 1:
        session = session_manager.get_session(parts[1])
        if session:
            session_manager.set_current(session)
            agent.ctx.session = session
            console.print(f"[green]Switched to session {parts[1]}[/green]")
        else:
            console.print(f"[red]Session not found: {parts[1]}[/red]")

    elif command == "/new":
        session = session_manager.create_session(agent.ctx.working_dir)
        session_manager.set_current(session)
        agent.ctx.session = session
        console.print("[green]New session created[/green]")

    elif command == "/plugins":
        plugins = plugin_manager.list_plugins()
        if not plugins:
            console.print("[dim]No plugins loaded[/dim]")
        else:
            for p in plugins:
                tools = ", ".join(p["tools"]) if p["tools"] else "none"
                console.print(f"  [cyan]{p['name']}[/cyan] v{p['version']} - {p['description']}  [dim](tools: {tools})[/dim]")

    elif command == "/models":
        console.print("Model failover chain (free first, then paid):")
        for i, m in enumerate(settings.get_model_chain()):
            badge = "[green]FREE[/green]" if m.is_free else "[yellow]PAID[/yellow]"
            console.print(f"  {i+1}. {m.name} {badge}")

    elif command == "/model" and len(parts) > 1:
        model_name = parts[1]
        # Validate model exists
        found = any(m.name == model_name for m in settings.models)
        if found:
            # Store preference (could be added to session)
            console.print(f"[green]Preferred model set to: {model_name}[/green]")
        else:
            console.print(f"[red]Unknown model: {model_name}[/red]")

    elif command in ("/clear", "/cls"):
        console.clear()
        print_banner()

    elif command in ("/exit", "/quit"):
        console.print("[yellow]Goodbye![/yellow]")
        raise typer.Exit()

    else:
        console.print(f"[red]Unknown command: {command}[/red]")


@app.command()
def mcp(
    working_dir: Optional[Path] = typer.Argument(None, help="Working directory"),
):
    """Run as MCP server."""
    asyncio.run(run_mcp_server(working_dir or Path.cwd()))


@app.command()
def customise():
    """Customise OrbitCode settings (interactive)."""
    run_customise()


@app.command()
def tui(
    working_dir: Optional[Path] = typer.Option(None, "--dir", "-d", help="Working directory"),
):
    """Launch TUI dashboard."""
    import anyio
    from orbitcode.config import get_settings

    async def _run():
        settings = reload_settings()
        model_router = ModelRouter(settings)
        session_manager = SessionManager(settings)
        tool_registry = get_registry()
        plugin_manager = PluginManager(settings)

        agent = await create_agent(
            working_dir=working_dir or Path.cwd(),
            session_manager=session_manager,
            model_router=model_router,
            tool_registry=tool_registry,
            settings=settings,
            plugin_manager=plugin_manager,
        )
        # TUI runs in its own event loop
        from orbitcode.core.tui import run_tui
        await run_tui(working_dir or Path.cwd(), agent)

    anyio.run(_run)


@app.command()
def plan(
    goal: str = typer.Argument(..., help="Goal to plan"),
    working_dir: Optional[Path] = typer.Option(None, "--dir", "-d", help="Working directory"),
    execute: bool = typer.Option(False, "--execute", "-e", help="Execute plan after creating"),
):
    """Create and optionally execute a plan for a goal."""
    import anyio
    from orbitcode.config import get_settings

    async def _run():
        settings = reload_settings()
        model_router = ModelRouter(settings)
        tool_registry = get_registry()

        planner = Planner(model_router, tool_registry, working_dir or Path.cwd(), settings)
        plan = await planner.create_plan(goal)
        console.print(planner.format_plan(plan))

        if execute or Confirm.ask("Execute this plan?"):
            await planner.execute_plan(plan)

    anyio.run(_run)


@app.command()
def index(
    working_dir: Optional[Path] = typer.Option(None, "--dir", "-d", help="Working directory"),
    force: bool = typer.Option(False, "--force", "-f", help="Force re-index"),
    query: Optional[str] = typer.Option(None, "--query", "-q", help="Search query"),
):
    """Index codebase or search indexed code."""
    from orbitcode.config import get_settings
    settings = reload_settings()

    indexer = CodeIndexer(working_dir or Path.cwd(), settings)

    if query:
        results = indexer.search(query)
        if results:
            for r in results:
                console.print(f"[cyan]{r['file_path']}:{r['start_line']}-{r['end_line']}[/cyan]")
                console.print(f"  {r['content'][:200]}...")
                console.print()
        else:
            console.print("[dim]No results[/dim]")
    else:
        stats = indexer.index_project(force=force)
        console.print(f"[green]Indexed: {stats['indexed']} files, {stats['chunks']} chunks[/green]")
        if stats['skipped']:
            console.print(f"[dim]Skipped: {stats['skipped']} unchanged files[/dim]")
        if stats['errors']:
            console.print(f"[red]Errors: {stats['errors']}[/red]")


@app.command()
def git(
    command: str = typer.Argument(..., help="Git command: status, diff, log, commit, push"),
    working_dir: Optional[Path] = typer.Option(None, "--dir", "-d", help="Working directory"),
    message: Optional[str] = typer.Option(None, "--message", "-m", help="Commit message"),
    file: Optional[str] = typer.Option(None, "--file", "-f", help="File for diff"),
):
    """Git operations."""
    git = GitIntegration(working_dir or Path.cwd())

    if not git.is_repo():
        console.print("[red]Not a git repository[/red]")
        return

    if command == "status":
        status = git.get_status()
        console.print(f"Branch: [bold]{status.branch}[/bold]")
        console.print(f"Dirty: {'Yes' if status.dirty else 'No'}")
        if status.staged_files:
            console.print(f"Staged: {', '.join(status.staged_files)}")
        if status.unstaged_files:
            console.print(f"Unstaged: {', '.join(status.unstaged_files)}")
        if status.untracked_files:
            console.print(f"Untracked: {', '.join(status.untracked_files)}")
        if status.ahead or status.behind:
            console.print(f"↑{status.ahead} ↓{status.behind}")

    elif command == "diff":
        diff = git.get_diff(staged=False, file=file)
        console.print(diff or "[dim]No changes[/dim]")

    elif command == "log":
        commits = git.get_log(limit=20)
        for c in commits:
            console.print(f"[cyan]{c.short_hash}[/cyan] {c.message} ({c.author}, {c.date.strftime('%Y-%m-%d')})")

    elif command == "commit":
        if not message:
            console.print("[red]Commit message required (-m)[/red]")
            return
        hash = git.commit(message)
        if hash:
            console.print(f"[green]Committed: {hash[:8]}[/green]")
        else:
            console.print("[red]Commit failed[/red]")

    elif command == "push":
        if git.push():
            console.print("[green]Pushed[/green]")
        else:
            console.print("[red]Push failed[/red]")

    else:
        console.print(f"[red]Unknown git command: {command}[/red]")


@app.command()
def doctor():
    """Check OrbitCode installation and configuration."""
    settings = reload_settings()
    console.print(Panel.fit(
        f"[bold]OrbitCode Doctor[/bold]\n\n"
        f"Version: {settings.app_version}\n"
        f"Data dir: {settings.data_dir}\n"
        f"Sessions: {settings.session_dir}\n"
        f"Plugins: {settings.plugins_dir}\n"
        f"OpenRouter API Key: {'✓ Set' if settings.openrouter_api_key else '✗ Not set (using env)'}\n"
        f"Models configured: {len(settings.models)}\n"
        f"Tools registered: {len(get_registry().list_tools())}",
        title="Status",
        border_style="green" if settings.openrouter_api_key else "yellow",
    ))


@app.command()
def install_shell_completion(shell: str = typer.Option("bash", help="Shell type (bash, zsh, fish)")):
    """Install shell completion."""
    import subprocess
    result = subprocess.run(["orbitcode", "--install-completion"], capture_output=True, text=True)
    if result.returncode == 0:
        console.print(f"[green]Completion for {shell} installed[/green]")
    else:
        console.print(f"[red]Failed: {result.stderr}[/red]")


if __name__ == "__main__":
    app()