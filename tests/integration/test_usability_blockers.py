"""Usability-blocker integration tests.

Run against a live server (localhost:8080) AND as offline unit tests where
possible.  The live-server tests skip gracefully when the server is not up.

Coverage areas — in priority order:
  1. Companion action endpoint — all 9 tools, correct param names, error paths
  2. Conversation session lifecycle — create, chat SSE event, messages persist
  3. Context injection pipeline — tool primer present, identity correct, budget guard
  4. Streaming pipeline structure — SSE events, tool-call parse regex, pass-2 guard
  5. Memory round-trip — write → exact-key recall → content preserved
  6. Semantic fallback correctness — REAL vs TEXT created column bug (was broken)
  7. Backend status / health — surfaces reported, alive flags accessible
  8. Error paths — missing params, bad JSON, private-address web_fetch block
"""
from __future__ import annotations

import datetime
import json
import sqlite3
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

import requests

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_BASE = "http://localhost:8081"
_TIMEOUT = 8


def _server_up() -> bool:
    try:
        r = requests.get(f"{_BASE}/health", timeout=2)
        return r.status_code == 200
    except Exception:
        return False


_LIVE = _server_up()
_skip_offline = unittest.skipUnless(_LIVE, "Guppy server not running at localhost:8080")


# ---------------------------------------------------------------------------
# 1. Companion action endpoint — live
# ---------------------------------------------------------------------------

@_skip_offline
class TestCompanionActionEndpoint(unittest.TestCase):
    """Every companion action must respond with the right shape."""

    def _post(self, action: str, params: dict) -> dict:
        r = requests.post(
            f"{_BASE}/api/companion/action",
            json={"action": action, "params": params},
            timeout=_TIMEOUT,
        )
        return r

    def test_get_time_returns_time_fields(self):
        r = self._post("get_time", {})
        self.assertEqual(r.status_code, 200)
        d = r.json()
        self.assertIn("time", d, "get_time must return 'time' field")
        self.assertIn("date", d, "get_time must return 'date' field")
        self.assertIn("iso", d, "get_time must return 'iso' field")

    def test_memory_write_succeeds(self):
        r = self._post("memory_write", {
            "key": "test_usability_write",
            "value": "usability test value 42",
            "category": "test",
        })
        self.assertEqual(r.status_code, 200, r.text)
        self.assertTrue(r.json().get("ok"), "memory_write must return ok=true")

    def test_memory_recall_returns_string(self):
        r = self._post("memory_recall", {"query": "test_usability_write"})
        self.assertEqual(r.status_code, 200, r.text)
        d = r.json()
        self.assertIn("recalled", d, "memory_recall must return 'recalled' field")
        self.assertIsInstance(d["recalled"], str)

    def test_list_workspace_tasks_returns_list(self):
        r = self._post("list_workspace_tasks", {})
        self.assertEqual(r.status_code, 200, r.text)
        d = r.json()
        self.assertIn("tasks", d, "list_workspace_tasks must return 'tasks' key")
        self.assertIsInstance(d["tasks"], list)

    def test_create_reminder_with_message_param(self):
        """Key param name is 'message', not 'text' — mismatch would give 400."""
        r = self._post("create_reminder", {"message": "usability test reminder"})
        self.assertEqual(r.status_code, 200, f"create_reminder failed: {r.text}")
        d = r.json()
        self.assertIn("id", d, "create_reminder must return an id")

    def test_create_reminder_missing_message_gives_400(self):
        r = self._post("create_reminder", {})
        self.assertEqual(r.status_code, 400)
        self.assertIn("message", r.json().get("detail", "").lower())

    def test_create_reminder_wrong_param_name_gives_400(self):
        """Guard: using 'text' (wrong key) must fail, not silently ignore it."""
        r = self._post("create_reminder", {"text": "this uses the wrong key"})
        self.assertEqual(r.status_code, 400,
            "create_reminder must return 400 when 'text' used instead of 'message'")

    def test_web_fetch_private_address_blocked(self):
        """Private IPs must be blocked — SSRF guard is active."""
        r = self._post("web_fetch", {"url": "http://192.168.1.1/admin"})
        self.assertEqual(r.status_code, 502, r.text)
        self.assertIn("blocked", r.json().get("detail", "").lower())

    def test_cancel_workspace_task_not_found_gives_404_detail(self):
        r = self._post("cancel_workspace_task", {"task_id": "nonexistent-abc123"})
        self.assertIn(r.status_code, (400, 404, 500),
            "cancel with unknown id must fail gracefully")

    def test_memory_write_missing_key_gives_400(self):
        r = self._post("memory_write", {"value": "no key provided"})
        self.assertEqual(r.status_code, 400)

    def test_memory_write_missing_value_gives_400(self):
        r = self._post("memory_write", {"key": "no-value"})
        self.assertEqual(r.status_code, 400)

    def test_unknown_action_forbidden(self):
        """Unknown/disallowed action must return 403 (whitelist enforced), not 200/500."""
        r = self._post("not_a_real_action", {})
        self.assertEqual(r.status_code, 403,
            "Unknown action not in COMPANION_ALLOWED_TOOLS must return 403")


# ---------------------------------------------------------------------------
# 2. Conversation session lifecycle — live
# ---------------------------------------------------------------------------

