from __future__ import annotations

import inspect
import sys
from functools import wraps
from typing import Any


def module_owner(module_name: str) -> Any:
    return sys.modules[module_name]


def call_module_attr(module_name: str, name: str, *args, **kwargs):
    return getattr(module_owner(module_name), name)(*args, **kwargs)


def bind_owner(module_name: str, func):
    signature = None
    try:
        original = inspect.signature(func)
        signature = original.replace(parameters=list(original.parameters.values())[1:])
    except Exception:
        signature = None

    @wraps(func)
    def wrapper(*args, **kwargs):
        return func(module_owner(module_name), *args, **kwargs)

    if signature is not None:
        wrapper.__signature__ = signature
    return wrapper


def bind_owner_async(module_name: str, func):
    signature = None
    try:
        original = inspect.signature(func)
        signature = original.replace(parameters=list(original.parameters.values())[1:])
    except Exception:
        signature = None

    @wraps(func)
    async def wrapper(*args, **kwargs):
        return await func(module_owner(module_name), *args, **kwargs)

    if signature is not None:
        wrapper.__signature__ = signature
    return wrapper


def build_owner_binding_alias_map(
    *,
    bind_owner: Any,
    bind_owner_async: Any,
    services_realtime_module: Any,
    services_ops_module: Any,
    services_instances_module: Any,
    services_host_module: Any,
    services_briefing_module: Any,
    services_runtime_module: Any,
) -> dict[str, Any]:
    return {
        "_prune_chat_idempotency_records": services_realtime_module.prune_chat_idempotency_records,
        "_build_chat_request_fingerprint": services_realtime_module.build_chat_request_fingerprint,
        "_register_chat_idempotency_key": services_realtime_module.register_chat_idempotency_key,
        "_resolve_chat_idempotency_key": services_realtime_module.resolve_chat_idempotency_key,
        "_takeover_chat_idempotency_key": services_realtime_module.takeover_chat_idempotency_key,
        "_complete_chat_idempotency_key": services_realtime_module.complete_chat_idempotency_key,
        "_clear_chat_idempotency_key": services_realtime_module.clear_chat_idempotency_key,
        "_should_use_rich_chat_prompt_context": services_realtime_module.should_use_rich_chat_prompt_context,
        "_should_use_rich_prompt_context": services_realtime_module.should_use_rich_prompt_context,
        "_build_chat_system_prompt": bind_owner(services_realtime_module.build_chat_system_prompt),
        "_save_voice_upload_tempfile": bind_owner_async(services_realtime_module.save_voice_upload_tempfile),
        "_read_jsonl_tail": services_ops_module.read_jsonl_tail,
        "_ensure_m2_instance_scaffold": bind_owner(services_instances_module.ensure_m2_instance_scaffold),
        "_load_instances_config": bind_owner(services_instances_module.load_instances_config),
        "_load_instance_state": bind_owner(services_instances_module.load_instance_state),
        "_save_instance_state": bind_owner(services_instances_module.save_instance_state),
        "_save_instances_config": bind_owner(services_instances_module.save_instances_config),
        "_load_normalized_instance_bundle": bind_owner(services_instances_module.load_normalized_instance_bundle),
        "_instance_config_entry": services_instances_module.instance_config_entry,
        "_default_instance_state": services_instances_module.default_instance_state,
        "_instance_names": services_instances_module.instance_names,
        "_get_instance_entry": services_instances_module.get_instance_entry,
        "_get_active_instance_context": bind_owner(services_instances_module.get_active_instance_context),
        "_coerce_int": services_instances_module.coerce_int,
        "_normalize_instances_config": services_instances_module.normalize_instances_config,
        "_normalize_instance_state": services_instances_module.normalize_instance_state,
        "_upsert_instance_config": services_instances_module.upsert_instance_config,
        "_activate_instance_state": services_instances_module.activate_instance_state,
        "_instance_limits_payload": services_instances_module.instance_limits_payload,
        "_emit_integration_heartbeat": bind_owner(services_host_module.emit_integration_heartbeat),
        "_read_daemon_runtime_status": bind_owner(services_host_module.read_daemon_runtime_status),
        "_read_window_context": bind_owner(services_host_module.read_window_context),
        "_read_resource_envelope_status": bind_owner(services_ops_module.read_resource_envelope_status),
        "_parse_iso_ts": services_ops_module.parse_iso_ts,
        "_p95": services_ops_module.p95,
        "_query_sqlite_telemetry": bind_owner(services_ops_module.query_sqlite_telemetry),
        "_query_jsonl_telemetry": bind_owner(services_ops_module.query_jsonl_telemetry),
        "_build_telemetry_report": services_ops_module.build_telemetry_report,
        "_latest_stress_report_path": bind_owner(services_ops_module.latest_stress_report_path),
        "_normalize_brief_text": services_briefing_module.normalize_brief_text,
        "_looks_like_brief_affirmation": services_briefing_module.looks_like_brief_affirmation,
        "_history_offered_morning_brief": services_briefing_module.history_offered_morning_brief,
        "_request_is_morning_brief": services_briefing_module.request_is_morning_brief,
        "_latest_daily_report_path": bind_owner(services_briefing_module.latest_daily_report_path),
        "_strip_markdown_prefix": services_briefing_module.strip_markdown_prefix,
        "_parse_markdown_sections": services_briefing_module.parse_markdown_sections,
        "_preview_markdown_section": services_briefing_module.preview_markdown_section,
        "_preview_plain_block": services_briefing_module.preview_plain_block,
        "_build_morning_brief_response": bind_owner(services_briefing_module.build_morning_brief_response),
        "_collect_runtime_bundle": bind_owner(services_ops_module.collect_runtime_bundle),
        "_do_repair_action": bind_owner(services_ops_module.do_repair_action),
        "_selected_local_runtime_backend": bind_owner(services_runtime_module.selected_local_runtime_backend),
        "_local_runtime_base_url": bind_owner(services_runtime_module.local_runtime_base_url),
        "_resolve_local_runtime_model": bind_owner(services_runtime_module.resolve_local_runtime_model),
        "_local_runtime_role_models": bind_owner(services_runtime_module.local_runtime_role_models),
        "_warm_ollama_chat_lane": bind_owner(services_runtime_module.warm_ollama_chat_lane),
        "_current_local_runtime_chat_model": bind_owner(services_runtime_module.current_local_runtime_chat_model),
        "_refresh_local_runtime_warm_status": bind_owner(services_runtime_module.refresh_local_runtime_warm_status),
        "_local_runtime_warm_cached_or_unknown": bind_owner(services_runtime_module.local_runtime_warm_cached_or_unknown),
        "_trigger_local_runtime_warm_refresh": bind_owner(services_runtime_module.trigger_local_runtime_warm_refresh),
        "_fetch_lemonade_model_ids": bind_owner(services_runtime_module.fetch_lemonade_model_ids),
        "_build_local_runtime_status": bind_owner(services_runtime_module.build_local_runtime_status),
        "_call_lemonade_chat": bind_owner(services_runtime_module.call_lemonade_chat),
        "_call_selected_local_runtime": bind_owner(services_runtime_module.call_selected_local_runtime),
        "_run_blocking": services_realtime_module.run_blocking,
        "_extract_text_from_anthropic_blocks": services_realtime_module.extract_text_from_anthropic_blocks,
        "_sanitize_chat_history": services_realtime_module.sanitize_chat_history,
        "_build_router_messages": services_realtime_module.build_router_messages,
        "_request_is_cacheable": bind_owner(services_realtime_module.request_is_cacheable),
        "_augment_system_with_history": services_realtime_module.augment_system_with_history,
        "_is_rate_limited_error": services_realtime_module.is_rate_limited_error,
        "_call_unified_inference": bind_owner(services_realtime_module.call_unified_inference),
        "_call_claude_with_tools": bind_owner(services_realtime_module.call_claude_with_tools),
        "_call_ollama_with_tools": bind_owner(services_realtime_module.call_ollama_with_tools),
        "_stream_chunks": services_realtime_module.stream_chunks,
        "_governance_summary_payload": bind_owner(services_instances_module.governance_summary_payload),
        "_workspace_connector_payload": bind_owner(services_instances_module.workspace_connector_payload),
        "_connector_inventory_payload": bind_owner(services_instances_module.connector_inventory_payload),
    }
