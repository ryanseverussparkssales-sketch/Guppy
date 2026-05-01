from __future__ import annotations

from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.guppy.api.routes_control import build_control_router


def _ctx() -> SimpleNamespace:
    return SimpleNamespace(require_rate_limit=lambda: "control-test")


def _route_contract(app: FastAPI) -> set[tuple[str, str]]:
    contract: set[tuple[str, str]] = set()
    for route in app.routes:
        for method in getattr(route, "methods", set()):
            if method not in {"HEAD", "OPTIONS"}:
                contract.add((method, route.path))
    return contract


def test_control_router_exposes_service_and_model_controls() -> None:
    app = FastAPI()
    app.include_router(build_control_router(_ctx()), prefix="/api/control")

    expected = {
        ("GET", "/api/control/services"),
        ("GET", "/api/control/services/{key}/health"),
        ("POST", "/api/control/services/{key}/on"),
        ("POST", "/api/control/services/{key}/off"),
        ("POST", "/api/control/services/{key}/reset"),
        ("GET", "/api/control/models/{key}/health"),
        ("POST", "/api/control/models/{key}/on"),
        ("POST", "/api/control/models/{key}/off"),
        ("POST", "/api/control/models/{key}/reset"),
        ("POST", "/api/control/models/{key}/restart"),
    }

    assert expected <= _route_contract(app)


def test_control_model_health_reports_backend_status(monkeypatch) -> None:
    from src.guppy.api import routes_backends

    monkeypatch.setitem(
        routes_backends._LLAMACPP_CONFIG,
        "llamacpp-test",
        {
            "port": 9123,
            "label": "Test Model",
            "note": "test note",
            "vram_gb": 1.5,
            "auto_start": False,
        },
    )
    monkeypatch.setattr(routes_backends, "_port_alive", lambda port: port == 9123)

    app = FastAPI()
    app.include_router(build_control_router(_ctx()), prefix="/api/control")
    client = TestClient(app)

    response = client.get("/api/control/models/llamacpp-test/health")

    assert response.status_code == 200
    payload = response.json()
    assert payload["key"] == "llamacpp-test"
    assert payload["label"] == "Test Model"
    assert payload["status"] == "online"
    assert payload["healthy"] is True


def test_control_api_service_health_reports_current_process() -> None:
    app = FastAPI()
    app.include_router(build_control_router(_ctx()), prefix="/api/control")
    client = TestClient(app)

    response = client.get("/api/control/services/api/health")

    assert response.status_code == 200
    payload = response.json()
    assert payload["key"] == "api"
    assert payload["service_name"] == "api"
    assert payload["state"] == "running"
    assert payload["health"] == "up"
    assert payload["pid"]
