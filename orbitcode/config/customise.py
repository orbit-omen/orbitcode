"""Customisation command for OrbitCode - modify ALL settings except brand identity (app_name, maker)."""
import os
import json
from pathlib import Path
from typing import Optional, Any, Dict, List

import typer
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt, Confirm
from rich.table import Table
from rich.syntax import Syntax

from orbitcode.config import get_settings, Settings, ModelConfig, HarnessConfig, reload_settings, PROTECTED_BRAND_FIELDS

console = Console()

# All customizable fields organized by category
CUSTOMISABLE_CATEGORIES = {
    "ui": {
        "title": "🎨 UI / TUI Settings",
        "fields": {
            "layout": {"type": "choice", "choices": ["stream", "studio", "command"], "desc": "Layout mode"},
            "theme": {"type": "string", "desc": "Theme name (orbit-nebula, orbit-midnight, orbit-solar, orbit-ghost, or custom .tcss)"},
            "icon_pack": {"type": "choice", "choices": ["nerd", "unicode", "ascii"], "desc": "Icon pack"},
            "show_left_tree": {"type": "bool", "desc": "Show left file tree"},
            "show_right_inspector": {"type": "bool", "desc": "Show right inspector panel"},
            "mouse_enabled": {"type": "bool", "desc": "Enable mouse interactions"},
            "animations": {"type": "bool", "desc": "Enable animations"},
            "mascot_enabled": {"type": "bool", "desc": "Enable animated mascot"},
            "mascot_style": {"type": "choice", "choices": ["full", "compact", "minimal"], "desc": "Mascot style variant"},
            "mascot_custom_ascii": {"type": "string", "desc": "Custom mascot frames (JSON)"},
            "status_bar_widgets": {"type": "list", "desc": "Status bar widgets to show"},
        }
    },
    "keybindings": {
        "title": "⌨️  Keybindings",
        "fields": {
            "keybindings": {"type": "keybindings", "desc": "Custom keybindings (JSON)"},
        }
    },
    "aliases": {
        "title": "🔗 Aliases",
        "fields": {
            "aliases": {"type": "aliases", "desc": "Custom slash command aliases (JSON)"},
        }
    },
    "core": {
        "title": "⚙️  Core Settings",
        "fields": {
            "log_level": {"type": "choice", "choices": ["DEBUG", "INFO", "WARNING", "ERROR"], "desc": "Logging verbosity"},
            "default_shell": {"type": "string", "desc": "Default shell for bash tool"},
            "data_dir": {"type": "path", "desc": "Data directory"},
        }
    },
    "providers": {
        "title": "🔌 Provider API Keys (from .env)",
        "fields": {
            "openrouter_base_url": {"type": "string", "desc": "OpenRouter API base URL"},
            "openrouter_referer": {"type": "string", "desc": "HTTP Referer header for OpenRouter"},
            "openrouter_title": {"type": "string", "desc": "X-Title header for OpenRouter"},
        }
    },
    "models": {
        "title": "🤖 Models & Failover",
        "fields": {
            "models": {"type": "models", "desc": "Model failover chain"},
            "planner_model": {"type": "string", "desc": "Model for planning tasks"},
            "coder_model": {"type": "string", "desc": "Model for coding tasks"},
            "reviewer_model": {"type": "string", "desc": "Model for code review"},
            "search_summarizer_model": {"type": "string", "desc": "Model for search result summarization"},
            "compactor_model": {"type": "string", "desc": "Model for session compaction"},
            "model_routing_rules": {"type": "list", "desc": "Routing rules (e.g., 'use claude for refactoring')"},
            "max_turn_cost_usd": {"type": "float", "desc": "Max cost per turn (USD)"},
            "max_session_cost_usd": {"type": "float", "desc": "Max cost per session (USD)"},
        }
    },
    "tools": {
        "title": "🔧 Tools",
        "fields": {
            "max_file_size": {"type": "int", "desc": "Max file size for read tool (bytes)"},
            "allowed_commands": {"type": "list", "desc": "Allowed command prefixes"},
            "blocked_commands": {"type": "list", "desc": "Blocked command patterns"},
        }
    },
    "session": {
        "title": "💾 Session",
        "fields": {
            "session_dir": {"type": "path", "desc": "Session directory"},
            "max_session_history": {"type": "int", "desc": "Max sessions to keep per project"},
            "auto_save_interval": {"type": "int", "desc": "Auto-save interval (seconds)"},
        }
    },
    "mcp": {
        "title": "🔌 MCP",
        "fields": {
            "mcp_enabled": {"type": "bool", "desc": "Enable MCP server"},
            "mcp_servers": {"type": "dict", "desc": "MCP server configurations (JSON)"},
        }
    },
    "plugins": {
        "title": "🔌 Plugins",
        "fields": {
            "plugins_dir": {"type": "path", "desc": "Plugins directory"},
            "enabled_plugins": {"type": "list", "desc": "Enabled plugin names"},
        }
    },
    "browser": {
        "title": "🌐 Browser",
        "fields": {
            "browser_enabled": {"type": "bool", "desc": "Enable browser automation"},
            "browser_headless": {"type": "bool", "desc": "Run browser headless"},
            "browser_timeout": {"type": "float", "desc": "Browser timeout (seconds)"},
        }
    },
    "search": {
        "title": "🔍 Search",
        "fields": {
            "web_search_enabled": {"type": "bool", "desc": "Enable web search"},
            "web_search_provider": {"type": "choice", "choices": ["duckduckgo", "brave", "serpapi", "google"], "desc": "Web search provider"},
            "web_search_api_key": {"type": "password", "desc": "Web search API key"},
            "google_grounding_enabled": {"type": "bool", "desc": "Enable Google AI Search / Grounding"},
            "search_cache_ttl_hours": {"type": "int", "desc": "Search cache TTL (hours)"},
            "compress_with_small_model": {"type": "bool", "desc": "Compress search results with small model"},
            "search_summarizer_model": {"type": "string", "desc": "Model for search summarization"},
        }
    },
    "learning": {
        "title": "🧠 Learning Engine",
        "fields": {
            "learning_enabled": {"type": "bool", "desc": "Enable self-learning"},
            "auto_inject_lessons": {"type": "bool", "desc": "Auto-inject lessons into prompts"},
            "max_lessons_per_prompt": {"type": "int", "desc": "Max lessons per prompt"},
            "auto_playbook": {"type": "bool", "desc": "Auto-generate PLAYBOOK.md"},
            "negative_rules_strict": {"type": "bool", "desc": "Enforce negative rules strictly"},
        }
    },
    "safety": {
        "title": "🛡️ Safety & Permissions",
        "fields": {
            "permission_mode": {"type": "choice", "choices": ["ask", "auto_edit", "plan", "yolo", "smart"], "desc": "Permission mode"},
            "shadow_git_checkpoints": {"type": "bool", "desc": "Create shadow git checkpoints"},
            "redact_secrets": {"type": "bool", "desc": "Redact secrets before LLM calls"},
            "sandbox_destructive_commands": {"type": "bool", "desc": "Sandbox destructive commands"},
            "destructive_patterns": {"type": "list", "desc": "Destructive command patterns"},
            "smart_mode_triggers": {"type": "list", "desc": "Smart mode confirmation triggers"},
        }
    },
    "harnesses": {
        "title": "🤖 External AI Harnesses",
        "fields": {
            "harnesses": {"type": "harnesses", "desc": "External harness configurations (JSON)"},
        }
    },
    "ponytail": {
        "title": "🐴 Ponytail Plugin",
        "fields": {
            "ponytail_enabled": {"type": "bool", "desc": "Enable ponytail plugin"},
            "ponytail_sass_level": {"type": "choice", "choices": ["1", "2", "3", "4", "5"], "desc": "Sass level (1-5)"},
            "ponytail_animations": {"type": "bool", "desc": "Enable random animation triggers"},
            "ponytail_roast_mode": {"type": "bool", "desc": "Enable roast mode"},
        }
    },
}


