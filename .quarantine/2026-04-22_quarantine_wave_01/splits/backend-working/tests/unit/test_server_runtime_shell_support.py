from __future__ import annotations

from collections import Counter
from types import SimpleNamespace

from src.guppy.api.server_runtime_shell_support import (
    build_runtime_app,
    build_server_context,
    detect_voice_backends,
)


def test_detect_voice_backends_prefers_kokoro_and_lazy_whisper() -> None:
    seen: list[str] = []

    def find_spec(name: str):
        seen.append(name)
        return object() if name in {"kokoro", "faster_whisper"} else None

    probe = detect_voice_backends(environ={}, find_spec=find_spec)

    assert probe.tts_backend == "kokoro"
    assert probe.stt_backend == "whisper"
    assert "kokoro module found" in probe.details
    assert "faster-whisper module found (lazy import)" in probe.details
    assert seen == ["kokoro", "faster_whisper"]


def test_detect_voice_backends_falls_back_to_google_stt() -> None:
    def find_spec(name: str):
        return object() if name == "speech_recognition" else None

    probe = detect_voice_backends(environ={}, find_spec=find_spec)

    assert probe.tts_backend == "sapi"
    assert probe.stt_backend == "google"
    assert "speech_recognition module found" in probe.details


def test_build_runtime_app_adds_cors_and_http_middleware() -> None:
    async def middleware(request, call_next):  # pragma: no cover - wiring only
        return await call_next(request)

    async def lifespan(_app):
        yield

    app = build_runtime_app(
        allowed_origins=["http://localhost:8081"],
        lifespan=lifespan,
        request_timing_middleware=middleware,
    )

    middleware_classes = [entry.cls.__name__ for entry in app.user_middleware]
    assert "CORSMiddleware" in middleware_classes
    assert "BaseHTTPMiddleware" in middleware_classes


def test_build_server_context_maps_owner_runtime_dependencies() -> None:
    owner = SimpleNamespace(
        DEV_MODE=True,
        GUPPY_CORE_AVAILABLE=True,
        core=object(),
        GUPPY_DAEMON_AVAILABLE=True,
        get_daemon_manager=lambda: "daemon",
        STATUS_INCLUDE_WINDOW_CONTEXT=False,
        GUPPY_VOICE_AVAILABLE=True,
        GUPPY_MEMORY_AVAILABLE=True,
        _status_cache={"status": "ok"},
        STATUS_CACHE_TTL_SECONDS=120.0,
        _startup_readiness_cached_or_unknown=lambda: {"overall": "READY"},
        _startup_readiness_snapshot=lambda: {"overall": "READY"},
        _startup_readiness_cache_expired=lambda: False,
        _trigger_startup_readiness_refresh=lambda: None,
        _build_local_runtime_status=lambda: {"state": "READY"},
        _read_resource_envelope_status=lambda: {"cpu": "ok"},
        _api_metrics_lock=object(),
        _api_metrics={"requests_total": 0, "path_counts": Counter(), "status_counts": Counter()},
        log_session_event=lambda *args, **kwargs: None,
        logger=object(),
        _path_config=object(),
        _read_window_context=lambda: {},
        _read_daemon_runtime_status=lambda: {"state": "READY"},
        tail_session_events=lambda *args, **kwargs: [],
        _read_jsonl_tail=lambda *args, **kwargs: [],
        _query_sqlite_telemetry=lambda *args, **kwargs: [],
        _query_jsonl_telemetry=lambda *args, **kwargs: [],
        _build_telemetry_report=lambda payload: {"count": len(payload)},
        _read_repair_token=lambda: "token",
        _do_repair_action=lambda *args, **kwargs: {"ok": True},
        _load_normalized_instance_bundle=lambda *args, **kwargs: ({}, {}, [], []),
        _load_instances_config=lambda: {},
        _normalize_instances_config=lambda payload: (payload, []),
        _upsert_instance_config=lambda *args, **kwargs: ({}, "created"),
        _save_instances_config=lambda payload: None,
        _instance_names=lambda payload: [],
        _load_instance_state=lambda *args, **kwargs: {},
        _normalize_instance_state=lambda *args, **kwargs: ({}, []),
        _default_instance_state=lambda *args, **kwargs: {},
        _activate_instance_state=lambda payload, name: payload,
        _save_instance_state=lambda payload: None,
        _get_instance_entry=lambda payload, name: None,
        _governance_summary_payload=lambda *args, **kwargs: {},
        _workspace_connector_payload=lambda *args, **kwargs: [],
        _connector_inventory_payload=lambda: [],
        _instance_limits_payload=lambda *args, **kwargs: {},
        run_connector_action=lambda *args, **kwargs: {"ok": True},
        save_workspace_connector_binding=lambda *args, **kwargs: None,
        resolve_instance_permissions=lambda *args, **kwargs: {},
        set_instance_tool_permission_policy=lambda *args, **kwargs: None,
        _call_module_attr=lambda name, *args, **kwargs: {"name": name, "args": args, "kwargs": kwargs},
        _INSTANCE_LOGGER_AVAILABLE=True,
        append_instance_log=lambda *args, **kwargs: None,
        delete_instance_log=lambda *args, **kwargs: None,
        read_instance_log_tail=lambda *args, **kwargs: [],
        read_instance_log_summary=lambda *args, **kwargs: {},
        _instance_query_lock=object(),
        _build_chat_request_fingerprint=lambda request: "fingerprint",
        _register_chat_idempotency_key=lambda *args, **kwargs: (True, None),
        _resolve_chat_idempotency_key=lambda *args, **kwargs: None,
        _takeover_chat_idempotency_key=lambda *args, **kwargs: (True, None, False),
        _complete_chat_idempotency_key=lambda *args, **kwargs: None,
        _get_active_instance_context=lambda: (None, None, None, None),
        _request_is_morning_brief=lambda request: False,
        _build_morning_brief_response=lambda: "brief",
        _latest_daily_report_path=lambda: None,
        _build_chat_system_prompt=lambda *args, **kwargs: "prompt",
        _request_is_cacheable=lambda request: False,
        _run_blocking=lambda *args, **kwargs: None,
        _save_voice_upload_tempfile=lambda *args, **kwargs: "temp.wav",
        _stream_chunks=lambda *args, **kwargs: iter(()),
    )
    auth_support = SimpleNamespace(
        require_rate_limit=lambda: "rate",
        require_auth_rate_limit=lambda: "auth-rate",
        verify_turnstile_token_auth=lambda token: True,
        create_access_token=lambda **kwargs: "token",
        access_token_expire_minutes=60,
    )

    context = build_server_context(
        owner=owner,
        app=build_runtime_app(
            allowed_origins=["http://localhost:8081"],
            lifespan=lambda _app: None,
            request_timing_middleware=lambda request, call_next: call_next(request),
        ),
        auth_request_support=auth_support,
        voice_probe=SimpleNamespace(
            tts_backend="kokoro",
            stt_backend="whisper",
            details=["kokoro module found"],
        ),
    )

    assert context.dev_mode is True
    assert context.voice_tts_backend == "kokoro"
    assert context.voice_stt_backend == "whisper"
    assert context.run_connector_action() == {"ok": True}
    assert context.call_unified_inference() == {"name": "_call_unified_inference", "args": (), "kwargs": {}}
    assert context.check_instance_tool_permission() == {
        "name": "check_instance_tool_permission",
        "args": (),
        "kwargs": {},
    }
