"""InferenceRouter V2 — Extended router with ProviderRegistry integration.

Extends the core InferenceRouter with:
- Dynamic provider registry integration (llamacpp-gemma/qwen3/pepe + cloud)
- Task-type-aware backend selection via registry.TASK_TYPE_PREFERRED_PROVIDERS
- TTL-cached liveness probes so healthy servers get priority automatically
- Automatic fallback chain: preferred local backend → Ollama → Haiku → Sonnet
- Health check coordination
- Metrics tracking to database (stub — wired, not yet persisted)

Migration status: Phase 2 — registry is PRIMARY, core is fallback.
    get_router() in _router_fragment_api.py returns InferenceRouterV2.
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, Dict, List, Optional, Tuple

from .provider_client import InferenceMetadata
from .provider_registry import ProviderRegistry, get_provider_registry
from ._router_fragment_core import InferenceRouter

logger = logging.getLogger(__name__)

# Liveness probe cache: {backend_id: (is_live, expires_at)}
_LIVENESS_CACHE: Dict[str, Tuple[bool, float]] = {}
_LIVENESS_TTL = 10.0  # seconds between full re-probes


class InferenceRouterV2(InferenceRouter):
    """Extended InferenceRouter with ProviderRegistry integration.

    Maintains backward compatibility with InferenceRouter interface while
    adding provider abstraction layer underneath.

    Usage:
        router = InferenceRouterV2()
        response, source, metadata = await router.query_async(
            system_prompt="...",
            user_text="...",
            task_type="complex",
        )
    """

    def __init__(self, settings_db=None, use_registry=True):
        """Initialize router with optional provider registry.

        Args:
            settings_db: Optional settings database for persistent provider config
            use_registry: If True, use ProviderRegistry for inference; if False,
                         fall back to core InferenceRouter behavior
        """
        super().__init__()
        self.use_registry = use_registry
        self.registry = get_provider_registry(settings_db) if use_registry else None
        self._metrics_db = None  # Will be set by caller if metrics tracking desired

    def set_metrics_db(self, db) -> None:
        """Set database connection for metrics tracking."""
        self._metrics_db = db

    async def query_async(
        self,
        system_prompt: str,
        user_text: str,
        tools: Optional[List[Dict[str, Any]]] = None,
        task_type: Optional[str] = None,
        preferred_provider: Optional[str] = None,
        **kwargs,
    ) -> Tuple[str, str, Dict[str, Any]]:
        """Execute inference with optional provider registry fallback.

        Returns:
            (response_text, source, metadata_dict)

            source: "local", "anthropic", "openai", "google", "cohere", "mistral"
            metadata_dict: Includes latency_ms, tokens, cost, etc.
        """
        start_time = time.time()

        # Auto-classify if not provided
        if not task_type:
            task_type = self._classify_task(user_text, system_prompt)

        # Use registry if enabled
        if self.use_registry and self.registry:
            try:
                response, metadata = await self._infer_via_registry(
                    prompt=user_text,
                    system_prompt=system_prompt,
                    task_type=task_type,
                    preferred_provider=preferred_provider,
                    **kwargs,
                )
                # Track metrics if database set
                if self._metrics_db:
                    await self._record_metrics(metadata)

                return response, metadata.provider, metadata.to_dict()

            except Exception as e:
                logger.warning(f"[ROUTERV2] Registry inference failed: {e}")
                if not self.use_registry:
                    raise
                # Fall through to core router

        # Fall back to core router behavior (for backward compatibility)
        logger.info("[ROUTERV2] Falling back to core InferenceRouter")
        # Core router uses sync interface; wrap in executor
        loop = asyncio.get_event_loop()
        response, source, metadata = await loop.run_in_executor(
            None,
            lambda: super().query(
                system_prompt=system_prompt,
                user_text=user_text,
                tools=tools,
                mode="auto",
            ),
        )
        return response, source, metadata

    async def _infer_via_registry(
        self,
        prompt: str,
        system_prompt: str,
        task_type: str,
        preferred_provider: Optional[str] = None,
        **kwargs,
    ) -> Tuple[str, InferenceMetadata]:
        """Execute inference through ProviderRegistry."""
        # Ensure health checks are recent
        await self._refresh_health_status(fresh=False)

        # Execute with fallback chain
        response, metadata = await self.registry.infer_with_fallback(
            prompt=prompt,
            system_prompt=system_prompt,
            task_type=task_type,
            preferred_model=preferred_provider,
            **kwargs,
        )
        return response, metadata

    async def _refresh_health_status(self, fresh: bool = False) -> None:
        """Refresh provider health status."""
        if not self.registry:
            return

        if fresh:
            # Force fresh health checks
            await self.registry.health_check_all()
        # Otherwise use cached checks (5 second TTL per registry)

    async def _record_metrics(self, metadata: InferenceMetadata) -> None:
        """Record inference metrics to database."""
        if not self._metrics_db:
            return

        try:
            # TODO: Implement metrics table insert
            # INSERT INTO inference_metrics (provider, model, task_type, latency_ms, success, cost, timestamp)
            # await self._metrics_db.insert("inference_metrics", metadata.to_dict())
            pass
        except Exception as e:
            logger.warning(f"[ROUTERV2] Failed to record metrics: {e}")

    # ── Sync query_smart override (Phase 2: registry-first) ──────────────────

    def query_smart(
        self,
        system_prompt: str,
        user_text: str,
        tools: Optional[List[Dict[str, Any]]] = None,
        messages: Optional[List[Dict[str, Any]]] = None,
    ) -> Tuple[str, str, Dict[str, Any]]:
        """Registry-aware smart dispatch.

        Priority:
          1. Preferred llamacpp backend for this task type (if server is live)
          2. Core query_smart() — Ollama → Haiku → Sonnet fallback chain

        The liveness check is TTL-cached (10 s) so there is no per-request HTTP
        overhead once the cache is warm.
        """
        task_type = self._classify_task(user_text, system_prompt)

        if self.use_registry and self.registry:
            preferred_backend = self._get_preferred_llamacpp_backend(task_type)
            if preferred_backend and self._check_backend_live(preferred_backend):
                logger.info(
                    "[V2] task=%s → preferred backend=%s", task_type, preferred_backend
                )
                result = self._call_llamacpp_backend(
                    preferred_backend, system_prompt, user_text, tools
                )
                if result:
                    source = f"local/{preferred_backend}"
                    meta = result.get("metadata", {})
                    meta["backend"] = preferred_backend
                    meta["task_type"] = task_type
                    return result["response"], source, meta

        # Fallback: original Ollama → Haiku → Sonnet chain
        logger.debug("[V2] No live llamacpp backend for task=%s — using core chain", task_type)
        return super().query_smart(system_prompt, user_text, tools, messages)

    def _get_preferred_llamacpp_backend(self, task_type: str) -> Optional[str]:
        """Ask registry for the preferred provider; return it only if it's a llamacpp server."""
        if not self.registry:
            return None
        preferred = self.registry.get_preferred_for_task(task_type)
        # Only intercept llamacpp backends here; "local" (Ollama) is handled by super()
        if preferred and preferred.startswith("llamacpp-"):
            return preferred
        return None

    def _check_backend_live(self, backend: str) -> bool:
        """Return cached liveness for *backend*, refreshing when TTL expires."""
        global _LIVENESS_CACHE
        now = time.monotonic()
        entry = _LIVENESS_CACHE.get(backend)
        if entry and entry[1] > now:
            return entry[0]

        # Re-probe all llamacpp backends in one pass (cheap — just a TCP connect)
        from .local_client import probe_backends
        try:
            results = probe_backends(timeout=0.8)
        except Exception:
            results = {}
        expires = now + _LIVENESS_TTL
        for name, live in results.items():
            _LIVENESS_CACHE[name] = (live, expires)
        return bool(results.get(backend, False))

    def _call_llamacpp_backend(
        self,
        backend: str,
        system_prompt: str,
        user_text: str,
        tools: Optional[list],
    ) -> Optional[Dict[str, Any]]:
        """Call a llamacpp server synchronously via local_client.local_chat()."""
        from .local_client import local_chat, _BACKEND_DEFAULT_MODELS
        from ._router_fragment_execution import _filter_tools

        model = _BACKEND_DEFAULT_MODELS.get(backend, backend)
        filtered_tools = _filter_tools(tools)
        messages: List[Dict[str, Any]] = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": user_text})

        try:
            return local_chat(
                model,
                messages,
                tools=filtered_tools or None,
                backend=backend,
                timeout=int(self.registry.get_config(backend).timeout_seconds if self.registry else 90),
                num_predict=self.local_num_predict,
            )
        except Exception as e:
            logger.warning("[V2] %s call failed: %s", backend, e)
            return None

    # ── Registry management helpers ───────────────────────────────────────────

    def get_registry_status(self) -> Dict[str, Any]:
        """Get provider registry status for diagnostics."""
        if not self.registry:
            return {"status": "registry disabled"}
        return self.registry.get_status()

    async def set_provider_enabled(self, provider_id: str, enabled: bool) -> bool:
        """Enable or disable a provider."""
        if not self.registry:
            return False
        return await self.registry.set_enabled(provider_id, enabled)

    async def health_check_provider(self, provider_id: str) -> bool:
        """Check health of a specific provider."""
        if not self.registry:
            return False
        return await self.registry.health_check(provider_id)


