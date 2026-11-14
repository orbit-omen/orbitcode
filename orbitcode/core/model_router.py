"""Model router with automatic failover across multiple providers (OpenRouter, Anthropic, OpenAI, Google, Groq, etc.)"""
import os
import logging
import time
from typing import Optional, List, Dict, Any
from dataclasses import dataclass
from enum import Enum

import httpx
from pydantic import BaseModel

from orbitcode.config import get_settings, ModelConfig, Settings
from orbitcode.core.learning import get_learning_engine

logger = logging.getLogger(__name__)


class ModelError(Exception):
    """Raised when all models in the chain fail."""
    def __init__(self, message: str, attempted_models: list[str], last_error: Optional[Exception] = None):
        super().__init__(message)
        self.attempted_models = attempted_models
        self.last_error = last_error


class ChatMessage(BaseModel):
    """Chat message format."""
    role: str  # system, user, assistant, tool
    content: str
    tool_calls: Optional[list[dict]] = None
    tool_call_id: Optional[str] = None


class ChatResponse(BaseModel):
    """Chat completion response."""
    content: str
    tool_calls: Optional[list[dict]] = None
    model: str
    usage: Optional[dict] = None
    latency_ms: float = 0
    provider: str = "unknown"


@dataclass
class ModelAttempt:
    """Result of a single model attempt."""
    model: str
    success: bool
    response: Optional[ChatResponse] = None
    error: Optional[Exception] = None
    latency_ms: float = 0


class ProviderType(Enum):
    """Supported provider types"""
    OPENROUTER = "openrouter"
    ANTHROPIC = "anthropic"
    OPENAI = "openai"
    GOOGLE = "google"
    GROQ = "groq"
    DEEPSEEK = "deepseek"
    XAI = "xai"
    TOGETHER = "together"
    FIREWORKS = "fireworks"
    MISTRAL = "mistral"
    OLLAMA = "ollama"
    LMSTUDIO = "lmstudio"
    CUSTOM = "custom"


# Provider-specific configurations
PROVIDER_CONFIGS = {
    ProviderType.OPENROUTER: {
        "base_url": "https://openrouter.ai/api/v1",
        "headers": lambda s: {"HTTP-Referer": s.openrouter_referer, "X-Title": s.openrouter_title},
        "supports_tools": True,
        "supports_streaming": True,
    },
    ProviderType.ANTHROPIC: {
        "base_url": "https://api.anthropic.com/v1",
        "headers": lambda s: {"x-api-key": s.anthropic_api_key, "anthropic-version": "2023-06-01"},
        "supports_tools": True,
        "supports_streaming": True,
        "payload_transform": "anthropic",
    },
    ProviderType.OPENAI: {
        "base_url": "https://api.openai.com/v1",
        "headers": lambda s: {"Authorization": f"Bearer {s.openai_api_key}"},
        "supports_tools": True,
        "supports_streaming": True,
    },
    ProviderType.GOOGLE: {
        "base_url": "https://generativelanguage.googleapis.com/v1beta",
        "headers": lambda s: {},
        "supports_tools": True,
        "supports_streaming": True,
        "payload_transform": "google",
        "api_key_param": "key",
    },
    ProviderType.GROQ: {
        "base_url": "https://api.groq.com/openai/v1",
        "headers": lambda s: {"Authorization": f"Bearer {s.groq_api_key}"},
        "supports_tools": True,
        "supports_streaming": True,
    },
    ProviderType.DEEPSEEK: {
        "base_url": "https://api.deepseek.com/v1",
        "headers": lambda s: {"Authorization": f"Bearer {s.deepseek_api_key}"},
        "supports_tools": True,
        "supports_streaming": True,
    },
    ProviderType.XAI: {
        "base_url": "https://api.x.ai/v1",
        "headers": lambda s: {"Authorization": f"Bearer {s.xai_api_key}"},
        "supports_tools": True,
        "supports_streaming": True,
    },
    ProviderType.TOGETHER: {
        "base_url": "https://api.together.xyz/v1",
        "headers": lambda s: {"Authorization": f"Bearer {s.together_api_key}"},
        "supports_tools": True,
        "supports_streaming": True,
    },
    ProviderType.FIREWORKS: {
        "base_url": "https://api.fireworks.ai/inference/v1",
        "headers": lambda s: {"Authorization": f"Bearer {s.fireworks_api_key}"},
        "supports_tools": True,
        "supports_streaming": True,
    },
    ProviderType.MISTRAL: {
        "base_url": "https://api.mistral.ai/v1",
        "headers": lambda s: {"Authorization": f"Bearer {s.mistral_api_key}"},
        "supports_tools": True,
        "supports_streaming": True,
    },
    ProviderType.OLLAMA: {
        "base_url": "http://localhost:11434/v1",
        "headers": lambda s: {},
        "supports_tools": True,
        "supports_streaming": True,
        "no_auth": True,
    },
    ProviderType.LMSTUDIO: {
        "base_url": "http://localhost:1234/v1",
        "headers": lambda s: {},
        "supports_tools": True,
        "supports_streaming": True,
        "no_auth": True,
    },
}


