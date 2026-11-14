"""First-run setup wizard for OrbitCode."""
import os
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt, Confirm
from rich.table import Table

from orbitcode.config import get_settings, Settings, ModelConfig, reload_settings

console = Console()


PROVIDER_PRESETS = {
    "openrouter": {
        "name": "OpenRouter (recommended)",
        "base_url": "https://openrouter.ai/api/v1",
        "api_key_env": "OPENROUTER_API_KEY",
        "help_url": "https://openrouter.ai/keys",
        "models": [
            ModelConfig(name="meta-llama/llama-3.2-3b-instruct:free", is_free=True, priority=0),
            ModelConfig(name="mistralai/mistral-7b-instruct:free", is_free=True, priority=1),
            ModelConfig(name="google/gemma-2-9b-it:free", is_free=True, priority=2),
            ModelConfig(name="qwen/qwen-2.5-7b-instruct:free", is_free=True, priority=3),
            ModelConfig(name="anthropic/claude-3.5-haiku", is_free=False, priority=10),
            ModelConfig(name="openai/gpt-4o-mini", is_free=False, priority=11),
        ],
    },
    "ollama": {
        "name": "Ollama (local, free, private)",
        "base_url": "http://localhost:11434/v1",
        "api_key_env": "OLLAMA_API_KEY",  # usually not needed
        "help_url": "https://ollama.com",
        "models": [
            ModelConfig(name="llama3.2:3b", provider="ollama", is_free=True, priority=0, base_url="http://localhost:11434/v1", api_key_env="OLLAMA_API_KEY"),
            ModelConfig(name="mistral:7b", provider="ollama", is_free=True, priority=1, base_url="http://localhost:11434/v1", api_key_env="OLLAMA_API_KEY"),
            ModelConfig(name="codellama:7b", provider="ollama", is_free=True, priority=2, base_url="http://localhost:11434/v1", api_key_env="OLLAMA_API_KEY"),
            ModelConfig(name="qwen2.5:7b", provider="ollama", is_free=True, priority=3, base_url="http://localhost:11434/v1", api_key_env="OLLAMA_API_KEY"),
        ],
    },
    "lmstudio": {
        "name": "LM Studio (local, free, private)",
        "base_url": "http://localhost:1234/v1",
        "api_key_env": "LMSTUDIO_API_KEY",  # usually not needed
        "help_url": "https://lmstudio.ai",
        "models": [
            ModelConfig(name="local-model", provider="lmstudio", is_free=True, priority=0, base_url="http://localhost:1234/v1", api_key_env="LMSTUDIO_API_KEY"),
        ],
    },
    "custom": {
        "name": "Custom OpenAI-compatible endpoint",
        "base_url": "",
        "api_key_env": "CUSTOM_API_KEY",
        "help_url": "",
        "models": [],
    },
}


def is_first_run() -> bool:
    """Check if this is the first run (no config file exists)."""
    config_path = Path.home() / ".orbitcode" / "config.toml"
    return not config_path.exists()


