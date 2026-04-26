from __future__ import annotations

import json
import shutil
import tempfile
import uuid
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from src.guppy.api import server as guppy_api


_TEST_TMP_ROOT = Path(__file__).resolve().parents[1] / ".tmp" / "test-scratch" / "chat-routing"


def _snapshot_api_paths():
    return guppy_api._path_config


def _restore_api_paths(snapshot) -> None:
    guppy_api._set_path_config_for_tests(
        config_dir=snapshot.config_dir,
        runtime_dir=snapshot.runtime_dir,
        instances_path=snapshot.instances_path,
        connector_bindings_path=snapshot.connector_bindings_path,
        instance_state_path=snapshot.instance_state_path,
        repair_token_file=snapshot.repair_token_file,
        ops_telemetry_db=snapshot.ops_telemetry_db,
    )


@contextmanager
def _temp_api_layout(
    *,
    instances_config: dict,
    instance_state: dict,
    daily_report_markdown: str | None = None,
    resource_envelope: dict | None = None,
):
    old_paths = _snapshot_api_paths()
    _TEST_TMP_ROOT.mkdir(parents=True, exist_ok=True)
    tmp_root = _TEST_TMP_ROOT / uuid.uuid4().hex
    tmp_root.mkdir(parents=True, exist_ok=False)
    try:
        cfg = tmp_root / "config"
        rt = tmp_root / "runtime"
        cfg.mkdir(parents=True, exist_ok=True)
        rt.mkdir(parents=True, exist_ok=True)

        instances_path = cfg / "instances.json"
        state_path = rt / "instance_state.json"
        instances_path.write_text(json.dumps(instances_config), encoding="utf-8")
        state_path.write_text(json.dumps(instance_state), encoding="utf-8")

        if resource_envelope is not None:
            (rt / "resource_envelope.status.json").write_text(json.dumps(resource_envelope), encoding="utf-8")
        if daily_report_markdown is not None:
            reports = rt / "daily_reports"
            reports.mkdir(parents=True, exist_ok=True)
            (reports / f"{guppy_api.datetime.now().strftime('%Y-%m-%d')}.md").write_text(
                daily_report_markdown,
                encoding="utf-8",
            )

        guppy_api._set_path_config_for_tests(
            config_dir=cfg,
            runtime_dir=rt,
            instances_path=instances_path,
            instance_state_path=state_path,
        )
        yield instances_path, state_path
    finally:
        _restore_api_paths(old_paths)
        shutil.rmtree(tmp_root, ignore_errors=True)


def _builder_instances_config() -> dict:
    return {
        "version": 1,
        "active_instance": "builder-collab",
        "instances": [
            {
                "name": "guppy-primary",
                "description": "Primary",
                "mode": "auto",
                "persona": "guppy",
                "voice": "default",
                "enabled": True,
                "type": "user_instance",
            },
            {
                "name": "builder-collab",
                "description": "Collaborator",
                "mode": "teaching",
                "persona": "guppy",
                "voice": "default",
                "enabled": True,
                "type": "builder_instance",
            },
        ],
    }


def _builder_instance_state() -> dict:
    return {
        "version": 1,
        "active_instance": "builder-collab",
        "instances": {
            "guppy-primary": {
                "status": "idle",
                "last_message": "",
                "last_updated": None,
                "message_count": 0,
                "model_currently_using": "auto",
            },
            "builder-collab": {
                "status": "active",
                "last_message": "",
                "last_updated": None,
                "message_count": 0,
                "model_currently_using": "teaching",
            },
        },
    }


def _with_rate_limit_override():
    app = guppy_api.app
    app.dependency_overrides[guppy_api.require_rate_limit] = lambda: "smoke-user"
    return app


