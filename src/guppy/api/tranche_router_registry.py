"""Shared registration for tranche surface routers.

Keeping these routers behind one registry prevents packaged entrypoints from
silently omitting a lower-tier module while the main dev server keeps working.
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from src.guppy.api.server_context import ServerContext


def build_tranche_routers(ctx: ServerContext) -> list[APIRouter]:
    from src.guppy.api.routes_conversations import build_conversations_router
    from src.guppy.api.routes_library import build_library_router
    from src.guppy.api.routes_model_roles import build_model_roles_router
    from src.guppy.api.routes_screen_monitor import build_screen_monitor_router
    from src.guppy.api.routes_workspace import build_workspace_router
    from src.guppy.api.services_model_manager import build_model_health_router

    model_roles_router, control_settings_router = build_model_roles_router(ctx)
    return [
        build_library_router(ctx),
        build_screen_monitor_router(ctx),
        model_roles_router,
        control_settings_router,
        build_model_health_router(ctx),
        build_conversations_router(ctx),
        build_workspace_router(ctx),
    ]


def register_tranche_routers(app: Any, ctx: ServerContext) -> list[APIRouter]:
    routers = build_tranche_routers(ctx)
    for router in routers:
        app.include_router(router)
    return routers
