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
    """Unified local inference provider — delegates to local_client for all backends.

    Supports every backend registered in local_client._BACKENDS:
      - "ollama"         — Ollama (default, native format)
      - "lmstudio"       — LM Studio (OpenAI-compat)
      - "lemonade"       — Lemonade (OpenAI-compat)
      - "llamacpp-gemma" — llama.cpp Gemma 4 E4B server (port 8080)
      - "llamacpp-qwen3" — llama.cpp Qwen3 35B server (port 8083)
      - "llamacpp-pepe"  — llama.cpp Pepe 8B server (port 8082)
      - "local_harness"  — Generic OpenAI-compat harness

    All HTTP logic, circuit breaking, retries, and payload formatting live in
    local_client.py — this class is a thin async wrapper over that sync API.
    """

    def __init__(
        self,
        model: str = "guppy",
        timeout: float = 60.0,
        backend: str = "ollama",
    ):
        """Initialise local backend client.

        Args:
            model:   Model name to request (or logical name like "gemma-4-heretic-ara").
            timeout: Request timeout in seconds.
            backend: Backend key from local_client._BACKENDS (e.g. "llamacpp-qwen3").
        """
        super().__init__("local", model, timeout)
        self.backend = backend

    async def infer(
        self,
        prompt: str,
        system_prompt: str = "",
        task_type: str = "simple",
        **kwargs,
    ) -> Tuple[str, InferenceMetadata]:
        """Execute inference via local_client.local_chat()."""
        from .local_client import local_chat

        start_time = time.time()
        metadata = InferenceMetadata(
            provider=f"local/{self.backend}",
            model=self.model,
            task_type=task_type,
            latency_ms=0.0,
        )

        messages: List[Dict[str, Any]] = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        num_predict = int(kwargs.get("num_predict", kwargs.get("max_tokens", 512)))

        try:
            loop = asyncio.get_event_loop()
            result = await asyncio.wait_for(
                loop.run_in_executor(
                    None,
                    lambda: local_chat(
                        self.model,
                        messages,
                        backend=self.backend,
                        timeout=int(self.timeout),
                        num_predict=num_predict,
                    ),
                ),
                timeout=self.timeout + 5,  # outer guard slightly above inner
            )

            if result is None:
                raise RuntimeError(f"[{self.backend}] no response (circuit open or parse failure)")

            response_text = str(result.get("response", "") or "")
            metadata.success = True
            metadata.latency_ms = (time.time() - start_time) * 1000
            return response_text, metadata

        except asyncio.TimeoutError:
            metadata.success = False
            metadata.error = f"{self.backend} timeout after {self.timeout}s"
            metadata.latency_ms = (time.time() - start_time) * 1000
            logger.warning(f"[LOCAL/{self.backend}] {metadata.error}")
            raise TimeoutError(metadata.error)

        except Exception as e:
            metadata.success = False
            metadata.error = str(e)
            metadata.latency_ms = (time.time() - start_time) * 1000
            logger.error(f"[LOCAL/{self.backend}] Inference failed: {e}")
            raise RuntimeError(f"{self.backend} inference error: {e}")

    async def health_check(self) -> bool:
        """Probe backend liveness via probe_backends() (lightweight, no inference)."""
        cached = self._get_cached_health()
        if cached is not None:
            return cached

        try:
            from .local_client import probe_backends
            loop = asyncio.get_event_loop()
            results = await asyncio.wait_for(
                loop.run_in_executor(None, lambda: probe_backends(timeout=1.5)),
                timeout=3.0,
            )
            healthy = bool(results.get(self.backend, False))
            self._cache_health(healthy)
            return healthy
        except Exception:
            self._cache_health(False)
            return False

    async def list_models(self) -> List[str]:
        """List models available on this backend."""
        try:
            from .local_client import list_local_models
            loop = asyncio.get_event_loop()
            return await asyncio.wait_for(
                loop.run_in_executor(None, lambda: list_local_models(backend=self.backend)),
                timeout=3.0,
            )
        except Exception as e:
            logger.warning(f"[LOCAL/{self.backend}] list_models failed: {e}")
            return []

    def estimate_cost(self, prompt_tokens: int, completion_tokens: int) -> float:
        """Local inference is always free."""
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
