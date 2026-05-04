"""Unit tests for history trimming and context budget logic.

Covers:
  - _trim_history_to_tokens: preserves recent turns, trims oldest first
  - sanitize_chat_history: applies per-backend limits correctly
  - _SURFACE_HISTORY_LIMITS: companion ≥ 20, workspace ≥ 40, codespace ≥ 30
"""
from __future__ import annotations

import pytest


def _make_history(n: int, chars_per_turn: int = 100) -> list[dict]:
    return [
        {"role": "user" if i % 2 == 0 else "assistant", "content": "x" * chars_per_turn}
        for i in range(n)
    ]


# ── 1. _trim_history_to_tokens ────────────────────────────────────────────

class TestTrimHistoryToTokens:

    def test_short_history_unchanged(self):
        from src.guppy.api.realtime_inference_support import _trim_history_to_tokens
        history = _make_history(5, 50)
        result = _trim_history_to_tokens(history, backend="llamacpp-hermes4", limit=50)
        assert len(result) == 5

    def test_turn_cap_applied_before_char_budget(self):
        """Fixed turn cap (limit) is always applied first."""
        from src.guppy.api.realtime_inference_support import _trim_history_to_tokens
        history = _make_history(100, 10)  # 100 short turns, well within char budget
        result = _trim_history_to_tokens(history, backend="llamacpp-hermes4", limit=20)
        assert len(result) <= 20

    def test_recent_turns_preserved_not_oldest(self):
        """When trimming, the most recent turns survive."""
        from src.guppy.api.realtime_inference_support import _trim_history_to_tokens
        history = [
            {"role": "user", "content": f"turn_{i}"}
            for i in range(50)
        ]
        result = _trim_history_to_tokens(history, backend="llamacpp-hermes4", limit=10)
        assert len(result) <= 10
        # The last items must be preserved
        last_content = {m["content"] for m in result}
        assert "turn_49" in last_content, "Most recent turn must be in result"
        assert "turn_0" not in last_content, "Oldest turn should have been trimmed"

    def test_char_budget_triggers_additional_trim(self):
        """If turns exceed char budget even after limit cap, front is trimmed further."""
        from src.guppy.api.realtime_inference_support import (
            _trim_history_to_tokens,
            _BACKEND_CONTEXT_TOKENS,
            _CONTEXT_RESERVE_TOKENS,
            _CHARS_PER_TOKEN,
        )
        # Use hermes3 (8K context = 8192 tokens)
        max_t = _BACKEND_CONTEXT_TOKENS["llamacpp-hermes3"]
        budget_chars = (max_t - _CONTEXT_RESERVE_TOKENS) * _CHARS_PER_TOKEN
        # Each turn = budget_chars // 2 so 3 turns already exceeds budget
        chars_per_turn = budget_chars // 2 + 1
        history = _make_history(6, chars_per_turn)
        result = _trim_history_to_tokens(history, backend="llamacpp-hermes3", limit=50)
        total_chars = sum(len(m["content"]) for m in result)
        assert total_chars <= budget_chars, (
            f"Trimmed history ({total_chars} chars) exceeds budget ({budget_chars} chars)"
        )

    def test_unknown_backend_uses_default_context(self):
        from src.guppy.api.realtime_inference_support import (
            _trim_history_to_tokens,
            _DEFAULT_CONTEXT_TOKENS,
            _CONTEXT_RESERVE_TOKENS,
            _CHARS_PER_TOKEN,
        )
        budget_chars = (_DEFAULT_CONTEXT_TOKENS - _CONTEXT_RESERVE_TOKENS) * _CHARS_PER_TOKEN
        history = _make_history(200, 50)
        result = _trim_history_to_tokens(history, backend="llamacpp-unknown", limit=200)
        total_chars = sum(len(m["content"]) for m in result)
        assert total_chars <= budget_chars


# ── 2. sanitize_chat_history ─────────────────────────────────────────────

class TestSanitizeChatHistory:

    def test_returns_list_for_dict_history(self):
        """sanitize_chat_history must not crash on non-list input."""
        from src.guppy.api.realtime_inference_support import sanitize_chat_history
        result = sanitize_chat_history({}, limit=10, backend=None)
        assert isinstance(result, list)

    def test_returns_list_for_none(self):
        from src.guppy.api.realtime_inference_support import sanitize_chat_history
        result = sanitize_chat_history(None, limit=10, backend=None)
        assert isinstance(result, list)

    def test_trims_to_limit(self):
        from src.guppy.api.realtime_inference_support import sanitize_chat_history
        history = _make_history(100, 20)
        result = sanitize_chat_history(history, limit=15, backend="llamacpp-hermes4")
        assert len(result) <= 15

    def test_preserves_most_recent(self):
        from src.guppy.api.realtime_inference_support import sanitize_chat_history
        history = [{"role": "user", "content": f"msg_{i}"} for i in range(30)]
        result = sanitize_chat_history(history, limit=10, backend="llamacpp-hermes4")
        contents = {m["content"] for m in result}
        assert "msg_29" in contents
        assert "msg_0" not in contents

    def test_strips_non_role_keys(self):
        """Extra keys like image_url or metadata should be dropped."""
        from src.guppy.api.realtime_inference_support import sanitize_chat_history
        history = [
            {"role": "user", "content": "hello", "image_url": "data:image/...", "ts": 123}
        ]
        result = sanitize_chat_history(history, limit=10, backend=None)
        assert len(result) == 1
        assert set(result[0].keys()) == {"role", "content"}

    def test_drops_messages_with_empty_content(self):
        from src.guppy.api.realtime_inference_support import sanitize_chat_history
        history = [
            {"role": "user", "content": "real message"},
            {"role": "assistant", "content": ""},
            {"role": "user", "content": "another"},
        ]
        result = sanitize_chat_history(history, limit=10, backend=None)
        contents = [m["content"] for m in result]
        assert "" not in contents


# ── 3. Per-surface history limits ─────────────────────────────────────────

class TestSurfaceHistoryLimits:

    def test_companion_limit_at_least_20(self):
        from src.guppy.api.realtime_inference_support import _SURFACE_HISTORY_LIMITS
        assert _SURFACE_HISTORY_LIMITS["companion"] >= 20

    def test_workspace_limit_at_least_40(self):
        from src.guppy.api.realtime_inference_support import _SURFACE_HISTORY_LIMITS
        assert _SURFACE_HISTORY_LIMITS.get("workspace", 0) >= 40

    def test_codespace_limit_at_least_30(self):
        from src.guppy.api.realtime_inference_support import _SURFACE_HISTORY_LIMITS
        assert _SURFACE_HISTORY_LIMITS.get("codespace", 0) >= 30

    def test_companion_limit_smaller_than_workspace(self):
        """Workspace handles larger context; its limit should be ≥ companion's."""
        from src.guppy.api.realtime_inference_support import _SURFACE_HISTORY_LIMITS
        companion = _SURFACE_HISTORY_LIMITS.get("companion", 0)
        workspace = _SURFACE_HISTORY_LIMITS.get("workspace", 0)
        assert workspace >= companion