def show_current_config():
    """Display current configuration organized by category."""
    settings = get_settings()

    for cat_key, cat in CUSTOMISABLE_CATEGORIES.items():
        table = Table(title=cat["title"], show_header=True, header_style="bold cyan")
        table.add_column("Setting", style="bold", width=35)
        table.add_column("Value", width=60)
        table.add_column("Description", width=50)

        for field_name, field_info in cat["fields"].items():
            if field_name in PROTECTED_BRAND_FIELDS:
                continue

            current = getattr(settings, field_name, None)
            display_val = format_value(field_name, current, field_info)

            table.add_row(field_name, display_val, field_info["desc"])

        console.print(table)
        console.print()

    # Show protected brand fields
    table = Table(title="🔒 Brand Identity (Protected)", show_header=True, header_style="bold red")
    table.add_column("Field", style="bold")
    table.add_column("Value")
    table.add_column("Status")
    table.add_row("app_name", settings.app_name, "IMMUTABLE")
    table.add_row("app_version", settings.app_version, "IMMUTABLE")
    table.add_row("maker", settings.maker, "IMMUTABLE")
    console.print(table)


def format_value(field_name: str, value: Any, field_info: Dict) -> str:
    """Format a value for display."""
    if value is None:
        return "[dim](not set)[/dim]"

    ftype = field_info.get("type", "string")

    if ftype == "bool":
        return "[green]✓[/green]" if value else "[red]✗[/red]"
    elif ftype == "list":
        if isinstance(value, list):
            return ", ".join(str(v) for v in value[:5]) + ("..." if len(value) > 5 else "")
        return str(value)
    elif ftype == "dict":
        return f"{{...}} ({len(value)} keys)" if isinstance(value, dict) else str(value)
    elif ftype == "path":
        return str(value)
    elif ftype == "models":
        return f"{len(value)} models" if isinstance(value, list) else str(value)
    elif ftype == "keybindings":
        return f"{len(value)} bindings" if isinstance(value, dict) else str(value)
    elif ftype == "aliases":
        return f"{len(value)} aliases" if isinstance(value, dict) else str(value)
    elif ftype == "harnesses":
        return f"{len(value)} harnesses" if isinstance(value, dict) else str(value)
    elif ftype == "password":
        return "[hidden]" if value else "[dim](not set)[/dim]"
    else:
        val_str = str(value)
        return val_str[:80] + "..." if len(val_str) > 80 else val_str


