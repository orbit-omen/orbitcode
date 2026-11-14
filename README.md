# OrbitCode

**AI Coding Agent with model failover, MCP, plugins, and session persistence** — made by OrbitOmen.

## Features

- 🔄 **Model Failover** — Automatically switches between free OpenRouter models (Llama, Mistral, Gemma, Qwen) then paid fallbacks (Claude, GPT-4o) on errors
- 🛠 **MCP Server** — Exposes all tools via Model Context Protocol for use with other agents
- 🔌 **Plugin System** — Extend with custom tools, hooks, and integrations
- 💾 **Session Persistence** — Auto-resumes where you left off; SQLite-backed history
- 🌐 **Web Search & Browser** — DuckDuckGo search + Playwright browser automation
- ⚡ **Rich CLI** — Interactive REPL with commands, streaming responses, syntax highlighting

## Installation

```bash
# From source (recommended for development)
git clone https://github.com/OrbitOmen/orbitcode
cd orbitcode
pip install -e ".[dev,browser,web]"
playwright install chromium

# Or install from PyPI (when published)
pip install orbitcode
```

## Configuration

Set your OpenRouter API key:

```bash
export OPENROUTER_API_KEY="your-key-here"
```

Optional: create `~/.orbitcode/config.toml` for custom settings:

```toml
[models]
# Custom model chain
custom_models = [
  {name = "meta-llama/llama-3.2-3b-instruct:free", is_free = true, priority = 0},
  {name = "anthropic/claude-3.5-haiku", is_free = false, priority = 10},
]
```

## Usage

### Interactive Mode (default)

```bash
ocode                    # Start in current directory
ocode /path/to/project   # Start in specific directory
ocode --resume           # Resume latest session
ocode --model "anthropic/claude-3.5-haiku"  # Prefer specific model first
```

### Commands in Interactive Mode

| Command | Description |
|---------|-------------|
| `/help` | Show help |
| `/sessions` | List recent sessions |
| `/session <id>` | Switch to session |
| `/new` | Start new session |
| `/plugins` | List loaded plugins |
| `/models` | Show model failover chain |
| `/model <name>` | Set preferred model |
| `/clear` | Clear screen |
| `/exit` | Exit |

### MCP Server Mode

```bash
ocode --mcp                    # Run MCP server on stdio
ocode --mcp /path/to/project   # With specific working directory
```

Then add to your MCP client config:

```json
{
  "mcpServers": {
    "orbitcode": {
      "command": "ocode",
      "args": ["--mcp", "/path/to/project"]
    }
  }
}
```

### Programmatic Use

```python
from orbitcode.core.agent import create_agent
from orbitcode.core.session import SessionManager
from orbitcode.core.model_router import ModelRouter
from orbitcode.tools.registry import get_registry
from pathlib import Path
import asyncio

async def main():
    working_dir = Path.cwd()
    settings = get_settings()
    
    model_router = ModelRouter(settings)
    session_manager = SessionManager(settings)
    tool_registry = get_registry()
    
    agent = await create_agent(working_dir, session_manager, model_router, tool_registry, settings)
    
    async for chunk in agent.run_stream("Create a hello world Python script"):
        print(chunk, end="", flush=True)

asyncio.run(main())
```

## Project Structure

```
orbitcode/
├── orbitcode/
│   ├── cli.py              # CLI entry point
│   ├── config/             # Settings management
│   ├── core/
│   │   ├── agent.py        # Main agent loop
│   │   ├── model_router.py # OpenRouter with failover
│   │   └── session.py      # SQLite session persistence
│   ├── tools/
│   │   ├── base.py         # Tool base classes
│   │   ├── registry.py     # Tool registry
│   │   ├── bash.py         # Shell commands
│   │   ├── read.py         # File reading
│   │   ├── write.py        # File writing
│   │   ├── edit.py         # String replacement edits
│   │   ├── glob.py         # File pattern matching
│   │   ├── grep.py         # Content search
│   │   ├── web_search.py   # DuckDuckGo search
│   │   └── browser.py      # Playwright browser
│   ├── mcp/
│   │   └── server.py       # MCP server
│   └── plugins/            # Plugin system
├── tests/
├── pyproject.toml
└── README.md
```

## Adding Plugins

Create a plugin in `~/.orbitcode/plugins/my_plugin/`:

```
my_plugin/
├── plugin.py
```

```python
# plugin.py
from orbitcode.plugins import Plugin
from orbitcode.tools.base import Tool, ToolResult, ToolContext

class MyTool(Tool):
    name = "my_tool"
    description = "Does something cool"
    parameters = {
        "type": "object",
        "properties": {
            "input": {"type": "string"}
        },
        "required": ["input"]
    }
    
    async def execute(self, ctx: ToolContext, input: str) -> ToolResult:
        return ToolResult(success=True, output=f"Processed: {input}")

class MyPlugin(Plugin):
    name = "my_plugin"
    version = "1.0.0"
    description = "My custom plugin"
    
    def __init__(self, settings=None):
        super().__init__(settings)
        self.tools = [MyTool()]
```

Enable in config:
```toml
enabled_plugins = ["my_plugin"]
```

## Model Failover Chain

Default chain (free first, then paid):

1. `meta-llama/llama-3.2-3b-instruct:free` (free)
2. `mistralai/mistral-7b-instruct:free` (free)
3. `google/gemma-2-9b-it:free` (free)
4. `qwen/qwen-2.5-7b-instruct:free` (free)
5. `anthropic/claude-3.5-haiku` (paid)
6. `openai/gpt-4o-mini` (paid)

On any error (timeout, rate limit, API error), automatically tries the next model.

## Development

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Lint
ruff check .
mypy orbitcode

# Format
ruff format .
```

## License

MIT — Made by OrbitOmen