def test_chat_route_forwards_active_instance_context() -> None:
    app = _with_rate_limit_override()
    calls: list[tuple[str | None, str | None, str]] = []

    try:
        with _temp_api_layout(
            instances_config=_builder_instances_config(),
            instance_state=_builder_instance_state(),
        ):
            def _fake_inference(message, system_prompt, mode=None, history=None, instance_name=None, instance_type=None, active_local_model=None):
                del system_prompt, mode, history
                calls.append((instance_name, instance_type, message))
                return f"ok:{instance_name}:{instance_type}"

            client = TestClient(app)
            with patch.object(guppy_api._server_context, "call_unified_inference", side_effect=_fake_inference), patch.object(
                guppy_api,
                "get_cached_response",
                return_value=None,
            ):
                assert client.post("/chat", json={"message": "hello"}).status_code == 200
                assert client.post(
                    "/instances/builder-collab/query",
                    json={"message": "builder question", "source_instance": "guppy-primary"},
                ).status_code == 200

        assert len(calls) >= 2
        assert calls[0][:2] == ("builder-collab", "builder_instance")
        assert calls[1][:2] == ("builder-collab", "builder_instance")
    finally:
        app.dependency_overrides.pop(guppy_api.require_rate_limit, None)


def test_chat_route_repairs_active_instance_before_persisting() -> None:
    app = _with_rate_limit_override()
    try:
        with _temp_api_layout(
            instances_config={
                "version": "bad",
                "active_instance": "missing",
                "instances": [{"description": "missing name"}, {"name": "guppy-primary", "mode": "auto", "enabled": True}],
            },
            instance_state={
                "instances": {
                    "ghost": {"status": "busy"},
                    "guppy-primary": {"status": "NOT_A_STATUS", "message_count": "3"},
                }
            },
        ) as (instances_path, state_path):
            client = TestClient(app)
            with patch.object(guppy_api._server_context, "call_unified_inference", return_value="ok"), patch.object(
                guppy_api,
                "get_cached_response",
                return_value=None,
            ):
                resp = client.post("/chat", json={"message": "hello"})

            assert resp.status_code == 200
            persisted_config = json.loads(instances_path.read_text(encoding="utf-8"))
            persisted_state = json.loads(state_path.read_text(encoding="utf-8"))
            assert persisted_config["active_instance"] == "guppy-primary"
            assert [item.get("name") for item in persisted_config["instances"]] == ["guppy-primary"]
            assert "ghost" not in persisted_state["instances"]
            assert persisted_state["instances"]["guppy-primary"]["status"] == "active"
    finally:
        app.dependency_overrides.pop(guppy_api.require_rate_limit, None)


def test_instance_query_route_rejects_blocked_source_workspace() -> None:
    app = _with_rate_limit_override()
    try:
        with _temp_api_layout(
            instances_config={
                "version": 1,
                "active_instance": "guppy-primary",
                "instances": [
                    {
                        "name": "guppy-primary",
                        "description": "Primary",
                        "mode": "auto",
                        "persona": "guppy",
                        "voice": "default",
                        "enabled": True,
                        "type": "user_instance",
                    },
                    {
                        "name": "source-readonly",
                        "description": "Reference",
                        "mode": "auto",
                        "persona": "guppy",
                        "voice": "default",
                        "enabled": True,
                        "type": "read_only_instance",
                    },
                ],
            },
            instance_state={
                "version": 1,
                "active_instance": "guppy-primary",
                "instances": {
                    "guppy-primary": {"status": "active", "message_count": 0},
                    "source-readonly": {"status": "idle", "message_count": 0},
                },
            },
        ):
            client = TestClient(app)
            with patch.object(
                guppy_api._server_context,
                "check_instance_tool_permission",
                return_value=(False, "query blocked", {"network": False}),
            ):
                resp = client.post(
                    "/instances/guppy-primary/query",
                    json={"message": "hi", "source_instance": "source-readonly"},
                )

            assert resp.status_code == 403
            assert "cannot use cross-workspace query" in resp.json()["detail"]
            assert "query blocked" in resp.json()["detail"]
    finally:
        app.dependency_overrides.pop(guppy_api.require_rate_limit, None)


