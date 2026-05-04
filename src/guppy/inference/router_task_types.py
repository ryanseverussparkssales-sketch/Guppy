"""Task-type routing for stream_unified_inference.

Handles tool_call / agentic / complex / simple / teaching waterfall routing.
Each block tries its preferred local backend(s) in order; all inference is
local-only (no cloud fallback).
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, AsyncGenerator

from src.guppy.inference.streaming_backends import (
    _stream_llamacpp_tokens,
)
from src.guppy.inference.local_client import (
    _BACKENDS as _LOCAL_BACKENDS,
    _BACKEND_DEFAULT_MODELS as _LOCAL_BACKEND_DEFAULT_MODELS,
)
from src.guppy.inference._routing_shared import (
    _SOURCE_SENTINEL,
    _merged_openai_tools,
    build_router_messages,
    sanitize_chat_history,
)

_log = logging.getLogger(__name__)


@dataclass
class _BackendSpec:
    """Per-backend parameters within a _RouteSpec."""

    key: str
    label: str = ""
    max_tool_rounds: int = 4
    escalate_on_all_tool_errors: bool = False
    auto_start: bool = False


@dataclass
class _RouteSpec:
    """Routing table entry for one task type."""

    task_type: str
    backends: list[_BackendSpec]
    requires_core: bool = True
    cloud_fallback: str = ""          # always empty — all inference is local-only


# Ordered routing table.  The dispatcher tries backends left-to-right and
# escalates to cloud only when every local backend has been exhausted.
_ROUTE_TABLE: list[_RouteSpec] = [
    # tool_call: xLAM-2-8B (#1 BFCL ≤8B, ~5 GB Q4) → Hermes 4 fallback.
    # No core guard — structured function-calling can still be attempted even
    # when the tool registry is unavailable.  xLAM is auto-started on demand.
    _RouteSpec(
        task_type="tool_call",
        backends=[
            _BackendSpec("llamacpp-xlam", label="xLAM-2-8B",
                         max_tool_rounds=4, escalate_on_all_tool_errors=True, auto_start=True),
            _BackendSpec("llamacpp-hermes4", label="Hermes 4", max_tool_rounds=4),
        ],
        requires_core=False,
        cloud_fallback="",
    ),
    # agentic: Qwen3 35B (strongest local) → Hermes 4 → Claude Sonnet.
    # Multi-step tool loops need a capable model; 8B models hallucinate tool results.
    # Pepe is never tried for agentic tasks.
    _RouteSpec(
        task_type="agentic",
        backends=[
            _BackendSpec("llamacpp-qwen3",  label="Qwen3 35B", max_tool_rounds=10),
            _BackendSpec("llamacpp-hermes4", label="Hermes 4",  max_tool_rounds=8),
        ],
        requires_core=True,
        cloud_fallback="",
    ),
    # complex: Hermes 4 (always-on workspace agent) → Claude Sonnet.
    # 14B handles multi-step reasoning and tool chains; Sonnet is the cloud safety net.
    _RouteSpec(
        task_type="complex",
        backends=[
            _BackendSpec("llamacpp-hermes4", label="Hermes 4 workspace agent", max_tool_rounds=6),
        ],
        requires_core=True,
        cloud_fallback="",
    ),
    # simple: Hermes 3 (fast 8B, uncensored) → Hermes 4 fallback.  No cloud escalation.
    _RouteSpec(
        task_type="simple",
        backends=[
            _BackendSpec("llamacpp-hermes3", label="Hermes 3"),
            _BackendSpec("llamacpp-hermes4", label="Hermes 4"),
        ],
        requires_core=True,
        cloud_fallback="",
    ),
    # teaching: Hermes 4 (quality 14B, always-on) → Hermes 3 fallback.  No cloud escalation.
    _RouteSpec(
        task_type="teaching",
        backends=[
            _BackendSpec("llamacpp-hermes4", label="Hermes 4"),
            _BackendSpec("llamacpp-hermes3", label="Hermes 3"),
        ],
        requires_core=True,
        cloud_fallback="",
    ),
]


def _resolve_port(backend_key: str) -> int:
    """Return the TCP port for *backend_key*, or 0 if not configured."""
    url = _LOCAL_BACKENDS.get(backend_key, {}).get("default_url", "")
    return int(url.rsplit(":", 1)[-1]) if ":" in url else 0


async def route_by_task_type(
    *,
    early_task_type: str,
    owner: Any,
    augmented_system: str,
    user_text: str,
    history: list,
    clean_history: list,
    instance_name: str | None,
    instance_type: str | None,
    requested_mode: str,
) -> AsyncGenerator[str, None]:
    """Yield streaming tokens for task-type-classified requests.

    Tries each task-type waterfall in order.  If a block succeeds it yields
    tokens (including the trailing ``_SOURCE_SENTINEL``) and returns.  If all
    fallbacks in a block fail, or the task type doesn't match any block, the
    function yields nothing so the caller can continue to general routing.
    """
    if requested_mode not in {"auto", ""}:
        return

    from src.guppy.api.routes_backends import _port_alive as _llc_port_alive

    def _tool_runner(name: str, args: dict) -> str:
        return str(owner.core.run_tool(
            name, args, instance_name=instance_name, instance_type=instance_type,
        ))

    for spec in _ROUTE_TABLE:
        if spec.task_type != early_task_type:
            continue
        if spec.requires_core and not owner.GUPPY_CORE_AVAILABLE:
            return

        for bspec in spec.backends:
            port = _resolve_port(bspec.key)
            if not port:
                continue
            if bspec.auto_start and not _llc_port_alive(port):
                try:
                    from src.guppy.api.routes_backends import ensure_backend_started
                    ensure_backend_started(bspec.key)
                except Exception as exc:
                    _log.warning("%s auto-start failed: %s", bspec.key, exc)
            if not _llc_port_alive(port):
                continue
            model = _LOCAL_BACKEND_DEFAULT_MODELS.get(bspec.key, "")
            if not model:
                continue
            label = bspec.label or bspec.key
            _log.info("%s task → routing to %s (port %d)", spec.task_type, label, port)
            msgs = build_router_messages(
                augmented_system, user_text, sanitize_chat_history(history)
            )
            tools = _merged_openai_tools(owner)
            try:
                async for token in _stream_llamacpp_tokens(
                    model=model,
                    backend=bspec.key,
                    messages=msgs,
                    tools=tools,
                    tool_runner=_tool_runner,
                    max_tool_rounds=bspec.max_tool_rounds,
                    escalate_on_all_tool_errors=bspec.escalate_on_all_tool_errors,
                ):
                    yield token
                yield _SOURCE_SENTINEL + f"{bspec.key}:{model}"
                return
            except RuntimeError as err:
                _log.warning(
                    "%s route via %s failed: %s — trying next backend",
                    spec.task_type, label, err,
                )

        return  # spec matched; all local backends tried