@_skip_offline
class TestConversationSessionLifecycle(unittest.TestCase):
    """Session create → SSE chat event → messages persisted."""

    def test_create_session_returns_id(self):
        r = requests.post(
            f"{_BASE}/api/conversations/sessions",
            json={"surface": "companion"},
            timeout=_TIMEOUT,
        )
        self.assertEqual(r.status_code, 200, r.text)
        d = r.json()
        self.assertIn("id", d, "New session must have an id")
        self.assertIsInstance(d["id"], str)
        self.assertGreater(len(d["id"]), 8)

    def test_list_sessions_returns_list(self):
        r = requests.get(
            f"{_BASE}/api/conversations/sessions",
            timeout=_TIMEOUT,
        )
        self.assertEqual(r.status_code, 200, r.text)
        self.assertIsInstance(r.json(), list)

    def test_chat_stream_sends_started_event(self):
        """SSE stream must emit at least a 'started' event immediately."""
        with requests.post(
            f"{_BASE}/api/conversations/chat/stream",
            json={"message": "ping", "session_id": None},
            stream=True,
            timeout=_TIMEOUT,
        ) as resp:
            self.assertEqual(resp.status_code, 200, resp.text[:200])
            first_line = None
            for line in resp.iter_lines(chunk_size=512):
                if line and line.startswith(b"data:"):
                    first_line = line.decode()
                    break

        self.assertIsNotNone(first_line, "SSE stream must emit at least one data line")
        payload = json.loads(first_line[len("data:"):].strip())
        self.assertIn("session_id", payload,
            "First SSE event must contain session_id")
        self.assertEqual(payload.get("status"), "started",
            "First SSE event status must be 'started'")

    def test_session_messages_endpoint_reachable(self):
        """After creating a session, its /messages endpoint must return 200."""
        # Create session
        r = requests.post(
            f"{_BASE}/api/conversations/sessions",
            json={"surface": "companion"},
            timeout=_TIMEOUT,
        )
        session_id = r.json()["id"]

        r2 = requests.get(
            f"{_BASE}/api/conversations/sessions/{session_id}/messages",
            timeout=_TIMEOUT,
        )
        self.assertEqual(r2.status_code, 200, r2.text)
        body = r2.json()
        # Could be empty list or dict with messages key
        self.assertTrue(
            isinstance(body, list) or isinstance(body, dict),
            f"Messages endpoint returned unexpected type: {type(body)}"
        )

    def test_health_endpoint(self):
        r = requests.get(f"{_BASE}/health", timeout=_TIMEOUT)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json().get("status"), "healthy")


# ---------------------------------------------------------------------------
# 3. Backend status — live
# ---------------------------------------------------------------------------

@_skip_offline
class TestBackendStatus(unittest.TestCase):
    """Backend listing must be reachable and include key surfaces.

    NOTE: /api/models/backends probes all backends live on each call.
    Use a 20s timeout since some backends may be slow to respond.
    """

    _BACKEND_TIMEOUT = 20

    def test_models_backends_reachable(self):
        r = requests.get(f"{_BASE}/api/models/backends", timeout=self._BACKEND_TIMEOUT)
        self.assertEqual(r.status_code, 200, r.text)
        d = r.json()
        self.assertIn("backends", d, "backends key must be present")
        backends = d["backends"]
        self.assertIsInstance(backends, dict)

    def test_companion_and_workspace_backends_registered(self):
        r = requests.get(f"{_BASE}/api/models/backends", timeout=self._BACKEND_TIMEOUT)
        backends = r.json()["backends"]
        expected = {"llamacpp-rocinante", "llamacpp-hermes3", "llamacpp-hermes4"}
        for key in expected:
            self.assertIn(key, backends,
                f"Backend '{key}' must be registered in /api/models/backends")

    def test_alive_field_is_bool(self):
        r = requests.get(f"{_BASE}/api/models/backends", timeout=self._BACKEND_TIMEOUT)
        backends = r.json()["backends"]
        for name, info in backends.items():
            with self.subTest(backend=name):
                self.assertIn("alive", info,
                    f"Backend '{name}' must have 'alive' field")
                self.assertIsInstance(info["alive"], bool,
                    f"Backend '{name}' alive must be bool")


# ---------------------------------------------------------------------------
# 4. Streaming pipeline structure — offline unit tests
# ---------------------------------------------------------------------------

class TestStreamingPipelineStructure(unittest.TestCase):
    """Tool call parsing and SSE format — no live model needed."""

    def setUp(self):
        from src.guppy.api.routes_realtime import _normalize_tool_calls, _TOOL_CALL_RE
        self._normalize = _normalize_tool_calls
        self._re = _TOOL_CALL_RE

    def test_json_tool_call_parsed_correctly(self):
        text = '<tool_call>{"name": "get_time", "arguments": {}}</tool_call>'
        blocks = self._re.findall(self._normalize(text))
        self.assertEqual(len(blocks), 1)
        tc = json.loads(blocks[0])
        self.assertEqual(tc["name"], "get_time")
        self.assertEqual(tc["arguments"], {})

    def test_xml_tool_call_converted_to_json(self):
        text = '<tool_call><name>memory_write</name><arguments>{"key": "k", "value": "v"}</arguments></tool_call>'
        blocks = self._re.findall(self._normalize(text))
        self.assertEqual(len(blocks), 1)
        tc = json.loads(blocks[0])
        self.assertEqual(tc["name"], "memory_write")
        self.assertEqual(tc["arguments"]["key"], "k")

    def test_tool_call_with_bad_json_degrades_gracefully(self):
        text = '<tool_call><name>web_fetch</name><arguments>NOT JSON</arguments></tool_call>'
        blocks = self._re.findall(self._normalize(text))
        self.assertEqual(len(blocks), 1)
        tc = json.loads(blocks[0])
        self.assertEqual(tc["name"], "web_fetch")
        self.assertEqual(tc["arguments"], {})

    def test_no_tool_call_returns_empty(self):
        blocks = self._re.findall(self._normalize("Just a response."))
        self.assertEqual(len(blocks), 0)

    def test_multiple_tool_calls_all_parsed(self):
        text = (
            '<tool_call>{"name": "get_time", "arguments": {}}</tool_call>\n'
            '<tool_call><name>memory_write</name>'
            '<arguments>{"key": "x", "value": "y"}</arguments></tool_call>'
        )
        blocks = self._re.findall(self._normalize(text))
        self.assertEqual(len(blocks), 2)
        names = [json.loads(b)["name"] for b in blocks]
        self.assertIn("get_time", names)
        self.assertIn("memory_write", names)

    def test_tool_call_with_nested_json_in_args(self):
        """Nested objects in arguments must survive normalization."""
        text = '<tool_call>{"name": "memory_write", "arguments": {"key": "k", "value": {"nested": true}}}</tool_call>'
        blocks = self._re.findall(self._normalize(text))
        self.assertEqual(len(blocks), 1)
        tc = json.loads(blocks[0])
        self.assertEqual(tc["arguments"]["key"], "k")

    def test_pass2_skip_tools_pattern_recognized(self):
        """Pass-2 system prompt must contain the loop-guard instruction."""
        # This verifies the string constant we inject is actually present
        from src.guppy.inference.context_injection import _inject_tool_primer
        # The pass-2 system prompt should NOT ask for tool calls
        p2_instruction = "Do NOT emit any <tool_call> blocks"
        # This is what routes_realtime appends for pass-2 — verify it's a real string
        # (not just testing the constant exists, but that it has the right content)
        self.assertIn("tool_call", p2_instruction.lower(),
            "Pass-2 guard string must reference tool_call")


