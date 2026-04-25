"""Unit tests for ChatHistoryDB, SettingsDB, and WorkspaceDB."""
from __future__ import annotations

import pytest

from src.guppy.api.routes_chat_history import ChatHistoryDB
from src.guppy.api.routes_settings import SettingsDB
from src.guppy.api.routes_workspaces import WorkspaceDB


# ── ChatHistoryDB ─────────────────────────────────────────────────────────────

class TestChatHistoryDB:
    @pytest.fixture
    def db(self, tmp_path):
        return ChatHistoryDB(db_path=str(tmp_path / "chat.db"))

    def test_create_and_retrieve_conversation(self, db):
        conv = db.create_conversation("ws-1", "Test Chat")
        assert conv["id"]
        assert conv["workspace_id"] == "ws-1"
        assert conv["title"] == "Test Chat"

    def test_default_title_when_omitted(self, db):
        conv = db.create_conversation("ws-1")
        assert "Conversation" in conv["title"]

    def test_list_conversations_empty(self, db):
        assert db.list_conversations("ws-1") == []

    def test_list_conversations_returns_created(self, db):
        db.create_conversation("ws-1", "A")
        db.create_conversation("ws-1", "B")
        convs = db.list_conversations("ws-1")
        assert len(convs) == 2

    def test_list_conversations_isolated_by_workspace(self, db):
        db.create_conversation("ws-1", "A")
        db.create_conversation("ws-2", "B")
        assert len(db.list_conversations("ws-1")) == 1
        assert len(db.list_conversations("ws-2")) == 1

    def test_get_conversation_with_messages(self, db):
        conv = db.create_conversation("ws-1", "Chat")
        db.add_message(conv["id"], "user", "hello", None)
        result = db.get_conversation_with_messages(conv["id"])
        assert result is not None
        assert len(result["messages"]) == 1
        assert result["messages"][0]["content"] == "hello"

    def test_get_conversation_returns_none_for_missing(self, db):
        assert db.get_conversation_with_messages("nonexistent") is None

    def test_add_message_increments_count(self, db):
        conv = db.create_conversation("ws-1", "C")
        db.add_message(conv["id"], "user", "hi", None)
        db.add_message(conv["id"], "assistant", "hey", "guppy")
        result = db.get_conversation_with_messages(conv["id"])
        assert len(result["messages"]) == 2

    def test_update_conversation_title(self, db):
        conv = db.create_conversation("ws-1", "Old")
        updated = db.update_conversation_title(conv["id"], "New")
        assert updated["title"] == "New"

    def test_update_conversation_returns_none_for_missing(self, db):
        assert db.update_conversation_title("nonexistent", "X") is None

    def test_delete_conversation(self, db):
        conv = db.create_conversation("ws-1", "Delete Me")
        db.delete_conversation(conv["id"])
        assert db.get_conversation_with_messages(conv["id"]) is None

    def test_search_conversations(self, db):
        conv = db.create_conversation("ws-1", "Python tips")
        db.add_message(conv["id"], "user", "tell me about asyncio", None)
        results = db.search_conversations("ws-1", "asyncio")
        assert len(results) == 1

    def test_search_no_match(self, db):
        db.create_conversation("ws-1", "Python tips")
        assert db.search_conversations("ws-1", "javascript") == []

    def test_db_path_resolves_to_user_data_dir_by_default(self, monkeypatch, tmp_path):
        monkeypatch.setenv("GUPPY_USER_DATA_DIR", str(tmp_path))
        import importlib
        import src.guppy.paths as paths
        importlib.reload(paths)
        import src.guppy.api.routes_chat_history as m
        importlib.reload(m)
        default_db = m.ChatHistoryDB()
        assert str(tmp_path) in default_db.db_path


# ── SettingsDB ────────────────────────────────────────────────────────────────

class TestSettingsDB:
    @pytest.fixture
    def db(self, tmp_path):
        return SettingsDB(db_path=str(tmp_path / "settings.db"))

    def test_default_provider_is_local(self, db):
        assert db.get_active_provider() == "local"

    def test_set_and_get_provider(self, db):
        db.set_active_provider("anthropic")
        assert db.get_active_provider() == "anthropic"

    def test_set_invalid_provider_raises(self, db):
        with pytest.raises(ValueError):
            db.set_active_provider("badprovider")

    def test_store_and_check_credential(self, db):
        db.store_credential("anthropic", "sk-test-key")
        status = db.get_credentials_status()
        assert status["anthropic"]["configured"] is True

    def test_unconfigured_provider_shows_false(self, db):
        status = db.get_credentials_status()
        assert status["anthropic"]["configured"] is False

    def test_delete_credential(self, db):
        db.store_credential("openai", "sk-xyz")
        db.delete_credential("openai")
        status = db.get_credentials_status()
        assert status["openai"]["configured"] is False

    def test_store_empty_key_raises(self, db):
        with pytest.raises(ValueError):
            db.store_credential("anthropic", "")

    def test_get_setting_returns_none_for_missing(self, db):
        assert db.get_setting("nonexistent_key") is None

    def test_set_and_get_setting(self, db):
        db.set_setting("theme", "dark")
        assert db.get_setting("theme") == "dark"


# ── WorkspaceDB ───────────────────────────────────────────────────────────────

class TestWorkspaceDB:
    @pytest.fixture
    def db(self, tmp_path):
        return WorkspaceDB(db_path=str(tmp_path / "workspaces.db"))

    def test_create_and_retrieve_workspace(self, db):
        ws = db.create_workspace("Project A", "My first workspace")
        assert ws["name"] == "Project A"
        assert ws["description"] == "My first workspace"
        assert ws["id"]

    def test_list_workspaces_empty(self, db):
        assert db.list_workspaces() == []

    def test_list_workspaces_returns_created(self, db):
        db.create_workspace("WS 1")
        db.create_workspace("WS 2")
        assert len(db.list_workspaces()) == 2

    def test_get_workspace_returns_none_for_missing(self, db):
        assert db.get_workspace("nonexistent") is None

    def test_get_workspace_returns_data(self, db):
        ws = db.create_workspace("WS")
        found = db.get_workspace(ws["id"])
        assert found["name"] == "WS"

    def test_update_workspace_name(self, db):
        ws = db.create_workspace("Old Name")
        updated = db.update_workspace(ws["id"], name="New Name")
        assert updated["name"] == "New Name"

    def test_update_workspace_raises_for_missing(self, db):
        with pytest.raises(ValueError):
            db.update_workspace("nonexistent", name="X")

    def test_delete_workspace(self, db):
        ws = db.create_workspace("Temp")
        db.delete_workspace(ws["id"])
        assert db.get_workspace(ws["id"]) is None

    def test_set_and_get_active_workspace(self, db):
        ws = db.create_workspace("Active WS")
        db.set_active_workspace(ws["id"])
        active = db.get_active_workspace()
        assert active is not None
        assert active["id"] == ws["id"]

    def test_get_active_workspace_returns_none_when_none_set(self, db):
        assert db.get_active_workspace() is None

    def test_activate_workspace_clears_previous_active(self, db):
        ws1 = db.create_workspace("WS 1")
        ws2 = db.create_workspace("WS 2")
        db.set_active_workspace(ws1["id"])
        db.set_active_workspace(ws2["id"])
        active = db.get_active_workspace()
        assert active["id"] == ws2["id"]
