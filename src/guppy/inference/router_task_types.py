"""Task-type routing for stream_unified_inference.

Handles tool_call / agentic / complex / simple / teaching waterfall routing.
Each block tries its preferred local backend(s) and falls back to cloud when
all local options are offline or fail.  Yields nothing if the task type does
not match any block (caller continues to general routing).
"""
from __future__ import annotations

import logging
from typing import Any, AsyncGenerator

from src.guppy.inference.streaming_backends import (
    _stream_llamacpp_tokens,
    _stream_claude_with_tools,
)
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

    # ── Tool-call routing: xLAM-2-8B → Hermes 4 (fallback) ─────────────────────
    # Single-tool invocation tasks where structured function-calling accuracy
    # matters. xLAM-2-8B-fc-r is #1 on BFCL V4 for its size class (~5 GB Q4).
    # Falls back to hermes4 if xLAM is offline.
    if early_task_type == "tool_call" and requested_mode in {"auto", ""}:
        from src.guppy.api.routes_backends import _port_alive as _llc_port_alive
        _XLAM_BACKEND = "llamacpp-xlam"
        _xlam_cfg = _LOCAL_BACKENDS.get(_XLAM_BACKEND, {})
        _xlam_url = _xlam_cfg.get("default_url", "")
        _xlam_port = int(_xlam_url.rsplit(":", 1)[-1]) if ":" in _xlam_url else 0
        if _xlam_port and not _llc_port_alive(_xlam_port):
            try:
                from src.guppy.api.routes_backends import ensure_backend_started
                ensure_backend_started(_XLAM_BACKEND)
            except Exception as exc:
                _log.warning("xLAM auto-start failed: %s", exc)

        if _xlam_port and _llc_port_alive(_xlam_port):
            _xlam_model = _LOCAL_BACKEND_DEFAULT_MODELS.get(_XLAM_BACKEND, "")
            if _xlam_model:
                _log.info("Tool-call task → routing to xLAM-2-8B (port %d)", _xlam_port)
                _xlam_messages = build_router_messages(
                    augmented_system, user_text, sanitize_chat_history(history)
                )
                _xlam_tools = _merged_openai_tools(owner)
                def _xlam_tool_runner(name: str, args: dict) -> str:
                    return str(owner.core.run_tool(
                        name, args,
                        instance_name=instance_name,
                        instance_type=instance_type,
                    ))
                try:
                    async for token in _stream_llamacpp_tokens(
                        model=_xlam_model,
                        backend=_XLAM_BACKEND,
                        messages=_xlam_messages,
                        tools=_xlam_tools,
                        tool_runner=_xlam_tool_runner,
                        max_tool_rounds=4,
                        escalate_on_all_tool_errors=True,
                    ):
                        yield token
                    yield _SOURCE_SENTINEL + f"{_XLAM_BACKEND}:{_xlam_model}"
                    return
                except RuntimeError as _xlam_err:
                    _log.warning(
                        "xLAM tool-call route failed: %s — falling back to Hermes 4",
                        _xlam_err,
                    )
        # xLAM offline or failed — try hermes4 as tool-call fallback
        _H4_BACKEND = "llamacpp-hermes4"
        _h4_cfg = _LOCAL_BACKENDS.get(_H4_BACKEND, {})
        _h4_url = _h4_cfg.get("default_url", "")
        _h4_port = int(_h4_url.rsplit(":", 1)[-1]) if ":" in _h4_url else 0
        if _h4_port and _llc_port_alive(_h4_port):
            _h4_model = _LOCAL_BACKEND_DEFAULT_MODELS.get(_H4_BACKEND, "")
            if _h4_model:
                _log.info("Tool-call fallback → Hermes 4 (port %d)", _h4_port)
                _h4_messages = build_router_messages(
                    augmented_system, user_text, sanitize_chat_history(history)
                )
                _h4_tools = _merged_openai_tools(owner)
                def _h4_tool_runner(name: str, args: dict) -> str:
                    return str(owner.core.run_tool(
                        name, args,
                        instance_name=instance_name,
                        instance_type=instance_type,
                    ))
                try:
                    async for token in _stream_llamacpp_tokens(
                        model=_h4_model,
                        backend=_H4_BACKEND,
                        messages=_h4_messages,
                        tools=_h4_tools,
                        tool_runner=_h4_tool_runner,
                        max_tool_rounds=4,
                    ):
                        yield token
                    yield _SOURCE_SENTINEL + f"{_H4_BACKEND}:{_h4_model}"
                    return
                except RuntimeError as _h4_err:
                    _log.warning(
                        "Hermes 4 tool-call fallback failed: %s — continuing to local models",
                        _h4_err,
                    )

    # ── Agentic routing: Qwen3 35B → Claude Sonnet ────────────────────────────
    # Multi-step tool-loop tasks (read all files, collect data, iterate over sets)
    # need a capable model. 8B models hallucinate fake results instead of calling
    # tools. Qwen3 35B-A3B MoE is the strongest local option (port 8083); Claude
    # Sonnet is the cloud fallback when Qwen3 is offline. Pepe is never tried
    # for agentic tasks.
    if early_task_type == "agentic" and requested_mode in {"auto", ""} and owner.GUPPY_CORE_AVAILABLE:
        from src.guppy.api.routes_backends import _port_alive as _llc_port_alive
        _QWEN3_BACKEND = "llamacpp-qwen3"
        _qwen3_cfg = _LOCAL_BACKENDS.get(_QWEN3_BACKEND, {})
        _qwen3_url = _qwen3_cfg.get("default_url", "")
        _qwen3_port = int(_qwen3_url.rsplit(":", 1)[-1]) if ":" in _qwen3_url else 0
        if _qwen3_port and _llc_port_alive(_qwen3_port):
            _qwen3_model = _LOCAL_BACKEND_DEFAULT_MODELS.get(_QWEN3_BACKEND, "")
            if _qwen3_model:
                _log.info("Agentic task → routing to Qwen3 35B (port %d)", _qwen3_port)
                _agentic_messages = build_router_messages(
                    augmented_system, user_text, sanitize_chat_history(history)
                )
                _agentic_tools = _merged_openai_tools(owner)
                def _qwen3_tool_runner(name: str, args: dict) -> str:
                    return str(owner.core.run_tool(
                        name, args,
                        instance_name=instance_name,
                        instance_type=instance_type,
                    ))
                try:
                    async for token in _stream_llamacpp_tokens(
                        model=_qwen3_model,
                        backend=_QWEN3_BACKEND,
                        messages=_agentic_messages,
                        tools=_agentic_tools,
                        tool_runner=_qwen3_tool_runner,
                        max_tool_rounds=10,  # agentic tasks may need more rounds
                    ):
                        yield token
                    yield _SOURCE_SENTINEL + f"{_QWEN3_BACKEND}:{_qwen3_model}"
                    return
                except RuntimeError as _qwen3_err:
                    _log.warning(
                        "Qwen3 agentic route failed: %s — escalating to Claude Sonnet",
                        _qwen3_err,
                    )

        # Qwen3 offline (or failed) — try Hermes 4 (always-on workspace agent) before cloud.
        # Never fall through to Pepe for agentic tasks.
        _H4_AGENTIC = "llamacpp-hermes4"
        _h4a_cfg = _LOCAL_BACKENDS.get(_H4_AGENTIC, {})
        _h4a_url = _h4a_cfg.get("default_url", "")
        _h4a_port = int(_h4a_url.rsplit(":", 1)[-1]) if ":" in _h4a_url else 0
        if _h4a_port and _llc_port_alive(_h4a_port):
            _h4a_model = _LOCAL_BACKEND_DEFAULT_MODELS.get(_H4_AGENTIC, "")
            if _h4a_model:
                _log.info("Agentic task: Qwen3 offline → Hermes 4 (port %d)", _h4a_port)
                _h4a_messages = build_router_messages(augmented_system, user_text, sanitize_chat_history(history))
                _h4a_tools = _merged_openai_tools(owner)
                def _h4a_tool_runner(name: str, args: dict) -> str:
                    return str(owner.core.run_tool(name, args,
                        instance_name=instance_name, instance_type=instance_type))
                try:
                    async for token in _stream_llamacpp_tokens(
                        model=_h4a_model,
                        backend=_H4_AGENTIC,
                        messages=_h4a_messages,
                        tools=_h4a_tools,
                        tool_runner=_h4a_tool_runner,
                        max_tool_rounds=8,
                    ):
                        yield token
                    yield _SOURCE_SENTINEL + f"{_H4_AGENTIC}:{_h4a_model}"
                    return
                except RuntimeError as _h4a_err:
                    _log.warning("Hermes 4 agentic fallback failed: %s — escalating to Claude Sonnet", _h4a_err)

        _ak = _get_cloud_api_key("anthropic", owner)
        if _ak:
            _log.info("Agentic task: local agents offline, routing to Claude Sonnet (streaming)")
            _agentic_msgs = build_router_messages(augmented_system, user_text, clean_history)
            _claude_tools = owner.core.TOOLS if owner.GUPPY_CORE_AVAILABLE else None
            def _claude_tool_runner(name: str, args: dict) -> str:
                return str(owner.core.run_tool(name, args,
                    instance_name=instance_name, instance_type=instance_type))
            try:
                async for token in _stream_claude_with_tools(
                    api_key=_ak,
                    model="claude-sonnet-4-6",
                    system_prompt=augmented_system,
                    messages=_agentic_msgs,
                    tools=_claude_tools,
                    tool_runner=_claude_tool_runner,
                ):
                    yield token
                yield _SOURCE_SENTINEL + "claude-sonnet-4-6"
                return
            except Exception as _cloud_err:
                _log.warning(
                    "Claude Sonnet agentic fallback failed: %s — continuing to local models",
                    _cloud_err,
                )
        # else: no API key or cloud failed — fall through to best available local

    # ── Complex routing: Hermes 4 (always-on) → Claude Sonnet ────────────────────
    # For complex tasks in auto mode, try the always-on Hermes 4 workspace agent
    # before touching the cloud or the general local pool. Hermes 4 at 14B handles
    # multi-step reasoning and tool chains well; Sonnet is the cloud safety net.
    if early_task_type == "complex" and requested_mode in {"auto", ""} and owner.GUPPY_CORE_AVAILABLE:
        from src.guppy.api.routes_backends import _port_alive as _llc_port_alive
        _H4_COMPLEX = "llamacpp-hermes4"
        _h4c_cfg = _LOCAL_BACKENDS.get(_H4_COMPLEX, {})
        _h4c_url = _h4c_cfg.get("default_url", "")
        _h4c_port = int(_h4c_url.rsplit(":", 1)[-1]) if ":" in _h4c_url else 0
        if _h4c_port and _llc_port_alive(_h4c_port):
            _h4c_model = _LOCAL_BACKEND_DEFAULT_MODELS.get(_H4_COMPLEX, "")
            if _h4c_model:
                _log.info("Complex task → Hermes 4 workspace agent (port %d)", _h4c_port)
                _h4c_messages = build_router_messages(augmented_system, user_text, sanitize_chat_history(history))
                _h4c_tools = _merged_openai_tools(owner)
                def _h4c_tool_runner(name: str, args: dict) -> str:
                    return str(owner.core.run_tool(name, args,
                        instance_name=instance_name, instance_type=instance_type))
                try:
                    async for token in _stream_llamacpp_tokens(
                        model=_h4c_model,
                        backend=_H4_COMPLEX,
                        messages=_h4c_messages,
                        tools=_h4c_tools,
                        tool_runner=_h4c_tool_runner,
                        max_tool_rounds=6,
                    ):
                        yield token
                    yield _SOURCE_SENTINEL + f"{_H4_COMPLEX}:{_h4c_model}"
                    return
                except RuntimeError as _h4c_err:
                    _log.warning("Hermes 4 complex route failed: %s — escalating to Sonnet", _h4c_err)

        _ak = _get_cloud_api_key("anthropic", owner)
        if _ak:
            _log.info("Complex task: Hermes 4 offline, routing to Claude Sonnet")
            _complex_msgs = build_router_messages(augmented_system, user_text, clean_history)
            _complex_tools = owner.core.TOOLS if owner.GUPPY_CORE_AVAILABLE else None
            def _complex_tool_runner(name: str, args: dict) -> str:
                return str(owner.core.run_tool(name, args,
                    instance_name=instance_name, instance_type=instance_type))
            try:
                async for token in _stream_claude_with_tools(
                    api_key=_ak,
                    model="claude-sonnet-4-6",
                    system_prompt=augmented_system,
                    messages=_complex_msgs,
                    tools=_complex_tools,
                    tool_runner=_complex_tool_runner,
                ):
                    yield token
                yield _SOURCE_SENTINEL + "claude-sonnet-4-6"
                return
            except Exception as _cplx_err:
                _log.warning("Claude Sonnet complex fallback failed: %s — continuing to local", _cplx_err)
        # else: fall through to general llama.cpp path

    # ── simple → Hermes 3 (fast 8B, uncensored) → Hermes 4 fallback ─────────────
    if early_task_type == "simple" and requested_mode in {"auto", ""} and owner.GUPPY_CORE_AVAILABLE:
        from src.guppy.api.routes_backends import _port_alive as _llc_port_alive
        _SIMPLE_ORDER = [
            ("llamacpp-hermes3", _LOCAL_BACKEND_DEFAULT_MODELS.get("llamacpp-hermes3", "")),
            ("llamacpp-hermes4", _LOCAL_BACKEND_DEFAULT_MODELS.get("llamacpp-hermes4", "")),
        ]
        for _sb, _sm in _SIMPLE_ORDER:
            _sc = _LOCAL_BACKENDS.get(_sb, {})
            _su = _sc.get("default_url", "")
            _sp = int(_su.rsplit(":", 1)[-1]) if ":" in _su else 0
            if not _sp or not _llc_port_alive(_sp) or not _sm:
                continue
            _s_msgs = build_router_messages(augmented_system, user_text, sanitize_chat_history(history))
            _s_tools = _merged_openai_tools(owner)
            def _s_tr(name: str, args: dict, _i=instance_name, _t=instance_type) -> str:
                return str(owner.core.run_tool(name, args, instance_name=_i, instance_type=_t))
            try:
                async for token in _stream_llamacpp_tokens(
                    model=_sm, backend=_sb, messages=_s_msgs, tools=_s_tools, tool_runner=_s_tr,
                ):
                    yield token
                yield _SOURCE_SENTINEL + f"{_sb}:{_sm}"
                return
            except RuntimeError:
                continue

    # ── teaching → Hermes 4 (quality 14B, always-on) → Hermes 3 fallback ────────
    if early_task_type == "teaching" and requested_mode in {"auto", ""} and owner.GUPPY_CORE_AVAILABLE:
        from src.guppy.api.routes_backends import _port_alive as _llc_port_alive
        _TEACH_ORDER = [
            ("llamacpp-hermes4", _LOCAL_BACKEND_DEFAULT_MODELS.get("llamacpp-hermes4", "")),
            ("llamacpp-hermes3", _LOCAL_BACKEND_DEFAULT_MODELS.get("llamacpp-hermes3", "")),
        ]
        for _tb, _tm in _TEACH_ORDER:
            _tc = _LOCAL_BACKENDS.get(_tb, {})
            _tu = _tc.get("default_url", "")
            _tp = int(_tu.rsplit(":", 1)[-1]) if ":" in _tu else 0
            if not _tp or not _llc_port_alive(_tp) or not _tm:
                continue
            _t_msgs = build_router_messages(augmented_system, user_text, sanitize_chat_history(history))
            _t_tools = _merged_openai_tools(owner)
            def _t_tr(name: str, args: dict, _i=instance_name, _t=instance_type) -> str:
                return str(owner.core.run_tool(name, args, instance_name=_i, instance_type=_t))
            try:
                async for token in _stream_llamacpp_tokens(
                    model=_tm, backend=_tb, messages=_t_msgs, tools=_t_tools, tool_runner=_t_tr,
                ):
                    yield token
                yield _SOURCE_SENTINEL + f"{_tb}:{_tm}"
                return
            except RuntimeError:
                continue
