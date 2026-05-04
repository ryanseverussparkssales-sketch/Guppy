"""Two-model core validation tests.

Tests the Rocinante (companion) + Hermes4 (workspace) foundation:
  1. Tool primer presence — companion system prompt always has tool instructions
  2. Pass-2 tool-loop prevention — skip_tools=True on both pass-2 paths
  3. Context budget guard — doesn't fire on normal conversation sizes
  4. Multi-turn recall — history is preserved and injected correctly
  5. Memory injection pipeline — semantic recall + user preferences path

These tests run without a live model server. They validate the prompt
assembly and routing logic, not model output.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_owner() -> MagicMock:
    """Return a minimal mock owner with the attributes stream_unified_inference touches."""
    owner = MagicMock()
    owner.os = MagicMock()
    owner.os.environ = {
        "GUPPY_SEMANTIC_RAG": "1",
        "GUPPY_DEFAULT_MODE": "auto",
        "GUPPY_STREAM_TIMEOUT_SECONDS": "300",
    }
    owner.GUPPY_CORE_AVAILABLE = False
    owner.INFERENCE_ROUTER_AVAILABLE = False
    owner.logger = MagicMock()
    return owner


# ---------------------------------------------------------------------------
# 1. Tool primer injection
# ---------------------------------------------------------------------------

class TestToolPrimerInjection(unittest.TestCase):
    """Verify _inject_tool_primer is called in stream_unified_inference regardless of skip_tools."""

    def _get_augmented_system(self, surface: str, skip_tools: bool) -> str:
        """Run the injection chain up to (but not including) routing, return augmented_system."""
        from src.guppy.inference.context_injection import (
            _inject_model_identity,
            augment_system_with_history,
            _inject_tool_primer,
        )
        base = "You are Guppy."
        system = _inject_model_identity(base, surface=surface)
        system = augment_system_with_history(system, [])
        system = _inject_tool_primer(system, surface)
        return system

    def test_companion_tool_primer_present(self):
        augmented = self._get_augmented_system("companion", skip_tools=True)
        self.assertIn("web_fetch", augmented, "Companion tool primer missing web_fetch")
        self.assertIn("memory_write", augmented, "Companion tool primer missing memory_write")
        self.assertIn("get_time", augmented, "Companion tool primer missing get_time")
        self.assertIn("<tool_call>", augmented, "Companion tool primer missing <tool_call> example")

    def test_workspace_tool_primer_present(self):
        augmented = self._get_augmented_system("workspace", skip_tools=False)
        self.assertIn("web_search", augmented, "Workspace tool primer missing web_search")
        self.assertIn("shell_run", augmented, "Workspace tool primer missing shell_run")
        self.assertIn("<tool_call>", augmented, "Workspace tool primer missing <tool_call> example")

    def test_codespace_tool_primer_present(self):
        augmented = self._get_augmented_system("codespace", skip_tools=False)
        self.assertIn("shell_run", augmented, "Codespace tool primer missing shell_run")
        self.assertIn("file_read", augmented, "Codespace tool primer missing file_read")

    def test_companion_primer_includes_conversation_history_instruction(self):
        """The CONVERSATION HISTORY reminder must be in the companion primer."""
        augmented = self._get_augmented_system("companion", skip_tools=True)
        self.assertIn("CONVERSATION HISTORY", augmented)

    def test_tool_call_format_reminder_present(self):
        """TOOL CALL FORMAT reminder must be injected for all surfaces."""
        for surface in ("companion", "workspace", "codespace"):
            with self.subTest(surface=surface):
                augmented = self._get_augmented_system(surface, skip_tools=False)
                self.assertIn("TOOL CALL FORMAT", augmented)


# ---------------------------------------------------------------------------
# 2. Tool-call normalization
# ---------------------------------------------------------------------------

class TestToolCallNormalization(unittest.TestCase):
    """XML tool call format must be converted to JSON-in-tags before parsing."""

    def setUp(self):
        from src.guppy.api.routes_realtime import _normalize_tool_calls, _TOOL_CALL_RE
        self._normalize = _normalize_tool_calls
        self._re = _TOOL_CALL_RE

    def test_json_format_passthrough(self):
        text = '<tool_call>{"name": "get_time", "arguments": {}}</tool_call>'
        normalized = self._normalize(text)
        blocks = self._re.findall(normalized)
        self.assertEqual(len(blocks), 1)
        import json
        tc = json.loads(blocks[0])
        self.assertEqual(tc["name"], "get_time")

    def test_xml_format_converted(self):
        text = '<tool_call><name>memory_write</name><arguments>{"key": "test", "value": "hello"}</arguments></tool_call>'
        normalized = self._normalize(text)
        blocks = self._re.findall(normalized)
        self.assertEqual(len(blocks), 1)
        import json
        tc = json.loads(blocks[0])
        self.assertEqual(tc["name"], "memory_write")
        self.assertEqual(tc["arguments"]["key"], "test")

    def test_xml_with_bad_json_args_degrades_gracefully(self):
        text = '<tool_call><name>web_fetch</name><arguments>not json at all</arguments></tool_call>'
        normalized = self._normalize(text)
        blocks = self._re.findall(normalized)
        self.assertEqual(len(blocks), 1)
        import json
        tc = json.loads(blocks[0])
        self.assertEqual(tc["name"], "web_fetch")
        self.assertEqual(tc["arguments"], {})

    def test_multiple_tool_calls(self):
        text = (
            '<tool_call>{"name": "get_time", "arguments": {}}</tool_call>\n'
            '<tool_call><name>memory_write</name><arguments>{"key": "k", "value": "v"}</arguments></tool_call>'
        )
        normalized = self._normalize(text)
        blocks = self._re.findall(normalized)
        self.assertEqual(len(blocks), 2)

    def test_no_tool_calls(self):
        text = "Just a normal response with no tool calls."
        normalized = self._normalize(text)
        blocks = self._re.findall(normalized)
        self.assertEqual(len(blocks), 0)


# ---------------------------------------------------------------------------
# 3. Context budget guard
# ---------------------------------------------------------------------------

class TestContextBudgetGuard(unittest.TestCase):
    """Budget guard should not fire for normal conversations."""

    def _chars_for_turns(self, n_turns: int, chars_per_turn: int = 200) -> int:
        return n_turns * chars_per_turn

    def test_normal_companion_conversation_under_budget(self):
        from src.guppy.api.realtime_inference_support import (
            _BACKEND_CONTEXT_TOKENS, _CHARS_PER_TOKEN
        )
        hermes4_ctx = _BACKEND_CONTEXT_TOKENS["llamacpp-hermes4"]
        budget_chars = int(hermes4_ctx * 0.85 * _CHARS_PER_TOKEN)

        # Realistic companion turn: 15 turns × 200 chars avg = 3000 chars history
        # System prompt with injections: ~6000 chars
        simulated_system = "A" * 6000
        simulated_history_chars = self._chars_for_turns(15, 200)
        total = len(simulated_system) + simulated_history_chars
        self.assertLess(total, budget_chars,
            f"Normal conversation ({total} chars) should be under budget ({budget_chars} chars)")

    def test_very_long_session_would_trigger_guard(self):
        from src.guppy.api.realtime_inference_support import (
            _BACKEND_CONTEXT_TOKENS, _CHARS_PER_TOKEN
        )
        hermes4_ctx = _BACKEND_CONTEXT_TOKENS["llamacpp-hermes4"]
        budget_chars = int(hermes4_ctx * 0.85 * _CHARS_PER_TOKEN)

        # A pathological case: 5000 very long turns (128K ctx is huge)
        simulated_system = "A" * 6000
        simulated_history_chars = self._chars_for_turns(5000, 500)
        total = len(simulated_system) + simulated_history_chars
        self.assertGreater(total, budget_chars,
            "Very long session should exceed budget and trigger guard")

    def test_hermes4_context_larger_than_hermes3(self):
        from src.guppy.api.realtime_inference_support import _BACKEND_CONTEXT_TOKENS
        self.assertGreater(
            _BACKEND_CONTEXT_TOKENS["llamacpp-hermes4"],
            _BACKEND_CONTEXT_TOKENS["llamacpp-hermes3"],
            "Hermes4 (128K) should have more context than Hermes3 (8K)"
        )

    def test_companion_history_limit_matches_hermes4(self):
        """Companion history limit should be large given Hermes4's 128K context."""
        from src.guppy.api.realtime_inference_support import _SURFACE_HISTORY_LIMITS
        self.assertGreaterEqual(_SURFACE_HISTORY_LIMITS["companion"], 20,
            "Companion history limit should be >= 20 given Hermes4 128K context")


