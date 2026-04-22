"""Compatibility facade for the split inference router."""

from __future__ import annotations

from ._router_fragment_core import *  # noqa: F401,F403
from ._router_fragment_execution import attach_router_execution_methods

attach_router_execution_methods(InferenceRouter)

from ._router_fragment_api import *  # noqa: E402,F401,F403