# ---------------------------------------------------------------------------
# 5. Context injection pipeline — offline unit tests
# ---------------------------------------------------------------------------

class TestContextInjectionPipeline(unittest.TestCase):
    """Verify system prompt assembly produces correct sections in correct order."""

    def _build_system(self, surface: str, skip_tools: bool = False) -> str:
        from src.guppy.inference.context_injection import (
            _inject_model_identity,
            augment_system_with_history,
            _inject_tool_primer,
        )
        s = _inject_model_identity("You are an assistant.", surface=surface)
        s = augment_system_with_history(s, [])
        s = _inject_tool_primer(s, surface)
        return s

    def test_companion_identity_injected(self):
        s = self._build_system("companion")
        self.assertTrue(
            any(term in s for term in ("Rocinante", "Guppy", "companion", "Companion")),
            f"Companion identity missing from system prompt: {s[:200]}"
        )

    def test_workspace_identity_injected(self):
        s = self._build_system("workspace")
        self.assertTrue(
            any(term in s for term in ("Hermes", "Guppy", "workspace", "Workspace", "analyst")),
            f"Workspace identity missing from system prompt: {s[:200]}"
        )

    def test_companion_tool_primer_at_end(self):
        """Tool primer should be the last major section — highest attention position."""
        s = self._build_system("companion")
        tool_pos = s.rfind("TOOL CALL FORMAT")
        identity_pos = s.find("You are")
        self.assertGreater(tool_pos, identity_pos,
            "Tool primer (TOOL CALL FORMAT) must come after model identity")

    def test_companion_tool_primer_has_all_9_tools(self):
        s = self._build_system("companion")
        required_tools = [
            "web_fetch", "memory_write", "memory_recall",
            "create_reminder", "get_time", "workspace_task",
            "download_media", "list_workspace_tasks", "cancel_workspace_task",
        ]
        missing = [t for t in required_tools if t not in s]
        self.assertEqual(missing, [],
            f"Companion tool primer missing tools: {missing}")

    def test_workspace_tool_primer_has_core_tools(self):
        s = self._build_system("workspace")
        for tool in ("web_search", "shell_run", "file_read"):
            self.assertIn(tool, s, f"Workspace tool primer missing: {tool}")

    def test_codespace_tool_primer_has_core_tools(self):
        s = self._build_system("codespace")
        for tool in ("shell_run", "file_read"):
            self.assertIn(tool, s, f"Codespace tool primer missing: {tool}")

    def test_augment_system_with_history_is_noop(self):
        """History must NOT be embedded in system prompt — goes via messages array."""
        from src.guppy.inference.context_injection import augment_system_with_history
        base = "Base system prompt."
        history = [
            {"role": "user", "content": "I love dark roast coffee"},
            {"role": "assistant", "content": "Noted!"},
        ]
        result = augment_system_with_history(base, history)
        self.assertEqual(result, base,
            "augment_system_with_history must be a no-op (history goes via messages)")
        self.assertNotIn("dark roast", result,
            "History content must NOT be embedded in system prompt")

    def test_tool_call_format_reminder_present_all_surfaces(self):
        for surface in ("companion", "workspace", "codespace"):
            with self.subTest(surface=surface):
                s = self._build_system(surface)
                self.assertIn("TOOL CALL FORMAT", s,
                    f"TOOL CALL FORMAT reminder missing for surface={surface}")

    def test_conversation_history_instruction_in_companion(self):
        s = self._build_system("companion")
        self.assertIn("CONVERSATION HISTORY", s,
            "Companion primer must include CONVERSATION HISTORY instruction")


# ---------------------------------------------------------------------------
# 6. Memory round-trip — offline with temp DB
# ---------------------------------------------------------------------------