def edit_category(category: str):
    """Edit all settings in a category."""
    settings = get_settings()
    cat = CUSTOMISABLE_CATEGORIES.get(category)
    if not cat:
        console.print(f"[red]Unknown category: {category}[/red]")
        return

    console.print(f"\n[bold]{cat['title']}[/bold]")

    for field_name, field_info in cat["fields"].items():
        if field_name in PROTECTED_BRAND_FIELDS:
            continue

        current = getattr(settings, field_name, None)
        new_value = edit_field(field_name, current, field_info)

        if new_value != current:
            setattr(settings, field_name, new_value)
            console.print(f"  [green]✓ {field_name} updated[/green]")

    _save_settings(settings)


def edit_field(field_name: str, current_value: Any, field_info: Dict) -> Any:
    """Interactively edit a single field."""
    ftype = field_info.get("type", "string")
    desc = field_info.get("desc", "")

    console.print(f"\n[bold]Editing:[/bold] {field_name}")
    console.print(f"[dim]{desc}[/dim]")
    console.print(f"Current: [cyan]{format_value(field_name, current_value, field_info)}[/cyan]")

    if ftype == "bool":
        return Confirm.ask("New value", default=bool(current_value))

    elif ftype == "int":
        val = Prompt.ask("New value", default=str(current_value or 0))
        try:
            return int(val)
        except ValueError:
            console.print("[red]Invalid integer[/red]")
            return current_value

    elif ftype == "float":
        val = Prompt.ask("New value", default=str(current_value or 0.0))
        try:
            return float(val)
        except ValueError:
            console.print("[red]Invalid number[/red]")
            return current_value

    elif ftype == "choice":
        choices = field_info.get("choices", [])
        console.print(f"Choices: {', '.join(choices)}")
        val = Prompt.ask("New value", choices=choices, default=str(current_value or choices[0]))
        return val

    elif ftype == "list":
        val = Prompt.ask("New value (comma-separated)", default=", ".join(current_value) if current_value else "")
        return [v.strip() for v in val.split(",") if v.strip()]

    elif ftype == "path":
        val = Prompt.ask("New path", default=str(current_value))
        return Path(val).expanduser().resolve()

    elif ftype == "password":
        val = Prompt.ask("New value", password=True, default="")
        return val if val else current_value

    elif ftype == "models":
        return edit_models(current_value or [])

    elif ftype == "keybindings":
        return edit_keybindings(current_value or {})

    elif ftype == "aliases":
        return edit_aliases(current_value or {})

    elif ftype == "harnesses":
        return edit_harnesses(current_value or {})

    elif ftype == "dict":
        console.print("[dim]Enter JSON object[/dim]")
        val = Prompt.ask("New value", default=json.dumps(current_value, indent=2) if current_value else "{}")
        try:
            return json.loads(val)
        except json.JSONDecodeError:
            console.print("[red]Invalid JSON[/red]")
            return current_value

    else:
        val = Prompt.ask("New value", default=str(current_value or ""))
        return val


