"""Google AI Search / Gemini Grounding Tool for Token-Saving Factual Queries"""
import os
import json
import hashlib
import time
from typing import Optional, List, Dict, Any
from dataclasses import dataclass

import httpx

from orbitcode.config import get_settings
from orbitcode.core.learning import get_learning_engine
from orbitcode.tools.base import Tool, ToolResult


@dataclass
class SearchResult:
    """Single search result"""
    title: str
    url: str
    snippet: str
    source: str = "google"


@dataclass
class GroundedAnswer:
    """Answer with grounding citations"""
    answer: str
    citations: List[SearchResult]
    tokens_saved: int


class GoogleSearchProvider:
    """Google Search + Gemini Grounding provider"""

    def __init__(self, settings=None):
        self.settings = settings or get_settings()
        self.api_key = os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY")
        self.cse_id = os.environ.get("GOOGLE_CSE_ID")  # Custom Search Engine ID
        self.grounding_enabled = bool(self.api_key)
        self.search_enabled = bool(self.api_key and self.cse_id)
        self._client: Optional[httpx.AsyncClient] = None
        self.learning_engine = get_learning_engine()

    @property
    def client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=30.0)
        return self._client

    async def close(self):
        if self._client:
            await self._client.aclose()
            self._client = None

    async def search(self, query: str, num_results: int = 5) -> List[SearchResult]:
        """Perform Google Custom Search"""
        if not self.search_enabled:
            return []

        # Check cache first
        cached = self.learning_engine.get_cached_search(query)
        if cached:
            return [SearchResult(**r) for r in cached]

        try:
            url = "https://www.googleapis.com/customsearch/v1"
            params = {
                "key": self.api_key,
                "cx": self.cse_id,
                "q": query,
                "num": min(num_results, 10),
            }

            response = await self.client.get(url, params=params)
            response.raise_for_status()
            data = response.json()

            results = []
            for item in data.get("items", []):
                results.append(SearchResult(
                    title=item.get("title", ""),
                    url=item.get("link", ""),
                    snippet=item.get("snippet", ""),
                    source="google"
                ))

            # Cache results
            self.learning_engine.cache_search_results(
                query,
                [asdict(r) for r in results],
                ttl_hours=self.settings.search_cache_ttl_hours if hasattr(self.settings, 'search_cache_ttl_hours') else 72
            )

            return results

        except Exception as e:
            return []

    async def grounded_generate(
        self,
        prompt: str,
        model: str = "gemini-1.5-flash",
        search_results: Optional[List[SearchResult]] = None
    ) -> GroundedAnswer:
        """Use Gemini with Grounding to generate answer from search results"""
        if not self.grounding_enabled:
            return GroundedAnswer(answer="", citations=[], tokens_saved=0)

        # If no search results provided, search first
        if search_results is None:
            search_results = await self.search(prompt)

        # Build grounding context
        context = "\n\n".join([
            f"Source: {r.title}\nURL: {r.url}\nContent: {r.snippet}"
            for r in search_results
        ])

        grounded_prompt = f"""Answer the following question using ONLY the provided sources.
Cite sources inline with [1], [2], etc.

Sources:
{context}

Question: {prompt}

Answer:"""

        try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
            params = {"key": self.api_key}
            payload = {
                "contents": [{"parts": [{"text": grounded_prompt}]}],
                "generationConfig": {
                    "temperature": 0.1,
                    "maxOutputTokens": 2048,
                }
            }

            response = await self.client.post(url, params=params, json=payload)
            response.raise_for_status()
            data = response.json()

            answer = data["candidates"][0]["content"]["parts"][0]["text"]

            # Estimate tokens saved (rough: 1500 tokens per search query vs 500 for grounded answer)
            tokens_saved = len(search_results) * 1000

            return GroundedAnswer(
                answer=answer,
                citations=search_results,
                tokens_saved=tokens_saved
            )

        except Exception as e:
            return GroundedAnswer(answer=str(e), citations=[], tokens_saved=0)


