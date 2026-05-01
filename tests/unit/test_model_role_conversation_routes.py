from __future__ import annotations

import sqlite3
from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.guppy import model_roles, paths
from src.guppy.api import (
    routes_conversations,
    routes_model_roles,
    routes_surface,
    routes_workspace,
)


def test_model_role_routes_are_rate_limited_and_persist_partner(tmp_path, monkeypatch) -> None:
    db_path = tmp_path / "guppy_main.db"
    rate_calls: list[str] = []

    monkeypatch.setattr(routes_surface, "_DB_PATH", "")
    monkeypatch.setattr(paths, "MAIN_DB_PATH", db_path)
    monkeypatch.setattr(paths, "ensure_user_data_dir", lambda: tmp_path)
    monkeypatch.setattr(routes_model_roles, "MAIN_DB_PATH", db_path)
    monkeypatch.setattr(routes_model_roles, "ensure_user_data_dir", lambda: tmp_path)

    ctx = SimpleNamespace(
        require_rate_limit=lambda: rate_calls.append("hit") or "unit-user",
    )
    app = FastAPI()
    model_router, control_router = routes_model_roles.build_model_roles_router(ctx)
    app.include_router(model_router)
    app.include_router(control_router)

    client = TestClient(app)
    response = client.put(
        "/api/model-roles/conversation-partner",
        json={"role": "conversation.partner.study"},
    )

    assert response.status_code == 200
    assert response.json() == {
        "ok": True,
        "conversation_partner": "conversation.partner.study",
    }
    assert rate_calls
    assert model_roles.get_active_conversation_partner() == "llamacpp-pepe"

    roles_response = client.get("/api/model-roles")
    assert roles_response.status_code == 200
    roles_payload = roles_response.json()
    assert (
        roles_payload["operator_settings"]["conversation_partner"]
        == "conversation.partner.study"
    )
    assert roles_payload["active_conversation_partner_role"] == "conversation.partner.study"
    assert roles_payload["active_conversation_partner_backend"] == "llamacpp-pepe"


