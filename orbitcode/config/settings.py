"""Settings management using Pydantic Settings - Fully customizable with protected brand identity."""
import os
from pathlib import Path
from typing import Optional, Dict, List, Any
from pydantic import Field, field_validator, ConfigDict
from pydantic_settings import BaseSettings, SettingsConfigDict


class ModelConfig(BaseSettings):
    """Configuration for a single model."""
    name: str
    provider: str = "openrouter"
    api_key_env: str = "OPENROUTER_API_KEY"
    base_url: str = "https://openrouter.ai/api/v1"
    max_tokens: int = 8192
    temperature: float = 0.1
    timeout: float = 60.0
    max_retries: int = 2
    is_free: bool = False
    priority: int = 0  # Lower = higher priority

    model_config = SettingsConfigDict(extra="ignore")


class HarnessConfig(BaseSettings):
    """Configuration for external AI harness adapters."""
    command: str
    args: List[str] = Field(default_factory=list)
    env: Dict[str, str] = Field(default_factory=dict)
    input_format: str = "text"  # text, json, markdown
    output_parser: str = "extract_code_blocks"  # extract_code_blocks, raw, json
    enabled: bool = True
    working_dir: Optional[str] = None

    # Custom command templates for personalized integration
    prompt_template: Optional[str] = None  # e.g., "{context}\n\n## Task:\n{prompt}"
    context_template: Optional[str] = None  # e.g., "### {file}\n```\n{content}\n```"
    version_flag: str = "--version"  # Command to check version
    use_stdin: bool = False  # Whether to pass prompt via stdin
    timeout: float = 120.0  # Timeout in seconds

    # Custom command overrides for specific tools
    # e.g., "claude_code": "fcc-claude" to use custom wrapper
    custom_command: Optional[str] = None

    model_config = SettingsConfigDict(extra="ignore")