class HybridSearchRouter:
    """Routes queries to appropriate handler: Google Search for factual, Model for reasoning"""

    FACTUAL_KEYWORDS = {
        "version", "latest", "release", "changelog", "documentation", "docs",
        "api reference", "how to install", "getting started", "tutorial",
        "error code", "exception", "stack trace", "deprecated", "migration",
        "best practice", "recommended", "official", "github", "npm", "pypi",
        "docker hub", "registry", "license", "pricing", "rate limit"
    }

    CODE_KEYWORDS = {
        "refactor", "implement", "write", "create", "design", "architecture",
        "algorithm", "optimize", "debug", "fix", "test", "review",
        "pattern", "structure", "organize", "clean up"
    }

    def __init__(self, settings=None, search_provider: Optional[GoogleSearchProvider] = None):
        self.settings = settings or get_settings()
        self.search_provider = search_provider or GoogleSearchProvider(settings)
        self.learning_engine = get_learning_engine()

    def classify_query(self, query: str) -> str:
        """Classify query as 'factual', 'code', or 'hybrid'"""
        query_lower = query.lower()

        factual_score = sum(1 for kw in self.FACTUAL_KEYWORDS if kw in query_lower)
        code_score = sum(1 for kw in self.CODE_KEYWORDS if kw in query_lower)

        if factual_score > code_score and factual_score >= 2:
            return "factual"
        elif code_score > factual_score and code_score >= 2:
            return "code"
        return "hybrid"

    async def route_and_execute(
        self,
        query: str,
        coding_model_router=None,
        task_type: str = "search"
    ) -> Dict[str, Any]:
        """Route query and execute with appropriate handler"""
        classification = self.classify_query(query)

        if classification == "factual":
            # Use Google Search + Grounding
            result = await self.search_provider.grounded_generate(query)
            return {
                "type": "grounded_search",
                "answer": result.answer,
                "citations": [asdict(c) for c in result.citations],
                "tokens_saved": result.tokens_saved,
                "classification": classification
            }

        elif classification == "code":
            # Use coding model directly (handled by caller)
            return {
                "type": "coding_model",
                "classification": classification,
                "query": query
            }

        else:  # hybrid
            # Search first, then feed to coding model
            search_results = await self.search_provider.search(query)
            return {
                "type": "hybrid",
                "search_results": [asdict(r) for r in search_results],
                "query": query,
                "classification": classification
            }

    async def close(self):
        await self.search_provider.close()


class SearchSummarizer:
    """Compress search results using a small/fast model before feeding to main model"""

    def __init__(self, settings=None, model_router=None):
        self.settings = settings or get_settings()
        self.model_router = model_router
        self.summarizer_model = getattr(self.settings, 'search_summarizer_model', None) or "ollama/llama3.2:3b"

    async def summarize(
        self,
        query: str,
        results: List[SearchResult],
        max_tokens: int = 500
    ) -> str:
        """Summarize search results to key facts only"""
        if not results:
            return "No relevant search results found."

        # Build compression prompt
        combined = "\n\n".join([
            f"[{i+1}] {r.title}\n{r.url}\n{r.snippet}"
            for i, r in enumerate(results)
        ])

        prompt = f"""Extract ONLY the key facts needed to answer: "{query}"

From these search results:
{combined}

Return a concise summary (max {max_tokens} tokens) with citations like [1], [2].
Focus on: versions, dates, API signatures, error codes, official recommendations.
Omit: marketing fluff, tutorials, opinions, outdated info.

Summary:"""

        if self.model_router:
            try:
                from orbitcode.core.model_router import ChatMessage
                messages = [ChatMessage(role="user", content=prompt)]
                response = await self.model_router.chat(
                    messages,
                    preferred_model=self.summarizer_model
                )
                return response.content
            except Exception:
                pass

        # Fallback: simple truncation
        return combined[:2000] + "..." if len(combined) > 2000 else combined


# Tool definition for the agent
class GoogleSearchTool(Tool):
    """Google Search tool for the agent"""

    name = "google_search"
    description = "Search the web for factual information, documentation, error solutions, library versions. Use for fact-seeking queries only."
    parameters = {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Search query - be specific (e.g., 'FastAPI 0.110 release notes', 'Python asyncio timeout error')"
            },
            "num_results": {
                "type": "integer",
                "description": "Number of results to return (default: 5)",
                "default": 5
            }
        },
        "required": ["query"]
    }

    def __init__(self):
        super().__init__()
        self.router = HybridSearchRouter()

    async def execute(self, query: str, num_results: int = 5) -> ToolResult:
        try:
            result = await self.router.route_and_execute(query)

            if result["type"] == "grounded_search":
                output = f"**Answer:** {result['answer']}\n\n**Sources:**\n"
                for i, cite in enumerate(result['citations'], 1):
                    output += f"[{i}] {cite['title']} - {cite['url']}\n"
                output += f"\n*Tokens saved: ~{result['tokens_saved']}*"
                return ToolResult(output=output, success=True, metadata={"tokens_saved": result['tokens_saved']})

            elif result["type"] == "hybrid":
                output = f"**Search Results for:** {result['query']}\n\n"
                for i, r in enumerate(result['search_results'], 1):
                    output += f"[{i}] **{r['title']}**\n{r['url']}\n{r['snippet']}\n\n"
                return ToolResult(output=output, success=True)

            else:
                return ToolResult(
                    output="This query is better handled by the coding model directly.",
                    success=False
                )

        except Exception as e:
            return ToolResult(output=f"Search failed: {e}", success=False)
        finally:
            await self.router.close()


def asdict(obj) -> dict:
    """Convert dataclass to dict"""
    if hasattr(obj, '__dataclass_fields__'):
        return {f: getattr(obj, f) for f in obj.__dataclass_fields__}
    return obj.__dict__ if hasattr(obj, '__dict__') else {}