def test_conversation_chat_uses_backend_key_and_stream_adapter(tmp_path, monkeypatch) -> None:
    db_path = tmp_path / "guppy_main.db"
    owner = SimpleNamespace(name="owner")
    rate_calls: list[str] = []
    stream_calls: list[tuple[tuple, dict]] = []

    monkeypatch.setattr(routes_conversations, "_DB_PATH", str(db_path))
    monkeypatch.setattr(routes_conversations, "ensure_user_data_dir", lambda: tmp_path)
    monkeypatch.setattr(
        routes_conversations,
        "get_active_conversation_partner",
        lambda: "llamacpp-rocinante",
    )

    async def fake_stream_unified_inference(*args, **kwargs):
        stream_calls.append((args, kwargs))
        yield "hello "
        yield (
            routes_conversations._SOURCE_SENTINEL
            + "llamacpp-rocinante:rocinante-x-12b"
        )
        yield "there"

    monkeypatch.setattr(
        routes_conversations,
        "stream_unified_inference",
        fake_stream_unified_inference,
    )

    ctx = SimpleNamespace(
        owner=owner,
        require_rate_limit=lambda: rate_calls.append("hit") or "unit-user",
    )
    app = FastAPI()
    app.include_router(routes_conversations.build_conversations_router(ctx))

    client = TestClient(app)
    response = client.post("/api/conversations/chat", json={"message": "Hi there"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert payload["response"] == "hello there"
    assert payload["session_id"]
    assert rate_calls

    assert len(stream_calls) == 1
    args, kwargs = stream_calls[0]
    assert args[0] is owner
    assert args[1] == "Hi there"
    assert "dedicated Conversations surface" in args[2]
    assert kwargs["mode"] == "local"
    assert kwargs["active_local_model"] == "llamacpp-rocinante"
    assert kwargs["skip_tools"] is True
    assert kwargs["history"][-1] == {"role": "user", "content": "Hi there"}

    with sqlite3.connect(db_path) as conn:
        session_row = conn.execute(
            "SELECT model_backend FROM conversation_sessions WHERE id = ?",
            (payload["session_id"],),
        ).fetchone()
        message_roles = [
            row[0]
            for row in conn.execute(
                "SELECT role FROM conversation_session_messages "
                "WHERE conversation_id = ? ORDER BY created_at",
                (payload["session_id"],),
            ).fetchall()
        ]

    assert session_row == ("llamacpp-rocinante",)
    assert message_roles == ["user", "assistant"]


def test_conversation_chat_stream_emits_start_done_and_saves_reply(
    tmp_path,
    monkeypatch,
) -> None:
    db_path = tmp_path / "guppy_main.db"
    owner = SimpleNamespace(name="owner")
    rate_calls: list[str] = []

    monkeypatch.setattr(routes_conversations, "_DB_PATH", str(db_path))
    monkeypatch.setattr(routes_conversations, "ensure_user_data_dir", lambda: tmp_path)
    monkeypatch.setattr(
        routes_conversations,
        "get_active_conversation_partner",
        lambda: "llamacpp-hermes3",
    )

    async def fake_stream_unified_inference(*_args, **_kwargs):
        yield "hello"
        yield " there"

    monkeypatch.setattr(
        routes_conversations,
        "stream_unified_inference",
        fake_stream_unified_inference,
    )

    ctx = SimpleNamespace(
        owner=owner,
        require_rate_limit=lambda: rate_calls.append("hit") or "unit-user",
    )
    app = FastAPI()
    app.include_router(routes_conversations.build_conversations_router(ctx))

    client = TestClient(app)
    response = client.post("/api/conversations/chat/stream", json={"message": "Hi"})

    assert response.status_code == 200
    body = response.text
    assert '"status": "started"' in body
    assert '"session_id":' in body
    assert '"token": "hello"' in body
    assert '"token": " there"' in body
    assert "data: [DONE]" in body
    assert rate_calls

    with sqlite3.connect(db_path) as conn:
        rows = conn.execute(
            "SELECT role, content FROM conversation_session_messages ORDER BY created_at"
        ).fetchall()

    assert rows == [("user", "Hi"), ("assistant", "hello there")]


def test_conversation_sessions_ignore_existing_chat_history_schema(tmp_path, monkeypatch) -> None:
    db_path = tmp_path / "guppy_main.db"
    owner = SimpleNamespace(name="owner")
    rate_calls: list[str] = []

    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """CREATE TABLE conversations (
                   id TEXT PRIMARY KEY,
                   workspace_id TEXT NOT NULL,
                   title TEXT NOT NULL,
                   created_at TEXT NOT NULL,
                   updated_at TEXT NOT NULL
               )"""
        )
        conn.commit()

    monkeypatch.setattr(routes_conversations, "_DB_PATH", str(db_path))
    monkeypatch.setattr(routes_conversations, "ensure_user_data_dir", lambda: tmp_path)
    monkeypatch.setattr(
        routes_conversations,
        "get_active_conversation_partner",
        lambda: "llamacpp-pepe",
    )

    ctx = SimpleNamespace(
        owner=owner,
        require_rate_limit=lambda: rate_calls.append("hit") or "unit-user",
    )
    app = FastAPI()
    app.include_router(routes_conversations.build_conversations_router(ctx))

    client = TestClient(app)
    response = client.get("/api/conversations/sessions")

    assert response.status_code == 200
    assert response.json() == []

    create_response = client.post("/api/conversations/sessions", json={})
    assert create_response.status_code == 200
    payload = create_response.json()
    assert payload["model_backend"] == "llamacpp-pepe"
    assert rate_calls

    with sqlite3.connect(db_path) as conn:
        legacy_columns = [
            row[1]
            for row in conn.execute("PRAGMA table_info(conversations)").fetchall()
        ]
        session_columns = [
            row[1]
            for row in conn.execute("PRAGMA table_info(conversation_sessions)").fetchall()
        ]

    assert "workspace_id" in legacy_columns
    assert "model_backend" in session_columns


def test_conversation_chat_executes_workspace_tool_without_exposing_tool_xml(
    tmp_path,
    monkeypatch,
) -> None:
    conversation_db = tmp_path / "guppy_main.db"
    surface_db = tmp_path / "surface.db"
    owner = SimpleNamespace(name="owner")
    rate_calls: list[str] = []

    # Initialise surface DB schema so _spawn_task_direct can write surface_tasks
    with sqlite3.connect(str(surface_db)) as _sc:
        _sc.executescript(routes_surface._SCHEMA)
        _sc.commit()

    monkeypatch.setattr(routes_conversations, "_DB_PATH", str(conversation_db))
    monkeypatch.setattr(routes_conversations, "ensure_user_data_dir", lambda: tmp_path)
    monkeypatch.setattr(routes_surface, "_DB_PATH", str(surface_db))
    monkeypatch.setattr(
        routes_conversations,
        "get_active_conversation_partner",
        lambda: "llamacpp-pepe",
    )

    async def fake_stream_unified_inference(*_args, **_kwargs):
        yield "I will queue that.\n"
        yield (
            '<tool_call>{"name":"workspace_task","arguments":'
            '{"task":"List files in src/guppy/api"}}</tool_call>'
        )

    monkeypatch.setattr(
        routes_conversations,
        "stream_unified_inference",
        fake_stream_unified_inference,
    )

    ctx = SimpleNamespace(
        owner=owner,
        require_rate_limit=lambda: rate_calls.append("hit") or "unit-user",
    )
    app = FastAPI()
    app.include_router(routes_conversations.build_conversations_router(ctx))

    client = TestClient(app)
    response = client.post(
        "/api/conversations/chat",
        json={"message": "Please queue a workspace task"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert "<tool_call" not in payload["response"]
    assert "I will queue that." in payload["response"]
    assert "Task queued" in payload["response"]
    assert payload["tool_results"][0]["name"] == "workspace_task"
    assert payload["tool_results"][0]["result"]["ok"] is True
    assert rate_calls

    task_id = payload["tool_results"][0]["result"]["task_id"]
    with sqlite3.connect(str(surface_db)) as conn:
        row = conn.execute(
            "SELECT id, title, source, status FROM surface_tasks WHERE id = ?",
            (task_id,),
        ).fetchone()

    assert row == (
        task_id,
        "List files in src/guppy/api",
        "conversations",
        "queued",
    )


def test_conversation_stream_filter_hides_split_tool_blocks() -> None:
    buffer = ""
    marker = None
    visible: list[str] = []

    for token in [
        "Before <",
        "tool",
        '_call>{"name":"workspace_task","arguments":{"task":"x"}}</tool_call> after',
    ]:
        buffer += token
        chunks, buffer, marker = routes_conversations._visible_stream_chunks(buffer, marker)
        visible.extend(chunks)

    if buffer and marker is None:
        visible.append(buffer)

    text = "".join(visible)
    assert "<tool_call" not in text
    assert "</tool_call>" not in text
    assert text == "Before  after"