class InferenceRouterFactory:
    """Factory to create router instances with appropriate configuration."""

    @staticmethod
    def create_router(
        use_registry: bool = True,
        settings_db=None,
        metrics_db=None,
    ) -> InferenceRouterV2:
        """Create a configured InferenceRouterV2 instance.

        Args:
            use_registry: Use ProviderRegistry for inference
            settings_db: Optional settings database for persistent config
            metrics_db: Optional metrics database for tracking

        Returns:
            Configured router instance
        """
        router = InferenceRouterV2(settings_db=settings_db, use_registry=use_registry)
        if metrics_db:
            router.set_metrics_db(metrics_db)
        return router


# Convenience functions for gradual migration

async def unified_inference_async(
    system_prompt: str,
    user_text: str,
    mode: str = "auto",
    task_type: Optional[str] = None,
    settings_db=None,
    metrics_db=None,
) -> Tuple[str, str, Dict[str, Any]]:
    """Drop-in replacement for InferenceRouter.query() but async.

    Enables gradual migration from sync to async inference.

    Args:
        system_prompt: System context
        user_text: User message
        mode: Router mode (auto, claude, ollama, local, etc.)
        task_type: Optional task classification override
        settings_db: Optional settings database
        metrics_db: Optional metrics database

    Returns:
        (response_text, source, metadata_dict)
    """
    router = InferenceRouterFactory.create_router(
        use_registry=True,
        settings_db=settings_db,
        metrics_db=metrics_db,
    )
    return await router.query_async(
        system_prompt=system_prompt,
        user_text=user_text,
        task_type=task_type,
    )