def edit_models(models: List[ModelConfig]) -> List[ModelConfig]:
    """Interactive model chain editor."""
    console.print("\n[bold]Model Chain Editor[/bold]")
    console.print("Current chain (free first, then paid):")

    models_list = list(models)

    while True:
        table = Table(show_header=True)
        table.add_column("#", width=3)
        table.add_column("Model", width=40)
        table.add_column("Provider", width=15)
        table.add_column("Free", width=6)
        table.add_column("Priority", width=8)

        for i, m in enumerate(models_list, 1):
            badge = "[green]✓[/green]" if m.is_free else "[yellow]✗[/yellow]"
            table.add_row(str(i), m.name, m.provider, badge, str(m.priority))

        console.print(table)
        console.print("\nOptions: [1] Add model  [2] Remove model  [3] Reorder  [4] Edit model  [5] Done")
        choice = Prompt.ask("Choose", choices=["1", "2", "3", "4", "5"], default="5")

        if choice == "1":  # Add
            name = Prompt.ask("Model name (e.g., anthropic/claude-3.5-sonnet)")
            if not name:
                continue
            provider = Prompt.ask("Provider", choices=["openrouter", "anthropic", "openai", "google", "groq", "deepseek", "xai", "ollama", "lmstudio", "custom"], default="openrouter")
            is_free = Confirm.ask("Is free?", default=False)
            priority = len(models_list)
            base_url = Prompt.ask("Base URL (empty for default)", default="")
            api_key_env = Prompt.ask("API key env var", default="OPENROUTER_API_KEY")

            models_list.append(ModelConfig(
                name=name,
                provider=provider,
                is_free=is_free,
                priority=priority,
                base_url=base_url or get_default_base_url(provider),
                api_key_env=api_key_env,
            ))
            console.print("[green]Model added[/green]")

        elif choice == "2":  # Remove
            if not models_list:
                console.print("[yellow]No models to remove[/yellow]")
                continue
            idx = Prompt.ask("Model number to remove", choices=[str(i) for i in range(1, len(models_list) + 1)])
            removed = models_list.pop(int(idx) - 1)
            console.print(f"[green]Removed:[/green] {removed.name}")

        elif choice == "3":  # Reorder
            if len(models_list) < 2:
                console.print("[yellow]Need at least 2 models to reorder[/yellow]")
                continue
            console.print("Enter new order as comma-separated numbers (e.g., 3,1,2)")
            order = Prompt.ask("New order", default=",".join(str(i) for i in range(1, len(models_list) + 1)))
            try:
                new_order = [int(x.strip()) - 1 for x in order.split(",")]
                if set(new_order) == set(range(len(models_list))):
                    models_list[:] = [models_list[i] for i in new_order]
                    for i, m in enumerate(models_list):
                        m.priority = i
                    console.print("[green]Reordered[/green]")
                else:
                    console.print("[red]Invalid order[/red]")
            except Exception:
                console.print("[red]Invalid format[/red]")

        elif choice == "4":  # Edit
            if not models_list:
                console.print("[yellow]No models to edit[/yellow]")
                continue
            idx = Prompt.ask("Model number to edit", choices=[str(i) for i in range(1, len(models_list) + 1)])
            m = models_list[int(idx) - 1]
            console.print(f"Editing: {m.name}")

            m.name = Prompt.ask("Name", default=m.name)
            m.provider = Prompt.ask("Provider", choices=["openrouter", "anthropic", "openai", "google", "groq", "deepseek", "xai", "ollama", "lmstudio", "custom"], default=m.provider)
            m.is_free = Confirm.ask("Free?", default=m.is_free)
            m.base_url = Prompt.ask("Base URL", default=m.base_url)
            m.api_key_env = Prompt.ask("API key env", default=m.api_key_env)
            m.max_tokens = int(Prompt.ask("Max tokens", default=str(m.max_tokens)))
            m.temperature = float(Prompt.ask("Temperature", default=str(m.temperature)))
            m.timeout = float(Prompt.ask("Timeout", default=str(m.timeout)))
            console.print("[green]Model updated[/green]")

        elif choice == "5":  # Done
            break

    return models_list


def get_default_base_url(provider: str) -> str:
    defaults = {
        "openrouter": "https://openrouter.ai/api/v1",
        "anthropic": "https://api.anthropic.com/v1",
        "openai": "https://api.openai.com/v1",
        "google": "https://generativelanguage.googleapis.com/v1beta",
        "groq": "https://api.groq.com/openai/v1",
        "deepseek": "https://api.deepseek.com/v1",
        "xai": "https://api.x.ai/v1",
        "ollama": "http://localhost:11434/v1",
        "lmstudio": "http://localhost:1234/v1",
    }
    return defaults.get(provider, "https://openrouter.ai/api/v1")


def edit_keybindings(bindings: Dict[str, str]) -> Dict[str, str]:
    """Edit keybindings."""
    console.print("\n[bold]Keybindings Editor[/bold]")
    console.print("Current bindings:")

    default_bindings = {
        "quit": "ctrl+q", "new_session": "ctrl+n", "save_session": "ctrl+s",
        "command_palette": "ctrl+p", "toggle_tree": "ctrl+b", "toggle_inspector": "ctrl+i",
        "cycle_mode": "ctrl+m", "rewind": "ctrl+r", "new_tab": "ctrl+t",
        "next_tab": "ctrl+tab", "prev_tab": "ctrl+shift+tab", "focus_input": "ctrl+f",
        "toggle_mascot": "ctrl+u", "layout_cycle": "ctrl+l", "theme_cycle": "ctrl+h",
    }

    # Merge with current
    all_bindings = {**default_bindings, **bindings}

    for action, key in sorted(all_bindings.items()):
        console.print(f"  {action}: [cyan]{key}[/cyan]")

    console.print("\nEnter bindings as JSON: {\"action\": \"key\"}")
    val = Prompt.ask("New bindings", default=json.dumps(bindings, indent=2))
    try:
        return json.loads(val)
    except json.JSONDecodeError:
        console.print("[red]Invalid JSON[/red]")
        return bindings


def edit_aliases(aliases: Dict[str, str]) -> Dict[str, str]:
    """Edit command aliases."""
    console.print("\n[bold]Aliases Editor[/bold]")
    console.print("Current aliases:")
    for alias, cmd in sorted(aliases.items()):
        console.print(f"  {alias} -> {cmd}")

    console.print("\nEnter aliases as JSON: {\"alias\": \"command\"}")
    val = Prompt.ask("New aliases", default=json.dumps(aliases, indent=2))
    try:
        return json.loads(val)
    except json.JSONDecodeError:
        console.print("[red]Invalid JSON[/red]")
        return aliases


