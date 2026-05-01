"""Surface-pinned routing for stream_unified_inference.

Handles companion / workspace / codespace waterfall routing.
Each surface has a fixed local-preference order and specific cloud-fallback
tiers (free Mistral/Cohere first, then paid Haiku or Sonnet).
"""
from __future__ import annotations

import logging
from typing import Any, AsyncGenerator

from src.guppy.inference.streaming_backends import (
    _stream_llamacpp_tokens,
    _stream_mistral_tokens,
    _stream_cohere_tokens,
    _stream_claude_with_tools,
)
from src.guppy.inference.context_injection import _inject_tool_primer
from src.guppy.inference.local_client import (
    _BACKENDS as _LOCAL_BACKENDS,
    _BACKEND_DEFAULT_MODELS as _LOCAL_BACKEND_DEFAULT_MODELS,
)
from src.guppy.inference._routing_shared import (
    _SOURCE_SENTINEL,
    _get_cloud_api_key,
    _merged_openai_tools,
    build_router_messages,
    sanitize_chat_history,
)

_log = logging.getLogger(__name__)


async def route_by_surface(
    *,
    surface: str,
    owner: Any,
    augmented_system: str,
    user_text: str,
    history: list,
    instance_name: str | None,
    instance_type: str | None,
    skip_tools: bool,
) -> AsyncGenerator[str, None]:
    """Yield streaming tokens for companion/workspace/codespace surfaces.

    Called only when the outer guard ``surface in {"companion", "workspace",
    "codespace"} and requested_mode in {"auto", ""}`` is satisfied.
    Always yields at least one token (tokens or an error message).
    """
    # Inject surface-specific tool primer + few-shot examples so local models
    # know exactly what tools exist here and when/how to invoke them.
    if not skip_tools:
        augmented_system = _inject_tool_primer(augmented_system, surface)

    from src.guppy.api.routes_backends import _port_alive as _sp_port_alive

    def _sp_backend_alive(key: str) -> str:
        """Return model name if backend is alive, else empty string."""
        _cfg = _LOCAL_BACKENDS.get(key, {})
        _url = _cfg.get("default_url", "")
        _port = int(_url.rsplit(":", 1)[-1]) if ":" in _url else 0
        _model = _LOCAL_BACKEND_DEFAULT_MODELS.get(key, "")
        return _model if (_port and _sp_port_alive(_port) and _model) else ""

    def _sp_make_messages(backend: str | None = None) -> list[dict]:
        return build_router_messages(augmented_system, user_text, sanitize_chat_history(history, backend=backend))

    def _sp_tool_runner(name: str, args: dict) -> str:
        return str(owner.core.run_tool(name, args,
            instance_name=instance_name, instance_type=instance_type))

    # Tools passed to companion are stripped to the basics (read/write memory,
    # create_reminder, web_fetch, workspace_task) — heavy agentic tools stay with workspace.
    _COMPANION_BASIC_TOOLS = [
        "memory_write", "memory_recall", "create_reminder",
        "web_fetch", "get_time", "workspace_task", "download_media",
    ]

    def _sp_companion_tools() -> list[dict] | None:
        if not owner.GUPPY_CORE_AVAILABLE:
            return None
        all_tools = _merged_openai_tools(owner) or []
        basic = [t for t in all_tools
                 if (t.get("function", {}).get("name") or t.get("name", "")) in _COMPANION_BASIC_TOOLS]
        return basic or None

    def _sp_full_tools() -> list[dict] | None:
        return _merged_openai_tools(owner) if owner.GUPPY_CORE_AVAILABLE else None

    # ── free cloud helpers ──
    def _sp_free_cloud_key() -> tuple[str, str]:
        """Return (provider, api_key) for first available free cloud provider."""
        _mk = _get_cloud_api_key("mistral", owner)
        if _mk:
            return ("mistral", _mk)
        _ck = _get_cloud_api_key("cohere", owner)
        if _ck:
            return ("cohere", _ck)
        return ("", "")

    async def _sp_stream_free_cloud(msgs: list[dict], tools, tr, label: str):
        _prov, _key = _sp_free_cloud_key()
        if not _key:
            return
        try:
            if _prov == "mistral":
                async for tok in _stream_mistral_tokens(_key, "mistral-small-latest", msgs):
                    yield tok
            else:
                async for tok in _stream_cohere_tokens(_key, "command-r-plus", msgs):
                    yield tok
            yield _SOURCE_SENTINEL + _prov
        except Exception as _fc_err:
            _log.warning("Surface %s free cloud (%s) failed: %s", surface, _prov, _fc_err)

    if surface == "companion":
        # Pass-1: Hermes3 (fast 8B, basic tools only)
        _h3m = _sp_backend_alive("llamacpp-hermes3")
        if _h3m:
            _msgs = _sp_make_messages("llamacpp-hermes3")
            _tools = _sp_companion_tools() if not skip_tools else None
            try:
                async for tok in _stream_llamacpp_tokens(
                    model=_h3m, backend="llamacpp-hermes3",
                    messages=_msgs, tools=_tools, tool_runner=_sp_tool_runner,
                    max_tool_rounds=2,
                ):
                    yield tok
                yield _SOURCE_SENTINEL + f"llamacpp-hermes3:{_h3m}"
                return
            except RuntimeError as _e:
                _log.warning("Companion Hermes3 failed: %s — trying orchestrator", _e)

        # Pass-2: Phi-4-mini dispatch as orchestrator (complex escalation)
        for _orch_key in ("llamacpp-phi4-mini", "llamacpp-dispatch"):
            _om = _sp_backend_alive(_orch_key)
            if _om:
                _msgs = _sp_make_messages(_orch_key)
                try:
                    async for tok in _stream_llamacpp_tokens(
                        model=_om, backend=_orch_key,
                        messages=_msgs, tools=_sp_full_tools(), tool_runner=_sp_tool_runner,
                        max_tool_rounds=6,
                    ):
                        yield tok
                    yield _SOURCE_SENTINEL + f"{_orch_key}:{_om}"
                    return
                except RuntimeError as _e:
                    _log.warning("Companion orchestrator %s failed: %s", _orch_key, _e)

        # Pass-3: free cloud (Mistral or Cohere)
        _prov, _fck = _sp_free_cloud_key()
        if _fck:
            _msgs = _sp_make_messages()
            try:
                _free_model = "mistral-small-latest" if _prov == "mistral" else "command-r-plus"
                _stream_fn = _stream_mistral_tokens if _prov == "mistral" else _stream_cohere_tokens
                async for tok in _stream_fn(_fck, _free_model, _msgs):
                    yield tok
                yield _SOURCE_SENTINEL + _prov
                return
            except Exception as _fe:
                _log.warning("Companion free cloud (%s) failed: %s", _prov, _fe)

        # Pass-4: paid Haiku (cheap/fast companion fallback)
        _ak = _get_cloud_api_key("anthropic", owner)
        if _ak:
            _msgs = _sp_make_messages()
            try:
                async for tok in _stream_claude_with_tools(
                    api_key=_ak, model="claude-haiku-4-5-20251001",
                    system_prompt=augmented_system, messages=_msgs,
                    tools=None, tool_runner=_sp_tool_runner,
                ):
                    yield tok
                yield _SOURCE_SENTINEL + "claude-haiku-4-5-20251001"
                return
            except Exception as _pe:
                _log.warning("Companion paid Haiku failed: %s", _pe)

        yield "⚠️ No backend available for companion surface."
        return

    elif surface == "workspace":
        # Pass-1: Phi-4-mini or dispatch as orchestrator
        for _orch_key in ("llamacpp-phi4-mini", "llamacpp-dispatch"):
            _om = _sp_backend_alive(_orch_key)
            if _om:
                _msgs = _sp_make_messages(_orch_key)
                try:
                    async for tok in _stream_llamacpp_tokens(
                        model=_om, backend=_orch_key,
                        messages=_msgs, tools=_sp_full_tools(), tool_runner=_sp_tool_runner,
                        max_tool_rounds=8,
                    ):
                        yield tok
                    yield _SOURCE_SENTINEL + f"{_orch_key}:{_om}"
                    return
                except RuntimeError as _e:
                    _log.warning("Workspace orchestrator %s failed: %s", _orch_key, _e)

        # Pass-2: workers — Hermes4 then Hermes3
        for _w_key in ("llamacpp-hermes4", "llamacpp-hermes3"):
            _wm = _sp_backend_alive(_w_key)
            if _wm:
                _msgs = _sp_make_messages(_w_key)
                try:
                    async for tok in _stream_llamacpp_tokens(
                        model=_wm, backend=_w_key,
                        messages=_msgs, tools=_sp_full_tools(), tool_runner=_sp_tool_runner,
                        max_tool_rounds=6,
                    ):
                        yield tok
                    yield _SOURCE_SENTINEL + f"{_w_key}:{_wm}"
                    return
                except RuntimeError as _e:
                    _log.warning("Workspace worker %s failed: %s", _w_key, _e)

        # Pass-3: free cloud
        _prov, _fck = _sp_free_cloud_key()
        if _fck:
            _msgs = _sp_make_messages()
            try:
                _free_model = "mistral-small-latest" if _prov == "mistral" else "command-r-plus"
                _stream_fn = _stream_mistral_tokens if _prov == "mistral" else _stream_cohere_tokens
                async for tok in _stream_fn(_fck, _free_model, _msgs):
                    yield tok
                yield _SOURCE_SENTINEL + _prov
                return
            except Exception as _fe:
                _log.warning("Workspace free cloud (%s) failed: %s", _prov, _fe)

        # Pass-4: paid Sonnet (capable workspace fallback)
        _ak = _get_cloud_api_key("anthropic", owner)
        if _ak:
            _msgs = _sp_make_messages()
            try:
                async for tok in _stream_claude_with_tools(
                    api_key=_ak, model="claude-sonnet-4-6",
                    system_prompt=augmented_system, messages=_msgs,
                    tools=_sp_full_tools(), tool_runner=_sp_tool_runner,
                ):
                    yield tok
                yield _SOURCE_SENTINEL + "claude-sonnet-4-6"
                return
            except Exception as _pe:
                _log.warning("Workspace paid Sonnet failed: %s", _pe)

        yield "⚠️ No backend available for workspace surface."
        return

    elif surface == "codespace":
        # No dedicated orchestrator — direct to workers
        for _w_key in ("llamacpp-hermes4", "llamacpp-hermes3"):
            _wm = _sp_backend_alive(_w_key)
            if _wm:
                _msgs = _sp_make_messages(_w_key)
                try:
                    async for tok in _stream_llamacpp_tokens(
                        model=_wm, backend=_w_key,
                        messages=_msgs, tools=_sp_full_tools(), tool_runner=_sp_tool_runner,
                        max_tool_rounds=6,
                    ):
                        yield tok
                    yield _SOURCE_SENTINEL + f"{_w_key}:{_wm}"
                    return
                except RuntimeError as _e:
                    _log.warning("Codespace worker %s failed: %s", _w_key, _e)

        # Free cloud fallback
        _prov, _fck = _sp_free_cloud_key()
        if _fck:
            _msgs = _sp_make_messages()
            try:
                _free_model = "mistral-small-latest" if _prov == "mistral" else "command-r-plus"
                _stream_fn = _stream_mistral_tokens if _prov == "mistral" else _stream_cohere_tokens
                async for tok in _stream_fn(_fck, _free_model, _msgs):
                    yield tok
                yield _SOURCE_SENTINEL + _prov
                return
            except Exception as _fe:
                _log.warning("Codespace free cloud (%s) failed: %s", _prov, _fe)

        # Paid Sonnet
        _ak = _get_cloud_api_key("anthropic", owner)
        if _ak:
            _msgs = _sp_make_messages()
            try:
                async for tok in _stream_claude_with_tools(
                    api_key=_ak, model="claude-sonnet-4-6",
                    system_prompt=augmented_system, messages=_msgs,
                    tools=_sp_full_tools(), tool_runner=_sp_tool_runner,
                ):
                    yield tok
                yield _SOURCE_SENTINEL + "claude-sonnet-4-6"
                return
            except Exception as _pe:
                _log.warning("Codespace paid Sonnet failed: %s", _pe)

        yield "⚠️ No backend available for codespace surface."
        return
