from __future__ import annotations

from dataclasses import dataclass
from functools import partial
from typing import Any, Callable

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.guppy.api.server_context import ServerContext


@dataclass(frozen=True, slots=True)
class VoiceBackendProbe:
    tts_backend: str
    stt_backend: str
    details: list[str]


@dataclass(frozen=True, slots=True)
class ServerRuntimeShell:
    app: FastAPI
    server_context: ServerContext


def detect_voice_backends(
    *,
    environ: Any,
    find_spec: Callable[[str], Any],
) -> VoiceBackendProbe:
    tts, stt, details = "sapi", "none", []
    try:
        if find_spec("kokoro") is not None:
            tts = "kokoro"
            details.append("kokoro module found")
        else:
            details.append("kokoro unavailable -> sapi fallback")
    except Exception:
        details.append("kokoro unavailable -> sapi fallback")

    probe_whisper = str(environ.get("GUPPY_API_PROBE_WHISPER", "0")).strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }
    try:
        if find_spec("faster_whisper") is not None:
            stt = "whisper"
            detail = "faster-whisper import ok" if probe_whisper else "faster-whisper module found (lazy import)"
            details.append(detail)
        else:
            raise ImportError("faster_whisper module not found")
    except Exception:
        try:
            if find_spec("speech_recognition") is not None:
                stt = "google"
                details.append("speech_recognition module found")
            else:
                details.append("no transcription backend available")
        except Exception:
            details.append("no transcription backend available")

    return VoiceBackendProbe(tts_backend=tts, stt_backend=stt, details=details)


def build_runtime_app(
    *,
    allowed_origins: list[str],
    lifespan: Any,
    request_timing_middleware: Callable[..., Any],
    title: str = "Guppy API",
    description: str = "Remote access API for Guppy AI assistant",
    version: str = "1.0.0",
) -> FastAPI:
    app = FastAPI(
        title=title,
        description=description,
        version=version,
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "X-Repair-Token", "X-Turnstile-Token"],
    )
    app.middleware("http")(request_timing_middleware)
    return app


