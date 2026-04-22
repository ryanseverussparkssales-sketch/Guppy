from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Awaitable, Callable

from fastapi import FastAPI

from src.guppy.api.server_paths import ServerPathConfig


@dataclass(slots=True)
class ServerContext:
    app: FastAPI
    owner: Any
    require_rate_limit: Callable[..., Any]
    require_auth_rate_limit: Callable[..., Any]
    require_repair_token: Callable[..., Any] | None
    verify_turnstile_token_auth: Callable[[str], Awaitable[bool]]
    create_access_token: Callable[..., str]
    access_token_expire_minutes: int
    dev_mode: bool
    guppy_core_available: bool
    core: Any
    guppy_daemon_available: bool
    get_daemon_manager: Callable[[], Any]
    status_include_window_context: bool
    guppy_voice_available: bool
    voice_tts_backend: str
    voice_stt_backend: str
    voice_backend_details: list[str]
    guppy_memory_available: bool
    status_cache: dict[str, Any]
    status_cache_ttl_seconds: float
    startup_readiness_cached_or_unknown: Callable[[], dict[str, Any]]
    startup_readiness_snapshot: Callable[[], dict[str, Any]]
    startup_readiness_cache_expired: Callable[[], bool]
    trigger_startup_readiness_refresh: Callable[[], None]
    build_local_runtime_status: Callable[[], dict[str, Any]]
    read_resource_envelope_status: Callable[[], dict[str, Any]]
    api_metrics_lock: Any
    api_metrics: dict[str, Any]
    log_session_event: Callable[..., None]
    logger: Any
    paths: ServerPathConfig
    read_window_context: Callable[[], dict[str, Any]]
    read_daemon_runtime_status: Callable[[], dict[str, Any]]
    tail_session_events: Callable[..., list[dict[str, Any]]]
    read_jsonl_tail: Callable[..., list[dict[str, Any]]]
    query_sqlite_telemetry: Callable[..., list[dict[str, Any]]]
    query_jsonl_telemetry: Callable[..., list[dict[str, Any]]]
    build_telemetry_report: Callable[[list[dict[str, Any]]], dict[str, Any]]
    read_repair_token: Callable[..., str]
    do_repair_action: Callable[..., dict[str, Any]]
    load_normalized_instance_bundle: Callable[..., tuple[dict[str, Any], dict[str, Any], list[str], list[str]]]
    load_instances_config: Callable[[], dict[str, Any]]
    normalize_instances_config: Callable[[dict[str, Any]], tuple[dict[str, Any], list[str]]]
    upsert_instance_config: Callable[..., tuple[dict[str, Any], str]]
    save_instances_config: Callable[[dict[str, Any]], None]
    instance_names: Callable[[dict[str, Any]], list[str]]
    load_instance_state: Callable[..., dict[str, Any]]
    normalize_instance_state: Callable[..., tuple[dict[str, Any], list[str]]]
    default_instance_state: Callable[..., dict[str, Any]]
    activate_instance_state: Callable[[dict[str, Any], str], dict[str, Any]]
    save_instance_state: Callable[[dict[str, Any]], None]
    get_instance_entry: Callable[[dict[str, Any], str], dict[str, Any] | None]
    governance_summary_payload: Callable[[str, str], dict[str, Any]]
    workspace_connector_payload: Callable[[str], list[dict[str, Any]]]
    connector_inventory_payload: Callable[[], list[dict[str, Any]]]
    instance_limits_payload: Callable[[dict[str, Any], dict[str, Any]], dict[str, int]]
    run_connector_action: Callable[..., dict[str, Any]]
    save_workspace_connector_binding: Callable[..., Any]
    resolve_instance_permissions: Callable[..., dict[str, Any]]
    set_instance_tool_permission_policy: Callable[..., Any]
    check_instance_tool_permission: Callable[..., tuple[bool, str, dict[str, Any]]]
    instance_logger_available: bool
    append_instance_log: Callable[..., Any]
    delete_instance_log: Callable[..., Any]
    read_instance_log_tail: Callable[..., list[dict[str, Any]]]
    read_instance_log_summary: Callable[..., dict[str, Any]]
    instance_query_lock: Any
    build_chat_request_fingerprint: Callable[[Any], str]
    register_chat_idempotency_key: Callable[..., tuple[bool, Any]]
    resolve_chat_idempotency_key: Callable[..., dict[str, Any] | None]
    takeover_chat_idempotency_key: Callable[..., tuple[bool, Any, bool]]
    complete_chat_idempotency_key: Callable[..., None]
    get_active_instance_context: Callable[[], tuple[str | None, str | None, str | None, str | None]]
    request_is_morning_brief: Callable[[Any], bool]
    build_morning_brief_response: Callable[[], str]
    latest_daily_report_path: Callable[[], Any]
    build_chat_system_prompt: Callable[..., str]
    request_is_cacheable: Callable[[Any], bool]
    run_blocking: Callable[..., Awaitable[Any]]
    call_unified_inference: Callable[..., Any]
    save_voice_upload_tempfile: Callable[..., Awaitable[str]]
    stream_chunks: Callable[..., Any]