class Settings(BaseSettings):
    """Main application settings - ALL CUSTOMIZABLE via config.toml"""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_nested_delimiter="__",
        extra="ignore",
    )

    # ==================== BRAND IDENTITY (PROTECTED - IMMUTABLE) ====================
    # These are frozen and cannot be modified via /customise or config.toml
    app_name: str = "OrbitCode"
    app_version: str = "0.1.0"
    maker: str = "OrbitOmen"

    # ==================== CORE PATHS ====================
    data_dir: Path = Field(default_factory=lambda: Path.home() / ".orbitcode")
    log_level: str = "INFO"

    # ==================== UI / TUI SETTINGS ====================
    layout: str = "studio"  # stream, studio, command
    theme: str = "orbit-nebula"  # orbit-nebula, orbit-midnight, orbit-solar, orbit-ghost, or custom .tcss filename
    icon_pack: str = "nerd"  # nerd, unicode, ascii
    show_left_tree: bool = True
    show_right_inspector: bool = True
    mouse_enabled: bool = True
    animations: bool = True
    mascot_enabled: bool = True
    mascot_style: str = "full"  # full, compact, minimal
    mascot_custom_ascii: Optional[str] = None
    status_bar_widgets: List[str] = Field(default_factory=lambda: [
        "model", "mode", "context", "tokens_saved", "layout", "mascot"
    ])

    # ==================== KEYBINDINGS (FULLY REMAPABLE) ====================
    keybindings: Dict[str, str] = Field(default_factory=lambda: {
        "quit": "ctrl+q",
        "new_session": "ctrl+n",
        "save_session": "ctrl+s",
        "command_palette": "ctrl+p",
        "toggle_tree": "ctrl+b",
        "toggle_inspector": "ctrl+i",
        "cycle_mode": "ctrl+m",
        "rewind": "ctrl+r",
        "new_tab": "ctrl+t",
        "next_tab": "ctrl+tab",
        "prev_tab": "ctrl+shift+tab",
        "focus_input": "ctrl+f",
        "toggle_mascot": "ctrl+u",
        "layout_cycle": "ctrl+l",
        "theme_cycle": "ctrl+h",
    })

    # ==================== ALIASES (USER-DEFINED SLASH COMMANDS) ====================
    aliases: Dict[str, str] = Field(default_factory=dict)

    # ==================== PROVIDER API KEYS (from .env) ====================
    # OpenRouter
    openrouter_api_key: Optional[str] = Field(default=None, validation_alias="OPENROUTER_API_KEY")
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    openrouter_referer: str = "https://github.com/orbit-omen/orbitcode"
    openrouter_title: str = "OrbitCode"

    # Direct Providers
    anthropic_api_key: Optional[str] = Field(default=None, validation_alias="ANTHROPIC_API_KEY")
    openai_api_key: Optional[str] = Field(default=None, validation_alias="OPENAI_API_KEY")
    google_api_key: Optional[str] = Field(default=None, validation_alias="GOOGLE_API_KEY")
    google_cse_id: Optional[str] = Field(default=None, validation_alias="GOOGLE_CSE_ID")
    groq_api_key: Optional[str] = Field(default=None, validation_alias="GROQ_API_KEY")
    deepseek_api_key: Optional[str] = Field(default=None, validation_alias="DEEPSEEK_API_KEY")
    xai_api_key: Optional[str] = Field(default=None, validation_alias="XAI_API_KEY")
    together_api_key: Optional[str] = Field(default=None, validation_alias="TOGETHER_API_KEY")
    fireworks_api_key: Optional[str] = Field(default=None, validation_alias="FIREWORKS_API_KEY")
    mistral_api_key: Optional[str] = Field(default=None, validation_alias="MISTRAL_API_KEY")

    # Key Pools (comma-separated for rotation)
    anthropic_api_keys: Optional[str] = Field(default=None, validation_alias="ANTHROPIC_API_KEYS")
    openai_api_keys: Optional[str] = Field(default=None, validation_alias="OPENAI_API_KEYS")
    google_api_keys: Optional[str] = Field(default=None, validation_alias="GOOGLE_API_KEYS")
    groq_api_keys: Optional[str] = Field(default=None, validation_alias="GROQ_API_KEYS")

    # ==================== MODEL ROLES & FAILOVER CHAINS ====================
    models: List[ModelConfig] = Field(default_factory=lambda: [
        ModelConfig(name="meta-llama/llama-3.2-3b-instruct:free", provider="openrouter", is_free=True, priority=0),
        ModelConfig(name="mistralai/mistral-7b-instruct:free", provider="openrouter", is_free=True, priority=1),
        ModelConfig(name="google/gemma-2-9b-it:free", provider="openrouter", is_free=True, priority=2),
        ModelConfig(name="qwen/qwen-2.5-7b-instruct:free", provider="openrouter", is_free=True, priority=3),
        ModelConfig(name="anthropic/claude-3.5-haiku", provider="openrouter", is_free=False, priority=10),
        ModelConfig(name="openai/gpt-4o-mini", provider="openrouter", is_free=False, priority=11),
    ])

    # Role-based model assignments (model name from chain or provider/model)
    planner_model: Optional[str] = None
    coder_model: Optional[str] = None
    reviewer_model: Optional[str] = None
    search_summarizer_model: Optional[str] = None
    compactor_model: Optional[str] = None

    # Model routing rules (DSL)
    model_routing_rules: List[str] = Field(default_factory=list)

    # Budget limits
    max_turn_cost_usd: float = 0.50
    max_session_cost_usd: float = 10.0

    # ==================== TOOLS ====================
    default_shell: str = Field(default_factory=lambda: os.environ.get("SHELL", "/bin/bash"))
    max_file_size: int = 10 * 1024 * 1024
    allowed_commands: List[str] = Field(default_factory=lambda: [
        "ls", "cat", "head", "tail", "grep", "rg", "find", "git", "python", "node",
        "npm", "pip", "cargo", "go", "make", "cmake", "docker", "kubectl", "terraform",
    ])
    blocked_commands: List[str] = Field(default_factory=lambda: [
        "rm -rf /", "dd if=", "mkfs", "fdisk", "shutdown", "reboot", "halt",
    ])

    # ==================== SESSION ====================
    session_dir: Path = Field(default_factory=lambda: Path.home() / ".orbitcode" / "sessions")
    max_session_history: int = 100
    auto_save_interval: int = 5

    # ==================== MCP ====================
    mcp_enabled: bool = True
    mcp_servers: Dict[str, Dict] = Field(default_factory=dict)

    # ==================== PLUGINS ====================
    plugins_dir: Path = Field(default_factory=lambda: Path.home() / ".orbitcode" / "plugins")
    enabled_plugins: List[str] = Field(default_factory=list)

    # ==================== BROWSER ====================
    browser_enabled: bool = True
    browser_headless: bool = True
    browser_timeout: float = 30.0

    # ==================== WEB SEARCH ====================
    web_search_enabled: bool = True
    web_search_provider: str = "duckduckgo"
    web_search_api_key: Optional[str] = None

    # ==================== GOOGLE AI SEARCH / GROUNDING ====================
    google_grounding_enabled: bool = True
    search_cache_ttl_hours: int = 72
    compress_with_small_model: bool = True
    search_summarizer_model: str = "ollama/llama3.2:3b"

    # ==================== LEARNING ENGINE ====================
    learning_enabled: bool = True
    auto_inject_lessons: bool = True
    max_lessons_per_prompt: int = 3
    auto_playbook: bool = True
    negative_rules_strict: bool = True

    # ==================== SAFETY / PERMISSION MODES ====================
    permission_mode: str = "smart"  # ask, auto_edit, plan, yolo, smart
    shadow_git_checkpoints: bool = True
    redact_secrets: bool = True
    sandbox_destructive_commands: bool = True
    destructive_patterns: List[str] = Field(default_factory=lambda: [
        "rm -rf", "git reset --hard", "git push --force", "DROP TABLE", "DELETE FROM",
        "truncate", "mkfs", "fdisk", "shutdown", "reboot", "> /dev/sd"
    ])

    # Smart mode specific triggers (asks for confirmation)
    smart_mode_triggers: List[str] = Field(default_factory=lambda: [
        "destructive_command",
        "large_file_change",  # >100 lines
        "external_api_cost",   # API calls that cost money
        "git_push",
        "long_test_run",       # >30 seconds
        "commit_no_message",
        "install_packages",
    ])

    # ==================== EXTERNAL HARNESS ADAPTERS ====================
    harnesses: Dict[str, HarnessConfig] = Field(default_factory=dict)

    # ==================== PONYTAIL PLUGIN ====================
    ponytail_enabled: bool = True
    ponytail_sass_level: int = 3
    ponytail_animations: bool = True
    ponytail_roast_mode: bool = False

    # ==================== VALIDATORS ====================
    @field_validator("data_dir", "session_dir", "plugins_dir", mode="before")
    @classmethod
    def expand_path(cls, v: str | Path) -> Path:
        if isinstance(v, str):
            return Path(v).expanduser().resolve()
        return v.expanduser().resolve()

    @field_validator("permission_mode")
    @classmethod
    def validate_permission_mode(cls, v: str) -> str:
        valid = {"ask", "auto_edit", "plan", "yolo", "smart"}
        if v not in valid:
            raise ValueError(f"permission_mode must be one of {valid}")
        return v

    @field_validator("layout")
    @classmethod
    def validate_layout(cls, v: str) -> str:
        valid = {"stream", "studio", "command"}
        if v not in valid:
            raise ValueError(f"layout must be one of {valid}")
        return v

    @field_validator("icon_pack")
    @classmethod
    def validate_icon_pack(cls, v: str) -> str:
        valid = {"nerd", "unicode", "ascii"}
        if v not in valid:
            raise ValueError(f"icon_pack must be one of {valid}")
        return v

    @field_validator("mascot_style")
    @classmethod
    def validate_mascot_style(cls, v: str) -> str:
        valid = {"full", "compact", "minimal"}
        if v not in valid:
            raise ValueError(f"mascot_style must be one of {valid}")
        return v

    @field_validator("web_search_provider")
    @classmethod
    def validate_web_search_provider(cls, v: str) -> str:
        valid = {"duckduckgo", "brave", "serpapi", "google"}
        if v not in valid:
            raise ValueError(f"web_search_provider must be one of {valid}")
        return v

    # ==================== HELPER METHODS ====================
    def get_model_chain(self) -> List[ModelConfig]:
        """Get models sorted by priority (free first, then paid)."""
        return sorted(self.models, key=lambda m: (not m.is_free, m.priority))

    def get_api_key(self, model: ModelConfig) -> Optional[str]:
        """Get API key for a model from environment with pool rotation support."""
        # Check for key pool first
        pool_env = f"{model.api_key_env}S"  # e.g., OPENROUTER_API_KEYS
        pool = os.environ.get(pool_env)
        if pool:
            keys = [k.strip() for k in pool.split(",") if k.strip()]
            if keys:
                # Simple rotation - could be enhanced with round-robin state
                import random
                return random.choice(keys)

        # Check single key
        env_val = os.environ.get(model.api_key_env)
        if env_val is not None:
            return env_val if env_val else None  # Empty string -> None for local models

        # Fallback to OpenRouter key
        return self.openrouter_api_key

    def get_key_pool(self, provider: str) -> List[str]:
        """Get key pool for a provider."""
        env_var = f"{provider.upper()}_API_KEYS"
        pool = os.environ.get(env_var)
        if pool:
            return [k.strip() for k in pool.split(",") if k.strip()]
        return []

    def is_brand_field(self, field_name: str) -> bool:
        """Check if a field is a protected brand field."""
        return field_name in {"app_name", "app_version", "maker"}

    def get_harness_config(self, name: str) -> Optional[HarnessConfig]:
        """Get harness configuration by name."""
        return self.harnesses.get(name)

    def get_all_harnesses(self) -> Dict[str, HarnessConfig]:
        """Get all enabled harness configurations."""
        return {k: v for k, v in self.harnesses.items() if v.enabled}


