"""Browser automation tool using Playwright."""
from typing import Optional
from pathlib import Path

from orbitcode.tools.base import Tool, ToolResult, ToolContext
from orbitcode.config import get_settings

try:
    from playwright.async_api import async_playwright, Browser, BrowserContext, Page
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False
    Browser = BrowserContext = Page = None


class BrowserTool(Tool):
    """Control a headless browser for web interaction."""

    name: ClassVar[str] = "browser"
    description: ClassVar[str] = "Navigate, click, type, and extract content from web pages using a headless browser."
    parameters: ClassVar[dict] = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["navigate", "click", "type", "get_text", "get_html", "screenshot", "wait", "execute_js"],
                "description": "Action to perform"
            },
            "url": {"type": "string", "description": "URL for navigate action"},
            "selector": {"type": "string", "description": "CSS selector for click/type/get_text"},
            "text": {"type": "string", "description": "Text to type"},
            "wait_ms": {"type": "integer", "description": "Milliseconds to wait", "default": 1000},
            "script": {"type": "string", "description": "JavaScript to execute"},
            "path": {"type": "string", "description": "Path to save screenshot"},
        },
        "required": ["action"],
    }

    def __init__(self):
        super().__init__()
        self._playwright = None
        self._browser: Optional[Browser] = None
        self._context: Optional[BrowserContext] = None
        self._page: Optional[Page] = None

    async def _ensure_browser(self, headless: bool = True):
        """Initialize browser if needed."""
        if not PLAYWRIGHT_AVAILABLE:
            raise RuntimeError("Playwright not installed. Run: pip install playwright && playwright install chromium")

        if self._browser is None:
            self._playwright = await async_playwright().start()
            self._browser = await self._playwright.chromium.launch(headless=headless)
            self._context = await self._browser.new_context(
                viewport={"width": 1280, "height": 720},
                user_agent="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36",
            )
            self._page = await self._context.new_page()

    async def execute(self, ctx: ToolContext, action: str, **params) -> ToolResult:
        settings = get_settings()
        if not settings.browser_enabled:
            return ToolResult(success=False, error="Browser is disabled in settings")

        try:
            await self._ensure_browser(settings.browser_headless)
            page = self._page

            if action == "navigate":
                url = params.get("url")
                if not url:
                    return ToolResult(success=False, error="url required for navigate")
                await page.goto(url, wait_until="networkidle", timeout=settings.browser_timeout * 1000)
                return ToolResult(success=True, output=f"Navigated to {url}")

            elif action == "click":
                selector = params.get("selector")
                if not selector:
                    return ToolResult(success=False, error="selector required for click")
                await page.click(selector, timeout=5000)
                return ToolResult(success=True, output=f"Clicked {selector}")

            elif action == "type":
                selector = params.get("selector")
                text = params.get("text")
                if not selector or text is None:
                    return ToolResult(success=False, error="selector and text required for type")
                await page.fill(selector, text, timeout=5000)
                return ToolResult(success=True, output=f"Typed into {selector}")

            elif action == "get_text":
                selector = params.get("selector")
                if not selector:
                    return ToolResult(success=False, error="selector required for get_text")
                text = await page.locator(selector).inner_text(timeout=5000)
                return ToolResult(success=True, output=text)

            elif action == "get_html":
                selector = params.get("selector")
                if selector:
                    html = await page.locator(selector).inner_html(timeout=5000)
                else:
                    html = await page.content()
                return ToolResult(success=True, output=html)

            elif action == "screenshot":
                path = params.get("path", "screenshot.png")
                full_path = (ctx.working_dir / path).resolve()
                full_path.parent.mkdir(parents=True, exist_ok=True)
                await page.screenshot(path=str(full_path), full_page=True)
                return ToolResult(success=True, output=f"Screenshot saved to {path}")

            elif action == "wait":
                wait_ms = params.get("wait_ms", 1000)
                await page.wait_for_timeout(wait_ms)
                return ToolResult(success=True, output=f"Waited {wait_ms}ms")

            elif action == "execute_js":
                script = params.get("script")
                if not script:
                    return ToolResult(success=False, error="script required for execute_js")
                result = await page.evaluate(script)
                return ToolResult(success=True, output=result)

            else:
                return ToolResult(success=False, error=f"Unknown action: {action}")

        except Exception as e:
            return ToolResult(success=False, error=f"Browser error: {e}")

    async def close(self):
        """Close browser and cleanup."""
        if self._page:
            await self._page.close()
        if self._context:
            await self._context.close()
        if self._browser:
            await self._browser.close()
        if self._playwright:
            await self._playwright.stop()
        self._page = self._context = self._browser = self._playwright = None