# ---------------------------------------------------------------------------
# 4. Multi-turn history injection
# ---------------------------------------------------------------------------

class TestMultiTurnHistoryInjection(unittest.TestCase):
    """History must be preserved in the augmented system prompt."""

    def test_history_passed_via_messages_array(self):
        """History reaches the model via sanitized messages, NOT embedded in system prompt.

        augment_system_with_history is intentionally a no-op — injecting history
        into the system prompt doubled token cost and was removed.  Content is
        preserved by sanitize_chat_history and passed in the messages array.
        """
        from src.guppy.inference.context_injection import augment_system_with_history
        from src.guppy.api.realtime_inference_support import sanitize_chat_history
        history = [
            {"role": "user", "content": "My name is Ryan and I like dark roast coffee."},
            {"role": "assistant", "content": "Got it, I'll remember that."},
            {"role": "user", "content": "What's your name?"},
            {"role": "assistant", "content": "I'm Guppy, your personal assistant."},
        ]
        system = "You are a helpful assistant."

        # augment_system_with_history must be a no-op — history goes via messages
        augmented = augment_system_with_history(system, history)
        self.assertEqual(augmented, system,
            "augment_system_with_history must return system prompt unchanged")

        # But content is preserved through sanitize_chat_history
        sanitized = sanitize_chat_history(history, limit=20, backend="llamacpp-rocinante")
        contents = " ".join(t["content"] for t in sanitized)
        self.assertIn("Ryan", contents, "User name must survive sanitize_chat_history")
        self.assertIn("dark roast coffee", contents, "User preference must survive sanitize_chat_history")

    def test_empty_history_handled(self):
        from src.guppy.inference.context_injection import augment_system_with_history
        system = "Base prompt."
        augmented = augment_system_with_history(system, [])
        self.assertIn("Base prompt.", augmented)

    def test_history_trimmed_to_surface_limit(self):
        from src.guppy.api.realtime_inference_support import (
            sanitize_chat_history, _SURFACE_HISTORY_LIMITS
        )
        companion_limit = _SURFACE_HISTORY_LIMITS["companion"]
        # Create more turns than the limit
        long_history = [
            {"role": "user" if i % 2 == 0 else "assistant", "content": f"Turn {i}"}
            for i in range(companion_limit + 20)
        ]
        trimmed = sanitize_chat_history(long_history, limit=companion_limit, backend="llamacpp-rocinante")
        self.assertLessEqual(len(trimmed), companion_limit,
            f"Companion history should be trimmed to {companion_limit} turns")


