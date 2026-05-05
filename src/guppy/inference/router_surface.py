"""Surface-pinned routing for stream_unified_inference.

Handles companion / workspace / codespace waterfall routing.
Each surface has a fixed local-preference order; all inference is local-only.
"""
from __future__ import annotations

import logging
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

_SURFACE_TEMPS: dict[str, float] = {
    "companion":  0.85,   # warmer — personality-first, creative
    "workspace":  0.75,   # balanced — task-focused but flexible
    "codespace":  0.60,   # precise — deterministic code generation
}


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
    active_local_model: str | None = None,
) -> AsyncGenerator[str, None]:
    """Yield streaming tokens for companion/workspace/codespace surfaces.

    Called only when the outer guard ``surface in {"companion", "workspace",
    "codespace"} and requested_mode in {"auto", ""}`` is satisfied.
    Always yields at least one token (tokens or an error message).
    """
    # Tool primer is already injected by stream_unified_inference unconditionally
    # before route_by_surface is called. Do NOT re-inject here — that causes
    # double injection (~300 wasted tokens) on every non-pass-2 call.

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

    def _sp_full_tools() -> list[dict] | None:
        return _merged_openai_tools(owner) if owner.GUPPY_CORE_AVAILABLE else None

    def _sp_suppress_think(msgs: list[dict]) -> list[dict]:
        """Suppress Qwen3/Hermes thinking mode via /no_think in both system and user messages.

        Qwen3-based models (including Hermes 4.3 36B Heretic) recognize /no_think
        in either the system or the last user message via the chat template. We set
        both so that thinking is disabled regardless of which the model checks first.
        """
        if not msgs:
            return msgs
        msgs = list(msgs)
        # Prepend /no_think to system message so the chat template disables thinking
        for i, m in enumerate(msgs):
            if m.get("role") == "system":
                if "/no_think" not in m["content"]:
                    msgs[i] = {**m, "content": "/no_think\n\n" + m["content"]}
                break
        # Also append to last user message (belt-and-suspenders)
        for i in range(len(msgs) - 1, -1, -1):
            if msgs[i].get("role") == "user":
                content = msgs[i]["content"]
                if not content.endswith(" /no_think"):
                    msgs[i] = {**msgs[i], "content": content + " /no_think"}
                break
        return msgs

    if surface == "companion":
        # ── Fast path: simple conversational queries → Phi-4-mini (port 8091) ─────────
        # Phi-4-mini is 2.3 GB vs 21.8 GB for the 36B — first token in ~0.3s vs ~3s.
        # Used for queries that need no tools, no memory recall, no file context.
        # Detection: ≤ 12 words AND no "heavy" cue keywords.
        # Falls through to hermes4 on failure or if phi4-mini is offline.
        _FAST_PATH_MAX_WORDS = 12
        _FAST_PATH_HEAVY_CUES = frozenset({
            # tools / operations
            "file", "task", "email", "calendar", "download", "remind", "search",
            "code", "run", "script", "workspace", "agent", "screen", "fetch",
            # memory / continuation
            "remember", "earlier", "previous", "follow", "continue", "again",
            # complexity signals
            "debug", "project", "explain", "compare", "tradeoff", "why", "how",
            "list", "write", "draft", "summarize", "analyze",
        })
        _user_words_lower = user_text.lower().split()
        _is_simple = (
            len(_user_words_lower) <= _FAST_PATH_MAX_WORDS
            and not any(cue in _user_words_lower for cue in _FAST_PATH_HEAVY_CUES)
            and active_local_model is None  # user override → always use their chosen model
        )

        if _is_simple:
            _fast_model = _sp_backend_alive("llamacpp-phi4-mini")
            if _fast_model:
                # Minimal prompt — avoid the 4K+ augmented companion system prompt that
                # would overwhelm phi4-mini's useful context and slow first-token time.
                _fast_sys = (
                    "You are Guppy — Ryan's personal AI. Sharp, direct, conversational. "
                    "Keep replies concise. No filler. Voice-optimized: short sentences."
                )
                _fast_msgs = build_router_messages(_fast_sys, user_text, [])
                try:
                    _yielded = False
                    async for tok in _stream_llamacpp_tokens(
                        model=_fast_model, backend="llamacpp-phi4-mini",
                        messages=_fast_msgs, tools=None, tool_runner=None,
                        max_tool_rounds=0,
                        thinking_budget=0,
                        max_tokens=512,
                        temperature=_SURFACE_TEMPS["companion"],
                    ):
                        yield tok
                        _yielded = True
                    if not _yielded:
                        raise RuntimeError("phi4-mini yielded 0 tokens")
                    yield _SOURCE_SENTINEL + f"llamacpp-phi4-mini:{_fast_model}"
                    return
                except RuntimeError as _fe:
                    _log.info("Companion fast-path (phi4-mini) failed: %s — falling through to hermes4", _fe)

        # ── Primary path: Hermes 4.3 36B Heretic (all other queries) ─────────────────
        # Small-context orchestrators must never be companion primaries — they
        # overflow on the full augmented system prompt and produce garbage.
        _COMPANION_EXCLUDED = {"llamacpp-dispatch", "llamacpp-phi4-mini", "llamacpp-xlam"}
        _p1_keys = []
        if active_local_model and active_local_model not in _COMPANION_EXCLUDED | {"llamacpp-hermes4"}:
            _p1_keys.append(active_local_model)
        _p1_keys.append("llamacpp-hermes4")
        _p1_keys.append("llamacpp-hermes3")  # on-demand fallback if 36B is down

        for _p1_key in _p1_keys:
            _p1m = _sp_backend_alive(_p1_key)
            if not _p1m:
                continue
            _msgs = _sp_suppress_think(_sp_make_messages(_p1_key))
            _tools = _sp_full_tools() if not skip_tools else None
            try:
                _yielded = False
                async for tok in _stream_llamacpp_tokens(
                    model=_p1m, backend=_p1_key,
                    messages=_msgs, tools=_tools, tool_runner=_sp_tool_runner,
                    max_tool_rounds=4,
                    thinking_budget=0,
                    max_tokens=8192,
                    temperature=_SURFACE_TEMPS["companion"],
                ):
                    yield tok
                    _yielded = True
                if not _yielded:
                    raise RuntimeError(f"{_p1_key} yielded 0 tokens — falling through")
                yield _SOURCE_SENTINEL + f"{_p1_key}:{_p1m}"
                return
            except RuntimeError as _e:
                _log.warning("Companion %s failed: %s — trying next", _p1_key, _e)

        yield "⚠️ No local model available for companion. Start llamacpp-hermes4 on port 8086."
        return

    elif surface == "workspace":
        # Pass-1: user-selected model OR Hermes4 (32K context, full tools, primary worker)
        # Phi4-mini / dispatch are orchestrators but have tiny context windows — they fall
        # through to hermes4 when the augmented workspace system prompt overflows them.
        # Ordering: user override → hermes4 → phi4-mini → dispatch
        _w1_keys = []
        if active_local_model:
            _w1_keys.append(active_local_model)
        for _k in ("llamacpp-hermes4", "llamacpp-phi4-mini", "llamacpp-dispatch"):
            if _k not in _w1_keys:
                _w1_keys.append(_k)

        for _w_key in _w1_keys:
            _wm = _sp_backend_alive(_w_key)
            if not _wm:
                continue
            _msgs = _sp_suppress_think(_sp_make_messages(_w_key))
            # Small-context models (phi4-mini, dispatch at 4K ctx) can't fit workspace prompt + tools
            _is_small_ctx = _w_key in ("llamacpp-phi4-mini", "llamacpp-dispatch")
            _tools = (None if _is_small_ctx else _sp_full_tools()) if not skip_tools else None
            try:
                _yielded = False
                async for tok in _stream_llamacpp_tokens(
                    model=_wm, backend=_w_key,
                    messages=_msgs, tools=_tools, tool_runner=_sp_tool_runner,
                    max_tool_rounds=8 if not _is_small_ctx else 3,
                    thinking_budget=0,
                    temperature=_SURFACE_TEMPS["workspace"],
                ):
                    yield tok
                    _yielded = True
                if not _yielded:
                    raise RuntimeError(f"{_w_key} yielded 0 tokens — falling through")
                yield _SOURCE_SENTINEL + f"{_w_key}:{_wm}"
                return
            except RuntimeError as _e:
                _log.warning("Workspace %s failed: %s — trying next", _w_key, _e)

        # Pass-2: Hermes3 fallback worker
        _h3m = _sp_backend_alive("llamacpp-hermes3")
        if _h3m and "llamacpp-hermes3" not in _w1_keys:
            _msgs = _sp_make_messages("llamacpp-hermes3")
            try:
                _yielded = False
                async for tok in _stream_llamacpp_tokens(
                    model=_h3m, backend="llamacpp-hermes3",
                    messages=_msgs, tools=_sp_full_tools(), tool_runner=_sp_tool_runner,
                    max_tool_rounds=2,
                    thinking_budget=0,
                    temperature=_SURFACE_TEMPS["workspace"],
                ):
                    yield tok
                    _yielded = True
                if not _yielded:
                    raise RuntimeError("hermes3 yielded 0 tokens")
                yield _SOURCE_SENTINEL + f"llamacpp-hermes3:{_h3m}"
                return
            except RuntimeError as _e:
                _log.warning("Workspace hermes3 fallback failed: %s", _e)

        yield "⚠️ No local model available for workspace. Start llamacpp-hermes4 on port 8086."
        return

    elif surface == "codespace":
        # No dedicated orchestrator — direct to workers (hermes4 preferred, hermes3 fallback)
        _cs_keys = []
        if active_local_model:
            _cs_keys.append(active_local_model)
        for _k in ("llamacpp-hermes4", "llamacpp-hermes3"):
            if _k not in _cs_keys:
                _cs_keys.append(_k)

        for _w_key in _cs_keys:
            _wm = _sp_backend_alive(_w_key)
            if not _wm:
                continue
            _msgs = _sp_suppress_think(_sp_make_messages(_w_key))
            try:
                _yielded = False
                async for tok in _stream_llamacpp_tokens(
                    model=_wm, backend=_w_key,
                    messages=_msgs, tools=_sp_full_tools(), tool_runner=_sp_tool_runner,
                    max_tool_rounds=6,
                    thinking_budget=0,
                    temperature=_SURFACE_TEMPS["codespace"],
                ):
                    yield tok
                    _yielded = True
                if not _yielded:
                    raise RuntimeError(f"{_w_key} yielded 0 tokens")
                yield _SOURCE_SENTINEL + f"{_w_key}:{_wm}"
                return
            except RuntimeError as _e:
                _log.warning("Codespace worker %s failed: %s — trying next", _w_key, _e)

        yield "⚠️ No local model available for codespace. Start llamacpp-hermes4 on port 8086."
        return
