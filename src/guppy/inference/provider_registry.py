"""Provider registry and factory for unified inference provider management.

Manages provider configurations from settings database, coordinates provider
lifecycle, and builds dynamic fallback chains based on enabled providers.

Registry Pattern:
    - Loads provider configs from SQLite settings DB
    - Maintains instance cache of ProviderClient objects
    - Supports enable/disable toggling at runtime
    - Tracks health status with cached checks
    - Builds priority chains for automatic fallback
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Set, Tuple

from .provider_client import (
    ProviderClient,
    LocalProviderClient,
    CloudProviderClient,
    InferenceMetadata,
)
from .provider_clients_cloud import (
    AnthropicClient,
    OpenAIClient,
    GoogleClient,
    CohereClient,
    MistralClient,
)

logger = logging.getLogger(__name__)


@dataclass
class ProviderConfig:
    """Configuration for a single provider."""
    id: str  # "local", "anthropic", "openai", "google", "cohere", "mistral"
    name: str  # Display name
    is_enabled: bool
    priority_order: int  # Lower = higher priority
    timeout_seconds: float
    retry_limit: int  # How many times to retry on timeout
    cost_per_1k_tokens: Optional[float] = None  # For estimation
    api_key: Optional[str] = None
    model_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to database-friendly dict."""
        return {
            "id": self.id,
            "name": self.name,
            "is_enabled": 1 if self.is_enabled else 0,
            "priority_order": self.priority_order,
            "timeout_seconds": self.timeout_seconds,
            "retry_limit": self.retry_limit,
            "cost_per_1k_tokens": self.cost_per_1k_tokens,
            "api_key": self.api_key,
            "model_id": self.model_id,
            "metadata": json.dumps(self.metadata),
        }


@dataclass
class ProviderHealth:
    """Health status for a provider."""
    provider_id: str
    is_healthy: bool
    last_check: datetime
    error_message: Optional[str] = None
    consecutive_failures: int = 0