def edit_harnesses(harnesses: Dict[str, Any]) -> Dict[str, Dict]:
    """Edit harness configurations."""
    console.print("\n[bold]Harness Configurations Editor[/bold]")
    console.print("Current harnesses:")

    # Convert HarnessConfig objects to dicts for display/editing
    current_dict = {}
    if isinstance(harnesses, dict):
        for name, config in sorted(harnesses.items()):
            if hasattr(config, 'command'):
                # It's a HarnessConfig object
                current_dict[name] = {
                    "command": config.command,
                    "args": config.args,
                    "env": config.env,
                    "input_format": config.input_format,
                    "output_parser": config.output_parser,
                    "enabled": config.enabled,
                    "working_dir": config.working_dir,
                    "prompt_template": config.prompt_template,
                    "context_template": config.context_template,
                    "version_flag": config.version_flag,
                    "use_stdin": config.use_stdin,
                    "timeout": config.timeout,
                    "custom_command": config.custom_command,
                }
            elif isinstance(config, dict):
                current_dict[name] = config
            console.print(f"  {name}: {current_dict[name].get('command', 'N/A')}")

    console.print("\nEnter harnesses as JSON")
    val = Prompt.ask("New harnesses", default=json.dumps(current_dict, indent=2))
    if not val.strip():
        return current_dict
    try:
        result = json.loads(val)
        if isinstance(result, dict):
            return result
        else:
            console.print("[red]Expected JSON object[/red]")
            return current_dict
    except json.JSONDecodeError:
        console.print("[red]Invalid JSON[/red]")
        return current_dict


def run_customise():
    """Run the interactive customisation menu."""
    console.print()
    console.print(Panel.fit(
        "[bold cyan]OrbitCode Customisation[/bold cyan]\n"
        "Modify ANY setting except app_name, app_version, and maker.\n"
        f"Brand identity: [bold #a855f7]OrbitCode[/] • by [bold #f472b6]OrbitOmen[/]",
        title="⚙️  Customise",
        border_style="cyan",
    ))

    settings = get_settings()

    # AI-assisted customization option
    console.print("\n[bold]Options:[/bold]")
    console.print("  [1] Browse & edit by category")
    console.print("  [2] Edit single setting")
    console.print("  [3] Edit model chain")
    console.print("  [4] Edit keybindings")
    console.print("  [5] Edit aliases")
    console.print("  [6] Edit harnesses")
    console.print("  [7] 🤖 AI-assisted customise (natural language)")
    console.print("  [8] View all settings")
    console.print("  [9] Reset to defaults")
    console.print("  [10] Export config")
    console.print("  [11] Import config")
    console.print("  [12] Exit")

    choice = Prompt.ask("Choose", choices=[str(i) for i in range(1, 13)], default="12")

    if choice == "1":
        # Browse by category
        categories = list(CUSTOMISABLE_CATEGORIES.keys())
        console.print("\nCategories:")
        for i, cat in enumerate(categories, 1):
            console.print(f"  {i}. {CUSTOMISABLE_CATEGORIES[cat]['title']}")

        idx = Prompt.ask("Category number", choices=[str(i) for i in range(1, len(categories) + 1)], default="")
        if idx:
            edit_category(categories[int(idx) - 1])

    elif choice == "2":
        # Edit single setting - flatten all fields
        all_fields = []
        for cat in CUSTOMISABLE_CATEGORIES.values():
            for fname, finfo in cat["fields"].items():
                if fname not in PROTECTED_BRAND_FIELDS:
                    all_fields.append((fname, finfo))

        console.print("\nAll editable settings:")
        for i, (fname, finfo) in enumerate(all_fields, 1):
            console.print(f"  {i}. {fname} - {finfo['desc']}")

        idx = Prompt.ask("Setting number", choices=[str(i) for i in range(1, len(all_fields) + 1)], default="")
        if idx:
            fname, finfo = all_fields[int(idx) - 1]
            current = getattr(settings, fname, None)
            new_value = edit_field(fname, current, finfo)
            if new_value != current:
                setattr(settings, fname, new_value)
                _save_settings(settings)
                console.print(f"[green]✓ {fname} updated[/green]")

    elif choice == "3":
        new_models = edit_models(settings.models.copy())
        if new_models != settings.models:
            settings.models = new_models
            _save_settings(settings)
            console.print("[green]✓ Model chain updated[/green]")

    elif choice == "4":
        new_bindings = edit_keybindings(settings.keybindings)
        if new_bindings != settings.keybindings:
            settings.keybindings = new_bindings
            _save_settings(settings)
            console.print("[green]✓ Keybindings updated[/green]")

    elif choice == "5":
        new_aliases = edit_aliases(settings.aliases)
        if new_aliases != settings.aliases:
            settings.aliases = new_aliases
            _save_settings(settings)
            console.print("[green]✓ Aliases updated[/green]")

    elif choice == "6":
        new_harnesses = edit_harnesses(settings.harnesses)
        if new_harnesses != settings.harnesses:
            settings.harnesses = new_harnesses
            _save_settings(settings)
            console.print("[green]✓ Harnesses updated[/green]")

    elif choice == "7":
        # AI-assisted customization
        ai_customise(settings)

    elif choice == "8":
        show_current_config()

    elif choice == "9":
        if Confirm.ask("[red]Reset ALL settings to defaults? This cannot be undone.[/red]", default=False):
            _reset_to_defaults()
            console.print("[green]✓ Reset to defaults[/green]")

    elif choice == "10":
        _export_config(settings)
        console.print("[green]✓ Config exported to orbitcode-config-backup.toml[/green]")

    elif choice == "11":
        path = Prompt.ask("Path to config file to import")
        _import_config(path)
        console.print("[green]✓ Config imported[/green]")

    elif choice == "12":
        console.print("[cyan]Goodbye![/cyan]")
        return


