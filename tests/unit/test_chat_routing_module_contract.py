from __future__ import annotations

from unittest.mock import patch

import pytest

from src.guppy.api import server as guppy_api
from src.guppy.api.routes_core import build_core_router
from src.guppy.api.routes_instances import build_instances_router
from src.guppy.api.routes_ops import build_ops_router
from src.guppy.api.routes_realtime import build_realtime_router
from src.guppy.api import services_runtime


class _FakeRouter:
    def __init__(self) -> None:
        self.anthropic_available = True
        self.LOCAL_MODEL = "guppy"
        self.LOCAL_TIER_MAP = {
            "simple": "guppy-fast",
            "complex": "guppy",
            "teaching": "guppy-teach",
        }

    def resolve_ui_route(self, **_kwargs):
        return {
            "task_type": "simple",
            "route": "haiku",
            "route_reason": "simple task classification",
            "executor": "claude",
            "model": "claude-haiku-4-5-20251001",
            "backup_model": "claude-sonnet-4-6",
        }

    def _classify_task(self, *_args, **_kwargs):
        return "simple"

    def query_local_paired(self, *_args, **_kwargs):
        return None

    def query_smart(self, *_args, **_kwargs):
        return ("smart response", "haiku", {"route_decision": "smart"})


def test_auto_mode_executes_ui_route_decision_through_claude_tools() -> None:
    router = _FakeRouter()

    with patch.object(guppy_api, "GUPPY_CORE_AVAILABLE", True), patch.object(
        guppy_api, "INFERENCE_ROUTER_AVAILABLE", True
    ), patch.object(guppy_api, "get_router", return_value=router), patch.object(
        guppy_api, "_call_claude_with_tools", return_value="Lima"
    ) as cloud_call, patch.object(guppy_api, "_call_ollama_with_tools") as local_call:
        response = guppy_api._call_unified_inference("What is the capital of Peru?", "SYSTEM", mode="auto")

    assert response == "Lima"
    cloud_call.assert_called_once()
    local_call.assert_not_called()
    _, kwargs = cloud_call.call_args
    assert kwargs["preferred_model"] == "claude-haiku-4-5-20251001"
    assert kwargs["backup_model"] == "claude-sonnet-4-6"


def test_auto_mode_executes_ollama_route_when_ui_decision_is_local() -> None:
    router = _FakeRouter()
    router.resolve_ui_route = lambda **_kwargs: {
        "task_type": "teaching",
        "route": "ollama_teaching",
        "route_reason": "teaching task -> guppy-teach/Ollama",
        "executor": "ollama",
        "model": "guppy-teach",
        "backup_model": "",
    }

    with patch.object(guppy_api, "GUPPY_CORE_AVAILABLE", True), patch.object(
        guppy_api, "INFERENCE_ROUTER_AVAILABLE", True
    ), patch.object(guppy_api, "get_router", return_value=router), patch.object(
        guppy_api,
        "_local_runtime_warm_cached_or_unknown",
        return_value={"backend": "ollama", "model": "guppy-teach", "chat_ready": True, "chat_state": "READY", "chat_detail": "warm"},
    ), patch.object(
        guppy_api, "_call_ollama_with_tools", return_value="Teaching answer"
    ) as local_call, patch.object(guppy_api, "_call_claude_with_tools") as cloud_call:
        response = guppy_api._call_unified_inference("Explain recursion", "SYSTEM", mode="auto")

    assert response == "Teaching answer"
    local_call.assert_called_once()
    cloud_call.assert_not_called()
    _, kwargs = local_call.call_args
    assert kwargs["model_override"] == "guppy-teach"


def test_local_mode_uses_tiered_model_with_tool_capable_wrapper() -> None:
    router = _FakeRouter()

    with patch.object(guppy_api, "GUPPY_CORE_AVAILABLE", True), patch.object(
        guppy_api, "INFERENCE_ROUTER_AVAILABLE", True
    ), patch.object(guppy_api, "get_router", return_value=router), patch.object(
        guppy_api,
        "_local_runtime_warm_cached_or_unknown",
        return_value={"backend": "ollama", "model": "guppy-fast", "chat_ready": True, "chat_state": "READY", "chat_detail": "warm"},
    ), patch.object(
        guppy_api, "_call_ollama_with_tools", return_value="Fast local answer"
    ) as local_call:
        response = guppy_api._call_unified_inference("Ping", "SYSTEM", mode="local")

    assert response == "Fast local answer"
    _, kwargs = local_call.call_args
    assert kwargs["model_override"] == "guppy-fast"


def test_local_mode_can_use_opt_in_lemonade_runtime() -> None:
    router = _FakeRouter()

    with patch.dict(
        guppy_api.os.environ,
        {
            "GUPPY_LOCAL_RUNTIME_BACKEND": "lemonade",
            "GUPPY_LEMONADE_FAST_MODEL": "Llama-3.2-1B-Instruct-GGUF",
        },
        clear=False,
    ), patch.object(guppy_api, "GUPPY_CORE_AVAILABLE", True), patch.object(
        guppy_api, "INFERENCE_ROUTER_AVAILABLE", True
    ), patch.object(guppy_api, "get_router", return_value=router), patch.object(
        guppy_api,
        "_local_runtime_warm_cached_or_unknown",
        return_value={"backend": "lemonade", "model": "Llama-3.2-1B-Instruct-GGUF", "chat_ready": True, "chat_state": "READY", "chat_detail": "warm"},
    ), patch.object(
        guppy_api, "_call_selected_local_runtime", return_value="Lemonade lane answer"
    ) as local_call, patch.object(guppy_api, "_call_ollama_with_tools") as ollama_call:
        response = guppy_api._call_unified_inference("Ping", "SYSTEM", mode="local")

    assert response == "Lemonade lane answer"
    local_call.assert_called_once()
    ollama_call.assert_not_called()
    _, kwargs = local_call.call_args
    assert kwargs["model_override"] == "guppy-fast"


