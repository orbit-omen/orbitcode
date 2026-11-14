"""OrbitCode TUI - Hybrid Adaptive Layout with Animated Mascot, Full Mouse Support, Hot-Reloadable Themes"""
try:
    from textual.app import App, ComposeResult
    from textual.containers import Container, Horizontal, Vertical, ScrollableContainer, Grid
    from textual.widgets import (
        Header, Footer, Static, Tree, Log, Input, Button, TabbedContent, TabPane,
        DataTable, Label, Select, Switch, RichLog, Markdown, Collapsible, Tabs
    )
    from textual.reactive import reactive, var
    from textual.binding import Binding
    from textual.message import Message
    from textual.events import Click, MouseDown, MouseUp, MouseMove
    from textual.geometry import Region
    from textual.screen import ModalScreen
    from textual.css.query import NoMatches
    TEXTUAL_AVAILABLE = True
except ImportError:
    TEXTUAL_AVAILABLE = False
    App = ComposeResult = Container = Horizontal = Vertical = ScrollableContainer = Grid = object
    Header = Footer = Static = Tree = Log = Input = Button = TabbedContent = TabPane = object
    DataTable = Label = Select = Switch = RichLog = Markdown = Collapsible = Tabs = object
    reactive = var = lambda x: x
    Binding = lambda *a, **k: None
    Message = Click = MouseDown = MouseUp = MouseMove = object
    Region = ModalScreen = NoMatches = object

from pathlib import Path
from typing import Optional, List, Dict, Any, Callable
from dataclasses import dataclass, field
from enum import Enum
import asyncio
import time

from orbitcode.config import get_settings, Settings, reload_settings
from orbitcode.core.mascot import OrbitMascot, MascotState, get_mascot_frames, ORBIT_MASCOT_FRAMES


class LayoutMode(Enum):
    STREAM = "stream"
    STUDIO = "studio"
    COMMAND = "command"


class PermissionMode(Enum):
    ASK = "ask"
    AUTO_EDIT = "auto_edit"
    PLAN = "plan"
    YOLO = "yolo"
    SMART = "smart"


@dataclass
class TUIState:
    working_dir: Path
    layout_mode: LayoutMode = LayoutMode.STUDIO
    theme_name: str = "orbit-nebula"
    icon_pack: str = "nerd"
    show_left_tree: bool = True
    show_right_inspector: bool = True
    mouse_enabled: bool = True
    animations: bool = True
    mascot_style: str = "full"
    mascot_custom_ascii: Optional[str] = None
    status_bar_widgets: List[str] = field(default_factory=lambda: [
        "model", "mode", "context", "tokens_saved", "layout", "mascot"
    ])
    current_tab: int = 0
    tabs: List[Dict] = field(default_factory=list)