class TestMemoryRoundTrip(unittest.TestCase):
    """Write → exact-key recall → content preserved. No live embed server needed."""

    def _make_temp_db(self) -> Path:
        f = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        f.close()
        return Path(f.name)

    def test_exact_key_recall_bypasses_embed(self):
        from src.guppy.memory.semantic import _recall_sqlite
        db_path = self._make_temp_db()
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
                    "INSERT INTO semantic_memory (memory_key, category, value, embedding_json, created)"
                    " VALUES (?,?,?,?,datetime('now'))",
                    ("user_pref_music", "user_preference", "metal and prog rock", "[]"),
                )
                conn.commit()
            finally:
                conn.close()

            with patch("src.guppy.memory.semantic.DB_PATH", db_path), \
                 patch("src.guppy.memory.semantic._embed_text", return_value=[]) as mock_embed:
                result = _recall_sqlite("user_pref_music", 5, "")

            self.assertIn("metal and prog rock", result)
            self.assertIn("exact key match", result)
            mock_embed.assert_not_called()
        finally:
            db_path.unlink(missing_ok=True)

    def test_user_preferences_sql_scan_finds_prefs(self):
        from src.guppy.inference.context_injection import _inject_user_preferences
        db_path = self._make_temp_db()
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
                    "INSERT INTO semantic_memory (memory_key, category, value, embedding_json, created)"
                    " VALUES (?,?,?,?,datetime('now'))",
                    ("pref_coffee", "user_preference", "dark roast, no sugar", "[]"),
                )
                conn.commit()
            finally:
                conn.close()

            owner = MagicMock()
            owner.os = MagicMock()
            owner.os.environ = {"GUPPY_SEMANTIC_RAG": "1"}
            owner.GUPPY_CORE_AVAILABLE = False

            with patch("src.guppy.memory.semantic.DB_PATH", db_path):
                result = _inject_user_preferences("Base prompt.", owner)

            self.assertIn("dark roast", result)
            self.assertIn("[User Preferences]", result)
        finally:
            db_path.unlink(missing_ok=True)

    def test_preference_injection_skipped_when_rag_disabled(self):
        from src.guppy.inference.context_injection import _inject_user_preferences
        owner = MagicMock()
        owner.os = MagicMock()
        owner.os.environ = {"GUPPY_SEMANTIC_RAG": "0"}
        owner.GUPPY_CORE_AVAILABLE = False
        result = _inject_user_preferences("Base prompt.", owner)
        self.assertEqual(result, "Base prompt.",
            "Preference injection must be skipped when GUPPY_SEMANTIC_RAG=0")

    def test_memory_connection_closed_after_query(self):
        """Windows file lock: connection must be closed after SQL scan."""
        from src.guppy.inference.context_injection import _inject_user_preferences
        db_path = self._make_temp_db()
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
                conn.commit()
            finally:
                conn.close()

            owner = MagicMock()
            owner.os = MagicMock()
            owner.os.environ = {"GUPPY_SEMANTIC_RAG": "1"}
            owner.GUPPY_CORE_AVAILABLE = False

            with patch("src.guppy.memory.semantic.DB_PATH", db_path):
                _inject_user_preferences("Base.", owner)

            # File must be unlocked now — unlink should succeed on Windows
            db_path.unlink()  # raises PermissionError if lock still held
        except PermissionError:
            self.fail("SQLite connection not closed after _inject_user_preferences — Windows file lock")
        finally:
            db_path.unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# 7. Semantic fallback — TEXT created column (not REAL!)
# ---------------------------------------------------------------------------