def test_local_runtime_status_reports_partial_when_alias_mapped_lane_is_usable() -> None:
    with patch.dict(
        guppy_api.os.environ,
        {
            "GUPPY_LOCAL_RUNTIME_BACKEND": "lemonade",
            "GUPPY_LEMONADE_FAST_MODEL": "Llama-3.2-1B-Instruct-GGUF",
        },
        clear=False,
    ), patch.object(
        guppy_api,
        "_fetch_lemonade_model_ids",
        return_value={"Llama-3.2-1B-Instruct-GGUF"},
    ):
        payload = guppy_api._build_local_runtime_status()

    assert payload["backend"] == "lemonade"
    assert payload["state"] == "PARTIAL"
    assert "fast" in payload["available_roles"]
    assert "complex" in payload["missing_roles"]
    assert payload["policy"]["runtime_baseline"] == "ollama"
    assert payload["policy"]["daily_model_promotion_candidate"] == "qwen3:8b"
    assert payload["chat_ready"] is False
    assert payload["chat_state"] == "UNKNOWN"


def test_selected_local_runtime_fast_fails_while_ollama_chat_lane_warms() -> None:
    with patch.dict(
        guppy_api.os.environ,
        {"GUPPY_LOCAL_RUNTIME_BACKEND": "ollama"},
        clear=False,
    ), patch.object(
        guppy_api,
        "_local_runtime_warm_cached_or_unknown",
        return_value={
            "backend": "ollama",
            "model": "guppy",
            "chat_ready": False,
            "chat_state": "WARMING",
            "chat_detail": "guppy warmup in progress",
        },
    ), patch.object(guppy_api, "_trigger_local_runtime_warm_refresh") as warm_trigger, patch.object(
        guppy_api, "_call_ollama_with_tools"
    ) as local_call:
        result = guppy_api._call_selected_local_runtime("Ping", "SYSTEM")

    warm_trigger.assert_called_once()
    local_call.assert_called_once()
    assert result is local_call.return_value


def test_startup_readiness_marks_local_runtime_partial_until_chat_ready() -> None:
    with patch.object(
        guppy_api,
        "_build_local_runtime_status",
        return_value={
            "backend": "ollama",
            "state": "READY",
            "detail": "Ollama model registry reachable",
            "chat_ready": False,
            "chat_state": "WARMING",
            "chat_detail": "guppy warmup in progress",
        },
    ), patch.object(guppy_api, "DEV_MODE", True), patch.object(
        guppy_api, "GUPPY_CORE_AVAILABLE", False
    ), patch.object(
        guppy_api, "GUPPY_VOICE_AVAILABLE", False
    ), patch.object(
        guppy_api, "GUPPY_DAEMON_AVAILABLE", False
    ), patch.object(
        guppy_api, "GUPPY_MEMORY_AVAILABLE", False
    ):
        payload = guppy_api._build_startup_readiness_payload()

    assert payload["checks"]["local_runtime"]["state"] == "PARTIAL"
    assert "warmup" in payload["checks"]["local_runtime"]["detail"].lower()


def test_claude_mode_raises_clear_error_when_route_is_unavailable() -> None:
    router = _FakeRouter()
    router.anthropic_available = False
    router.resolve_ui_route = lambda **_kwargs: {
        "task_type": "simple",
        "route": "cloud_unavailable",
        "route_reason": "manual cloud mode requested but API key missing",
        "executor": "error",
        "error": "cloud_only mode requires ANTHROPIC_API_KEY",
    }

    with patch.object(guppy_api, "GUPPY_CORE_AVAILABLE", True), patch.object(
        guppy_api, "INFERENCE_ROUTER_AVAILABLE", True
    ), patch.object(guppy_api, "get_router", return_value=router):
        with pytest.raises(RuntimeError, match="ANTHROPIC_API_KEY"):
            guppy_api._call_unified_inference("Hello", "SYSTEM", mode="claude")


def _normalized_route_signatures(router) -> set[tuple[str, tuple[str, ...] | None]]:
    signatures: set[tuple[str, tuple[str, ...] | None]] = set()
    for route in router.routes:
        methods = getattr(route, "methods", None)
        normalized_methods = tuple(sorted(methods)) if methods else None
        signatures.add((route.path, normalized_methods))
    return signatures


def test_api_route_registration_parity_with_modular_routers() -> None:
    modular_routes = set()
    for builder in (
        build_core_router,
        build_instances_router,
        build_ops_router,
        build_realtime_router,
    ):
        modular_routes |= _normalized_route_signatures(builder(guppy_api._server_context))

    app_routes = _normalized_route_signatures(guppy_api.app)
    missing = modular_routes - app_routes
    assert not missing, f"Missing app route registrations: {sorted(missing)}"


def test_startup_readiness_cache_expiry_transitions_with_monkeypatched_time(monkeypatch) -> None:
    state = guppy_api._runtime_state
    original_expires_at = state.startup_check_cache.get("expires_at", 0.0)
    try:
        with state.startup_check_cache_lock:
            state.startup_check_cache["expires_at"] = 200.0

        monkeypatch.setattr(services_runtime.time, "time", lambda: 150.0)
        assert guppy_api._startup_readiness_cache_expired() is False

        monkeypatch.setattr(services_runtime.time, "time", lambda: 250.0)
        assert guppy_api._startup_readiness_cache_expired() is True
    finally:
        with state.startup_check_cache_lock:
            state.startup_check_cache["expires_at"] = original_expires_at
