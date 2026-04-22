from __future__ import annotations

from fastapi.testclient import TestClient

from api.app import app


def test_catalog_routes_expose_root_status_and_inventory_shapes(monkeypatch) -> None:
    from api.routes import catalog as catalog_routes

    monkeypatch.setattr(
        catalog_routes,
        "_providers_payload",
        lambda: {
            "anthropic": {"configured": True, "active_model": "claude-sonnet-4-6", "models": [{"id": "claude-sonnet-4-6", "name": "Claude Sonnet 4.6", "tier": "smart"}]},
            "openai": {"configured": False, "active_model": "", "models": []},
            "google": {"configured": False, "active_model": "", "models": []},
            "local": {
                "configured": True,
                "backend": "ollama",
                "active_model": "guppy",
                "models": [{"id": "guppy", "name": "guppy", "tier": "local"}],
                "backends": {"ollama": {"alive": True}, "lmstudio": {"alive": False}, "lemonade": {"alive": False}},
            },
        },
    )
    monkeypatch.setattr(
        catalog_routes,
        "_instance_snapshot_payload",
        lambda: {
            "active_instance": "guppy-primary",
            "instances": [
                {
                    "name": "guppy-primary",
                    "status": "active",
                    "mode": "auto",
                    "model_currently_using": "guppy",
                    "message_count": 3,
                }
            ],
        },
    )
    monkeypatch.setattr(
        catalog_routes,
        "connector_inventory",
        lambda: [{"id": "gmail", "auth_state": "ready"}],
    )

    client = TestClient(app)

    root = client.get("/")
    assert root.status_code == 200
    assert root.json()["status"] == "healthy"

    status = client.get("/api/status")
    assert status.status_code == 200
    assert status.json()["health"] == "healthy"

    providers = client.get("/providers")
    assert providers.status_code == 200
    assert providers.json()["local"]["backend"] == "ollama"

    models = client.get("/api/models")
    assert models.status_code == 200
    assert {item["id"] for item in models.json()} == {"claude-sonnet-4-6", "guppy"}

    tools = client.get("/api/tools")
    assert tools.status_code == 200
    assert any(item["id"] == "read_file" for item in tools.json())

    instances_snapshot = client.get("/instances")
    assert instances_snapshot.status_code == 200
    assert instances_snapshot.json()["active_instance"] == "guppy-primary"

    instances = client.get("/api/instances")
    assert instances.status_code == 200
    assert instances.json()[0]["status"] == "running"

    connectors = client.get("/connectors")
    assert connectors.status_code == 200
    assert connectors.json()["connectors"][0]["id"] == "gmail"