def build_server_context(
    *,
    owner: Any,
    app: FastAPI,
    auth_request_support: Any,
    voice_probe: VoiceBackendProbe,
) -> ServerContext:
    return ServerContext(
        app=app,
        owner=owner,
        require_rate_limit=auth_request_support.require_rate_limit,
        require_auth_rate_limit=auth_request_support.require_auth_rate_limit,
        require_repair_token=None,
        verify_turnstile_token_auth=auth_request_support.verify_turnstile_token_auth,
        create_access_token=auth_request_support.create_access_token,
        access_token_expire_minutes=auth_request_support.access_token_expire_minutes,
        dev_mode=bool(owner.DEV_MODE),
        guppy_core_available=owner.GUPPY_CORE_AVAILABLE,
        core=owner.core,
        guppy_daemon_available=owner.GUPPY_DAEMON_AVAILABLE,
        get_daemon_manager=owner.get_daemon_manager,
        status_include_window_context=owner.STATUS_INCLUDE_WINDOW_CONTEXT,
        guppy_voice_available=owner.GUPPY_VOICE_AVAILABLE,
        voice_tts_backend=voice_probe.tts_backend,
        voice_stt_backend=voice_probe.stt_backend,
        voice_backend_details=voice_probe.details,
        guppy_memory_available=owner.GUPPY_MEMORY_AVAILABLE,
        status_cache=owner._status_cache,
        status_cache_ttl_seconds=owner.STATUS_CACHE_TTL_SECONDS,
        startup_readiness_cached_or_unknown=owner._startup_readiness_cached_or_unknown,
        startup_readiness_snapshot=owner._startup_readiness_snapshot,
        startup_readiness_cache_expired=owner._startup_readiness_cache_expired,
        trigger_startup_readiness_refresh=owner._trigger_startup_readiness_refresh,
        build_local_runtime_status=owner._build_local_runtime_status,
        read_resource_envelope_status=owner._read_resource_envelope_status,
        api_metrics_lock=owner._api_metrics_lock,
        api_metrics=owner._api_metrics,
        log_session_event=owner.log_session_event,
        logger=owner.logger,
        paths=owner._path_config,
        read_window_context=owner._read_window_context,
        read_daemon_runtime_status=owner._read_daemon_runtime_status,
        tail_session_events=owner.tail_session_events,
        read_jsonl_tail=owner._read_jsonl_tail,
        query_sqlite_telemetry=owner._query_sqlite_telemetry,
        query_jsonl_telemetry=owner._query_jsonl_telemetry,
        build_telemetry_report=owner._build_telemetry_report,
        read_repair_token=owner._read_repair_token,
        do_repair_action=owner._do_repair_action,
        load_normalized_instance_bundle=owner._load_normalized_instance_bundle,
        load_instances_config=owner._load_instances_config,
        normalize_instances_config=owner._normalize_instances_config,
        upsert_instance_config=owner._upsert_instance_config,
        save_instances_config=owner._save_instances_config,
        instance_names=owner._instance_names,
        load_instance_state=owner._load_instance_state,
        normalize_instance_state=owner._normalize_instance_state,
        default_instance_state=owner._default_instance_state,
        activate_instance_state=owner._activate_instance_state,
        save_instance_state=owner._save_instance_state,
        get_instance_entry=owner._get_instance_entry,
        governance_summary_payload=owner._governance_summary_payload,
        workspace_connector_payload=owner._workspace_connector_payload,
        connector_inventory_payload=owner._connector_inventory_payload,
        instance_limits_payload=owner._instance_limits_payload,
        run_connector_action=owner.run_connector_action,
        save_workspace_connector_binding=owner.save_workspace_connector_binding,
        resolve_instance_permissions=owner.resolve_instance_permissions,
        set_instance_tool_permission_policy=owner.set_instance_tool_permission_policy,
        check_instance_tool_permission=partial(owner._call_module_attr, "check_instance_tool_permission"),
        instance_logger_available=owner._INSTANCE_LOGGER_AVAILABLE,
        append_instance_log=owner.append_instance_log,
        delete_instance_log=owner.delete_instance_log,
        read_instance_log_tail=owner.read_instance_log_tail,
        read_instance_log_summary=owner.read_instance_log_summary,
        instance_query_lock=owner._instance_query_lock,
        build_chat_request_fingerprint=owner._build_chat_request_fingerprint,
        register_chat_idempotency_key=owner._register_chat_idempotency_key,
        resolve_chat_idempotency_key=owner._resolve_chat_idempotency_key,
        takeover_chat_idempotency_key=owner._takeover_chat_idempotency_key,
        complete_chat_idempotency_key=owner._complete_chat_idempotency_key,
        get_active_instance_context=owner._get_active_instance_context,
        request_is_morning_brief=owner._request_is_morning_brief,
        build_morning_brief_response=owner._build_morning_brief_response,
        latest_daily_report_path=owner._latest_daily_report_path,
        build_chat_system_prompt=owner._build_chat_system_prompt,
        request_is_cacheable=owner._request_is_cacheable,
        run_blocking=owner._run_blocking,
        call_unified_inference=partial(owner._call_module_attr, "_call_unified_inference"),
        save_voice_upload_tempfile=owner._save_voice_upload_tempfile,
        stream_chunks=owner._stream_chunks,
    )


def build_server_shell(
    *,
    owner: Any,
    allowed_origins: list[str],
    lifespan: Any,
    auth_request_support: Any,
    voice_probe: VoiceBackendProbe,
) -> ServerRuntimeShell:
    app = build_runtime_app(
        allowed_origins=allowed_origins,
        lifespan=lifespan,
        request_timing_middleware=auth_request_support.request_timing_middleware,
    )
    return ServerRuntimeShell(
        app=app,
        server_context=build_server_context(
            owner=owner,
            app=app,
            auth_request_support=auth_request_support,
            voice_probe=voice_probe,
        ),
    )