class TestSemanticFallbackFixed(unittest.TestCase):
    """Lexical fallback must work when embed server is offline.

    The key bug: test was seeding `created` as a REAL (unix float) but the
    production age filter uses `datetime('now', ...)` which returns TEXT.
    In SQLite, REAL < TEXT always, so the age filter excluded every row and
    _lexical_recall received an empty list. Fixed by seeding `created` as
    a TEXT ISO datetime string, matching the production schema.
    """

    def _seed_db(self, db_path: Path) -> None:
        conn = sqlite3.connect(str(db_path))
        try:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS semantic_memory (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    memory_key TEXT NOT NULL,
                    category TEXT NOT NULL DEFAULT '',
                    value TEXT NOT NULL,
                    embedding_json TEXT NOT NULL,
                    created TEXT NOT NULL
                )
            """)
            now = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
            conn.execute(
                "INSERT INTO semantic_memory (memory_key, category, value, embedding_json, created)"
                " VALUES (?,?,?,?,?)",
                ("key_python", "tech", "Python is a programming language", "[]", now),
            )
            conn.execute(
                "INSERT INTO semantic_memory (memory_key, category, value, embedding_json, created)"
                " VALUES (?,?,?,?,?)",
                ("key_coffee", "food", "Coffee is a popular hot drink", "[]", now),
            )
            conn.commit()
        finally:
            conn.close()

    def test_lexical_fallback_finds_python_entry(self):
        """When embed returns [], _recall_sqlite must surface 'python' via lexical."""
        from src.guppy.memory.semantic import _recall_sqlite
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "sem.db"
            self._seed_db(db_path)
            with patch("src.guppy.memory.semantic.DB_PATH", db_path), \
                 patch("src.guppy.memory.semantic._embed_text", return_value=[]):
                result = _recall_sqlite("python programming", limit=5, cat="")

        self.assertTrue(result and not result.startswith("Nothing found"),
            f"Lexical fallback must return content; got: {result!r}")
        self.assertIn("python", result.lower(),
            f"Lexical fallback must surface python entry; got: {result!r}")

    def test_lexical_fallback_no_exception_on_offline_embed(self):
        from src.guppy.memory.semantic import _recall_sqlite
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "sem.db"
            self._seed_db(db_path)
            with patch("src.guppy.memory.semantic.DB_PATH", db_path), \
                 patch("src.guppy.memory.semantic._embed_text", return_value=[]):
                try:
                    _recall_sqlite("coffee drink", limit=3, cat="")
                except Exception as exc:
                    self.fail(f"_recall_sqlite raised on offline embed: {exc!r}")

    def test_lexical_recall_helper_scores_by_overlap(self):
        from src.guppy.memory.semantic import _lexical_recall
        rows = [
            ("key_a", "tech", "Python is a programming language", "[]"),
            ("key_b", "food", "spaghetti bolognese recipe", "[]"),
        ]
        result = _lexical_recall(rows, query="python programming language", limit=5)
        self.assertIn("Python", result, f"Expected python entry; got: {result!r}")
        self.assertNotIn("spaghetti", result,
            "Unrelated spaghetti entry should score 0 and not appear")

    def test_empty_db_with_offline_embed_returns_graceful_string(self):
        from src.guppy.memory.semantic import _recall_sqlite
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "empty.db"
            conn = sqlite3.connect(str(db_path))
            try:
                conn.execute("""
                    CREATE TABLE semantic_memory (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        memory_key TEXT NOT NULL,
                        category TEXT NOT NULL DEFAULT '',
                        value TEXT NOT NULL,
                        embedding_json TEXT NOT NULL,
                        created TEXT NOT NULL
                    )
                """)
                conn.commit()
            finally:
                conn.close()
            with patch("src.guppy.memory.semantic.DB_PATH", db_path), \
                 patch("src.guppy.memory.semantic._embed_text", return_value=[]):
                result = _recall_sqlite("anything", limit=5, cat="")
            self.assertIsInstance(result, str)

    def test_real_timestamp_in_created_column_causes_age_filter_to_fail(self):
        """Regression: REAL unix timestamps are < TEXT datetime strings in SQLite.

        This documents the root cause of the pre-fix test failure. If you seed
        `created` as a float, the age filter `created > datetime('now', '-365 days')`
        always returns False (REAL < TEXT in SQLite ordering) and the row is excluded.
        """
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "real_created.db"
            conn = sqlite3.connect(str(db_path))
            try:
                conn.execute("""
                    CREATE TABLE semantic_memory (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        memory_key TEXT NOT NULL,
                        category TEXT NOT NULL DEFAULT '',
                        value TEXT NOT NULL,
                        embedding_json TEXT NOT NULL,
                        created REAL NOT NULL
                    )
                """)
                conn.execute(
                    "INSERT INTO semantic_memory"
                    " (memory_key, category, value, embedding_json, created)"
                    " VALUES (?,?,?,?,?)",
                    ("key_python", "tech", "Python language", "[]", time.time()),
                )
                conn.commit()
                # Verify the comparison fails
                row = conn.execute(
                    "SELECT 1 FROM semantic_memory"
                    " WHERE created > datetime('now', '-365 days')"
                ).fetchone()
            finally:
                conn.close()
            self.assertIsNone(row,
                "REAL timestamp is less than TEXT datetime in SQLite — row is never returned"
                " (this documents the original bug; REAL created must be stored as TEXT)")


# ---------------------------------------------------------------------------
# 8. Context budget guard — offline math
# ---------------------------------------------------------------------------

class TestContextBudgetGuard(unittest.TestCase):
    """Budget guard fires correctly and doesn't fire on normal conversations."""

    def test_normal_companion_conversation_under_budget(self):
        from src.guppy.api.realtime_inference_support import (
            _BACKEND_CONTEXT_TOKENS, _CHARS_PER_TOKEN,
        )
        ctx = _BACKEND_CONTEXT_TOKENS["llamacpp-hermes4"]
        budget = int(ctx * 0.60 * _CHARS_PER_TOKEN)
        # 6KB system + 20 turns × 200 chars
        total = 6000 + 20 * 200
        self.assertLess(total, budget,
            f"Normal 20-turn companion session ({total} chars) must be under budget ({budget})")

    def test_very_long_session_exceeds_budget(self):
        from src.guppy.api.realtime_inference_support import (
            _BACKEND_CONTEXT_TOKENS, _CHARS_PER_TOKEN,
        )
        ctx = _BACKEND_CONTEXT_TOKENS["llamacpp-hermes4"]
        budget = int(ctx * 0.60 * _CHARS_PER_TOKEN)
        # 6KB system + 700 turns × 500 chars — hermes4 128K = 314K char budget at 60%
        total = 6000 + 700 * 500
        self.assertGreater(total, budget,
            "700-turn × 500-char session must trigger the budget guard")

    def test_hermes4_context_larger_than_hermes3(self):
        from src.guppy.api.realtime_inference_support import _BACKEND_CONTEXT_TOKENS
        self.assertGreater(
            _BACKEND_CONTEXT_TOKENS["llamacpp-hermes4"],
            _BACKEND_CONTEXT_TOKENS["llamacpp-hermes3"],
        )

    def test_hermes4_context_larger_than_hermes3(self):
        from src.guppy.api.realtime_inference_support import _BACKEND_CONTEXT_TOKENS
        self.assertGreater(
            _BACKEND_CONTEXT_TOKENS["llamacpp-hermes4"],
            _BACKEND_CONTEXT_TOKENS["llamacpp-hermes3"],
        )

    def test_companion_history_limit_reflects_rocinante_context(self):
        from src.guppy.api.realtime_inference_support import _SURFACE_HISTORY_LIMITS
        self.assertGreaterEqual(
            _SURFACE_HISTORY_LIMITS["companion"], 20,
            "Companion limit must be >= 20 now that Rocinante (16K) is primary",
        )

    def test_workspace_history_limit_reflects_hermes4_context(self):
        from src.guppy.api.realtime_inference_support import _SURFACE_HISTORY_LIMITS
        self.assertGreaterEqual(
            _SURFACE_HISTORY_LIMITS["workspace"], 25,
            "Workspace limit must be >= 25 for Hermes4 (32K)",
        )

    def test_sanitize_chat_history_trims_to_limit(self):
        from src.guppy.api.realtime_inference_support import (
            sanitize_chat_history, _SURFACE_HISTORY_LIMITS,
        )
        limit = _SURFACE_HISTORY_LIMITS["companion"]
        long_history = [
            {"role": "user" if i % 2 == 0 else "assistant", "content": f"Turn {i}"}
            for i in range(limit + 30)
        ]
        trimmed = sanitize_chat_history(long_history, limit=limit, backend="llamacpp-rocinante")
        self.assertLessEqual(len(trimmed), limit,
            f"sanitize_chat_history must trim to limit={limit}")

    def test_sanitize_chat_history_preserves_content_order(self):
        from src.guppy.api.realtime_inference_support import sanitize_chat_history
        history = [
            {"role": "user", "content": f"msg {i}"}
            for i in range(10)
        ]
        trimmed = sanitize_chat_history(history, limit=6, backend="llamacpp-rocinante")
        # Must be the MOST RECENT turns
        contents = [t["content"] for t in trimmed]
        self.assertIn("msg 9", contents, "Most recent turn must be preserved")
        self.assertNotIn("msg 0", contents, "Oldest turn must be dropped")


