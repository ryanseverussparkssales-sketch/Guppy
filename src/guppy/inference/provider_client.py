"""Provider abstraction layer for unified inference interface.

Enables interchangeable providers (local Ollama, Anthropic, OpenAI, Google, Cohere, Mistral)
with standardized health checks, cost tracking, and fallback chains.

Abstract Interface (ProviderClient):
    infer(prompt, system_prompt, model, **kwargs) -> (response_text, metadata)
    health_check() -> bool
    list_models() -> List[str]
    estimate_cost(prompt_tokens, completion_tokens) -> float

Concrete Implementations:
    LocalProviderClient - Ollama (via HTTP API)
    CloudProviderClient - Base for cloud providers (subclass for each provider)
"""

from __future__ import annotations

import asyncio
import json
import logging
import urllib.error
import urllib.request
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


@dataclass
class InferenceMetadata:
    """Metadata for inference execution."""
    provider: str
    model: str
    task_type: str  # simple, complex, teaching, code, vault
    latency_ms: float
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    cost: float = 0.0
    success: bool = True
    error: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to database-friendly dict."""
        return {
            "provider": self.provider,
            "model": self.model,
            "task_type": self.task_type,
            "latency_ms": self.latency_ms,
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "total_tokens": self.total_tokens,
            "cost": self.cost,
            "success": 1 if self.success else 0,
            "error": self.error,
            "timestamp": self.timestamp.isoformat(),
        }


class ProviderClient(ABC):
    """Abstract base class for all inference providers."""

    def __init__(self, provider_name: str, model: str, timeout: float = 30.0):
        """Initialize provider client.

        Args:
            provider_name: "local", "anthropic", "openai", "google", "cohere", "mistral"
            model: Model ID/name for this provider
            timeout: Request timeout in seconds
        """
        self.provider_name = provider_name
        self.model = model
        self.timeout = timeout
        self._health_check_cache: Optional[Tuple[bool, float]] = None
        self._health_check_cache_ttl = 5.0  # 5 second cache
        self._last_health_check = 0.0

    @abstractmethod
    async def infer(
        self,
        prompt: str,
        system_prompt: str = "",
        task_type: str = "simple",
        **kwargs,
    ) -> Tuple[str, InferenceMetadata]:
        """Execute inference on this provider.

        Args:
            prompt: User message / request
            system_prompt: System context
            task_type: Task classification (simple, complex, teaching, etc.)
            **kwargs: Provider-specific options (temperature, max_tokens, etc.)

        Returns:
            (response_text, metadata)

        Raises:
            TimeoutError: If request exceeds timeout
            RuntimeError: If provider unavailable
        """
        pass

    @abstractmethod
    async def health_check(self) -> bool:
        """Check if provider is available and responding.

        Returns:
            True if healthy, False otherwise
        """
        pass

    @abstractmethod
    async def list_models(self) -> List[str]:
        """List available models from this provider.

        Returns:
            List of model IDs/names
        """
        pass

    @abstractmethod
    def estimate_cost(
        self,
        prompt_tokens: int,
        completion_tokens: int,
    ) -> float:
        """Estimate cost in USD for this inference.

        Args:
            prompt_tokens: Input token count
            completion_tokens: Output token count

        Returns:
            Estimated cost in USD
        """
        pass

    def _get_cached_health(self) -> Optional[bool]:
        """Check health cache; return cached result if still valid."""
        if self._health_check_cache is None:
            return None
        healthy, timestamp = self._health_check_cache
        if time.time() - timestamp < self._health_check_cache_ttl:
            return healthy
        self._health_check_cache = None
        return None

    def _cache_health(self, healthy: bool) -> None:
        """Cache health check result with timestamp."""
        self._health_check_cache = (healthy, time.time())


class LocalProviderClient(ProviderClient):
    """Ollama local inference provider."""

    OLLAMA_API_BASE = "http://127.0.0.1:11434/api"

    def __init__(
        self,
        model: str = "guppy",
        timeout: float = 60.0,
        ollama_base_url: Optional[str] = None,
    ):
        """Initialize Ollama client.

        Args:
            model: Model name (e.g., "guppy", "guppy-fast", "guppy-teach")
            timeout: Request timeout in seconds (local models can take longer)
            ollama_base_url: Override default Ollama base URL
        """
        super().__init__("local", model, timeout)
        self.ollama_base_url = ollama_base_url or self.OLLAMA_API_BASE
        self._local_models_cache: Optional[List[str]] = None

    async def infer(
        self,
        prompt: str,
        system_prompt: str = "",
        task_type: str = "simple",
        **kwargs,
    ) -> Tuple[str, InferenceMetadata]:
        """Call Ollama via HTTP API."""
        start_time = time.time()
        metadata = InferenceMetadata(
            provider="local",
            model=self.model,
            task_type=task_type,
            latency_ms=0.0,
        )

        try:
            # Ollama chat endpoint
            url = f"{self.ollama_base_url}/chat"
            request_payload = {
                "model": self.model,
                "messages": [
                    {"role": "system", "content": system_prompt} if system_prompt else None,
                    {"role": "user", "content": prompt},
                ],
                "stream": False,
                "temperature": kwargs.get("temperature", 0.7),
                "num_predict": kwargs.get("num_predict", 512),
            }
            # Remove None messages
            request_payload["messages"] = [m for m in request_payload["messages"] if m]

            request_data = json.dumps(request_payload).encode("utf-8")
            request = urllib.request.Request(
                url,
                data=request_data,
                headers={"Content-Type": "application/json"},
            )

            # Execute with timeout
            loop = asyncio.get_event_loop()
            response_text = await asyncio.wait_for(
                loop.run_in_executor(
                    None,
                    self._make_request,
                    request,
                ),
                timeout=self.timeout,
            )

            metadata.success = True
            metadata.latency_ms = (time.time() - start_time) * 1000
            return response_text, metadata

        except asyncio.TimeoutError:
            metadata.success = False
            metadata.error = f"Ollama timeout after {self.timeout}s"
            metadata.latency_ms = (time.time() - start_time) * 1000
            logger.warning(f"[LOCAL] {metadata.error}")
            raise TimeoutError(metadata.error)

        except Exception as e:
            metadata.success = False
            metadata.error = str(e)
            metadata.latency_ms = (time.time() - start_time) * 1000
            logger.error(f"[LOCAL] Inference failed: {e}")
            raise RuntimeError(f"Ollama inference error: {e}")

    @staticmethod
    def _make_request(request: urllib.request.Request) -> str:
        """Execute HTTP request (sync wrapper for executor)."""
        with urllib.request.urlopen(request, timeout=10) as response:
            data = json.loads(response.read().decode("utf-8"))
            # Ollama returns message.content
            if "message" in data and "content" in data["message"]:
                return data["message"]["content"]
            return ""

    async def health_check(self) -> bool:
        """Check if Ollama is responding via lightweight endpoint.

        Uses GET /api/v1/models (model listing) instead of inference.
        Expected latency: 20-50ms vs 500-2000ms for minimal inference.
        """
        cached = self._get_cached_health()
        if cached is not None:
            return cached

        try:
            # Phase 4a: Use lightweight /api/v1/models endpoint instead of inference
            url = f"{self.ollama_base_url}/v1/models"
            request = urllib.request.Request(url)
            loop = asyncio.get_event_loop()
            result = await asyncio.wait_for(
                loop.run_in_executor(None, self._make_health_request, request),
                timeout=2.0,
            )
            self._cache_health(result)
            return result
        except Exception:
            self._cache_health(False)
            return False

    @staticmethod
    def _make_health_request(request: urllib.request.Request) -> bool:
        """Execute health check (sync wrapper for executor).

        Phase 4a: Check connectivity via lightweight endpoint.
        """
        try:
            with urllib.request.urlopen(request, timeout=2) as response:
                return response.status == 200
        except Exception:
            return False

    async def list_models(self) -> List[str]:
        """List available models from Ollama."""
        if self._local_models_cache is not None:
            return self._local_models_cache

        try:
            url = f"{self.ollama_base_url}/tags"
            request = urllib.request.Request(url)
            loop = asyncio.get_event_loop()
            models = await asyncio.wait_for(
                loop.run_in_executor(None, self._fetch_models, request),
                timeout=2.0,
            )
            self._local_models_cache = models
            return models
        except Exception as e:
            logger.warning(f"[LOCAL] Failed to list models: {e}")
            return []

    @staticmethod
    def _fetch_models(request: urllib.request.Request) -> List[str]:
        """Fetch model list from Ollama (sync wrapper)."""
        try:
            with urllib.request.urlopen(request, timeout=2) as response:
                data = json.loads(response.read().decode("utf-8"))
                # Ollama returns {"models": [{"name": "...", "size": ..., ...}]}
                if "models" in data:
                    return [m["name"] for m in data["models"]]
                return []
        except Exception:
            return []

    def estimate_cost(self, prompt_tokens: int, completion_tokens: int) -> float:
        """Local inference is free."""
        return 0.0


class CloudProviderClient(ProviderClient):
    """Base class for cloud provider clients (Anthropic, OpenAI, Google, Cohere, Mistral).

    Subclass this for each provider with:
        - Provider-specific API client initialization in __init__
        - API-specific infer() implementation
        - _lightweight_health_check() via lightweight API endpoint (not inference)
        - list_models() from provider model catalog
        - estimate_cost() based on provider pricing

    Health Checks: Phase 4a introduces lightweight health checks using real but cheap endpoints
    instead of minimal inference. Each provider implements _lightweight_health_check() using:
        - Model listing endpoints (fast, free/included)
        - Connectivity checks (OPTIONS/HEAD requests)
        - No token consumption or billing impact

    Example subclass:

        class AnthropicClient(CloudProviderClient):
            def __init__(self, api_key, model="claude-opus-4-6", timeout=30):
                super().__init__("anthropic", model, timeout)
                import anthropic
                self.client = anthropic.Anthropic(api_key=api_key)

            async def _lightweight_health_check(self) -> bool:
                # Check via OPTIONS request (no inference needed)
                ...
    """

    def __init__(
        self,
        provider_name: str,
        model: str,
        api_key: str,
        timeout: float = 30.0,
    ):
        """Initialize cloud provider client.

        Args:
            provider_name: "anthropic", "openai", "google", "cohere", "mistral"
            model: Model ID for this provider
            api_key: API authentication key
            timeout: Request timeout in seconds
        """
        super().__init__(provider_name, model, timeout)
        self.api_key = api_key

    async def infer(
        self,
        prompt: str,
        system_prompt: str = "",
        task_type: str = "simple",
        **kwargs,
    ) -> Tuple[str, InferenceMetadata]:
        """Execute inference via cloud API.

        Must be implemented by subclass.
        """
        raise NotImplementedError(f"Subclass must implement infer()")

    @abstractmethod
    async def _lightweight_health_check(self) -> bool:
        """Check provider health via lightweight endpoint (not inference).

        Phase 4a: Each provider must implement a health check using a real but cheap endpoint:
        - Model listing endpoints (included in API quota)
        - Connectivity checks (OPTIONS/HEAD requests)
        - No token consumption or billing impact

        Expected latencies: 30-100ms per provider (was 500-2000ms via minimal inference)

        Returns:
            True if provider is reachable and responding, False otherwise.
        """
        raise NotImplementedError(f"Subclass must implement _lightweight_health_check()")

    async def health_check(self) -> bool:
        """Check cloud provider health via lightweight endpoint.

        Delegates to _lightweight_health_check() with caching.
        """
        cached = self._get_cached_health()
        if cached is not None:
            return cached

        try:
            result = await self._lightweight_health_check()
            self._cache_health(result)
            return result
        except Exception as e:
            logger.debug(f"[{self.provider_name.upper()}] Health check failed: {e}")
            self._cache_health(False)
            return False

    async def list_models(self) -> List[str]:
        """List available models from cloud provider.

        Override in subclass with actual API model listing.
        """
        return [self.model]  # Fallback: just return configured model

    def estimate_cost(self, prompt_tokens: int, completion_tokens: int) -> float:
        """Estimate cost based on provider pricing.

        Override in subclass with actual pricing rates.

        Standard pricing (as of 2026-04):
            - Anthropic Haiku: $0.80 / 1M input, $4 / 1M output
            - Anthropic Sonnet: $3 / 1M input, $15 / 1M output
            - OpenAI GPT-4o: $5 / 1M input, $15 / 1M output
            - Google Gemini: $0.075 / 1M input, $0.3 / 1M output
        """
        return 0.0  # Placeholder; override in subclass