def ai_customise(settings: Settings):
    """AI-assisted natural language customization."""
    console.print(Panel(
        "[bold]AI-Assisted Customisation[/bold]\n"
        "Describe what you want in natural language.\n"
        "Examples:\n"
        "  • \"Make it faster and use cheaper models\"\n"
        "  • \"I want a dark theme with green accents\"\n"
        "  • \"Set up Claude Code and Codex as external harnesses\"\n"
        "  • \"Enable smart mode but ask for git pushes\"\n"
        "  • \"Add a custom mascot from my ASCII art\"\n"
        "  • \"Create aliases for common tasks\"",
        title="🤖 AI Customise",
        border_style="magenta",
    ))

    prompt = Prompt.ask("\nWhat would you like to change? (or 'cancel')")
    if prompt.lower() in ("cancel", "exit", "quit"):
        return

    # Parse natural language and apply changes
    changes = parse_natural_language_config(prompt, settings)

    if not changes:
        console.print("[yellow]Could not parse request. Try being more specific.[/yellow]")
        return

    console.print("\n[bold]Proposed changes:[/bold]")
    for field, value in changes.items():
        current = getattr(settings, field, None)
        console.print(f"  {field}: {format_value(field, current, {'type': 'string'})} → [green]{value}[/green]")

    if Confirm.ask("\nApply these changes?"):
        for field, value in changes.items():
            setattr(settings, field, value)
        _save_settings(settings)
        console.print("[green]✓ Changes applied![/green]")


def parse_natural_language_config(prompt: str, settings: Settings) -> Dict[str, Any]:
    """Parse natural language config request (simplified - would use LLM in production)."""
    prompt_lower = prompt.lower()
    changes = {}

    # Simple keyword matching - in production, use an LLM
    if "fast" in prompt_lower or "speed" in prompt_lower:
        changes["permission_mode"] = "auto_edit"
        changes["planner_model"] = "groq/llama-3.3-70b-versatile"
        changes["coder_model"] = "groq/llama-3.3-70b-versatile"

    if "cheap" in prompt_lower or "cost" in prompt_lower or "free" in prompt_lower:
        changes["permission_mode"] = "smart"
        # Ensure free models first
        free_models = [m for m in settings.models if m.is_free]
        if free_models:
            changes["models"] = free_models + [m for m in settings.models if not m.is_free]

    if "dark" in prompt_lower and "green" in prompt_lower:
        changes["theme"] = "orbit-midnight"  # Would need custom theme

    if "claude code" in prompt_lower:
        changes.setdefault("harnesses", {})["claude_code"] = {
            "command": "claude",
            "args": ["--model", "opus"],
            "enabled": True
        }

    if "codex" in prompt_lower:
        changes.setdefault("harnesses", {})["codex"] = {
            "command": "codex",
            "args": ["--model", "gpt-4o"],
            "enabled": True
        }

    if "smart mode" in prompt_lower:
        changes["permission_mode"] = "smart"
        if "git push" in prompt_lower:
            changes.setdefault("smart_mode_triggers", []).append("git_push")

    if "mascot" in prompt_lower and "custom" in prompt_lower:
        changes["mascot_custom_ascii"] = json.dumps({"idle": ["Custom mascot!"]})

    return changes