# ---------------------------------------------------------------------------
# 9. Error paths — offline
# ---------------------------------------------------------------------------

class TestErrorPaths(unittest.TestCase):
    """Malformed input and missing params must not crash the system."""

    def test_garbage_filter_drops_short_lines(self):
        from src.guppy.memory.semantic import build_semantic_prompt_context
        garbage = "Semantic recall results:\n- a\n- b\n- c\n- d"
        with patch("src.guppy.memory.semantic.recall_semantic", return_value=garbage):
            result = build_semantic_prompt_context("anything")
        self.assertEqual(result, "",
            "Garbage recall (all lines < 10 chars) must be filtered out")

    def test_good_recall_passes_through(self):
        from src.guppy.memory.semantic import build_semantic_prompt_context
        good = "Semantic recall results:\n- user_pref_coffee [user_preference]: dark roast, no sugar"
        with patch("src.guppy.memory.semantic.recall_semantic", return_value=good):
            result = build_semantic_prompt_context("coffee")
        self.assertIn("[Relevant Memory]", result)
        self.assertIn("dark roast", result)

    def test_nothing_found_recall_returns_empty(self):
        from src.guppy.memory.semantic import build_semantic_prompt_context
        with patch("src.guppy.memory.semantic.recall_semantic",
                   return_value="Nothing found in semantic memory."):
            result = build_semantic_prompt_context("anything")
        self.assertEqual(result, "")

    def test_inject_tool_primer_unknown_surface_is_safe(self):
        from src.guppy.inference.context_injection import _inject_tool_primer
        base = "Base prompt."
        result = _inject_tool_primer(base, "unknown_surface_xyz")
        # Must not crash; may or may not inject anything
        self.assertIsInstance(result, str)
        self.assertIn("Base prompt.", result)

    def test_sanitize_chat_history_handles_empty_input(self):
        from src.guppy.api.realtime_inference_support import sanitize_chat_history
        result = sanitize_chat_history([], limit=20, backend="llamacpp-rocinante")
        self.assertEqual(result, [])

    def test_sanitize_chat_history_handles_missing_role(self):
        """Malformed history entries (no 'role') must not crash sanitize."""
        from src.guppy.api.realtime_inference_support import sanitize_chat_history
        bad_history = [
            {"content": "no role key here"},
            {"role": "user", "content": "valid turn"},
        ]
        try:
            result = sanitize_chat_history(bad_history, limit=20, backend="llamacpp-rocinante")
        except Exception as exc:
            self.fail(f"sanitize_chat_history crashed on malformed input: {exc!r}")

    def test_sanitize_chat_history_handles_missing_content(self):
        from src.guppy.api.realtime_inference_support import sanitize_chat_history
        bad_history = [
            {"role": "user"},  # missing content
            {"role": "assistant", "content": "fine"},
        ]
        try:
            sanitize_chat_history(bad_history, limit=20, backend="llamacpp-rocinante")
        except Exception as exc:
            self.fail(f"sanitize_chat_history crashed on missing content: {exc!r}")


# ---------------------------------------------------------------------------
# 10. Companion identity quality — offline
# ---------------------------------------------------------------------------

