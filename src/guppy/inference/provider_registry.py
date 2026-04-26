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
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from utils.db_utils import open_db
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

_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS provider_configs (
    id              TEXT PRIMARY KEY,
    is_enabled      INTEGER NOT NULL DEFAULT 1,
    model_id        TEXT,
    priority_order  INTEGER
);
"""

_DEFAULT_DB_PATH = Path(
    os.environ.get("GUPPY_PROVIDER_DB", "runtime/settings/provider_configs.sqlite3")
)


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

    # Task-type → ordered list of preferred provider IDs.
    # The registry uses this to front-load the best provider for the job
    # before falling back through the priority-order chain.
    TASK_TYPE_PREFERRED_PROVIDERS: Dict[str, List[str]] = {
        "simple":   ["llamacpp-pepe",  "local", "anthropic", "openai", "google"],
        "complex":  ["llamacpp-qwen3", "local", "anthropic", "openai", "google"],
        "teaching": ["local", "llamacpp-qwen3", "anthropic", "openai"],
        "code":     ["local", "llamacpp-qwen3", "anthropic", "openai"],
        "vision":   ["llamacpp-gemma", "local", "anthropic", "openai"],
        "vault":    ["local", "llamacpp-qwen3"],
    }

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
        # ── llama.cpp (ROCm/HIP) servers — one per model ──────────────────────
        # is_enabled=True; servers not running will fail health checks and be
        # skipped automatically — no manual toggling needed.
        "llamacpp-gemma": ProviderConfig(
            id="llamacpp-gemma",
            name="llama.cpp — Gemma 4 E4B Heretic ARA",
            is_enabled=True,
            priority_order=11,
            timeout_seconds=90.0,
            retry_limit=0,
            cost_per_1k_tokens=0.0,
            model_id=os.environ.get("LLAMACPP_GEMMA_MODEL", "gemma-4-heretic-ara"),
        ),
        "llamacpp-qwen3": ProviderConfig(
            id="llamacpp-qwen3",
            name="llama.cpp — Qwen3 35B MoE (Uncensored)",
            is_enabled=True,
            priority_order=12,
            timeout_seconds=120.0,
            retry_limit=0,
            cost_per_1k_tokens=0.0,
            model_id=os.environ.get("LLAMACPP_QWEN3_MODEL", "qwen3-35b-uncensored"),
        ),
        "llamacpp-pepe": ProviderConfig(
            id="llamacpp-pepe",
            name="llama.cpp — Assistant Pepe 8B",
            is_enabled=True,
            priority_order=13,
            timeout_seconds=60.0,
            retry_limit=0,
            cost_per_1k_tokens=0.0,
            model_id=os.environ.get("LLAMACPP_PEPE_MODEL", "assistant-pepe-8b"),
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

        # Merge persisted overrides (is_enabled, model_id, priority_order) from settings DB.
        if self.settings_db:
            try:
                with open_db(self.settings_db, schema_sql=_SCHEMA_SQL) as conn:
                    rows = conn.execute(
                        "SELECT id, is_enabled, model_id, priority_order FROM provider_configs"
                    ).fetchall()
                for row_id, is_enabled, model_id, priority_order in rows:
                    cfg = self._configs.get(row_id)
                    if cfg is None:
                        continue
                    cfg.is_enabled = bool(is_enabled)
                    if model_id is not None:
                        cfg.model_id = model_id
                    if priority_order is not None:
                        cfg.priority_order = priority_order
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
                        backend="ollama",
                    )
                elif provider_id in {"llamacpp-gemma", "llamacpp-qwen3", "llamacpp-pepe"}:
                    client = LocalProviderClient(
                        model=config.model_id or provider_id,
                        timeout=config.timeout_seconds,
                        backend=provider_id,  # routes to correct llama.cpp server
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

            if self.settings_db:
                try:
                    with open_db(self.settings_db, schema_sql=_SCHEMA_SQL) as conn:
                        conn.execute(
                            "INSERT INTO provider_configs (id, is_enabled) VALUES (?, ?)"
                            " ON CONFLICT(id) DO UPDATE SET is_enabled=excluded.is_enabled",
                            (provider_id, 1 if enabled else 0),
                        )
                        conn.commit()
                except Exception as e:
                    logger.warning(f"[REGISTRY] Failed to persist {provider_id} enabled={enabled}: {e}")
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

    def get_preferred_for_task(self, task_type: str) -> Optional[str]:
        """Return the highest-priority *healthy* preferred provider for a task type.

        Scans TASK_TYPE_PREFERRED_PROVIDERS in order and returns the first that is
        both enabled and healthy (from the last cached health check).  Returns None
        if no preferred provider is currently available.
        """
        preferred = self.TASK_TYPE_PREFERRED_PROVIDERS.get(task_type, [])
        for provider_id in preferred:
            config = self._configs.get(provider_id)
            if not config or not config.is_enabled:
                continue
            health = self._health.get(provider_id)
            # Accept providers with no health record yet (will be checked on first use)
            # or those that are healthy.
            if health is None or health.is_healthy:
                return provider_id
        return None

    def build_fallback_chain(
        self,
        task_type: str = "simple",
        exclude: Optional[Set[str]] = None,
    ) -> List[str]:
        """Build provider fallback chain for a task type.

        Returns list of provider IDs ordered by:
          1. Task-type preference (TASK_TYPE_PREFERRED_PROVIDERS)
          2. Priority order (lower number = higher priority)

        Filtered by: is_enabled, not excluded, not repeatedly failing.

        Args:
            task_type: Task classification (simple, complex, teaching, etc.)
            exclude: Set of provider IDs to skip

        Returns:
            List of provider IDs in fallback order
        """
        exclude = exclude or set()

        # Collect eligible providers, honouring health / enable state
        eligible: List[str] = []
        for provider_id, config in sorted(
            self._configs.items(),
            key=lambda x: x[1].priority_order,
        ):
            if not config.is_enabled or provider_id in exclude:
                continue
            health = self._health.get(provider_id)
            if health and not health.is_healthy and health.consecutive_failures > 2:
                continue
            eligible.append(provider_id)

        # Re-order so that task-type preferred providers come first
        preferred_order = self.TASK_TYPE_PREFERRED_PROVIDERS.get(task_type, [])
        preferred_eligible = [p for p in preferred_order if p in eligible]
        rest = [p for p in eligible if p not in preferred_eligible]
        return preferred_eligible + rest

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
        _registry = ProviderRegistry(settings_db or _DEFAULT_DB_PATH)
    return _registry
