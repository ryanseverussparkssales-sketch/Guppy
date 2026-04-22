from __future__ import annotations

from pathlib import Path

from src.guppy.memory import memory_store


def test_workspace_scoped_recent_messages_prefer_matching_workspace(tmp_path: Path) -> None:
    db_path = tmp_path / "memory.db"

    memory_store.save_conversation_message(db_path, "legacy-session", "user", "legacy note")
    memory_store.save_conversation_message(
        db_path,
        "builder-session",
        "user",
        "builder question",
        workspace_name="builder-collab",
    )
    memory_store.save_conversation_message(
        db_path,
        "builder-session",
        "assistant",
        "builder answer",
        workspace_name="builder-collab",
    )
    memory_store.save_conversation_message(
        db_path,
        "primary-session",
        "user",
        "primary question",
        workspace_name="guppy-primary",
    )
    memory_store.save_conversation_message(
        db_path,
        "primary-session",
        "assistant",
        "primary answer",
        workspace_name="guppy-primary",
    )

    recent = memory_store.get_recent_messages_text(
        db_path,
        exclude_session="active-session",
        workspace_name="builder-collab",
    )

    assert "builder question" in recent
    assert "builder answer" in recent
    assert "primary question" not in recent
    assert "legacy note" not in recent


def test_workspace_scoped_recent_messages_fall_back_to_legacy_rows(tmp_path: Path) -> None:
    db_path = tmp_path / "memory.db"

    memory_store.save_conversation_message(db_path, "legacy-session", "user", "legacy question")
    memory_store.save_conversation_message(db_path, "legacy-session", "assistant", "legacy answer")

    recent = memory_store.get_recent_messages_text(
        db_path,
        exclude_session="active-session",
        workspace_name="builder-collab",
    )

    assert "legacy question" in recent
    assert "legacy answer" in recent


def test_load_recent_history_can_filter_by_workspace(tmp_path: Path) -> None:
    db_path = tmp_path / "memory.db"

    memory_store.save_conversation_message(
        db_path,
        "shared-session",
        "user",
        "primary note",
        workspace_name="guppy-primary",
    )
    memory_store.save_conversation_message(
        db_path,
        "shared-session",
        "assistant",
        "builder note",
        workspace_name="builder-collab",
    )

    history = memory_store.load_recent_history_records(
        db_path,
        session_id="shared-session",
        workspace_name="builder-collab",
    )

    assert history == [{"role": "assistant", "content": "builder note"}]


def test_workspace_memory_snapshot_prefers_matching_workspace_and_counts_sessions(tmp_path: Path) -> None:
    db_path = tmp_path / "memory.db"

    memory_store.save_conversation_message(
        db_path,
        "builder-session-1",
        "user",
        "builder question one",
        workspace_name="builder-collab",
    )
    memory_store.save_conversation_message(
        db_path,
        "builder-session-1",
        "assistant",
        "builder answer one",
        workspace_name="builder-collab",
    )
    memory_store.save_conversation_message(
        db_path,
        "builder-session-2",
        "user",
        "builder question two",
        workspace_name="builder-collab",
    )

    snapshot = memory_store.get_workspace_memory_snapshot(db_path, "builder-collab")

    assert snapshot["workspace_name"] == "builder-collab"
    assert snapshot["message_count"] == 3
    assert snapshot["session_count"] == 2
    assert snapshot["latest_message"] == "builder question two"
    assert snapshot["used_legacy_fallback"] is False


def test_workspace_memory_snapshot_can_fall_back_to_legacy_rows(tmp_path: Path) -> None:
    db_path = tmp_path / "memory.db"

    memory_store.save_conversation_message(db_path, "legacy-session", "user", "legacy question")
    memory_store.save_conversation_message(db_path, "legacy-session", "assistant", "legacy answer")

    snapshot = memory_store.get_workspace_memory_snapshot(db_path, "builder-collab")

    assert snapshot["workspace_name"] == "builder-collab"
    assert snapshot["message_count"] == 2
    assert snapshot["session_count"] == 1
    assert snapshot["latest_message"] == "legacy answer"
    assert snapshot["used_legacy_fallback"] is True
