from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from src.guppy.api import realtime_inference_support


class _FakeRouter:
    LOCAL_MODEL = "guppy"
    LOCAL_CODE_MODEL = "guppy-code"
    HAIKU_BOOST_CODE_REVIEW = "code"
    LOCAL_TIER_MAP = {"simple": "guppy-fast", "complex": "guppy"}
    anthropic_available = True

    def _classify_task(self, *_args, **_kwargs):
        return "simple"

    def query_local_paired(self, *_args, **_kwargs):
        return None

    def query_with_boost(self, *_args, **_kwargs):
        return {"response": "code", "source": "local", "metadata": {"usage": {}}}

    def resolve_ui_route(self, **_kwargs):
        return {
            "executor": "claude",
            "model": "claude-haiku",
            "backup_model": "claude-sonnet",
        }

    def query_smart(self, *_args, **_kwargs):
        return ("smart", "haiku", {"usage": {}})


def _build_owner() -> SimpleNamespace:
    owner = SimpleNamespace()
    owner.GUPPY_CORE_AVAILABLE = True
    owner.INFERENCE_ROUTER_AVAILABLE = True
    owner.os = SimpleNamespace(environ={})
    owner.core = SimpleNamespace(TOOLS=[])
    owner.logger = Mock()
    owner.get_router = Mock(return_value=_FakeRouter())
    owner._call_claude_with_tools = Mock(return_value="claude")
    owner._call_ollama_with_tools = Mock(return_value="ollama")
    owner._call_selected_local_runtime = Mock(return_value="local")
    return owner


def test_sanitize_chat_history_filters_invalid_entries() -> None:
    history = [
        {"role": "system", "content": "ignore"},
        {"role": "user", "content": "hello"},
        {"role": "assistant", "content": "reply"},
        {"role": "user", "content": ""},
        "bad",
    ]

    result = realtime_inference_support.sanitize_chat_history(history)

    assert result == [
        {"role": "user", "content": "hello"},
        {"role": "assistant", "content": "reply"},
    ]


def test_call_unified_inference_falls_back_to_claude_without_router_when_key_set() -> None:
    owner = _build_owner()
    owner.INFERENCE_ROUTER_AVAILABLE = False
    owner.os.environ["ANTHROPIC_API_KEY"] = "sk-test"

    result = realtime_inference_support.call_unified_inference(owner, "Hi", "SYSTEM")

    assert result == "claude"
    owner._call_claude_with_tools.assert_called_once()


def test_call_unified_inference_raises_without_router_and_no_key() -> None:
    owner = _build_owner()
    owner.INFERENCE_ROUTER_AVAILABLE = False

    with pytest.raises(RuntimeError, match="llamacpp backend"):
        realtime_inference_support.call_unified_inference(owner, "Hi", "SYSTEM")


def test_call_unified_inference_local_mode_uses_selected_runtime() -> None:
    owner = _build_owner()

    result = realtime_inference_support.call_unified_inference(
        owner,
        "Ping",
        "SYSTEM",
        mode="local",
    )

    assert result == "local"
    _, kwargs = owner._call_selected_local_runtime.call_args
    assert kwargs["model_override"] == "guppy-fast"


def test_call_unified_inference_surfaces_route_errors_for_explicit_cloud_mode() -> None:
    owner = _build_owner()
    owner.get_router.return_value.resolve_ui_route = lambda **_kwargs: {
        "executor": "error",
        "error": "cloud_only mode requires ANTHROPIC_API_KEY",
    }

    with pytest.raises(RuntimeError, match="ANTHROPIC_API_KEY"):
        realtime_inference_support.call_unified_inference(
            owner,
            "Hello",
            "SYSTEM",
            mode="claude",
        )
