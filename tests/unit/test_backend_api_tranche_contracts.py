from __future__ import annotations

from fastapi.testclient import TestClient

from api.app import app


def test_health_contract_fields() -> None:
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    payload = response.json()
    assert isinstance(payload.get("status"), str)
    assert payload.get("schema_version") == 1
    providers = payload.get("providers")
    assert isinstance(providers, dict)
    assert isinstance(providers.get("openai"), bool)
    assert isinstance(providers.get("anthropic"), bool)


def test_chat_contract_fields() -> None:
    client = TestClient(app)
    response = client.post(
        "/chat",
        json={
            "schema_version": 1,
            "message": "hello",
            "history": [{"role": "user", "content": "ping"}],
            "mode": "auto",
            "persona": "guppy",
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload.get("schema_version") == 1
    assert isinstance(payload.get("reply"), str)
    assert isinstance(payload.get("model"), str)
    assert isinstance(payload.get("latency_ms"), int)
    assert payload.get("finish_reason") in {"stop", "length", "error"}


def test_chat_stream_emits_sse_events() -> None:
    client = TestClient(app)
    with client.stream(
        "POST",
        "/chat/stream",
        json={"schema_version": 1, "message": "stream test", "history": []},
    ) as response:
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")
        body = "".join(response.iter_text())

    assert "data:" in body
    assert '"schema_version": 1' in body
    assert '"done": true' in body
