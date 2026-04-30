from __future__ import annotations

import sqlite3
from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.guppy import model_roles, paths
from src.guppy.api import routes_conversations, routes_model_roles, routes_surface


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
            "SELECT model_backend FROM conversations WHERE id = ?",
            (payload["session_id"],),
        ).fetchone()
        message_roles = [
            row[0]
            for row in conn.execute(
                "SELECT role FROM conversation_messages "
                "WHERE conversation_id = ? ORDER BY created_at",
                (payload["session_id"],),
            ).fetchall()
        ]

    assert session_row == ("llamacpp-rocinante",)
    assert message_roles == ["user", "assistant"]
