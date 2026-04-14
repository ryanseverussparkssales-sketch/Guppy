"""
tests/test_inference_router_fallback.py
Behavior tests for inference_router fallback chains.

Critical scenarios covered:
  - Ollama down  → Haiku wins       (simple task)
  - Haiku down   → Sonnet wins      (simple task)
  - Both cloud down → Ollama wins   (complex task)
  - All backends down → RuntimeError
  - Teaching task → Ollama first    (local preferred)
  - Complex task → Sonnet first     (high-reasoning path)
"""
from __future__ import annotations

import pytest
from unittest.mock import patch, MagicMock
from src.guppy.inference.router import InferenceRouter


# ── Helpers ───────────────────────────────────────────────────────────────────

def _haiku_result(text: str = "haiku response") -> dict:
    return {
        "response": text,
        "model": "claude-haiku-4-5-20251001",
        "source": "haiku",
        "tool_calls": [],
        "metadata": {"timestamp": "2026-01-01T00:00:00"},
    }


def _sonnet_result(text: str = "sonnet response") -> dict:
    return {
        "response": text,
        "model": "claude-sonnet-4-6",
        "source": "sonnet",
        "tool_calls": [],
        "metadata": {"timestamp": "2026-01-01T00:00:00"},
    }


def _local_result(text: str = "local response") -> dict:
    return {
        "response": text,
        "model": "guppy",
        "source": "local",
        "tool_calls": [],
        "metadata": {"timestamp": "2026-01-01T00:00:00"},
    }


def _make_router() -> InferenceRouter:
    """Create a router with Anthropic marked available (key doesn't need to be real)."""
    router = InferenceRouter.__new__(InferenceRouter)
    # Manually set attributes to avoid env-dependent __init__
    router.current_primary = "local"
    router.fallback_chain = ["local", "haiku", "sonnet"]
    router.low_compute_mode = False
    router.local_num_predict = 512
    router.haiku_model_override = InferenceRouter.HAIKU_MODEL
    router.sonnet_model_override = InferenceRouter.SONNET_MODEL
    router.LOCAL_MODEL = InferenceRouter.LOCAL_MODEL
    router.LOCAL_FAST_MODEL = InferenceRouter.LOCAL_FAST_MODEL
    router.LOCAL_TEACH_MODEL = InferenceRouter.LOCAL_TEACH_MODEL
    router.LOCAL_CODE_MODEL = InferenceRouter.LOCAL_CODE_MODEL
    router.LOCAL_VAULT_MODEL = InferenceRouter.LOCAL_VAULT_MODEL
    router.LOCAL_TIER_MAP = {
        "simple": router.LOCAL_FAST_MODEL,
        "complex": router.LOCAL_MODEL,
        "teaching": router.LOCAL_TEACH_MODEL,
    }
    router.anthropic_available = True
    router.anthropic_client = MagicMock()
    return router


# ── Tests: simple task fallback chain ────────────────────────────────────────

class TestSimpleTaskFallback:

    def test_ollama_down_haiku_wins(self):
        """
        Scenario: simple task, Ollama unreachable → Haiku should answer.
        The most expected production failure mode: local model offline.
        """
        router = _make_router()
        with (
            patch.object(router, "_classify_task", return_value="simple"),
            patch.object(router, "query_haiku", return_value=_haiku_result()) as mock_haiku,
            patch.object(router, "query_sonnet") as mock_sonnet,
            patch.object(router, "query_local") as mock_local,
        ):
            text, source, meta = router.query_smart("sys", "hello")

        assert source == "haiku"
        assert text == "haiku response"
        mock_haiku.assert_called_once()
        mock_sonnet.assert_not_called()
        mock_local.assert_not_called()

    def test_haiku_down_sonnet_wins(self):
        """
        Scenario: simple task, Haiku returns None (timeout/error) → Sonnet should answer.
        """
        router = _make_router()
        with (
            patch.object(router, "_classify_task", return_value="simple"),
            patch.object(router, "query_haiku", return_value=None) as mock_haiku,
            patch.object(router, "query_sonnet", return_value=_sonnet_result()) as mock_sonnet,
            patch.object(router, "query_local") as mock_local,
        ):
            text, source, meta = router.query_smart("sys", "hello")

        assert source == "sonnet"
        assert text == "sonnet response"
        mock_haiku.assert_called_once()
        mock_sonnet.assert_called_once()
        mock_local.assert_not_called()

    def test_both_cloud_down_local_wins(self):
        """
        Scenario: simple task, Haiku and Sonnet both fail → local is last resort.
        """
        router = _make_router()
        with (
            patch.object(router, "_classify_task", return_value="simple"),
            patch.object(router, "query_haiku", return_value=None),
            patch.object(router, "query_sonnet", return_value=None),
            patch.object(router, "query_local", return_value=_local_result()) as mock_local,
        ):
            text, source, meta = router.query_smart("sys", "hello")

        assert source == "local"
        assert text == "local response"
        mock_local.assert_called_once()

    def test_all_backends_down_raises(self):
        """
        Scenario: all backends fail → RuntimeError with informative message.
        Ensures the caller is never silently left with an empty response.
        """
        router = _make_router()
        with (
            patch.object(router, "_classify_task", return_value="simple"),
            patch.object(router, "query_haiku", return_value=None),
            patch.object(router, "query_sonnet", return_value=None),
            patch.object(router, "query_local", return_value=None),
        ):
            with pytest.raises(RuntimeError, match="All backends failed"):
                router.query_smart("sys", "hello")


# ── Tests: complex task fallback chain ───────────────────────────────────────