def _save_settings(settings: Settings):
    """Save settings to config.toml and .env."""
    import tomli_w

    config_dir = Path.home() / ".orbitcode"
    config_path = config_dir / "config.toml"

    # Build model list
    model_list = []
    for m in settings.models:
        model_list.append({
            "name": m.name,
            "provider": m.provider,
            "api_key_env": m.api_key_env,
            "base_url": m.base_url,
            "max_tokens": m.max_tokens,
            "temperature": m.temperature,
            "timeout": m.timeout,
            "max_retries": m.max_retries,
            "is_free": m.is_free,
            "priority": m.priority,
        })

    # Build harness list - handle both HarnessConfig objects and dicts
    harness_list = {}
    for name, h in settings.harnesses.items():
        # Support both HarnessConfig objects and plain dicts (from JSON editor)
        if hasattr(h, 'command'):
            # It's a HarnessConfig object
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
        elif isinstance(h, dict):
            # It's a dict from JSON editor - extract values with defaults
            harness_list[name] = {
                "command": h.get("command", ""),
                "args": h.get("args", []),
                "env": h.get("env", {}),
                "input_format": h.get("input_format", "text"),
                "output_parser": h.get("output_parser", "extract_code_blocks"),
                "enabled": h.get("enabled", True),
                "working_dir": h.get("working_dir"),
                "prompt_template": h.get("prompt_template"),
                "context_template": h.get("context_template"),
                "version_flag": h.get("version_flag", "--version"),
                "use_stdin": h.get("use_stdin", False),
                "timeout": h.get("timeout", 120.0),
                "custom_command": h.get("custom_command"),
            }

    config_data = {
        "app_name": "OrbitCode",  # Protected
        "app_version": settings.app_version,  # Protected
        "maker": "OrbitOmen",  # Protected
        "layout": settings.layout,
        "theme": settings.theme,
        "icon_pack": settings.icon_pack,
        "show_left_tree": settings.show_left_tree,
        "show_right_inspector": settings.show_right_inspector,
        "mouse_enabled": settings.mouse_enabled,
        "animations": settings.animations,
        "mascot_enabled": settings.mascot_enabled,
        "mascot_style": settings.mascot_style,
        "mascot_custom_ascii": settings.mascot_custom_ascii,
        "status_bar_widgets": settings.status_bar_widgets,
        "keybindings": settings.keybindings,
        "aliases": settings.aliases,
        "log_level": settings.log_level,
        "default_shell": settings.default_shell,
        "data_dir": str(settings.data_dir),
        "openrouter_base_url": settings.openrouter_base_url,
        "openrouter_referer": settings.openrouter_referer,
        "openrouter_title": settings.openrouter_title,
        "models": model_list,
        "planner_model": settings.planner_model,
        "coder_model": settings.coder_model,
        "reviewer_model": settings.reviewer_model,
        "search_summarizer_model": settings.search_summarizer_model,
        "compactor_model": settings.compactor_model,
        "model_routing_rules": settings.model_routing_rules,
        "max_turn_cost_usd": settings.max_turn_cost_usd,
        "max_session_cost_usd": settings.max_session_cost_usd,
        "max_file_size": settings.max_file_size,
        "allowed_commands": settings.allowed_commands,
        "blocked_commands": settings.blocked_commands,
        "session_dir": str(settings.session_dir),
        "max_session_history": settings.max_session_history,
        "auto_save_interval": settings.auto_save_interval,
        "mcp_enabled": settings.mcp_enabled,
        "mcp_servers": settings.mcp_servers,
        "plugins_dir": str(settings.plugins_dir),
        "enabled_plugins": settings.enabled_plugins,
        "browser_enabled": settings.browser_enabled,
        "browser_headless": settings.browser_headless,
        "browser_timeout": settings.browser_timeout,
        "web_search_enabled": settings.web_search_enabled,
        "web_search_provider": settings.web_search_provider,
        "google_grounding_enabled": settings.google_grounding_enabled,
        "search_cache_ttl_hours": settings.search_cache_ttl_hours,
        "compress_with_small_model": settings.compress_with_small_model,
        "search_summarizer_model": settings.search_summarizer_model,
        "learning_enabled": settings.learning_enabled,
        "auto_inject_lessons": settings.auto_inject_lessons,
        "max_lessons_per_prompt": settings.max_lessons_per_prompt,
        "auto_playbook": settings.auto_playbook,
        "negative_rules_strict": settings.negative_rules_strict,
        "ponytail_enabled": settings.ponytail_enabled,
        "ponytail_sass_level": settings.ponytail_sass_level,
        "ponytail_animations": settings.ponytail_animations,
        "ponytail_roast_mode": settings.ponytail_roast_mode,
        "permission_mode": settings.permission_mode,
        "shadow_git_checkpoints": settings.shadow_git_checkpoints,
        "redact_secrets": settings.redact_secrets,
        "sandbox_destructive_commands": settings.sandbox_destructive_commands,
        "destructive_patterns": settings.destructive_patterns,
        "smart_mode_triggers": settings.smart_mode_triggers,
        "harnesses": harness_list,
    }

    # Filter out None values to avoid TOML serialization issues (including nested in harnesses)
    def filter_none(d):
        if isinstance(d, dict):
            return {k: filter_none(v) for k, v in d.items() if v is not None}
        elif isinstance(d, list):
            return [filter_none(v) for v in d if v is not None]
        return d

    filtered_config = filter_none(config_data)
    config_path.write_text(tomli_w.dumps(filtered_config))
    reload_settings()


def _reset_to_defaults():
    """Reset configuration to defaults."""
    config_dir = Path.home() / ".orbitcode"
    config_path = config_dir / "config.toml"
    env_path = config_dir / ".env"

    if config_path.exists():
        config_path.unlink()
    if env_path.exists():
        env_path.unlink()

    reload_settings()