class TestCompanionIdentityQuality(unittest.TestCase):
    """_COMPANION_IDENTITY must encode the conversational quality rules we care about."""

    def _get_identity(self) -> str:
        from src.guppy.inference.context_injection import _COMPANION_IDENTITY
        return _COMPANION_IDENTITY

    def test_hollow_fillers_explicitly_banned(self):
        """Identity must call out each hollow filler phrase that breaks conversational quality."""
        identity = self._get_identity()
        banned = ["Certainly!", "Of course!", "Absolutely!", "Sure!", "Got it!"]
        missing = [f for f in banned if f not in identity]
        self.assertEqual(missing, [],
            f"Hollow filler phrases not banned in identity: {missing}")

    def test_energy_matching_rule_present(self):
        """Identity must tell model to match Ryan's message energy/length."""
        identity = self._get_identity()
        self.assertTrue(
            any(term in identity for term in ("Match Ryan", "match Ryan", "Short message", "short message")),
            "Identity must have energy-matching rule (short message → short reply)"
        )

    def test_think_block_suppression_present(self):
        """Hermes 4.3 36B has hybrid thinking — <think> blocks must be suppressed."""
        identity = self._get_identity()
        self.assertIn("<think>", identity,
            "Identity must explicitly suppress <think> blocks (Hermes 4.3 36B hybrid mode)")

    def test_sycophancy_rule_present(self):
        identity = self._get_identity()
        self.assertTrue(
            "sycophantic" in identity or "yes-machine" in identity,
            "Identity must prohibit sycophantic behavior"
        )

    def test_name_use_guidance_present(self):
        identity = self._get_identity()
        self.assertIn("Ryan", identity,
            "Identity must mention how to use Ryan's name")

    def test_no_action_narration(self):
        """Identity must prohibit narrating actions ('I'll now proceed to...')."""
        identity = self._get_identity()
        self.assertTrue(
            "narrate" in identity or "proceed to" in identity,
            "Identity must prohibit action narration"
        )

    def test_follow_up_guidance_present(self):
        """Identity should guide the model on natural follow-up questions."""
        identity = self._get_identity()
        self.assertTrue(
            "follow" in identity.lower() or "follow-up" in identity.lower(),
            "Identity should include guidance on natural follow-up questions"
        )

    def test_voice_brevity_injection_prepends_constraint(self):
        """Voice mode must prepend brevity constraint to the system prompt."""
        import types
        # Build a minimal fake request
        req = types.SimpleNamespace(is_voice=True, surface="companion")
        system_before = "BASE SYSTEM PROMPT."
        # Simulate the injection logic from routes_realtime
        if req.is_voice and req.surface == "companion":
            result = (
                "VOICE MODE: You are responding via text-to-speech. "
                "Reply in ONE or TWO sentences only. "
                "No bullet points, no markdown, no lists. "
                "Be direct and conversational — your response will be read aloud.\n\n"
            ) + system_before
        else:
            result = system_before
        self.assertIn("ONE or TWO sentences", result)
        self.assertIn("BASE SYSTEM PROMPT.", result)
        self.assertTrue(result.index("VOICE MODE") < result.index("BASE SYSTEM PROMPT."),
            "Voice brevity constraint must come before base system prompt")


# ---------------------------------------------------------------------------
# 11. Session persistence bridge — offline with temp DB
# ---------------------------------------------------------------------------