class TestComplexTaskFallback:

    def test_sonnet_wins_on_complex_task(self):
        """
        Complex task: Sonnet is tried first for best reasoning quality.
        """
        router = _make_router()
        with (
            patch.object(router, "_classify_task", return_value="complex"),
            patch.object(router, "query_sonnet", return_value=_sonnet_result()) as mock_sonnet,
            patch.object(router, "query_haiku") as mock_haiku,
            patch.object(router, "query_local") as mock_local,
        ):
            text, source, meta = router.query_smart("sys", "complex question")

        assert source == "sonnet"
        mock_sonnet.assert_called_once()
        mock_haiku.assert_not_called()
        mock_local.assert_not_called()

    def test_sonnet_down_haiku_wins_on_complex(self):
        """
        Complex task, Sonnet fails → Haiku is the next fallback.
        """
        router = _make_router()
        with (
            patch.object(router, "_classify_task", return_value="complex"),
            patch.object(router, "query_sonnet", return_value=None),
            patch.object(router, "query_haiku", return_value=_haiku_result()) as mock_haiku,
            patch.object(router, "query_local") as mock_local,
        ):
            text, source, meta = router.query_smart("sys", "complex question")

        assert source == "haiku"
        mock_haiku.assert_called_once()
        mock_local.assert_not_called()

    def test_both_cloud_down_local_wins_on_complex(self):
        """
        Complex task, both cloud backends fail → local is the final fallback.
        """
        router = _make_router()
        with (
            patch.object(router, "_classify_task", return_value="complex"),
            patch.object(router, "query_sonnet", return_value=None),
            patch.object(router, "query_haiku", return_value=None),
            patch.object(router, "query_local", return_value=_local_result()),
        ):
            text, source, meta = router.query_smart("sys", "complex question")

        assert source == "local"

    def test_sonnet_rate_limit_falls_through_to_haiku(self):
        """A Sonnet 429 should not abort the complex-task fallback chain."""
        router = _make_router()
        router.anthropic_client.messages.create.side_effect = RuntimeError("429 Too Many Requests")

        with (
            patch.object(router, "_classify_task", return_value="complex"),
            patch.object(router, "query_haiku", return_value=_haiku_result()) as mock_haiku,
            patch.object(router, "query_local") as mock_local,
        ):
            text, source, meta = router.query_smart("sys", "complex question")

        assert source == "haiku"
        assert text == "haiku response"
        mock_haiku.assert_called_once()
        mock_local.assert_not_called()

    def test_all_backends_down_complex_raises(self):
        router = _make_router()
        with (
            patch.object(router, "_classify_task", return_value="complex"),
            patch.object(router, "query_sonnet", return_value=None),
            patch.object(router, "query_haiku", return_value=None),
            patch.object(router, "query_local", return_value=None),
        ):
            with pytest.raises(RuntimeError, match="All backends failed"):
                router.query_smart("sys", "complex question")


# ── Tests: teaching task fallback chain ──────────────────────────────────────

class TestTeachingTaskFallback:

    def test_teaching_tries_local_first(self):
        """
        Teaching task: Ollama/Merlin should be attempted first (Socratic mode).
        """
        router = _make_router()
        with (
            patch.object(router, "_classify_task", return_value="teaching"),
            patch.object(router, "query_local", return_value=_local_result()) as mock_local,
            patch.object(router, "query_haiku") as mock_haiku,
            patch.object(router, "query_sonnet") as mock_sonnet,
        ):
            text, source, meta = router.query_smart("sys", "explain recursion")

        assert source == "local"
        mock_local.assert_called_once()
        mock_haiku.assert_not_called()
        mock_sonnet.assert_not_called()

    def test_teaching_local_down_falls_back_to_haiku(self):
        """
        Teaching task, Ollama unavailable → Haiku takes over.
        """
        router = _make_router()
        with (
            patch.object(router, "_classify_task", return_value="teaching"),
            patch.object(router, "query_local", return_value=None),
            patch.object(router, "query_haiku", return_value=_haiku_result()) as mock_haiku,
            patch.object(router, "query_sonnet") as mock_sonnet,
        ):
            text, source, meta = router.query_smart("sys", "explain recursion")

        assert source == "haiku"
        mock_haiku.assert_called_once()
        mock_sonnet.assert_not_called()

    def test_teaching_all_down_raises(self):
        router = _make_router()
        with (
            patch.object(router, "_classify_task", return_value="teaching"),
            patch.object(router, "query_local", return_value=None),
            patch.object(router, "query_haiku", return_value=None),
            patch.object(router, "query_sonnet", return_value=None),
        ):
            with pytest.raises(RuntimeError, match="All backends failed"):
                router.query_smart("sys", "explain recursion")


# ── Tests: _ollama_call failure isolation ────────────────────────────────────

class TestOllamaCallFailure:

    def test_ollama_call_urlerror_returns_none(self):
        """
        _ollama_call must return None (not raise) on URLError so callers can fall through.
        """
        import urllib.error
        router = _make_router()
        # urlopen raises URLError (Ollama not running)
        with patch("urllib.request.urlopen", side_effect=urllib.error.URLError("Connection refused")):
            result = router._ollama_call(
                model="guppy",
                system_prompt="sys",
                user_text="hello",
                timeout=1,
            )
        assert result is None

    def test_ollama_call_timeout_returns_none(self):
        """
        _ollama_call must return None on socket timeout, not raise.
        """
        import socket
        router = _make_router()
        with patch("urllib.request.urlopen", side_effect=socket.timeout("timed out")):
            result = router._ollama_call(
                model="guppy",
                system_prompt="sys",
                user_text="hello",
                timeout=1,
            )
        assert result is None