def _export_config(settings: Settings):
    """Export current config to a backup file."""
    import tomli_w

    backup_path = Path.cwd() / "orbitcode-config-backup.toml"

    model_list = []
    for m in settings.models:
        model_list.append({
            "name": m.name, "provider": m.provider, "api_key_env": m.api_key_env,
            "base_url": m.base_url, "max_tokens": m.max_tokens, "temperature": m.temperature,
            "timeout": m.timeout, "max_retries": m.max_retries, "is_free": m.is_free,
            "priority": m.priority,
        })

    harness_list = {}
    for name, h in settings.harnesses.items():
        # Support both HarnessConfig objects and plain dicts (from JSON editor)
        if hasattr(h, 'command'):
            # It's a HarnessConfig object
            harness_list[name] = {
                "command": h.command, "args": h.args, "env": h.env,
                "input_format": h.input_format, "output_parser": h.output_parser,
                "enabled": h.enabled, "working_dir": h.working_dir,
                "prompt_template": h.prompt_template,
                "context_template": h.context_template,
                "version_flag": h.version_flag,
                "use_stdin": h.use_stdin,
                "timeout": h.timeout,
                "custom_command": h.custom_command,
            }
        elif isinstance(h, dict):
            # It's a dict from JSON editor - extract values with defaults
            harness_list[name] = {
                "command": h.get("command", ""),
                "args": h.get("args", []),
                "env": h.get("env", {}),
                "input_format": h.get("input_format", "text"),
                "output_parser": h.get("output_parser", "extract_code_blocks"),
                "enabled": h.get("enabled", True),
                "working_dir": h.get("working_dir"),
                "prompt_template": h.get("prompt_template"),
                "context_template": h.get("context_template"),
                "version_flag": h.get("version_flag", "--version"),
                "use_stdin": h.get("use_stdin", False),
                "timeout": h.get("timeout", 120.0),
                "custom_command": h.get("custom_command"),
            }

    config_data = {
        "app_name": "OrbitCode", "app_version": settings.app_version, "maker": "OrbitOmen",
        "layout": settings.layout, "theme": settings.theme, "icon_pack": settings.icon_pack,
        "show_left_tree": settings.show_left_tree, "show_right_inspector": settings.show_right_inspector,
        "mouse_enabled": settings.mouse_enabled, "animations": settings.animations,
        "mascot_enabled": settings.mascot_enabled, "mascot_style": settings.mascot_style,
        "mascot_custom_ascii": settings.mascot_custom_ascii,
        "status_bar_widgets": settings.status_bar_widgets,
        "keybindings": settings.keybindings, "aliases": settings.aliases,
        "log_level": settings.log_level, "default_shell": settings.default_shell,
        "data_dir": str(settings.data_dir),
        "openrouter_base_url": settings.openrouter_base_url,
        "openrouter_referer": settings.openrouter_referer, "openrouter_title": settings.openrouter_title,
        "models": model_list,
        "planner_model": settings.planner_model, "coder_model": settings.coder_model,
        "reviewer_model": settings.reviewer_model, "search_summarizer_model": settings.search_summarizer_model,
        "compactor_model": settings.compactor_model, "model_routing_rules": settings.model_routing_rules,
        "max_turn_cost_usd": settings.max_turn_cost_usd, "max_session_cost_usd": settings.max_session_cost_usd,
        "max_file_size": settings.max_file_size, "allowed_commands": settings.allowed_commands,
        "blocked_commands": settings.blocked_commands,
        "session_dir": str(settings.session_dir), "max_session_history": settings.max_session_history,
        "auto_save_interval": settings.auto_save_interval,
        "mcp_enabled": settings.mcp_enabled, "mcp_servers": settings.mcp_servers,
        "plugins_dir": str(settings.plugins_dir), "enabled_plugins": settings.enabled_plugins,
        "browser_enabled": settings.browser_enabled, "browser_headless": settings.browser_headless,
        "browser_timeout": settings.browser_timeout,
        "web_search_enabled": settings.web_search_enabled, "web_search_provider": settings.web_search_provider,
        "google_grounding_enabled": settings.google_grounding_enabled,
        "search_cache_ttl_hours": settings.search_cache_ttl_hours,
        "compress_with_small_model": settings.compress_with_small_model,
        "search_summarizer_model": settings.search_summarizer_model,
        "learning_enabled": settings.learning_enabled, "auto_inject_lessons": settings.auto_inject_lessons,
        "max_lessons_per_prompt": settings.max_lessons_per_prompt, "auto_playbook": settings.auto_playbook,
        "negative_rules_strict": settings.negative_rules_strict,
        "ponytail_enabled": settings.ponytail_enabled,
        "ponytail_sass_level": settings.ponytail_sass_level,
        "ponytail_animations": settings.ponytail_animations,
        "ponytail_roast_mode": settings.ponytail_roast_mode,
        "permission_mode": settings.permission_mode, "shadow_git_checkpoints": settings.shadow_git_checkpoints,
        "redact_secrets": settings.redact_secrets, "sandbox_destructive_commands": settings.sandbox_destructive_commands,
        "destructive_patterns": settings.destructive_patterns, "smart_mode_triggers": settings.smart_mode_triggers,
        "harnesses": harness_list,
    }

    # Filter out None values to avoid TOML serialization issues (including nested in harnesses)
    def filter_none(d):
        if isinstance(d, dict):
            return {k: filter_none(v) for k, v in d.items() if v is not None}
        elif isinstance(d, list):
            return [filter_none(v) for v in d if v is not None]
        return d

    filtered_config = filter_none(config_data)
    backup_path.write_text(tomli_w.dumps(filtered_config))


def _import_config(path: str):
    """Import config from a file."""
    import shutil

    src = Path(path).expanduser().resolve()
    if not src.exists():
        console.print(f"[red]File not found: {src}[/red]")
        return

    config_dir = Path.home() / ".orbitcode"
    config_dir.mkdir(parents=True, exist_ok=True)

    dst = config_dir / "config.toml"
    shutil.copy2(src, dst)

    reload_settings()