def run_wizard() -> Settings:
    """Run the interactive first-run setup wizard."""
    console.print()
    console.print(Panel.fit(
        "[bold cyan]Welcome to OrbitCode![/bold cyan]\n"
        "Let's set up your AI provider and preferences.",
        title="🚀 First Run Setup",
        border_style="cyan",
    ))

    # Step 1: Choose provider
    console.print("\n[bold]Step 1: Choose your AI provider[/bold]")
    table = Table(show_header=True, header_style="bold")
    table.add_column("#", style="cyan", width=3)
    table.add_column("Provider", style="bold")
    table.add_column("Description")
    table.add_column("Cost")

    providers = list(PROVIDER_PRESETS.keys())
    for i, key in enumerate(providers, 1):
        p = PROVIDER_PRESETS[key]
        cost = "Free" if all(m.is_free for m in p["models"]) else "Free + Paid" if any(m.is_free for m in p["models"]) else "Paid"
        if key in ("ollama", "lmstudio"):
            cost = "Free (local)"
        table.add_row(str(i), p["name"], "", cost)

    console.print(table)

    choice = Prompt.ask(
        "Select provider",
        choices=[str(i) for i in range(1, len(providers) + 1)],
        default="1",
    )
    provider_key = providers[int(choice) - 1]
    provider = PROVIDER_PRESETS[provider_key]

    # Step 2: API Key / Base URL
    console.print(f"\n[bold]Step 2: Configure {provider['name']}[/bold]")

    base_url = provider["base_url"]
    api_key = None

    if provider_key == "custom":
        base_url = Prompt.ask("Base URL (e.g., https://api.example.com/v1)", default="")
        if not base_url:
            console.print("[red]Base URL is required for custom provider[/red]")
            return run_wizard()

    if provider["api_key_env"] not in ("OLLAMA_API_KEY", "LMSTUDIO_API_KEY") or Confirm.ask("Do you have an API key?", default=True):
        api_key = Prompt.ask(f"API Key (get from {provider['help_url']})", password=True)
        if not api_key and provider_key != "custom":
            console.print("[yellow]Warning: No API key provided. Some models may not work.[/yellow]")

    # Step 3: Model preferences
    console.print("\n[bold]Step 3: Model preferences[/bold]")
    if provider["models"]:
        console.print("Default models for this provider:")
        for i, m in enumerate(provider["models"], 1):
            badge = "[green]FREE[/green]" if m.is_free else "[yellow]PAID[/yellow]"
            console.print(f"  {i}. {m.name} {badge}")

        if Confirm.ask("Use these defaults?", default=True):
            models = provider["models"]
        else:
            models = _custom_model_chain()
    else:
        models = _custom_model_chain()

    # Step 4: Shell & Editor
    console.print("\n[bold]Step 4: Environment[/bold]")
    default_shell = os.environ.get("SHELL", "/bin/bash")
    shell = Prompt.ask("Default shell", default=default_shell)

    editor = os.environ.get("EDITOR", "code")
    editor = Prompt.ask("Default editor (for `ocode edit`)", default=editor)

    # Step 5: Features
    console.print("\n[bold]Step 5: Enable features[/bold]")
    browser_enabled = Confirm.ask("Enable browser automation (Playwright)?", default=True)
    web_search_enabled = Confirm.ask("Enable web search (DuckDuckGo)?", default=True)

    # Build settings
    settings = Settings(
        openrouter_base_url=base_url,
        openrouter_api_key=api_key,
        models=models,
        default_shell=shell,
        browser_enabled=browser_enabled,
        web_search_enabled=web_search_enabled,
    )

    # Save config
    _save_config(settings, api_key, provider_key, base_url, provider)

    console.print(Panel.fit(
        "[green]✓ Setup complete![/green]\n"
        f"Config saved to ~/.orbitcode/config.toml\n"
        f"Run [bold]ocode[/bold] to start.",
        title="Done",
        border_style="green",
    ))

    return reload_settings()


def _custom_model_chain() -> list[ModelConfig]:
    """Let user define custom model chain."""
    models = []
    console.print("\nAdd models (empty name to finish):")
    while True:
        name = Prompt.ask("Model name (e.g., anthropic/claude-3.5-sonnet)", default="")
        if not name:
            break
        is_free = Confirm.ask("Is this model free?", default=False)
        priority = len(models)
        base_url = Prompt.ask("Base URL (empty for default)", default="")
        models.append(ModelConfig(
            name=name,
            is_free=is_free,
            priority=priority,
            base_url=base_url or "https://openrouter.ai/api/v1",
        ))
    return models


def _save_config(settings: Settings, api_key: Optional[str], provider_key: str, base_url: str, provider: dict):
    """Save configuration to TOML file."""
    import tomli_w

    config_dir = Path.home() / ".orbitcode"
    config_dir.mkdir(parents=True, exist_ok=True)
    config_path = config_dir / "config.toml"

    # Build TOML structure
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

    config_data = {
        "app_name": "OrbitCode",
        "app_version": "0.1.0",
        "data_dir": str(settings.data_dir),
        "log_level": "INFO",
        "openrouter_base_url": base_url,
        "openrouter_referer": "https://github.com/orbit-omen/orbitcode",
        "openrouter_title": "OrbitCode",
        "default_shell": settings.default_shell,
        "max_file_size": settings.max_file_size,
        "session_dir": str(settings.session_dir),
        "max_session_history": settings.max_session_history,
        "auto_save_interval": settings.auto_save_interval,
        "mcp_enabled": settings.mcp_enabled,
        "plugins_dir": str(settings.plugins_dir),
        "enabled_plugins": settings.enabled_plugins,
        "browser_enabled": settings.browser_enabled,
        "browser_headless": settings.browser_headless,
        "browser_timeout": settings.browser_timeout,
        "web_search_enabled": settings.web_search_enabled,
        "web_search_provider": settings.web_search_provider,
        "models": model_list,
    }

    # Write config
    config_path.write_text(tomli_w.dumps(config_data))

    # Write .env for API key
    if api_key:
        env_path = config_dir / ".env"
        api_key_env = provider["api_key_env"]
        env_content = f"{api_key_env}={api_key}\n"
        env_path.write_text(env_content)
        # Secure permissions
        env_path.chmod(0o600)


def load_or_wizard() -> Settings:
    """Load settings or run wizard if first run."""
    if is_first_run():
        return run_wizard()
    return get_settings()