"""Web search tool using DuckDuckGo (free, no API key needed)."""
import asyncio
from typing import Optional
from urllib.parse import quote_plus

import httpx
from bs4 import BeautifulSoup

from orbitcode.tools.base import Tool, ToolResult, ToolContext
from orbitcode.config import get_settings


class WebSearchTool(Tool):
    """Search the web using DuckDuckGo HTML scraping."""

    name: ClassVar[str] = "web_search"
    description: ClassVar[str] = "Search the web for information. Returns top results with snippets and URLs."
    parameters: ClassVar[dict] = {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Search query"},
            "max_results": {"type": "integer", "description": "Maximum results to return", "default": 10},
        },
        "required": ["query"],
    }

    def __init__(self):
        super().__init__()
        self._client: Optional[httpx.AsyncClient] = None

    @property
    def client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(30.0),
                headers={"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36"},
                follow_redirects=True,
            )
        return self._client

    async def execute(self, ctx: ToolContext, query: str, max_results: int = 10) -> ToolResult:
        settings = get_settings()
        if not settings.web_search_enabled:
            return ToolResult(success=False, error="Web search is disabled in settings")

        try:
            url = f"https://html.duckduckgo.com/html/?q={quote_plus(query)}"
            response = await self.client.get(url)
            response.raise_for_status()

            soup = BeautifulSoup(response.text, "html.parser")
            results = []

            for result in soup.select(".result__snippet, .result__url, .result__title"):
                # DuckDuckGo HTML structure varies; try multiple selectors
                pass

            # More robust parsing
            for link in soup.select("a.result__snippet, a.result__url, .result__snippet"):
                text = link.get_text(strip=True)
                href = link.get("href", "")
                if text and href and len(results) < max_results:
                    results.append({"title": text[:200], "url": href, "snippet": text[:300]})

            # Fallback: try different selectors
            if not results:
                for item in soup.select(".result"):
                    title_elem = item.select_one(".result__title, h2")
                    snippet_elem = item.select_one(".result__snippet")
                    url_elem = item.select_one(".result__url")
                    if title_elem:
                        title = title_elem.get_text(strip=True)
                        snippet = snippet_elem.get_text(strip=True) if snippet_elem else ""
                        url = url_elem.get_text(strip=True) if url_elem else ""
                        if title:
                            results.append({"title": title, "url": url, "snippet": snippet})
                            if len(results) >= max_results:
                                break

            return ToolResult(
                success=True,
                output=results,
                metadata={"query": query, "count": len(results)},
            )
        except Exception as e:
            return ToolResult(success=False, error=f"Web search error: {e}")

    async def close(self):
        if self._client:
            await self._client.aclose()
            self._client = None