def test_chat_route_uses_morning_brief_shortcut() -> None:
    app = _with_rate_limit_override()
    try:
        with _temp_api_layout(
            instances_config={
                "version": 1,
                "active_instance": "guppy-primary",
                "instances": [
                    {
                        "name": "guppy-primary",
                        "description": "Primary",
                        "mode": "auto",
                        "persona": "guppy",
                        "voice": "default",
                        "enabled": True,
                        "type": "user_instance",
                    }
                ],
            },
            instance_state={
                "version": 1,
                "active_instance": "guppy-primary",
                "instances": {
                    "guppy-primary": {
                        "status": "active",
                        "last_message": "",
                        "last_updated": None,
                        "message_count": 0,
                        "model_currently_using": "auto",
                    }
                },
            },
            daily_report_markdown=(
                "## Key Actions\n- Review top task\n- Check runtime health\n\n"
                "## World News\n| Topic | Status |\n|---|---|\n| Markets | Stable |\n\n"
                "## Carry-Forward Items\n1. Follow up on builder work\n"
            ),
            resource_envelope={"state": "ok", "message": "resource envelope within limits"},
        ):
            client = TestClient(app)
            with patch.object(guppy_api._server_context, "call_unified_inference", side_effect=AssertionError("inference should not run")):
                resp = client.post(
                    "/chat",
                    json={
                        "message": "yes lets",
                        "history": [
                            {
                                "role": "assistant",
                                "content": "Shall I prepare your morning brief? I can pull together today's reminders.",
                            }
                        ],
                    },
                )

            assert resp.status_code == 200
            payload = resp.json()
            assert payload["brief"] is True
            assert "Morning brief for" in payload["response"]
            assert "Review top task" in payload["response"]
            assert "runtime/daily_reports/" in payload["response"]
    finally:
        app.dependency_overrides.pop(guppy_api.require_rate_limit, None)


def test_chat_route_simple_request_uses_light_prompt_context() -> None:
    app = _with_rate_limit_override()
    client = TestClient(app)
    captured: dict[str, object] = {}

    def _fake_prompt(*_args, **kwargs):
        captured.update(kwargs)
        return "SYSTEM"

    try:
        with patch.object(guppy_api.core, "get_startup_system", side_effect=_fake_prompt), patch.object(
            guppy_api._server_context,
            "call_unified_inference",
            return_value="ok",
        ), patch.object(
            guppy_api,
            "get_cached_response",
            return_value=None,
        ):
            resp = client.post("/chat", json={"message": "ping"})

        assert resp.status_code == 200
        assert not bool(captured.get("include_memory_context"))
        assert not bool(captured.get("include_semantic_context"))
    finally:
        app.dependency_overrides.pop(guppy_api.require_rate_limit, None)


def test_chat_route_follow_up_request_keeps_rich_prompt_context() -> None:
    app = _with_rate_limit_override()
    client = TestClient(app)
    captured: dict[str, object] = {}

    def _fake_prompt(*_args, **kwargs):
        captured.update(kwargs)
        return "SYSTEM"

    try:
        with patch.object(guppy_api.core, "get_startup_system", side_effect=_fake_prompt), patch.object(
            guppy_api._server_context,
            "call_unified_inference",
            return_value="ok",
        ), patch.object(
            guppy_api,
            "get_cached_response",
            return_value=None,
        ):
            resp = client.post(
                "/chat",
                json={
                    "message": "continue the debugging plan and explain the tradeoffs",
                    "history": [{"role": "assistant", "content": "I can draft a debugging plan."}],
                },
            )

        assert resp.status_code == 200
        assert bool(captured.get("include_memory_context"))
        assert bool(captured.get("include_semantic_context"))
    finally:
        app.dependency_overrides.pop(guppy_api.require_rate_limit, None)