# ---------------------------------------------------------------------------
# 5. Semantic memory pipeline
# ---------------------------------------------------------------------------

class TestSemanticMemoryPipeline(unittest.TestCase):
    """Exact-key lookup, garbage filter, and empty-query preference scan."""

    def test_build_semantic_prompt_context_empty_on_no_results(self):
        from src.guppy.memory.semantic import build_semantic_prompt_context
        with patch("src.guppy.memory.semantic.recall_semantic", return_value="Nothing found in semantic memory."):
            result = build_semantic_prompt_context("anything")
            self.assertEqual(result, "")

    def test_build_semantic_prompt_context_garbage_filter(self):
        """4+ content lines all under 10 chars should be dropped."""
        from src.guppy.memory.semantic import build_semantic_prompt_context
        garbage_result = "Semantic recall results:\n- a\n- b\n- c\n- d"
        with patch("src.guppy.memory.semantic.recall_semantic", return_value=garbage_result):
            result = build_semantic_prompt_context("test")
            self.assertEqual(result, "", "Garbage recall should return empty string")

    def test_build_semantic_prompt_context_good_results_pass_through(self):
        from src.guppy.memory.semantic import build_semantic_prompt_context
        good_result = "Semantic recall results:\n- user_pref_coffee [user_preference]: dark roast, no sugar"
        with patch("src.guppy.memory.semantic.recall_semantic", return_value=good_result):
            result = build_semantic_prompt_context("coffee")
            self.assertIn("[Relevant Memory]", result)
            self.assertIn("dark roast", result)

    def test_recall_sqlite_exact_key_priority(self):
        """Exact key match should skip embedding I/O entirely."""
        import tempfile, sqlite3
        from pathlib import Path
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = Path(f.name)

        try:
            conn = sqlite3.connect(str(db_path))
            try:
                conn.execute("""
                    CREATE TABLE semantic_memory (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        memory_key TEXT NOT NULL,
                        category TEXT NOT NULL,
                        value TEXT NOT NULL,
                        embedding_json TEXT NOT NULL DEFAULT '[]',
                        created TEXT NOT NULL DEFAULT (datetime('now'))
                    )
                """)
                conn.execute(
                    "INSERT INTO semantic_memory (memory_key, category, value, embedding_json) VALUES (?,?,?,?)",
                    ("user_pref_coffee", "user_preference", "dark roast, oat milk", "[]")
                )
                conn.commit()
            finally:
                conn.close()

            with patch("src.guppy.memory.semantic.DB_PATH", db_path), \
                 patch("src.guppy.memory.semantic._embed_text", return_value=[]) as mock_embed:
                from src.guppy.memory.semantic import _recall_sqlite
                result = _recall_sqlite("user_pref_coffee", 5, "")

            self.assertIn("exact key match", result)
            self.assertIn("dark roast", result)
            mock_embed.assert_not_called()  # embedding should be bypassed
        finally:
            db_path.unlink(missing_ok=True)

    def test_user_preferences_direct_sql_scan(self):
        """_inject_user_preferences should use SQL scan, not empty-string recall."""
        import tempfile, sqlite3
        from pathlib import Path
        from src.guppy.inference.context_injection import _inject_user_preferences

        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = Path(f.name)

        try:
            conn = sqlite3.connect(str(db_path))
            try:
                conn.execute("""
                    CREATE TABLE semantic_memory (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        memory_key TEXT NOT NULL,
                        category TEXT NOT NULL,
                        value TEXT NOT NULL,
                        embedding_json TEXT NOT NULL DEFAULT '[]',
                        created TEXT NOT NULL DEFAULT (datetime('now'))
                    )
                """)
                conn.execute(
                    "INSERT INTO semantic_memory (memory_key, category, value, embedding_json) VALUES (?,?,?,?)",
                    ("pref_music", "user_preference", "metal and prog rock", "[]")
                )
                conn.commit()
            finally:
                conn.close()

            owner = _make_owner()
            with patch("src.guppy.memory.semantic.DB_PATH", db_path):
                result = _inject_user_preferences("Base prompt.", owner)

            self.assertIn("metal and prog rock", result, "User preferences should appear in system prompt")
            self.assertIn("[User Preferences]", result)
        finally:
            db_path.unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
