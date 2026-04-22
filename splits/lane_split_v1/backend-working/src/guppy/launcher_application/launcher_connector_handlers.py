"""Shell-side connector action handler functions.

Each function takes *owner* (a ``LauncherWindow`` instance) as first argument
and delegates to the connector workflow helpers, encapsulating the
``backend_available`` flag so the shell stays thin.
"""
from __future__ import annotations

from src.guppy.launcher_application import (
    apply_connector_action_feedback,
    connector_backend_available,
    drain_connector_action_events,
    handle_connector_action_request,
    handle_connector_guided_link_request,
    perform_connector_action_request,
    run_connector_action_request,
    save_instance_connector_binding,
    start_connector_action_async,
    start_connector_guided_link_async,
)

_BACKEND = connector_backend_available()


def perform_request(owner, payload: dict) -> dict:
    return perform_connector_action_request(owner, payload, backend_available=_BACKEND)


def apply_feedback(owner, record: dict, *, refresh_after: bool = True) -> dict:
    return apply_connector_action_feedback(owner, record, refresh_after=refresh_after)


def run_request(owner, payload: dict, *, refresh_after: bool = True) -> dict:
    return run_connector_action_request(
        owner, payload, refresh_after=refresh_after, backend_available=_BACKEND
    )


def start_async(owner, payload: dict, *, refresh_after: bool = True) -> None:
    start_connector_action_async(
        owner, payload, refresh_after=refresh_after, backend_available=_BACKEND
    )


def start_guided_link_async(owner, payload: dict) -> None:
    start_connector_guided_link_async(owner, payload, backend_available=_BACKEND)


def drain_events(owner) -> None:
    drain_connector_action_events(owner)


def on_action_requested(owner, payload: dict) -> None:
    handle_connector_action_request(owner, payload, backend_available=_BACKEND)


def on_guided_link_requested(owner, payload: dict) -> None:
    handle_connector_guided_link_request(owner, payload, backend_available=_BACKEND)


def on_instance_connector_binding_save_requested(owner, payload: dict) -> None:
    save_instance_connector_binding(owner, payload, backend_available=_BACKEND)