class ProviderRegistry:
    """Registry and factory for all inference providers.

    Coordinates provider lifecycle, builds fallback chains, tracks health,
    and manages the provider client instance pool.
    """

    # Default provider configurations (can be overridden by settings DB)
    DEFAULT_CONFIGS = {
        "local": ProviderConfig(
            id="local",
            name="Local (Ollama)",
            is_enabled=True,
            priority_order=10,  # Highest priority
            timeout_seconds=60.0,
            retry_limit=0,  # Local doesn't fall back
            cost_per_1k_tokens=0.0,
            model_id=os.environ.get("OLLAMA_MODEL", "guppy"),
        ),
        "anthropic": ProviderConfig(
            id="anthropic",
            name="Anthropic (Claude)",
            is_enabled=bool(os.environ.get("ANTHROPIC_API_KEY", "").strip()),
            priority_order=20,
            timeout_seconds=30.0,
            retry_limit=2,
            cost_per_1k_tokens=None,  # Variable by model
            api_key=os.environ.get("ANTHROPIC_API_KEY", "").strip(),
            model_id=os.environ.get("ANTHROPIC_MODEL", "claude-opus-4-6"),
        ),
        "openai": ProviderConfig(
            id="openai",
            name="OpenAI (GPT)",
            is_enabled=bool(os.environ.get("OPENAI_API_KEY", "").strip()),
            priority_order=25,
            timeout_seconds=30.0,
            retry_limit=2,
            cost_per_1k_tokens=None,
            api_key=os.environ.get("OPENAI_API_KEY", "").strip(),
            model_id=os.environ.get("OPENAI_MODEL", "gpt-4o-mini"),
        ),
        "google": ProviderConfig(
            id="google",
            name="Google (Gemini)",
            is_enabled=bool(os.environ.get("GOOGLE_API_KEY", "").strip()),
            priority_order=26,
            timeout_seconds=30.0,
            retry_limit=2,
            cost_per_1k_tokens=None,
            api_key=os.environ.get("GOOGLE_API_KEY", "").strip(),
            model_id=os.environ.get("GOOGLE_MODEL", "gemini-2.0-flash"),
        ),
        "cohere": ProviderConfig(
            id="cohere",
            name="Cohere",
            is_enabled=bool(os.environ.get("COHERE_API_KEY", "").strip()),
            priority_order=27,
            timeout_seconds=30.0,
            retry_limit=2,
            cost_per_1k_tokens=None,
            api_key=os.environ.get("COHERE_API_KEY", "").strip(),
            model_id=os.environ.get("COHERE_MODEL", "command-r-plus-08-2024"),
        ),
        "mistral": ProviderConfig(
            id="mistral",
            name="Mistral",
            is_enabled=bool(os.environ.get("MISTRAL_API_KEY", "").strip()),
            priority_order=28,
            timeout_seconds=30.0,
            retry_limit=2,
            cost_per_1k_tokens=None,
            api_key=os.environ.get("MISTRAL_API_KEY", "").strip(),
            model_id=os.environ.get("MISTRAL_MODEL", "mistral-large-latest"),
        ),
    }

    def __init__(self, settings_db=None):
        """Initialize registry.

        Args:
            settings_db: Optional settings database connection for persisting configs.
                        If None, uses default configs only.
        """
        self.settings_db = settings_db
        self._configs: Dict[str, ProviderConfig] = {}
        self._clients: Dict[str, ProviderClient] = {}
        self._health: Dict[str, ProviderHealth] = {}
        self._lock = asyncio.Lock()

        # Load initial configurations
        self._load_configs()

    def _load_configs(self) -> None:
        """Load provider configurations from defaults + settings DB."""
        # Start with defaults
        self._configs = {k: v for k, v in self.DEFAULT_CONFIGS.items()}

        # Override with settings DB if available
        if self.settings_db:
            try:
                # TODO: Implement settings DB query to load provider configs
                # db_configs = self.settings_db.get_provider_configs()
                # for cfg in db_configs:
                #     self._configs[cfg.id] = cfg
                pass
            except Exception as e:
                logger.warning(f"[REGISTRY] Failed to load configs from settings DB: {e}")

        # Initialize health tracking for all providers
        now = datetime.utcnow()
        for provider_id in self._configs:
            self._health[provider_id] = ProviderHealth(
                provider_id=provider_id,
                is_healthy=False,  # Will be checked on demand
                last_check=now,
            )

    def get_config(self, provider_id: str) -> Optional[ProviderConfig]:
        """Get configuration for a provider."""
        return self._configs.get(provider_id)

    async def get_client(self, provider_id: str) -> Optional[ProviderClient]:
        """Get or create a provider client.

        Returns None if provider is disabled or configuration missing.
        """
        async with self._lock:
            # Return cached client if available
            if provider_id in self._clients:
                return self._clients[provider_id]

            # Get config
            config = self.get_config(provider_id)
            if not config or not config.is_enabled:
                return None

            # Create new client based on provider type
            try:
                if provider_id == "local":
                    client = LocalProviderClient(
                        model=config.model_id or "guppy",
                        timeout=config.timeout_seconds,
                    )
                elif provider_id == "anthropic":
                    # Cloud providers need API key
                    if not config.api_key:
                        logger.warning(f"[REGISTRY] {provider_id} enabled but no API key")
                        return None
                    client = AnthropicClient(
                        api_key=config.api_key,
                        model=config.model_id or "claude-opus-4-6",
                        timeout=config.timeout_seconds,
                    )
                elif provider_id == "openai":
                    if not config.api_key:
                        logger.warning(f"[REGISTRY] {provider_id} enabled but no API key")
                        return None
                    client = OpenAIClient(
                        api_key=config.api_key,
                        model=config.model_id or "gpt-4o-mini",
                        timeout=config.timeout_seconds,
                    )
                elif provider_id == "google":
                    if not config.api_key:
                        logger.warning(f"[REGISTRY] {provider_id} enabled but no API key")
                        return None
                    client = GoogleClient(
                        api_key=config.api_key,
                        model=config.model_id or "gemini-2.0-flash",
                        timeout=config.timeout_seconds,
                    )
                elif provider_id == "cohere":
                    if not config.api_key:
                        logger.warning(f"[REGISTRY] {provider_id} enabled but no API key")
                        return None
                    client = CohereClient(
                        api_key=config.api_key,
                        model=config.model_id or "command-r-plus-08-2024",
                        timeout=config.timeout_seconds,
                    )
                elif provider_id == "mistral":
                    if not config.api_key:
                        logger.warning(f"[REGISTRY] {provider_id} enabled but no API key")
                        return None
                    client = MistralClient(
                        api_key=config.api_key,
                        model=config.model_id or "mistral-large-latest",
                        timeout=config.timeout_seconds,
                    )
                else:
                    logger.warning(f"[REGISTRY] Unknown provider: {provider_id}")
                    return None

                self._clients[provider_id] = client
                logger.info(f"[REGISTRY] Created client for {provider_id}")
                return client

            except Exception as e:
                logger.error(f"[REGISTRY] Failed to create {provider_id} client: {e}")
                return None

    async def set_enabled(self, provider_id: str, enabled: bool) -> bool:
        """Enable or disable a provider."""
        async with self._lock:
            config = self._configs.get(provider_id)
            if not config:
                return False

            config.is_enabled = enabled

            # Disconnect client if disabling
            if not enabled:
                self._clients.pop(provider_id, None)
                logger.info(f"[REGISTRY] Disabled {provider_id}")
            else:
                # Pre-create client on enable
                await self.get_client(provider_id)

            # TODO: Persist to settings DB
            return True

    async def health_check_all(self) -> Dict[str, bool]:
        """Check health of all enabled providers."""
        results = {}
        for provider_id, config in self._configs.items():
            if not config.is_enabled:
                results[provider_id] = False
                continue

            healthy = await self.health_check(provider_id)
            results[provider_id] = healthy

        return results

    async def health_check(self, provider_id: str) -> bool:
        """Check health of a single provider."""
        async with self._lock:
            # Check cache first
            health = self._health.get(provider_id)
            if health and (datetime.utcnow() - health.last_check) < timedelta(seconds=5):
                return health.is_healthy

            # Get or create client
            client = await self.get_client(provider_id)
            if not client:
                healthy = False
                error = "No client available"
            else:
                try:
                    healthy = await asyncio.wait_for(client.health_check(), timeout=3.0)
                    error = None if healthy else "Health check returned False"
                except asyncio.TimeoutError:
                    healthy = False
                    error = "Health check timeout"
                except Exception as e:
                    healthy = False
                    error = str(e)

            # Update health status
            if provider_id not in self._health:
                self._health[provider_id] = ProviderHealth(
                    provider_id=provider_id,
                    is_healthy=healthy,
                    last_check=datetime.utcnow(),
                    error_message=error,
                )
            else:
                health = self._health[provider_id]
                if healthy:
                    health.consecutive_failures = 0
                else:
                    health.consecutive_failures += 1
                health.is_healthy = healthy
                health.last_check = datetime.utcnow()
                health.error_message = error

            if not healthy:
                logger.debug(f"[REGISTRY] {provider_id} unhealthy: {error}")

            return healthy

    def build_fallback_chain(
        self,
        task_type: str = "simple",
        exclude: Optional[Set[str]] = None,
    ) -> List[str]:
        """Build provider fallback chain for a task type.

        Returns list of provider IDs sorted by priority, filtered by:
        - is_enabled = True
        - is_healthy (from last check)
        - not in exclude set

        Args:
            task_type: Task classification (simple, complex, teaching, etc.)
            exclude: Set of provider IDs to skip

        Returns:
            List of provider IDs in fallback order
        """
        exclude = exclude or set()
        candidates = []

        for provider_id, config in sorted(
            self._configs.items(),
            key=lambda x: x[1].priority_order,
        ):
            # Skip disabled, excluded, or unhealthy
            if not config.is_enabled:
                continue
            if provider_id in exclude:
                continue

            health = self._health.get(provider_id)
            if health and not health.is_healthy:
                # Skip providers with consecutive failures
                if health.consecutive_failures > 2:
                    continue

            candidates.append(provider_id)

        return candidates

    async def infer_with_fallback(
        self,
        prompt: str,
        system_prompt: str = "",
        task_type: str = "simple",
        preferred_model: Optional[str] = None,
        **kwargs,
    ) -> Tuple[str, InferenceMetadata]:
        """Execute inference with automatic fallback chain.

        Tries providers in order until one succeeds or retries exhausted.

        Args:
            prompt: User message
            system_prompt: System context
            task_type: Task classification
            preferred_model: Preferred provider ID (will be tried first)
            **kwargs: Additional inference options

        Returns:
            (response_text, metadata)

        Raises:
            RuntimeError: If all providers fail or chain is empty
        """
        # Build fallback chain with preferred provider first
        chain = self.build_fallback_chain(task_type)

        if preferred_model and preferred_model in chain:
            # Move preferred to front
            chain.remove(preferred_model)
            chain.insert(0, preferred_model)

        if not chain:
            raise RuntimeError(f"No available providers for task_type={task_type}")

        last_error: Optional[Exception] = None

        for provider_id in chain:
            client = await self.get_client(provider_id)
            if not client:
                continue

            config = self._configs[provider_id]
            retry_count = 0

            while retry_count <= config.retry_limit:
                try:
                    response, metadata = await asyncio.wait_for(
                        client.infer(
                            prompt=prompt,
                            system_prompt=system_prompt,
                            task_type=task_type,
                            **kwargs,
                        ),
                        timeout=client.timeout,
                    )
                    logger.info(
                        f"[REGISTRY] Inference succeeded via {provider_id} "
                        f"({metadata.latency_ms:.0f}ms)"
                    )
                    return response, metadata

                except asyncio.TimeoutError:
                    last_error = TimeoutError(
                        f"{provider_id} timeout after {client.timeout}s"
                    )
                    retry_count += 1
                    if retry_count <= config.retry_limit:
                        logger.debug(
                            f"[REGISTRY] {provider_id} timeout, retry {retry_count}/{config.retry_limit}"
                        )
                    else:
                        logger.debug(f"[REGISTRY] {provider_id} failed after {config.retry_limit} retries")
                        break

                except Exception as e:
                    last_error = e
                    logger.debug(f"[REGISTRY] {provider_id} failed: {e}")
                    break  # Don't retry non-timeout errors

        # All providers exhausted
        raise RuntimeError(
            f"All providers failed for task_type={task_type}. "
            f"Last error: {last_error}"
        )

    def get_status(self) -> Dict[str, Any]:
        """Get registry status for diagnostics."""
        return {
            "providers": {
                provider_id: {
                    "enabled": config.is_enabled,
                    "priority": config.priority_order,
                    "healthy": self._health[provider_id].is_healthy,
                    "cached": provider_id in self._clients,
                    "timeout": config.timeout_seconds,
                }
                for provider_id, config in self._configs.items()
            },
            "fallback_chains": {
                task_type: self.build_fallback_chain(task_type)
                for task_type in ["simple", "complex", "teaching"]
            },
        }


# Global registry instance
_registry: Optional[ProviderRegistry] = None


def get_provider_registry(settings_db=None) -> ProviderRegistry:
    """Get or create the global provider registry."""
    global _registry
    if _registry is None:
        _registry = ProviderRegistry(settings_db)
    return _registry
