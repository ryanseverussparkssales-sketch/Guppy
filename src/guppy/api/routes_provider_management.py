"""Provider management API routes.

Endpoints for:
    - GET /api/providers/health - Check health of all providers
    - GET /api/providers/health/{provider_id} - Check specific provider
    - POST /api/providers/{provider_id}/enable - Enable provider
    - POST /api/providers/{provider_id}/disable - Disable provider
    - GET /api/providers/config - Get provider registry status
    - POST /api/providers/config/reset - Reset to default configs

These routes integrate with ProviderRegistry for dynamic provider management.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict

from fastapi import APIRouter, HTTPException, Depends

from src.guppy.api.server_context import ServerContext
from src.guppy.inference.provider_registry import get_provider_registry

logger = logging.getLogger(__name__)


def build_provider_management_router(ctx: ServerContext) -> APIRouter:
    """Build provider management API router.

    Args:
        ctx: Server context with database and auth

    Returns:
        APIRouter with provider endpoints
    """
    router = APIRouter(prefix="/api/providers")
    registry = get_provider_registry()  # Get global registry

    @router.get("/health")
    async def get_all_health(_user_id: str = Depends(ctx.require_rate_limit)) -> Dict[str, Any]:
        """Check health of all configured providers.

        Returns:
            {
                "timestamp": "2026-04-25T10:30:00Z",
                "providers": {
                    "local": {"healthy": true, "latency_ms": 0},
                    "anthropic": {"healthy": true, "latency_ms": 245},
                    "openai": {"healthy": false, "error": "API key not configured"}
                },
                "fallback_chains": {
                    "simple": ["local", "anthropic", "openai"],
                    "complex": ["anthropic", "openai", "local"]
                }
            }
        """
        try:
            health = await registry.health_check_all()
            return {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "providers": health,
                "fallback_chains": {
                    "simple": registry.build_fallback_chain("simple"),
                    "complex": registry.build_fallback_chain("complex"),
                    "teaching": registry.build_fallback_chain("teaching"),
                },
            }
        except Exception as e:
            logger.error(f"[ROUTES] Health check failed: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    @router.get("/health/{provider_id}")
    async def get_provider_health(
        provider_id: str,
        _user_id: str = Depends(ctx.require_rate_limit),
    ) -> Dict[str, Any]:
        """Check health of a specific provider.

        Args:
            provider_id: Provider identifier (local, anthropic, openai, etc.)

        Returns:
            {
                "provider_id": "anthropic",
                "healthy": true,
                "latency_ms": 245,
                "model": "claude-opus-4-6",
                "error": null
            }
        """
        try:
            config = registry.get_config(provider_id)
            if not config:
                raise HTTPException(status_code=404, detail=f"Provider {provider_id} not found")

            healthy = await registry.health_check(provider_id)
            health_info = registry._health.get(provider_id)

            return {
                "provider_id": provider_id,
                "healthy": healthy,
                "enabled": config.is_enabled,
                "model": config.model_id,
                "timeout_seconds": config.timeout_seconds,
                "error": health_info.error_message if health_info else None,
                "last_check": health_info.last_check.isoformat() if health_info else None,
            }
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"[ROUTES] Health check for {provider_id} failed: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    @router.post("/{provider_id}/enable")
    async def enable_provider(
        provider_id: str,
        _user_id: str = Depends(ctx.require_rate_limit),
    ) -> Dict[str, Any]:
        """Enable a provider.

        Args:
            provider_id: Provider to enable

        Returns:
            {"provider_id": "openai", "enabled": true, "message": "Enabled"}
        """
        try:
            config = registry.get_config(provider_id)
            if not config:
                raise HTTPException(status_code=404, detail=f"Provider {provider_id} not found")

            success = await registry.set_enabled(provider_id, True)
            if not success:
                raise HTTPException(status_code=400, detail=f"Failed to enable {provider_id}")

            logger.info(f"[ROUTES] Enabled provider {provider_id}")
            return {
                "provider_id": provider_id,
                "enabled": True,
                "message": f"Provider {provider_id} enabled",
            }
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"[ROUTES] Failed to enable {provider_id}: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    @router.post("/{provider_id}/disable")
    async def disable_provider(
        provider_id: str,
        _user_id: str = Depends(ctx.require_rate_limit),
    ) -> Dict[str, Any]:
        """Disable a provider.

        Args:
            provider_id: Provider to disable

        Returns:
            {"provider_id": "openai", "enabled": false, "message": "Disabled"}
        """
        try:
            config = registry.get_config(provider_id)
            if not config:
                raise HTTPException(status_code=404, detail=f"Provider {provider_id} not found")

            if provider_id == "local":
                raise HTTPException(status_code=400, detail="Cannot disable local provider")

            success = await registry.set_enabled(provider_id, False)
            if not success:
                raise HTTPException(status_code=400, detail=f"Failed to disable {provider_id}")

            logger.info(f"[ROUTES] Disabled provider {provider_id}")
            return {
                "provider_id": provider_id,
                "enabled": False,
                "message": f"Provider {provider_id} disabled",
            }
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"[ROUTES] Failed to disable {provider_id}: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    @router.get("/config")
    async def get_provider_config(_user_id: str = Depends(ctx.require_rate_limit)) -> Dict[str, Any]:
        """Get current provider registry configuration and status.

        Returns full registry status including fallback chains and health.
        """
        try:
            status = registry.get_status()
            return {
                "status": "ok",
                "registry": status,
            }
        except Exception as e:
            logger.error(f"[ROUTES] Failed to get provider config: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    @router.post("/config/reset")
    async def reset_provider_config(_user_id: str = Depends(ctx.require_rate_limit)) -> Dict[str, Any]:
        """Reset provider configuration to defaults.

        Useful for recovery or troubleshooting.
        """
        try:
            # Reload defaults from environment
            registry._load_configs()
            logger.info("[ROUTES] Reset provider config to defaults")
            return {
                "status": "ok",
                "message": "Provider config reset to defaults",
            }
        except Exception as e:
            logger.error(f"[ROUTES] Failed to reset provider config: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    return router