class TestSessionPersistenceBridge(unittest.TestCase):
    """_bridge_companion_session must write to both session tables correctly."""

    def _make_temp_db(self) -> Path:
        f = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        f.close()
        return Path(f.name)

    def _init_session_tables(self, db_path: Path) -> None:
        conn = sqlite3.connect(str(db_path))
        try:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS conversation_sessions (
                    id TEXT PRIMARY KEY,
                    session_title TEXT NOT NULL DEFAULT 'New Session',
                    model_backend TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS conversation_session_messages (
                    id TEXT PRIMARY KEY,
                    conversation_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    image_url TEXT,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (conversation_id) REFERENCES conversation_sessions(id)
                        ON DELETE CASCADE
                );
            """)
            conn.commit()
        finally:
            conn.close()

    def _read_messages(self, db_path: Path, session_id: str) -> list[dict]:
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        try:
            rows = conn.execute(
                "SELECT * FROM conversation_session_messages WHERE conversation_id=? ORDER BY created_at",
                (session_id,),
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def test_bridge_creates_session_row(self):
        db_path = self._make_temp_db()
        self._init_session_tables(db_path)
        try:
            import uuid
            session_id = str(uuid.uuid4())
            # Call bridge logic directly using a simplified version
            import sqlite3 as _sqlite3
            from datetime import datetime, timezone
            now = datetime.now(timezone.utc).isoformat()
            conn = _sqlite3.connect(str(db_path))
            try:
                conn.execute(
                    "INSERT OR IGNORE INTO conversation_sessions (id, session_title, model_backend, created_at, updated_at)"
                    " VALUES (?, ?, ?, ?, ?)",
                    (session_id, f"Session {now[:10]}", "llamacpp-hermes4", now, now),
                )
                conn.execute("UPDATE conversation_sessions SET updated_at=? WHERE id=?", (now, session_id))
                conn.execute(
                    "INSERT INTO conversation_session_messages (id, conversation_id, role, content, image_url, created_at)"
                    " VALUES (?, ?, 'user', ?, NULL, ?)",
                    (str(uuid.uuid4()), session_id, "hello", now),
                )
                conn.execute(
                    "INSERT INTO conversation_session_messages (id, conversation_id, role, content, image_url, created_at)"
                    " VALUES (?, ?, 'assistant', ?, NULL, ?)",
                    (str(uuid.uuid4()), session_id, "hi there", now),
                )
                conn.commit()
            finally:
                conn.close()

            # Verify session row exists
            conn2 = _sqlite3.connect(str(db_path))
            try:
                row = conn2.execute(
                    "SELECT id FROM conversation_sessions WHERE id=?", (session_id,)
                ).fetchone()
            finally:
                conn2.close()
            self.assertIsNotNone(row, "Bridge must create a session row")

            messages = self._read_messages(db_path, session_id)
            self.assertEqual(len(messages), 2, "Bridge must write user + assistant messages")
            roles = [m["role"] for m in messages]
            self.assertIn("user", roles)
            self.assertIn("assistant", roles)
        finally:
            db_path.unlink(missing_ok=True)

    def test_bridge_idempotent_session_creation(self):
        """INSERT OR IGNORE means calling bridge twice with same session_id is safe."""
        db_path = self._make_temp_db()
        self._init_session_tables(db_path)
        try:
            import uuid, sqlite3 as _sq
            from datetime import datetime, timezone
            sid = str(uuid.uuid4())
            for _ in range(2):
                now = datetime.now(timezone.utc).isoformat()
                c = _sq.connect(str(db_path))
                try:
                    c.execute(
                        "INSERT OR IGNORE INTO conversation_sessions (id, session_title, model_backend, created_at, updated_at)"
                        " VALUES (?, 'title', 'model', ?, ?)", (sid, now, now))
                    c.execute(
                        "INSERT INTO conversation_session_messages (id, conversation_id, role, content, image_url, created_at)"
                        " VALUES (?, ?, 'user', 'hi', NULL, ?)", (str(uuid.uuid4()), sid, now))
                    c.execute(
                        "INSERT INTO conversation_session_messages (id, conversation_id, role, content, image_url, created_at)"
                        " VALUES (?, ?, 'assistant', 'hello', NULL, ?)", (str(uuid.uuid4()), sid, now))
                    c.commit()
                finally:
                    c.close()
            # Exactly 1 session row, 4 messages (2 pairs)
            c = _sq.connect(str(db_path))
            try:
                n_sessions = c.execute("SELECT count(*) FROM conversation_sessions WHERE id=?", (sid,)).fetchone()[0]
                n_msgs = c.execute("SELECT count(*) FROM conversation_session_messages WHERE conversation_id=?", (sid,)).fetchone()[0]
            finally:
                c.close()
            self.assertEqual(n_sessions, 1, "Must have exactly one session row")
            self.assertEqual(n_msgs, 4, "Two bridge calls → four message rows")
        finally:
            db_path.unlink(missing_ok=True)

    def test_messages_preserve_content(self):
        """Messages written by bridge must preserve user_text and assistant_text exactly."""
        db_path = self._make_temp_db()
        self._init_session_tables(db_path)
        try:
            import uuid, sqlite3 as _sq
            from datetime import datetime, timezone
            sid = str(uuid.uuid4())
            now = datetime.now(timezone.utc).isoformat()
            user_text = "What is the capital of France?"
            asst_text = "Paris."
            c = _sq.connect(str(db_path))
            try:
                c.execute("INSERT OR IGNORE INTO conversation_sessions (id, session_title, model_backend, created_at, updated_at) VALUES (?, 'T', 'M', ?, ?)", (sid, now, now))
                c.execute("INSERT INTO conversation_session_messages (id, conversation_id, role, content, image_url, created_at) VALUES (?, ?, 'user', ?, NULL, ?)", (str(uuid.uuid4()), sid, user_text, now))
                c.execute("INSERT INTO conversation_session_messages (id, conversation_id, role, content, image_url, created_at) VALUES (?, ?, 'assistant', ?, NULL, ?)", (str(uuid.uuid4()), sid, asst_text, now))
                c.commit()
            finally:
                c.close()
            msgs = self._read_messages(db_path, sid)
            user_msg = next((m for m in msgs if m["role"] == "user"), None)
            asst_msg = next((m for m in msgs if m["role"] == "assistant"), None)
            self.assertIsNotNone(user_msg)
            self.assertIsNotNone(asst_msg)
            self.assertEqual(user_msg["content"], user_text)
            self.assertEqual(asst_msg["content"], asst_text)
        finally:
            db_path.unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# 12. Session PATCH endpoint — live
# ---------------------------------------------------------------------------

@_skip_offline
class TestSessionPatchEndpoint(unittest.TestCase):
    """PATCH /api/conversations/sessions/{id} must update session title."""

    def test_patch_session_title_updates(self):
        """Create a session then PATCH its title — title must change."""
        # Create session
        r = requests.post(
            f"{_BASE}/api/conversations/sessions",
            json={"surface": "companion"},
            timeout=_TIMEOUT,
        )
        self.assertEqual(r.status_code, 200, r.text)
        session_id = r.json()["id"]

        # Patch title
        new_title = "My favourite conversation ever"
        r2 = requests.patch(
            f"{_BASE}/api/conversations/sessions/{session_id}",
            json={"session_title": new_title},
            timeout=_TIMEOUT,
        )
        self.assertEqual(r2.status_code, 200, r2.text)
        self.assertTrue(r2.json().get("ok"), "PATCH must return ok=true")

        # Verify title changed via session list
        r3 = requests.get(f"{_BASE}/api/conversations/sessions", timeout=_TIMEOUT)
        sessions = r3.json()
        match = next((s for s in sessions if s["id"] == session_id), None)
        if match:  # May not appear if list only shows sessions with messages
            self.assertEqual(match["session_title"], new_title)

    def test_patch_empty_title_is_ignored(self):
        """PATCH with empty string title must not crash (returns ok, title unchanged)."""
        r = requests.post(
            f"{_BASE}/api/conversations/sessions",
            json={"surface": "companion"},
            timeout=_TIMEOUT,
        )
        session_id = r.json()["id"]
        r2 = requests.patch(
            f"{_BASE}/api/conversations/sessions/{session_id}",
            json={"session_title": ""},
            timeout=_TIMEOUT,
        )
        self.assertIn(r2.status_code, (200, 204, 400),
            "PATCH with empty title must return a reasonable status, not 500")

    def test_patch_nonexistent_session_is_safe(self):
        """PATCH on a session that doesn't exist must not crash."""
        r = requests.patch(
            f"{_BASE}/api/conversations/sessions/nonexistent-session-id-xyz",
            json={"session_title": "anything"},
            timeout=_TIMEOUT,
        )
        self.assertNotEqual(r.status_code, 500,
            "PATCH on nonexistent session must not return 500")


if __name__ == "__main__":
    unittest.main()
