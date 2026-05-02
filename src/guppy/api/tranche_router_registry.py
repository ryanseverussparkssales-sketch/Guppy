"""Shared registration for tranche surface routers.

Keeping these routers behind one registry prevents packaged entrypoints from
silently omitting a lower-tier module while the main dev server keeps working.
"""
from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter

from src.guppy.api.server_context import ServerContext

logger = logging.getLogger(__name__)

# Each entry: (import_path, factory_name, description)
# Factories that return multiple routers use a special 'multi' marker — the
# function must return an iterable of APIRouter objects.
_TRANCHE_REGISTRY = [
    ("src.guppy.api.routes_library",          "build_library_router",       "library /api/library/*"),
    ("src.guppy.api.routes_screen_monitor",   "build_screen_monitor_router","screen_monitor /api/screen/*"),
    ("src.guppy.api.routes_model_roles",      "build_model_roles_router",   "model_roles /api/model-roles + /api/control/operator-settings"),
    ("src.guppy.api.services_model_manager",  "build_model_health_router",  "model_health /api/models/health"),
    ("src.guppy.api.routes_conversations",    "build_conversations_router", "conversations /api/conversations/*"),
    ("src.guppy.api.routes_workspace",        "build_workspace_router",     "workspace /api/workspace-view/*"),
]


def register_tranche_routers(app: Any, ctx: ServerContext) -> list[APIRouter]:
    """Register all tranche surface routers with per-router error isolation.

    A failure in one router never prevents the others from loading.
    """
    registered: list[APIRouter] = []
    fail_count = 0

    for mod_path, factory_name, label in _TRANCHE_REGISTRY:
        try:
            import importlib
            mod = importlib.import_module(mod_path)
            result = getattr(mod, factory_name)(ctx)
            # Some factories return a tuple of routers (e.g. build_model_roles_router)
            if isinstance(result, (list, tuple)):
                for r in result:
                    app.include_router(r)
                    registered.append(r)
            else:
                app.include_router(result)
                registered.append(result)
            logger.debug("Tranche router registered: %s", label)
        except Exception as exc:
            fail_count += 1
            logger.error("FAILED to register tranche router %s (%s.%s): %s",
                         label, mod_path, factory_name, exc)

    if fail_count:
        logger.warning(
            "%d tranche router(s) failed — those paths will return 404.", fail_count
        )

    return registered