def test_chat_route_persists_and_curates_memory_after_response() -> None:
    app = _with_rate_limit_override()
    client = TestClient(app)

    try:
        with patch.object(
            guppy_api._server_context,
            "call_unified_inference",
            return_value="Understood. The Local LLM page should remain separate from Home.",
        ), patch.object(
            guppy_api,
            "get_cached_response",
            return_value=None,
        ), patch.object(
            guppy_api.memory,
            "save_message",
        ) as save_message, patch.object(
            guppy_api.memory,
            "promote_durable_chat_memory",
            return_value=[{"key": "product.the_local_llm_page_scope"}],
        ) as promote_memory:
            resp = client.post(
                "/chat",
                json={
                    "message": "I prefer concise answers. The Local LLM page should stay out of Home.",
                    "session_id": "chat-memory-1",
                },
            )

        assert resp.status_code == 200
        assert save_message.call_count == 2
        save_message.assert_any_call(
            "chat-memory-1",
            "user",
            "I prefer concise answers. The Local LLM page should stay out of Home.",
            workspace_name="guppy-primary",
        )
        save_message.assert_any_call(
            "chat-memory-1",
            "assistant",
            "Understood. The Local LLM page should remain separate from Home.",
            workspace_name="guppy-primary",
        )
        promote_memory.assert_called_once()
        args, kwargs = promote_memory.call_args
        assert args[0] == "I prefer concise answers. The Local LLM page should stay out of Home."
        assert "remain separate from Home" in args[1]
        assert kwargs["session_id"] == "chat-memory-1"
    finally:
        app.dependency_overrides.pop(guppy_api.require_rate_limit, None)


def test_chat_voice_route_simple_transcription_uses_light_prompt_context() -> None:
    app = _with_rate_limit_override()
    client = TestClient(app)
    captured: dict[str, object] = {}

    class _FakeVoice:
        def transcribe_audio(self, _path):
            return "ping"

    def _fake_prompt(*_args, **kwargs):
        captured.update(kwargs)
        return "SYSTEM"

    try:
        with patch.object(guppy_api.voice, "GuppyVoice", return_value=_FakeVoice()), patch.object(
            guppy_api.core,
            "get_startup_system",
            side_effect=_fake_prompt,
        ), patch.object(
            guppy_api._server_context,
            "call_unified_inference",
            return_value="ok",
        ):
            resp = client.post(
                "/chat/voice",
                files={"file": ("sample.wav", b"fake-audio", "audio/wav")},
            )

        assert resp.status_code == 200
        assert not bool(captured.get("include_memory_context"))
        assert not bool(captured.get("include_semantic_context"))
    finally:
        app.dependency_overrides.pop(guppy_api.require_rate_limit, None)


def test_chat_voice_route_rejects_oversized_upload_before_transcription() -> None:
    app = _with_rate_limit_override()
    client = TestClient(app)
    try:
        with patch.object(guppy_api, "GUPPY_CORE_AVAILABLE", True), patch.object(
            guppy_api,
            "GUPPY_VOICE_AVAILABLE",
            True,
        ), patch.object(
            guppy_api,
            "VOICE_UPLOAD_MAX_BYTES",
            4,
        ), patch.object(guppy_api.voice, "GuppyVoice") as voice_ctor:
            resp = client.post(
                "/chat/voice",
                files={"file": ("sample.wav", b"12345", "audio/wav")},
            )

        assert resp.status_code == 413
        assert "Audio upload exceeds" in resp.json()["detail"]
        voice_ctor.assert_not_called()
    finally:
        app.dependency_overrides.pop(guppy_api.require_rate_limit, None)


def test_websocket_route_simple_request_uses_light_prompt_context() -> None:
    captured: dict[str, object] = {}

    def _fake_prompt(*_args, **kwargs):
        captured.update(kwargs)
        return "SYSTEM"

    client = TestClient(guppy_api.app)
    with patch.object(guppy_api.jwt, "decode", return_value={"sub": "smoke-user"}), patch.object(
        guppy_api.core,
        "get_startup_system",
        side_effect=_fake_prompt,
    ), patch.object(
        guppy_api._server_context,
        "call_unified_inference",
        return_value="ok",
    ):
        with client.websocket_connect("/ws") as websocket:
            websocket.send_json({"token": "smoke-token"})
            assert websocket.receive_json() == {"status": "authenticated"}
            websocket.send_json({"message": "ping", "session_id": "ws-smoke"})
            assert websocket.receive_json() == {"chunk": "ok "}
            assert websocket.receive_json() == {"done": True}

    assert not bool(captured.get("include_memory_context"))
    assert not bool(captured.get("include_semantic_context"))