# Protected brand fields that can never be modified
PROTECTED_BRAND_FIELDS = frozenset({"app_name", "app_version", "maker"})


_settings: Optional[Settings] = None


def get_settings() -> Settings:
    """Get singleton settings instance."""
    global _settings
    if _settings is None:
        _settings = _load_settings_from_file()
        # Ensure directories exist
        _settings.data_dir.mkdir(parents=True, exist_ok=True)
        _settings.session_dir.mkdir(parents=True, exist_ok=True)
        _settings.plugins_dir.mkdir(parents=True, exist_ok=True)
    return _settings


def _load_settings_from_file() -> Settings:
    """Load settings from config.toml with proper model and harness parsing."""
    import tomli
    import os
    from pathlib import Path

    config_dir = Path.home() / ".orbitcode"
    config_path = config_dir / "config.toml"
    env_path = config_dir / ".env"

    # Load .env file manually
    if env_path.exists():
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, value = line.split("=", 1)
                    os.environ[key.strip()] = value.strip()

    if config_path.exists():
        with open(config_path, "rb") as f:
            config_data = tomli.load(f)

        # Parse models from config
        models = []
        for m in config_data.get("models", []):
            models.append(ModelConfig(
                name=m.get("name", ""),
                provider=m.get("provider", "openrouter"),
                api_key_env=m.get("api_key_env", "OPENROUTER_API_KEY"),
                base_url=m.get("base_url", "https://openrouter.ai/api/v1"),
                max_tokens=m.get("max_tokens", 8192),
                temperature=m.get("temperature", 0.1),
                timeout=m.get("timeout", 60.0),
                max_retries=m.get("max_retries", 2),
                is_free=m.get("is_free", False),
                priority=m.get("priority", 0),
            ))

        # Parse harnesses from config
        harnesses = {}
        for name, h in config_data.get("harnesses", {}).items():
            harnesses[name] = HarnessConfig(
                command=h.get("command", ""),
                args=h.get("args", []),
                env=h.get("env", {}),
                input_format=h.get("input_format", "text"),
                output_parser=h.get("output_parser", "extract_code_blocks"),
                enabled=h.get("enabled", True),
                working_dir=h.get("working_dir"),
                prompt_template=h.get("prompt_template"),
                context_template=h.get("context_template"),
                version_flag=h.get("version_flag", "--version"),
                use_stdin=h.get("use_stdin", False),
                timeout=h.get("timeout", 120.0),
                custom_command=h.get("custom_command"),
            )

        # Remove parsed sections so pydantic doesn't try to parse them
        config_data.pop("models", None)
        config_data.pop("harnesses", None)

        # Create settings with parsed models and harnesses
        return Settings(models=models, harnesses=harnesses, **config_data)
    else:
        return Settings()


def reload_settings() -> Settings:
    """Reload settings (useful for testing and after config changes)."""
    global _settings
    _settings = None
    return get_settings()