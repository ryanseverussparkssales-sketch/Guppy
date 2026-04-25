"""Integration test: chat conversation → memory persistence → recall round-trip.

Covers the core north-star flow: messages saved during a chat session are
retrievable via history and fact recall, and preference candidates extracted
from user text are promoted to durable semantic memory.
"""

import tempfile
import unittest
from pathlib import Path

from src.guppy.memory.memory_store import (
    forget_fact,
    load_recent_history_records,
    open_memory_connection,
    recall_facts,
    remember_fact,
    save_conversation_message,
)


def _tmp_db() -> Path:
    """Return a path to a fresh temp database (caller owns cleanup)."""
    f = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    f.close()
    return Path(f.name)


class TestChatMemoryRoundtrip(unittest.TestCase):
    def setUp(self):
        self.db = _tmp_db()
        # Touch the schema by opening a connection (memory_store creates tables on first open)
        conn = open_memory_connection(self.db)
        conn.close()

    def tearDown(self):
        try:
            self.db.unlink(missing_ok=True)
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Conversation persistence
    # ------------------------------------------------------------------

    def test_save_and_load_conversation_messages(self):
        session = "sess-001"
        save_conversation_message(self.db, session, "user", "Hello, what's on my agenda today?")
        save_conversation_message(self.db, session, "assistant", "You have three meetings and a call.")

        history = load_recent_history_records(self.db, session_id=session)

        self.assertEqual(len(history), 2)
        self.assertEqual(history[0]["role"], "user")
        self.assertIn("agenda", history[0]["content"])
        self.assertEqual(history[1]["role"], "assistant")
        self.assertIn("meetings", history[1]["content"])

    def test_conversation_history_is_ordered_oldest_first(self):
        session = "sess-order"
        for i in range(5):
            save_conversation_message(self.db, session, "user", f"message {i}")

        history = load_recent_history_records(self.db, session_id=session)
        contents = [h["content"] for h in history]
        self.assertEqual(contents, [f"message {i}" for i in range(5)])

    def test_history_limit_is_respected(self):
        session = "sess-limit"
        for i in range(10):
            save_conversation_message(self.db, session, "user", f"msg {i}")

        history = load_recent_history_records(self.db, session_id=session, limit=3)
        self.assertEqual(len(history), 3)

    def test_workspace_isolation(self):
        session = "sess-ws"
        save_conversation_message(self.db, session, "user", "workspace alpha msg", workspace_name="alpha")
        save_conversation_message(self.db, session, "user", "workspace beta msg", workspace_name="beta")

        alpha = load_recent_history_records(self.db, session_id=session, workspace_name="alpha")
        beta = load_recent_history_records(self.db, session_id=session, workspace_name="beta")

        self.assertEqual(len(alpha), 1)
        self.assertIn("alpha", alpha[0]["content"])
        self.assertEqual(len(beta), 1)
        self.assertIn("beta", beta[0]["content"])

    # ------------------------------------------------------------------
    # Fact memory (remember / recall / forget)
    # ------------------------------------------------------------------

    def test_remember_and_recall_fact(self):
        result = remember_fact(self.db, "user_city", "Austin", category="identity")
        self.assertIn("Remembered", result)

        recalled = recall_facts(self.db, query="user_city")
        self.assertIn("Austin", recalled)
        self.assertIn("identity", recalled)

    def test_recall_by_category(self):
        remember_fact(self.db, "pref_theme", "dark mode", category="preference")
        remember_fact(self.db, "user_name", "Ryan", category="identity")

        prefs = recall_facts(self.db, category="preference")
        self.assertIn("dark mode", prefs)
        self.assertNotIn("Ryan", prefs)

    def test_remember_updates_existing_key(self):
        remember_fact(self.db, "fav_color", "blue", category="preference")
        result = remember_fact(self.db, "fav_color", "green", category="preference")
        self.assertIn("Updated", result)

        recalled = recall_facts(self.db, query="fav_color")
        self.assertIn("green", recalled)
        self.assertNotIn("blue", recalled)

    def test_forget_removes_fact(self):
        remember_fact(self.db, "temp_key", "temp_value")
        forget_fact(self.db, "temp_key")

        recalled = recall_facts(self.db, query="temp_key")
        self.assertEqual(recalled, "Nothing found in memory.")

    # ------------------------------------------------------------------
    # End-to-end: chat turn → promoted durable memory
    # ------------------------------------------------------------------

    def test_chat_turn_then_fact_persist_and_recall(self):
        """Simulate a full chat turn: save messages, store a fact derived from
        the turn, then recall it — verifying memory persists across the session."""
        session = "sess-e2e"
        user_msg = "I prefer working late at night, usually after 10pm."
        assistant_msg = "Got it — I'll schedule tasks for late-night hours."

        save_conversation_message(self.db, session, "user", user_msg)
        save_conversation_message(self.db, session, "assistant", assistant_msg)

        # Simulate the runtime promoting a fact extracted from the turn
        remember_fact(self.db, "work_schedule", "prefers late night after 10pm", category="preference")

        # Verify the conversation is persisted
        history = load_recent_history_records(self.db, session_id=session)
        self.assertEqual(len(history), 2)

        # Verify the promoted fact is recallable
        recalled = recall_facts(self.db, query="work_schedule")
        self.assertIn("late night", recalled)
        self.assertIn("preference", recalled)


if __name__ == "__main__":
    unittest.main()