class OrbitCodeTUI(App):
    """Main TUI application for OrbitCode with hybrid layouts and mascot."""

    CSS_PATH = None  # Will be set dynamically based on theme

    BINDINGS = [
        Binding("ctrl+q", "quit", "Quit", show=True),
        Binding("ctrl+n", "new_session", "New Session"),
        Binding("ctrl+s", "save_session", "Save"),
        Binding("ctrl+p", "command_palette", "Command Palette"),
        Binding("ctrl+b", "toggle_tree", "Toggle Tree"),
        Binding("ctrl+i", "toggle_inspector", "Toggle Inspector"),
        Binding("ctrl+m", "cycle_mode", "Cycle Mode"),
        Binding("ctrl+r", "rewind", "Rewind"),
        Binding("ctrl+t", "new_tab", "New Tab"),
        Binding("ctrl+tab", "next_tab", "Next Tab"),
        Binding("ctrl+shift+tab", "prev_tab", "Prev Tab"),
        Binding("ctrl+f", "focus_input", "Focus Input"),
        Binding("ctrl+u", "toggle_mascot", "Toggle Mascot"),
        Binding("ctrl+l", "cycle_layout", "Cycle Layout"),
        Binding("ctrl+h", "cycle_theme", "Cycle Theme"),
        Binding("f1", "help", "Help"),
    ]

    # Reactive state
    layout_mode = reactive(LayoutMode.STUDIO)
    theme_name = reactive("orbit-nebula")
    current_mode = reactive(PermissionMode.SMART)
    mascot_state = reactive(MascotState.IDLE)
    tokens_saved = reactive(0)
    context_usage = reactive(0.0)
    active_model = reactive("auto")

    def __init__(
        self,
        working_dir: Path,
        agent=None,
        settings: Optional[Settings] = None,
        **kwargs
    ):
        super().__init__(**kwargs)
        self.state = TUIState(working_dir=working_dir)
        self.agent = agent
        self.settings = settings or get_settings()
        self._chat_log = None
        self._file_tree = None
        self._input = None
        self._mascot = None
        self._status_bar = None
        self._tab_bar = None
        self._right_inspector = None
        self._left_tree = None
        self._splitter_h = None
        self._splitter_v = None
        self._command_palette_open = False
        self._layout_cycle = [LayoutMode.STREAM, LayoutMode.STUDIO, LayoutMode.COMMAND]
        self._theme_cycle = ["orbit-nebula", "orbit-midnight", "orbit-solar", "orbit-ghost"]
        self._mode_cycle = [PermissionMode.ASK, PermissionMode.AUTO_EDIT, PermissionMode.PLAN, PermissionMode.YOLO, PermissionMode.SMART]

        # Apply settings to state
        self._apply_settings()

    def _apply_settings(self):
        """Apply settings to TUI state."""
        self.state.layout_mode = LayoutMode(self.settings.layout)
        self.state.theme_name = self.settings.theme
        self.state.icon_pack = self.settings.icon_pack
        self.state.show_left_tree = self.settings.show_left_tree
        self.state.show_right_inspector = self.settings.show_right_inspector
        self.state.mouse_enabled = self.settings.mouse_enabled
        self.state.animations = self.settings.animations
        self.state.mascot_style = self.settings.mascot_style
        self.state.mascot_custom_ascii = self.settings.mascot_custom_ascii
        self.state.status_bar_widgets = self.settings.status_bar_widgets
        self.layout_mode = self.state.layout_mode
        self.theme_name = self.state.theme_name
        self.current_mode = PermissionMode(self.settings.permission_mode)

    def compose(self) -> ComposeResult:
        """Compose the UI based on current layout mode."""
        yield Header(show_clock=True, name="OrbitCode • by OrbitOmen")

        # Main layout container
        with Container(id="main-container"):
            # Session tabs at top
            yield SessionTabs(id="session-tabs")

            # Layout depends on mode
            if self.layout_mode == LayoutMode.STREAM:
                yield from self._compose_stream_layout()
            elif self.layout_mode == LayoutMode.STUDIO:
                yield from self._compose_studio_layout()
            elif self.layout_mode == LayoutMode.COMMAND:
                yield from self._compose_command_layout()

        yield Footer()

    def _compose_stream_layout(self) -> ComposeResult:
        """Claude Code style single-column stream layout."""
        with Vertical(id="stream-layout"):
            # Mascot banner
            with Container(id="mascot-banner"):
                self._mascot = OrbitMascot(
                    style_variant=self.state.mascot_style,
                    custom_frames=self._parse_custom_frames() if self.state.mascot_custom_ascii else None,
                    enabled=self.settings.mascot_enabled,
                    id="mascot-widget"
                )
                yield self._mascot

            # Chat area
            yield RichLog(id="chat", highlight=True, markup=True, wrap=True)

            # Input area
            with Container(id="input-area"):
                yield Input(
                    placeholder="Type your message... (Enter to send, Shift+Enter for newline)",
                    id="input"
                )

    def _compose_studio_layout(self) -> ComposeResult:
        """3-pane IDE layout: Left Tree + Center Chat + Right Inspector."""
        with Horizontal(id="studio-layout"):
            # Left sidebar - File Tree + Git
            if self.state.show_left_tree:
                with Vertical(id="left-sidebar", classes="sidebar"):
                    yield Static("📁 Files", classes="panel-title", id="tree-title")
                    self._file_tree = Tree(str(self.state.working_dir.name), id="file-tree")
                    self._file_tree.show_root = True
                    self._file_tree.root.expand()
                    yield self._file_tree

                    yield Static("🔧 Git", classes="panel-title", id="git-title")
                    yield Static("", id="git-panel")

            # Center - Chat
            with Vertical(id="center-pane", classes="main-pane"):
                # Mascot in header
                with Container(id="center-header"):
                    self._mascot = OrbitMascot(
                        style_variant=self.state.mascot_style,
                        custom_frames=self._parse_custom_frames() if self.state.mascot_custom_ascii else None,
                        enabled=self.settings.mascot_enabled,
                        id="mascot-widget"
                    )
                    yield self._mascot

                yield RichLog(id="chat", highlight=True, markup=True, wrap=True)

                # Input area
                with Container(id="input-area"):
                    yield Input(
                        placeholder="Type your message... (Enter to send, Shift+Enter for newline)",
                        id="input"
                    )

            # Right sidebar - Inspector tabs
            if self.state.show_right_inspector:
                with Vertical(id="right-sidebar", classes="sidebar inspector"):
                    yield InspectorTabs(id="inspector-tabs")
                    self._right_inspector = TabbedContent(id="inspector-content")
                    yield self._right_inspector

    def _compose_command_layout(self) -> ComposeResult:
        """OpenCode-style multi-tab with floating tool cards and telemetry sidebar."""
        with Horizontal(id="command-layout"):
            # Left - minimal file tree
            if self.state.show_left_tree:
                with Vertical(id="left-sidebar", classes="sidebar compact"):
                    yield Static("📁 Files", classes="panel-title")
                    self._file_tree = Tree(str(self.state.working_dir.name), id="file-tree")
                    self._file_tree.show_root = True
                    yield self._file_tree

            # Center - Tabbed chat sessions with floating tool cards
            with Vertical(id="center-pane", classes="main-pane"):
                # Tab bar for multiple sessions
                yield SessionTabs(id="session-tabs")

                # Chat area
                yield RichLog(id="chat", highlight=True, markup=True, wrap=True)

                # Floating tool cards container
                yield ScrollableContainer(id="tool-cards", classes="floating-cards")

                # Input area
                with Container(id="input-area"):
                    yield Input(
                        placeholder="Type your message... (Enter to send, Shift+Enter for newline)",
                        id="input"
                    )

            # Right - Orbital Telemetry sidebar
            if self.state.show_right_inspector:
                with Vertical(id="telemetry-sidebar", classes="sidebar telemetry"):
                    yield Static("🛰️ Telemetry", classes="panel-title")
                    yield TelemetryPanel(id="telemetry-panel")

    def _parse_custom_frames(self) -> Optional[dict]:
        """Parse custom ASCII frames from config string."""
        if not self.state.mascot_custom_ascii:
            return None
        try:
            import json
            return json.loads(self.state.mascot_custom_ascii)
        except Exception:
            return None

    def on_mount(self) -> None:
        """Initialize UI on mount."""
        self._chat_log = self.query_one("#chat", RichLog)
        self._input = self.query_one("#input", Input)
        self._load_file_tree()
        self._update_git_status()
        self._load_theme()
        self._input.focus()

        # Add welcome message
        self._add_welcome_message()

        # Start status update timer
        self.set_interval(1.0, self._update_status_bar)

        # Start mascot idle monitor
        if self._mascot:
            self.set_interval(5.0, self._check_mascot_idle)

    def _load_theme(self):
        """Load and apply theme."""
        theme_path = Path.home() / ".orbitcode" / "themes" / f"{self.theme_name}.tcss"
        if not theme_path.exists():
            # Try built-in themes
            theme_path = Path(__file__).parent.parent / "themes" / f"{self.theme_name}.tcss"

        if theme_path.exists():
            self.CSS_PATH = theme_path
            self.refresh_css()

    def _load_file_tree(self):
        """Load project files into tree."""
        if not self._file_tree:
            return

        self._file_tree.root.expand()
        self._add_tree_nodes(self._file_tree.root, self.state.working_dir)

    def _add_tree_nodes(self, node, path: Path, max_depth: int = 3, current_depth: int = 0):
        """Recursively add tree nodes."""
        if current_depth >= max_depth:
            return

        try:
            items = sorted(path.iterdir(), key=lambda p: (p.is_file(), p.name.lower()))
            for item in items:
                if item.name.startswith(".") and item.name not in {".gitignore", ".env.example", ".orbitcode"}:
                    continue
                if item.name in {"__pycache__", "node_modules", ".git", "venv", ".venv", "dist", "build"}:
                    continue

                icon = self._get_file_icon(item)
                label = f"{icon} {item.name}"
                child = node.add(label, data={"path": item, "is_file": item.is_file()})
                if item.is_dir():
                    child.expand()
                    self._add_tree_nodes(child, item, max_depth, current_depth + 1)
        except PermissionError:
            pass

    def _get_file_icon(self, path: Path) -> str:
        """Get file icon based on icon pack."""
        icons = {
            "nerd": {"file": "󰈙", "dir": "󰉋", "py": "󰌠", "js": "󰌞", "ts": "󰛦", "md": "󰍔", "json": "󰘦", "toml": "󰘦", "yaml": "󰘦"},
            "unicode": {"file": "📄", "dir": "📁", "py": "🐍", "js": "📜", "ts": "📘", "md": "📝", "json": "📋", "toml": "📋", "yaml": "📋"},
            "ascii": {"file": "[F]", "dir": "[D]", "py": "[P]", "js": "[J]", "ts": "[T]", "md": "[M]", "json": "[J]", "toml": "[T]", "yaml": "[Y]"},
        }
        pack = icons.get(self.state.icon_pack, icons["unicode"])

        if path.is_dir():
            return pack["dir"]

        suffix = path.suffix.lower()
        return {
            ".py": pack["py"], ".js": pack["js"], ".ts": pack["ts"], ".tsx": pack["ts"],
            ".jsx": pack["js"], ".md": pack["md"], ".json": pack["json"],
            ".toml": pack["toml"], ".yaml": pack["yaml"], ".yml": pack["yaml"],
            ".rs": "🦀", ".go": "🐹", ".java": "☕", ".cpp": "⚙️", ".c": "⚙️",
            ".html": "🌐", ".css": "🎨", ".scss": "🎨", ".svg": "🎨",
            ".sh": "🔧", ".bash": "🔧", ".zsh": "🔧", ".fish": "🔧",
            ".dockerfile": "🐳", ".gitignore": "🚫", ".env": "🔐",
        }.get(suffix, pack["file"])

    def _update_git_status(self):
        """Update git status panel."""
        try:
            from orbitcode.core.git import GitIntegration
            git = GitIntegration(self.state.working_dir)
            if git.is_repo():
                status = git.get_status()
                text = f"Branch: [bold]{status.branch}[/bold]\n"
                if status.dirty:
                    text += "[yellow]● Dirty[/yellow]\n"
                if status.staged_files:
                    text += f"[green]Staged:[/green] {len(status.staged_files)}\n"
                if status.unstaged_files:
                    text += f"[red]Unstaged:[/red] {len(status.unstaged_files)}\n"
                if status.untracked_files:
                    text += f"[blue]Untracked:[/blue] {len(status.untracked_files)}\n"
                if status.ahead or status.behind:
                    text += f"↑{status.ahead} ↓{status.behind}"
            else:
                text = "[dim]Not a git repository[/dim]"
        except Exception as e:
            text = f"[red]Git error: {e}[/red]"

        try:
            self.query_one("#git-panel", Static).update(text)
        except NoMatches:
            pass

    def _add_welcome_message(self):
        """Add welcome message to chat."""
        if not self._chat_log:
            return

        self._chat_log.write(f"[bold #a855f7]OrbitCode[/] [bold #f472b6]v{self.settings.app_version}[/]")
        self._chat_log.write(f"[dim]by OrbitOmen[/dim]")
        self._chat_log.write(f"[dim]Working directory: {self.state.working_dir}[/dim]")
        self._chat_log.write(f"[dim]Layout: {self.layout_mode.value} | Mode: {self.current_mode.value} | Theme: {self.theme_name}[/dim]")
        self._chat_log.write("")
        self._chat_log.write("[dim]Type your request or use /help for commands[/dim]")
        self._chat_log.write("")

    def _update_status_bar(self):
        """Update status bar widgets."""
        if not self._status_bar:
            return

        widgets = []
        for widget_name in self.state.status_bar_widgets:
            if widget_name == "model":
                widgets.append(f"[Model: {self.active_model}]")
            elif widget_name == "mode":
                widgets.append(f"[Mode: {self.current_mode.value}]")
            elif widget_name == "context":
                widgets.append(f"[Context: {self.context_usage:.0%}]")
            elif widget_name == "tokens_saved":
                widgets.append(f"[Saved: {self.tokens_saved:,} tok]")
            elif widget_name == "layout":
                widgets.append(f"[Layout: {self.layout_mode.value}]")
            elif widget_name == "mascot":
                widgets.append(f"[Mascot: {self.mascot_state.value}]")

        # Update footer or status area
        # Footer is handled by Textual automatically

    def _check_mascot_idle(self):
        """Check if mascot should sleep."""
        if self._mascot and self.mascot_state == MascotState.IDLE:
            # Could implement sleep logic here
            pass

    # ==================== EVENT HANDLERS ====================

    async def on_input_submitted(self, event: Input.Submitted) -> None:
        """Handle user input submission."""
        message = event.value.strip()
        if not message:
            return

        event.input.value = ""
        self._chat_log.write(f"[bold #22d3ee]You:[/bold #22d3ee] {message}")

        if self.agent:
            self.mascot_state = MascotState.THINKING
            if self._mascot:
                self._mascot.thinking()

            try:
                async for chunk in self.agent.run_stream(message):
                    if isinstance(chunk, str):
                        self._chat_log.write(chunk, scroll_end=True)
                    elif isinstance(chunk, dict) and chunk.get("type") == "tool_call":
                        tool_name = chunk.get("tool", "")
                        result = chunk.get("result", "")
                        self._chat_log.write(f"\n[bold #f59e0b]Tool:[/bold #f59e0b] {tool_name}")
                        self._chat_log.write(f"[dim]{result[:500]}[/dim]\n")

                        # Update mascot for tool running
                        if self._mascot:
                            self._mascot.tool_running()

            except Exception as e:
                self._chat_log.write(f"[red]Error: {e}[/red]")
                if self._mascot:
                    self._mascot.error()
        else:
            self._chat_log.write("[yellow]Agent not connected. Running in UI-only mode.[/yellow]")

        # Reset mascot to happy/idle
        if self._mascot:
            self._mascot.happy()
        self.mascot_state = MascotState.HAPPY

        # Record activity for mascot
        if self._mascot:
            self._mascot.record_activity()

    def on_tree_node_selected(self, event: Tree.NodeSelected) -> None:
        """Handle file selection in tree - pin to context."""
        data = event.node.data
        if data and data.get("is_file"):
            path = data["path"]
            try:
                content = path.read_text(encoding="utf-8", errors="replace")
                rel_path = path.relative_to(self.state.working_dir)
                self._chat_log.write(f"[bold]File:[/bold] {rel_path}")
                self._chat_log.write(f"```\n{content[:3000]}\n```")

                # Pin to context (visual indicator)
                event.node.set_label(f"📌 {event.node.label}")
            except Exception as e:
                self._chat_log.write(f"[red]Error reading file: {e}[/red]")

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses (approval cards, etc.)."""
        button_id = event.button.id
        if button_id and button_id.startswith("approve-"):
            # Handle approval buttons
            action = button_id.split("-")[1]
            # Process approval
            pass

    def on_click(self, event: Click) -> None:
        """Handle click events for mouse interactions."""
        if not self.state.mouse_enabled:
            return

        # Clickable file/line chips in chat
        # Clickable status bar pills
        # Clickable tabs
        pass

    # ==================== ACTIONS ====================

    def action_quit(self) -> None:
        """Quit the application."""
        self.exit()

    def action_new_session(self) -> None:
        """Start a new session."""
        self._chat_log.clear()
        self._add_welcome_message()
        if self.agent:
            self.agent.ctx.session = self.agent.ctx.session_manager.create_session(self.state.working_dir)

    def action_save_session(self) -> None:
        """Save current session."""
        if self.agent:
            self.agent.ctx.session_manager.save_session(self.agent.ctx.session)
        self._chat_log.write("[green]Session saved[/green]")

    def action_command_palette(self) -> None:
        """Show command palette."""
        self._show_command_palette()

    def _show_command_palette(self):
        """Show fuzzy-searchable command palette."""
        # Create modal with command palette
        commands = [
            ("/help", "Show help"),
            ("/plan", "Create a plan"),
            ("/git", "Git operations"),
            ("/index", "Index codebase"),
            ("/models", "Show model chain"),
            ("/theme", "Change theme"),
            ("/layout", "Change layout"),
            ("/customise", "Customise settings"),
            ("/rewind", "Rewind session"),
            ("/race", "Race models"),
            ("/snip", "Use snippet"),
            ("/btw", "Random tech fact"),
            ("/dance", "Dancing bot"),
            ("/anime", "Anime girl"),
            ("/matrix", "Matrix rain"),
            ("/snake", "Play snake"),
            # Ponytail plugin commands
            ("/sass", "Get sassy comment"),
            ("/fact", "Random tech fact"),
            ("/roast", "Roast yourself/code/git"),
            ("/encourage", "Get encouragement"),
            ("/animate", "Trigger mascot animation (dance, party, hacker, rainbow, cosmic)"),
            ("/party", "Party mode!"),
            ("/hacker", "Hacker mode!"),
            ("/rainbow", "Rainbow mascot!"),
            ("/cosmic", "Cosmic thinking mode!"),
            ("/exit", "Exit"),
        ]

        # Show in chat for now
        self._chat_log.write("[bold]Command Palette:[/bold]")
        for cmd, desc in commands:
            self._chat_log.write(f"  {cmd} - {desc}")

    def action_toggle_tree(self) -> None:
        """Toggle left file tree."""
        self.state.show_left_tree = not self.state.show_left_tree
        self.settings.show_left_tree = self.state.show_left_tree
        self._recompose_layout()

    def action_toggle_inspector(self) -> None:
        """Toggle right inspector."""
        self.state.show_right_inspector = not self.state.show_right_inspector
        self.settings.show_right_inspector = self.state.show_right_inspector
        self._recompose_layout()

    def action_cycle_mode(self) -> None:
        """Cycle permission mode."""
        current_idx = self._mode_cycle.index(self.current_mode)
        next_idx = (current_idx + 1) % len(self._mode_cycle)
        self.current_mode = self._mode_cycle[next_idx]
        self.settings.permission_mode = self.current_mode.value
        if self.agent:
            self.agent.set_mode(self.current_mode.value)
        self._chat_log.write(f"[green]Mode: {self.current_mode.value}[/green]")
        self.refresh()

    def action_rewind(self) -> None:
        """Show rewind tree."""
        self._chat_log.write("[yellow]Rewind feature - click to restore previous state[/yellow]")

    def action_new_tab(self) -> None:
        """Create new session tab."""
        # Add new tab
        pass

    def action_next_tab(self) -> None:
        """Switch to next tab."""
        pass

    def action_prev_tab(self) -> None:
        """Switch to previous tab."""
        pass

    def action_focus_input(self) -> None:
        """Focus input field."""
        self._input.focus()

    def action_toggle_mascot(self) -> None:
        """Toggle mascot visibility."""
        self.settings.mascot_enabled = not self.settings.mascot_enabled
        if self._mascot:
            self._mascot.enabled = self.settings.mascot_enabled
            self._mascot.refresh()

    def action_cycle_layout(self) -> None:
        """Cycle through layout modes."""
        current_idx = self._layout_cycle.index(self.layout_mode)
        next_idx = (current_idx + 1) % len(self._layout_cycle)
        self.layout_mode = self._layout_cycle[next_idx]
        self.settings.layout = self.layout_mode.value
        self._recompose_layout()
        self._chat_log.write(f"[green]Layout: {self.layout_mode.value}[/green]")

    def action_cycle_theme(self) -> None:
        """Cycle through themes."""
        current_idx = self._theme_cycle.index(self.theme_name) if self.theme_name in self._theme_cycle else 0
        next_idx = (current_idx + 1) % len(self._theme_cycle)
        self.theme_name = self._theme_cycle[next_idx]
        self.settings.theme = self.theme_name
        self._load_theme()
        self._chat_log.write(f"[green]Theme: {self.theme_name}[/green]")

    def action_help(self) -> None:
        """Show help."""
        self._show_command_palette()

    def _recompose_layout(self):
        """Recompose the layout (requires app restart in Textual)."""
        self._chat_log.write("[yellow]Layout change requires restart. Run: orbitcode tui[/yellow]")

    def on_unmount(self) -> None:
        """Cleanup on unmount."""
        if self.agent:
            self.agent.ctx.session_manager.save_current()


class SessionTabs(Static):
    """Session tabs widget for multi-tab support."""

    def compose(self) -> ComposeResult:
        yield Tabs(
            "Session 1",
            "Session 2",
            "+ New",
            id="session-tabs"
        )


class InspectorTabs(Static):
    """Right inspector tab buttons."""

    def compose(self) -> ComposeResult:
        with Horizontal(id="inspector-tab-bar"):
            yield Button("📁 Diff", id="tab-diff", classes="inspector-tab-btn")
            yield Button("👁 Preview", id="tab-preview", classes="inspector-tab-btn")
            yield Button("📝 Context", id="tab-context", classes="inspector-tab-btn")
            yield Button("🧠 Lessons", id="tab-lessons", classes="inspector-tab-btn")
            yield Button("🔍 Search", id="tab-search", classes="inspector-tab-btn")
            yield Button("📊 Telemetry", id="tab-telemetry", classes="inspector-tab-btn")


class TelemetryPanel(Static):
    """Telemetry panel for command layout."""

    def compose(self) -> ComposeResult:
        yield DataTable(id="telemetry-table")

    def on_mount(self) -> None:
        table = self.query_one("#telemetry-table", DataTable)
        table.add_columns("Metric", "Value")
        table.add_row("Tokens Saved", "0")
        table.add_row("Cache Hits", "0")
        table.add_row("Lessons Learned", "0")
        table.add_row("Model Switches", "0")
        table.add_row("Errors Recovered", "0")


class CommandPaletteScreen(ModalScreen):
    """Fuzzy-searchable command palette modal."""

    def __init__(self, commands: List[tuple], callback: Callable[[str], None]):
        super().__init__()
        self.commands = commands
        self.callback = callback

    def compose(self) -> ComposeResult:
        with Container(classes="command-palette"):
            yield Input(placeholder="Search commands...", id="palette-input")
            yield Static("", id="palette-results")

    def on_input_changed(self, event: Input.Changed) -> None:
        """Filter commands based on input."""
        query = event.value.lower()
        results = self.query_one("#palette-results", Static)

        matches = [
            (cmd, desc) for cmd, desc in self.commands
            if query in cmd.lower() or query in desc.lower()
        ]

        output = "\n".join([f"  {cmd} - {desc}" for cmd, desc in matches[:20]])
        results.update(output)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Execute selected command."""
        query = event.value.strip()
        if query:
            self.callback(query)
        self.app.pop_screen()


async def run_tui(working_dir: Path, agent=None, settings: Optional[Settings] = None):
    """Run the TUI application."""
    if not TEXTUAL_AVAILABLE:
        raise RuntimeError("Textual not installed. Run: pip install textual")

    app = OrbitCodeTUI(working_dir, agent, settings)
    await app.run_async()


def launch_tui(working_dir: Path, agent=None, settings: Optional[Settings] = None):
    """Launch TUI in a new event loop."""
    asyncio.run(run_tui(working_dir, agent, settings))