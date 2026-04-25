"""Compatibility facade for the split inference router."""

from __future__ import annotations

from ._router_fragment_core import (
    InferenceRouter,
    VALID_MODES,
    VALID_MODES_DISPLAY,
    LAUNCHER_MODES,
    LAUNCHER_MODES_DISPLAY,
)
from ._router_fragment_execution import attach_router_execution_methods

attach_router_execution_methods(InferenceRouter)

from ._router_fragment_api import (  # noqa: E402
    get_router,
    route_inference,
    route_inference_code,
    route_inference_vault,
    route_inference_local,
    route_inference_smart,
    resolve_ui_route,
)

__all__ = [
    "InferenceRouter",
    "VALID_MODES",
    "VALID_MODES_DISPLAY",
    "LAUNCHER_MODES",
    "LAUNCHER_MODES_DISPLAY",
    "get_router",
    "route_inference",
    "route_inference_code",
    "route_inference_vault",
    "route_inference_local",
    "route_inference_smart",
    "resolve_ui_route",
]