class ModelRouter:
    """Routes requests through a chain of models with automatic failover across providers."""

    def __init__(self, settings: Optional[Settings] = None):
        self.settings = settings or get_settings()
        self._clients: Dict[str, httpx.AsyncClient] = {}
        self._model_chain = self.settings.get_model_chain()
        self.learning_engine = get_learning_engine()
        self._key_rotation_state: Dict[str, int] = {}

    def _get_client(self, base_url: str) -> httpx.AsyncClient:
        """Get or create HTTP client for a base URL."""
        if base_url not in self._clients:
            self._clients[base_url] = httpx.AsyncClient(
                timeout=httpx.Timeout(120.0, connect=10.0),
                limits=httpx.Limits(max_connections=20, max_keepalive_connections=5),
            )
        return self._clients[base_url]

    async def close(self):
        """Close all HTTP clients."""
        for client in self._clients.values():
            await client.aclose()
        self._clients.clear()

    def _get_provider_type(self, model: ModelConfig) -> ProviderType:
        """Determine provider type from model config."""
        provider = model.provider.lower()
        try:
            return ProviderType(provider)
        except ValueError:
            return ProviderType.CUSTOM

    def _get_provider_config(self, provider: ProviderType) -> dict:
        """Get provider configuration."""
        return PROVIDER_CONFIGS.get(provider, PROVIDER_CONFIGS[ProviderType.CUSTOM])

    def _get_headers(self, model: ModelConfig) -> dict:
        """Get headers for a specific model request."""
        provider = self._get_provider_type(model)
        config = self._get_provider_config(provider)

        # Local providers don't require auth
        if config.get("no_auth"):
            return {"Content-Type": "application/json"}

        # Get API key (with pool rotation)
        api_key = self.settings.get_api_key(model)
        if not api_key and provider != ProviderType.CUSTOM:
            raise ModelError(
                f"No API key found for model {model.name} (provider: {provider.value}). "
                f"Set {model.api_key_env} or corresponding API_KEY env var.",
                attempted_models=[model.name],
            )

        # Build headers using provider config
        if "headers" in config:
            headers = config["headers"](self.settings)
        else:
            headers = {"Content-Type": "application/json"}
            if api_key:
                headers["Authorization"] = f"Bearer {api_key}"

        return headers

    def _get_base_url(self, model: ModelConfig) -> str:
        """Get base URL for model."""
        provider = self._get_provider_type(model)
        config = self._get_provider_config(provider)
        return model.base_url or config.get("base_url", "https://openrouter.ai/api/v1")

    def _build_payload(self, model: ModelConfig, messages: list[ChatMessage], tools: Optional[list[dict]] = None) -> dict:
        """Build the request payload - handles provider-specific formats."""
        provider = self._get_provider_type(model)
        config = self._get_provider_config(provider)

        # Convert messages to provider format
        formatted_messages = [m.model_dump(exclude_none=True) for m in messages]

        if config.get("payload_transform") == "anthropic":
            # Anthropic format: separate system prompt, no tool_calls in messages
            system_prompt = ""
            anthropic_messages = []
            for msg in formatted_messages:
                if msg["role"] == "system":
                    system_prompt = msg["content"]
                else:
                    anthropic_messages.append(msg)

            payload = {
                "model": model.name,
                "messages": anthropic_messages,
                "max_tokens": model.max_tokens,
                "temperature": model.temperature,
            }
            if system_prompt:
                payload["system"] = system_prompt
            if tools:
                payload["tools"] = tools
                payload["tool_choice"] = "auto"
            return payload

        elif config.get("payload_transform") == "google":
            # Google Gemini format
            payload = {
                "contents": formatted_messages,
                "generationConfig": {
                    "maxOutputTokens": model.max_tokens,
                    "temperature": model.temperature,
                }
            }
            if tools:
                payload["tools"] = [{"function_declarations": tools}]
            return payload

        else:
            # OpenAI-compatible format (OpenRouter, OpenAI, Groq, etc.)
            payload = {
                "model": model.name,
                "messages": formatted_messages,
                "max_tokens": model.max_tokens,
                "temperature": model.temperature,
            }
            if tools:
                payload["tools"] = tools
                payload["tool_choice"] = "auto"
            return payload

    def _get_endpoint(self, model: ModelConfig, streaming: bool = False) -> str:
        """Get the API endpoint for a model."""
        base_url = self._get_base_url(model)
        provider = self._get_provider_type(model)
        config = self._get_provider_config(provider)

        if config.get("payload_transform") == "anthropic":
            return f"{base_url}/messages"
        elif config.get("payload_transform") == "google":
            api_key = self.settings.google_api_key
            key_param = f"?key={api_key}" if api_key else ""
            return f"{base_url}/models/{model.name}:{'streamGenerateContent' if streaming else 'generateContent'}{key_param}"
        else:
            return f"{base_url}/chat/completions"

    async def _try_model(
        self,
        model: ModelConfig,
        messages: list[ChatMessage],
        tools: Optional[list[dict]] = None,
        streaming: bool = False,
        task_type: str = "coding"
    ) -> ModelAttempt:
        """Attempt a single model with provider-specific handling."""
        start_time = time.time()
        provider = self._get_provider_type(model)

        try:
            client = self._get_client(self._get_base_url(model))
            headers = self._get_headers(model)
            payload = self._build_payload(model, messages, tools)
            endpoint = self._get_endpoint(model, streaming)

            if streaming:
                # Streaming handled separately
                return await self._try_model_stream(model, messages, tools, task_type)

            response = await client.post(
                endpoint,
                headers=headers,
                json=payload,
                timeout=model.timeout,
            )
            response.raise_for_status()
            data = response.json()

            latency_ms = (time.time() - start_time) * 1000

            # Parse response based on provider
            content, tool_calls, usage = self._parse_response(data, provider)

            chat_response = ChatResponse(
                content=content or "",
                tool_calls=tool_calls,
                model=model.name,
                usage=usage,
                latency_ms=latency_ms,
                provider=provider.value,
            )

            # Record success for learning
            tokens_used = usage.get("total_tokens", 0) if usage else 0
            self.learning_engine.record_model_result(
                model.name, task_type, True, latency_ms, tokens_used
            )

            return ModelAttempt(
                model=model.name,
                success=True,
                response=chat_response,
                latency_ms=latency_ms,
            )

        except httpx.HTTPStatusError as e:
            latency_ms = (time.time() - start_time) * 1000
            error_msg = f"HTTP {e.response.status_code}: {e.response.text}"
            logger.warning(f"Model {model.name} ({provider.value}) failed: {error_msg}")

            # Handle rate limiting - try key rotation
            if e.response.status_code == 429:
                rotated = await self._try_key_rotation(model, provider)
                if rotated:
                    return await self._try_model(model, messages, tools, streaming, task_type)

            self.learning_engine.record_model_result(
                model.name, task_type, False, latency_ms, 0
            )
            return ModelAttempt(
                model=model.name,
                success=False,
                error=ModelError(error_msg, [model.name], e),
                latency_ms=latency_ms,
            )

        except httpx.TimeoutException as e:
            latency_ms = (time.time() - start_time) * 1000
            logger.warning(f"Model {model.name} timed out")
            return ModelAttempt(
                model=model.name,
                success=False,
                error=ModelError(f"Timeout: {e}", [model.name], e),
                latency_ms=latency_ms,
            )

        except Exception as e:
            latency_ms = (time.time() - start_time) * 1000
            logger.warning(f"Model {model.name} error: {e}")
            return ModelAttempt(
                model=model.name,
                success=False,
                error=ModelError(str(e), [model.name], e),
                latency_ms=latency_ms,
            )

    async def _try_model_stream(
        self,
        model: ModelConfig,
        messages: list[ChatMessage],
        tools: Optional[list[dict]] = None,
        task_type: str = "coding"
    ) -> ModelAttempt:
        """Stream attempt - returns a special attempt that yields chunks."""
        # For streaming, we return a special marker - actual streaming in chat_stream
        return ModelAttempt(model=model.name, success=True, response=None)

    def _parse_response(self, data: dict, provider: ProviderType) -> tuple:
        """Parse response based on provider format."""
        if provider == ProviderType.ANTHROPIC:
            content = data.get("content", [{}])[0].get("text", "")
            tool_calls = None
            if "tool_use" in str(data.get("content", [])):
                tool_calls = [
                    {"id": tc.get("id"), "name": tc.get("name"), "arguments": tc.get("input")}
                    for tc in data.get("content", []) if tc.get("type") == "tool_use"
                ]
            usage = data.get("usage")
            return content, tool_calls, usage

        elif provider == ProviderType.GOOGLE:
            # Gemini format
            candidates = data.get("candidates", [{}])
            content = candidates[0].get("content", {}).get("parts", [{}])[0].get("text", "")
            usage = data.get("usageMetadata")
            return content, None, usage

        else:
            # OpenAI-compatible format
            choice = data["choices"][0]
            message = choice["message"]
            content = message.get("content", "") or ""
            tool_calls = message.get("tool_calls")
            usage = data.get("usage")
            return content, tool_calls, usage

    async def _try_key_rotation(self, model: ModelConfig, provider: ProviderType) -> bool:
        """Try rotating to next API key in pool on rate limit."""
        pool_key = f"{provider.value}_api_keys"
        pool = self.settings.get_key_pool(provider.value.lower())

        if not pool or len(pool) <= 1:
            return False

        current_idx = self._key_rotation_state.get(pool_key, 0)
        next_idx = (current_idx + 1) % len(pool)
        self._key_rotation_state[pool_key] = next_idx

        logger.info(f"Rotated {provider.value} API key to index {next_idx}")
        return True

    def _build_model_chain(self, preferred_model: Optional[str] = None, task_type: str = "coding") -> List[ModelConfig]:
        """Build model chain with dynamic re-ranking from learning engine."""
        chain = list(self._model_chain)

        # Apply role-based model selection
        role_model_map = {
            "planning": self.settings.planner_model,
            "coding": self.settings.coder_model,
            "reviewing": self.settings.reviewer_model,
            "search": self.settings.search_summarizer_model,
            "compacting": self.settings.compactor_model,
        }
        role_model = role_model_map.get(task_type)
        if role_model:
            # Move role-specific model to front
            chain = [m for m in chain if m.name == role_model] + [m for m in chain if m.name != role_model]

        # Apply learning-based re-ranking
        if self.settings.learning_enabled:
            rankings = self.learning_engine.get_model_rankings(task_type)
            if rankings:
                # Reorder by success rate
                ranked_names = [r[0] for r in rankings]
                chain = sorted(chain, key=lambda m: ranked_names.index(m.name) if m.name in ranked_names else 999)

        # Apply preferred model
        if preferred_model:
            chain = [m for m in chain if m.name == preferred_model] + [m for m in chain if m.name != preferred_model]

        # Apply routing rules from config
        for rule in self.settings.model_routing_rules:
            chain = self._apply_routing_rule(chain, rule)

        return chain

    def _apply_routing_rule(self, chain: List[ModelConfig], rule: str) -> List[ModelConfig]:
        """Apply a routing rule (simple DSL: 'use <model> for <task>')."""
        # Simple rule parsing - can be extended
        rule_lower = rule.lower().strip()
        if rule_lower.startswith("use "):
            parts = rule_lower.split(" for ")
            if len(parts) == 2:
                model_name = parts[0][4:].strip()
                # Move specified model to front for matching tasks
                chain = [m for m in chain if m.name == model_name] + [m for m in chain if m.name != model_name]
        return chain

    async def chat(
        self,
        messages: list[ChatMessage],
        tools: Optional[list[dict]] = None,
        preferred_model: Optional[str] = None,
        task_type: str = "coding",
    ) -> ChatResponse:
        """Send a chat request with automatic failover across all providers."""
        chain = self._build_model_chain(preferred_model, task_type)
        attempted = []
        last_error = None

        for model in chain:
            attempted.append(model.name)
            logger.info(f"Trying model: {model.name} (provider: {model.provider}, free={model.is_free})")

            attempt = await self._try_model(model, messages, tools, task_type=task_type)
            if attempt.success:
                logger.info(f"Success with model: {model.name} ({attempt.latency_ms:.0f}ms)")
                return attempt.response

            last_error = attempt.error

        # All models failed
        raise ModelError(
            f"All {len(attempted)} models failed. Last error: {last_error}",
            attempted_models=attempted,
            last_error=last_error,
        )

    async def chat_stream(
        self,
        messages: list[ChatMessage],
        tools: Optional[list[dict]] = None,
        preferred_model: Optional[str] = None,
        task_type: str = "coding",
    ):
        """Stream chat response with automatic failover."""
        chain = self._build_model_chain(preferred_model, task_type)

        for model in chain:
            logger.info(f"Trying model (stream): {model.name} (provider: {model.provider})")
            try:
                client = self._get_client(self._get_base_url(model))
                headers = self._get_headers(model)
                payload = {**self._build_payload(model, messages, tools), "stream": True}
                endpoint = self._get_endpoint(model, streaming=True)

                async with client.stream("POST", endpoint, headers=headers, json=payload, timeout=model.timeout) as response:
                    response.raise_for_status()
                    async for line in response.aiter_lines():
                        if line.startswith("data: "):
                            data = line[6:]
                            if data == "[DONE]":
                                yield "", None, model.name, True
                                return
                            import json
                            try:
                                chunk = json.loads(data)
                                content, tool_calls = self._parse_stream_chunk(chunk, self._get_provider_type(model))
                                if content or tool_calls:
                                    yield content, tool_calls, model.name, False
                            except json.JSONDecodeError:
                                continue
            except Exception as e:
                logger.warning(f"Stream model {model.name} failed: {e}")
                continue

        raise ModelError("All models failed for streaming", attempted_models=[m.name for m in chain])

    def _parse_stream_chunk(self, chunk: dict, provider: ProviderType) -> tuple:
        """Parse streaming chunk based on provider."""
        if provider == ProviderType.ANTHROPIC:
            if chunk.get("type") == "content_block_delta":
                delta = chunk.get("delta", {})
                return delta.get("text", ""), None
            return "", None

        elif provider == ProviderType.GOOGLE:
            candidates = chunk.get("candidates", [{}])
            content = candidates[0].get("content", {}).get("parts", [{}])[0].get("text", "")
            return content, None

        else:
            # OpenAI-compatible
            choices = chunk.get("choices", [{}])
            delta = choices[0].get("delta", {})
            content = delta.get("content", "")
            tool_calls = delta.get("tool_calls")
            return content, tool_calls

    def get_available_models(self) -> List[Dict[str, Any]]:
        """Get list of all configured models with metadata."""
        return [
            {
                "name": m.name,
                "provider": m.provider,
                "is_free": m.is_free,
                "priority": m.priority,
                "max_tokens": m.max_tokens,
            }
            for m in self._model_chain
        ]