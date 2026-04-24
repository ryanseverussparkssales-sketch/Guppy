"""Wave 3 — auth token endpoint + persona system prompt tests."""
from __future__ import annotations

import json
import os
from contextlib import contextmanager
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

_TEST_SECRET = "wave3-test-secret-only"
_TEST_API_KEY = "wave3-test-api-key-only"


# ── Helpers ────────────────────────────────────────────────────────────────────

@contextmanager
def _client_ctx(extra_env: dict | None = None):
    """Context manager: TestClient active while patch.dict is in scope."""
    env = {"GUPPY_JWT_SECRET": _TEST_SECRET, "GUPPY_API_KEY": _TEST_API_KEY}
    if extra_env:
        env.update(extra_env)
    with patch.dict(os.environ, env):
        from api.app import app
        yield TestClient(app)


# ── POST /auth/token ───────────────────────────────────────────────────────────


def test_token_returns_bearer_on_valid_key() -> None:
    with _client_ctx() as client:
        resp = client.post("/auth/token", json={"api_key": _TEST_API_KEY})
    assert resp.status_code == 200
    body = resp.json()
    assert body["token_type"] == "bearer"
    assert isinstance(body["access_token"], str)
    assert len(body["access_token"]) > 20
    assert body["schema_version"] == 1


def test_token_rejects_wrong_key() -> None:
    with _client_ctx() as client:
        resp = client.post("/auth/token", json={"api_key": "totally-wrong-key"})
    assert resp.status_code == 401
    assert resp.json()["detail"]["code"] == "invalid_api_key"


def test_token_disabled_when_api_key_not_configured() -> None:
    with patch.dict(os.environ, {"GUPPY_JWT_SECRET": _TEST_SECRET, "GUPPY_API_KEY": ""}):
        from api.app import app
        client = TestClient(app)
        resp = client.post("/auth/token", json={"api_key": "anything"})
    assert resp.status_code == 503
    assert resp.json()["detail"]["code"] == "auth_not_configured"


def test_token_can_be_used_on_chat_endpoint() -> None:
    """Token issued by /auth/token must be accepted by POST /chat."""
    with _client_ctx() as client:
        from api.auth import create_access_token
        token = create_access_token("api-client")
        resp = client.post(
            "/chat",
            json={"message": "hello", "history": []},
            headers={"Authorization": f"Bearer {token}"},
        )
    assert resp.status_code == 200


# ── Persona / mode system prompts ─────────────────────────────────────────────


def test_system_prompt_guppy_default() -> None:
    from api.routes.chat import ChatRequest, _system_prompt

    req = ChatRequest(message="hi")
    prompt = _system_prompt(req)
    assert "guppy" in prompt.lower()
    assert "assistant" in prompt.lower()


def test_system_prompt_merlin_persona() -> None:
    from api.routes.chat import ChatRequest, _system_prompt

    req = ChatRequest(message="hi", persona="merlin")
    prompt = _system_prompt(req)
    assert "merlin" in prompt.lower()


def test_system_prompt_precise_mode_appends_suffix() -> None:
    from api.routes.chat import ChatRequest, _system_prompt

    req = ChatRequest(message="hi", mode="precise")
    prompt = _system_prompt(req)
    assert "terse" in prompt.lower() or "factual" in prompt.lower()


def test_system_prompt_creative_mode_appends_suffix() -> None:
    from api.routes.chat import ChatRequest, _system_prompt

    req = ChatRequest(message="hi", mode="creative")
    prompt = _system_prompt(req)
    assert "imaginative" in prompt.lower() or "expansive" in prompt.lower()


def test_build_messages_injects_system_role_first() -> None:
    from api.routes.chat import ChatRequest, _build_messages

    req = ChatRequest(
        message="hello",
        history=[{"role": "user", "content": "ping"}],
        persona="merlin",
    )
    msgs = _build_messages(req)
    assert msgs[0]["role"] == "system"
    assert "merlin" in msgs[0]["content"].lower()
    # history entry
    assert msgs[1] == {"role": "user", "content": "ping"}
    # current message
    assert msgs[-1] == {"role": "user", "content": "hello"}


def test_unknown_persona_falls_back_to_guppy() -> None:
    from api.routes.chat import ChatRequest, _system_prompt

    req = ChatRequest(message="hi", persona="unknown-bot-x")
    prompt = _system_prompt(req)
    assert "guppy" in prompt.lower()


# ── Cloud boundary audit ───────────────────────────────────────────────────────


def test_api_cloud_surface_has_no_desktop_imports() -> None:
    """Audit api/ for forbidden desktop-runtime imports."""
    import ast
    from pathlib import Path

    _FORBIDDEN_MODULES = {
        "guppy_core",
        "src.guppy.voice",
        "src.guppy.daemon",
        "src.guppy.launcher_application",
        "utils.env_bootstrap",
        "utils.db_utils",
        "src.guppy.paths",
    }

    root = Path(__file__).resolve().parents[2]
    api_dir = root / "api"
    violations: list[str] = []

    for py_file in sorted(api_dir.rglob("*.py")):
        source = py_file.read_text(encoding="utf-8")
        try:
            tree = ast.parse(source)
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            module = ""
            if isinstance(node, ast.ImportFrom) and node.module:
                module = node.module
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    module = alias.name
                    for forbidden in _FORBIDDEN_MODULES:
                        if module == forbidden or module.startswith(f"{forbidden}."):
                            violations.append(f"{py_file.relative_to(root)}: imports {module}")
                continue
            for forbidden in _FORBIDDEN_MODULES:
                if module == forbidden or module.startswith(f"{forbidden}."):
                    violations.append(f"{py_file.relative_to(root)}: imports {module}")

    assert violations == [], "Cloud API surface has desktop imports:\n" + "\n".join(violations)
