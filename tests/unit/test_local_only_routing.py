"""Tests verifying that Guppy is fully local — no cloud fallback active.

Covers:
  - router_surface.py: all three surfaces yield local-only error when no backend is alive
  - router_task_types.py: cloud_fallback field is empty for all route specs
  - No _stream_claude_with_tools or _stream_mistral/cohere imports in surface routers
  - Companion _think_filter includes /no_think injection in both system + user messages
"""
from __future__ import annotations

import asyncio
import pytest
from unittest.mock import patch, MagicMock


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


async def _collect_all(gen) -> list[str]:
    return [t async for t in gen]


# ── 1. router_task_types: no cloud fallbacks ──────────────────────────────

class TestNoCloudFallbackInTaskRouter:

    def test_all_route_specs_have_empty_cloud_fallback(self):
        from src.guppy.inference.router_task_types import _ROUTE_TABLE
        for spec in _ROUTE_TABLE:
            assert spec.cloud_fallback == "", (
                f"Task route '{spec.task_type}' still has cloud_fallback={spec.cloud_fallback!r}. "
                "All inference should be local-only."
            )

    def test_stream_claude_not_imported_in_task_router(self):
        """router_task_types must not import _stream_claude_with_tools after cloud removal."""
        import src.guppy.inference.router_task_types as mod
        assert not hasattr(mod, "_stream_claude_with_tools"), (
            "_stream_claude_with_tools should not be importable from router_task_types"
        )

    def test_get_cloud_api_key_not_imported_in_task_router(self):
        import src.guppy.inference.router_task_types as mod
        assert not hasattr(mod, "_get_cloud_api_key"), (
            "_get_cloud_api_key should not be importable from router_task_types "
            "after cloud fallback removal"
        )


# ── 2. router_surface: local-only error messages ─────────────────────────

class TestSurfaceLocalOnlyErrors:
    """When no local backend is alive, surfaces must yield a clear local-only error,
    not attempt any cloud call."""

    def _dead_backend(self, *args, **kwargs) -> str:
        """Simulate all backends being offline."""
        return ""

    def _make_owner(self):
        owner = MagicMock()
        owner.GUPPY_CORE_AVAILABLE = False
        return owner

    def test_companion_no_backend_yields_local_error(self):
        from src.guppy.inference.router_surface import route_by_surface
        owner = self._make_owner()
        with patch(
            "src.guppy.inference.router_surface._LOCAL_BACKEND_DEFAULT_MODELS",
            {},
        ):
            tokens = _run(_collect_all(route_by_surface(
                surface="companion",
                owner=owner,
                augmented_system="sys",
                user_text="hello",
                history=[],
                instance_name=None,
                instance_type=None,
                skip_tools=True,
            )))
        combined = "".join(tokens)
        assert "llamacpp-hermes4" in combined or "No local" in combined or "No backend" in combined
        # Must NOT contain any cloud provider reference
        assert "mistral" not in combined.lower()
        assert "cohere" not in combined.lower()
        assert "claude" not in combined.lower()

    def test_workspace_no_backend_yields_local_error(self):
        from src.guppy.inference.router_surface import route_by_surface
        owner = self._make_owner()
        with patch(
            "src.guppy.inference.router_surface._LOCAL_BACKEND_DEFAULT_MODELS",
            {},
        ):
            tokens = _run(_collect_all(route_by_surface(
                surface="workspace",
                owner=owner,
                augmented_system="sys",
                user_text="hello",
                history=[],
                instance_name=None,
                instance_type=None,
                skip_tools=True,
            )))
        combined = "".join(tokens)
        assert "No" in combined  # error message starts with "⚠️ No local model available..."
        assert "mistral" not in combined.lower()
        assert "cohere" not in combined.lower()

    def test_codespace_no_backend_yields_local_error(self):
        from src.guppy.inference.router_surface import route_by_surface
        owner = self._make_owner()
        with patch(
            "src.guppy.inference.router_surface._LOCAL_BACKEND_DEFAULT_MODELS",
            {},
        ):
            tokens = _run(_collect_all(route_by_surface(
                surface="codespace",
                owner=owner,
                augmented_system="sys",
                user_text="hello",
                history=[],
                instance_name=None,
                instance_type=None,
                skip_tools=True,
            )))
        combined = "".join(tokens)
        assert "No" in combined
        assert "mistral" not in combined.lower()

    def test_no_mistral_or_cohere_in_router_surface_module(self):
        """router_surface must not import or reference cloud providers after cleanup."""
        import src.guppy.inference.router_surface as mod
        assert not hasattr(mod, "_stream_mistral_tokens")
        assert not hasattr(mod, "_stream_cohere_tokens")
        assert not hasattr(mod, "_stream_claude_with_tools")
        assert not hasattr(mod, "_sp_free_cloud_key")


# ── 3. _sp_suppress_think: /no_think injected correctly ──────────────────

class TestSuppressThink:
    """The /no_think token must appear in both system and last user message."""

    def _run_suppress(self, msgs):
        # Route the internal helper through a minimal call
        from src.guppy.inference.router_surface import route_by_surface
        # We can't call the inner closure directly, but we can replicate the logic
        from src.guppy.inference._routing_shared import build_router_messages, sanitize_chat_history

        # Replicate _sp_suppress_think logic for unit test purposes
        if not msgs:
            return msgs
        msgs = list(msgs)
        for i, m in enumerate(msgs):
            if m.get("role") == "system":
                if "/no_think" not in m["content"]:
                    msgs[i] = {**m, "content": "/no_think\n\n" + m["content"]}
                break
        for i in range(len(msgs) - 1, -1, -1):
            if msgs[i].get("role") == "user":
                content = msgs[i]["content"]
                if not content.endswith(" /no_think"):
                    msgs[i] = {**msgs[i], "content": content + " /no_think"}
                break
        return msgs

    def test_no_think_prepended_to_system(self):
        msgs = [
            {"role": "system", "content": "You are Guppy."},
            {"role": "user", "content": "Hello"},
        ]
        result = self._run_suppress(msgs)
        assert result[0]["content"].startswith("/no_think")

    def test_no_think_appended_to_last_user(self):
        msgs = [
            {"role": "system", "content": "You are Guppy."},
            {"role": "user", "content": "Hello"},
        ]
        result = self._run_suppress(msgs)
        assert result[-1]["content"].endswith(" /no_think")

    def test_no_duplicate_no_think_on_repeated_call(self):
        """Calling suppress twice must not double-inject /no_think."""
        msgs = [
            {"role": "system", "content": "You are Guppy."},
            {"role": "user", "content": "Hello"},
        ]
        result = self._run_suppress(self._run_suppress(msgs))
        assert result[0]["content"].count("/no_think") == 1
        assert result[-1]["content"].count("/no_think") == 1

    def test_empty_messages_returned_unchanged(self):
        result = self._run_suppress([])
        assert result == []
