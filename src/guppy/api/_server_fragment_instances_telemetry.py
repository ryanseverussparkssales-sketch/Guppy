from src.guppy.api.instance_config_support import (
    default_instance_state as _support_default_instance_state,
    ensure_instance_scaffold as _support_ensure_instance_scaffold,
    get_active_instance_context as _support_get_active_instance_context,
    get_instance_entry as _support_get_instance_entry,
    instance_config_entry as _support_instance_config_entry,
    instance_names as _support_instance_names,
    load_instance_state as _support_load_instance_state,
    load_instances_config as _support_load_instances_config,
    load_normalized_instance_bundle as _support_load_normalized_instance_bundle,
    save_instance_state as _support_save_instance_state,
    save_instances_config as _support_save_instances_config,
)


def _ensure_m2_instance_scaffold() -> None:
    _support_ensure_instance_scaffold(
        config_dir=_config_dir,
        runtime_dir=_runtime_dir,
        instances_path=_instances_path,
        instance_state_path=_instance_state_path,
    )


def _load_instances_config() -> dict[str, Any]:
    return _support_load_instances_config(
        ensure_scaffold=_ensure_m2_instance_scaffold,
        instances_path=_instances_path,
    )


def _load_instance_state(config: Optional[dict[str, Any]] = None) -> dict[str, Any]:
    return _support_load_instance_state(
        ensure_scaffold=_ensure_m2_instance_scaffold,
        instance_state_path=_instance_state_path,
        config=config,
    )


def _save_instance_state(state: dict[str, Any]) -> None:
    _support_save_instance_state(
        state,
        instance_state_path=_instance_state_path,
        atomic_json_io=_ATOMIC_JSON_IO,
        write_json_atomic=write_json_atomic,
    )


def _save_instances_config(config: dict[str, Any]) -> None:
    _support_save_instances_config(
        config,
        instances_path=_instances_path,
        atomic_json_io=_ATOMIC_JSON_IO,
        write_json_atomic=write_json_atomic,
    )


def _load_normalized_instance_bundle(*, persist_repairs: bool = False) -> tuple[dict[str, Any], dict[str, Any], list[str], list[str]]:
    return _support_load_normalized_instance_bundle(
        persist_repairs=persist_repairs,
        load_instances_config_fn=_load_instances_config,
        normalize_instances_config_fn=_normalize_instances_config,
        save_instances_config_fn=_save_instances_config,
        load_instance_state_fn=_load_instance_state,
        normalize_instance_state_fn=_normalize_instance_state,
        instance_names_fn=_instance_names,
        save_instance_state_fn=_save_instance_state,
    )


def _instance_config_entry(
    *,
    name: str,
    description: str = "",
    mode: str = "auto",
    persona: str = "guppy",
    voice: str = "default",
    enabled: bool = True,
    instance_type: str = "user_instance",
    created_at: str | None = None,
) -> dict[str, Any]:
    return _support_instance_config_entry(
        name=name,
        description=description,
        mode=mode,
        persona=persona,
        voice=voice,
        enabled=enabled,
        instance_type=instance_type,
        created_at=created_at,
    )


def _default_instance_state(mode: str = "auto") -> dict[str, Any]:
    return _support_default_instance_state(mode)


def _instance_names(config: dict[str, Any]) -> list[str]:
    return _support_instance_names(config)


def _get_instance_entry(config: dict[str, Any], name: str) -> dict[str, Any] | None:
    return _support_get_instance_entry(config, name)


def _get_active_instance_context() -> tuple[str | None, str | None, str | None, str | None]:
    return _support_get_active_instance_context(
        load_normalized_instance_bundle_fn=_load_normalized_instance_bundle,
        get_instance_entry_fn=_get_instance_entry,
    )


def _coerce_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except Exception:
        return default


def _normalize_instances_config(raw: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    warnings: list[str] = []
    version = max(1, _coerce_int(raw.get("version", 1), 1))
    raw_instances = raw.get("instances")
    if not isinstance(raw_instances, list):
        warnings.append("instances must be a list; using default instance set")
        raw_instances = []

    seen: set[str] = set()
    items: list[dict[str, Any]] = []
    for idx, entry in enumerate(raw_instances):
        if not isinstance(entry, dict):
            warnings.append(f"instances[{idx}] ignored: expected object")
            continue
        name = str(entry.get("name", "")).strip()
        if not name:
            warnings.append(f"instances[{idx}] ignored: missing name")
            continue
        if name in seen:
            warnings.append(f"instances[{idx}] ignored: duplicate name '{name}'")
            continue
        seen.add(name)
        items.append(
            _instance_config_entry(
                name=name,
                description=str(entry.get("description", "")).strip(),
                mode=str(entry.get("mode", "auto") or "auto").strip().lower() or "auto",
                persona=str(entry.get("persona", "guppy") or "guppy").strip() or "guppy",
                voice=str(entry.get("voice", "default") or "default").strip() or "default",
                enabled=bool(entry.get("enabled", True)),
                instance_type=str(entry.get("type", "user_instance") or "user_instance").strip() or "user_instance",
                created_at=str(entry.get("created_at", "")).strip() or None,
            )
        )

    if not items:
        warnings.append("no valid instance entries found; restored default primary instance")
        items = [
            _instance_config_entry(
                name="guppy-primary",
                description="Primary foreground assistant instance",
                mode="auto",
                persona="guppy",
                voice="default",
                enabled=True,
                instance_type="user_instance",
            )
        ]

    configured_active = str(raw.get("active_instance", "")).strip()
    valid_names = [item["name"] for item in items]
    active_instance = configured_active if configured_active in valid_names else valid_names[0]
    if configured_active and configured_active not in valid_names:
        warnings.append(f"active_instance '{configured_active}' not found; using '{active_instance}'")
    elif not configured_active:
        warnings.append(f"active_instance missing; using '{active_instance}'")

    return {
        "version": version,
        "active_instance": active_instance,
        "instances": items,
    }, warnings


def _normalize_instance_state(
    raw: dict[str, Any],
    *,
    valid_names: list[str],
    active_instance: str,
) -> tuple[dict[str, Any], list[str]]:
    warnings: list[str] = []
    raw_instances = raw.get("instances")
    if not isinstance(raw_instances, dict):
        warnings.append("state.instances must be an object; rebuilding instance runtime state")
        raw_instances = {}

    normalized_instances: dict[str, dict[str, Any]] = {}
    for key in raw_instances.keys():
        if key not in valid_names:
            warnings.append(f"state instance '{key}' ignored: not present in config")

    allowed_status = {"idle", "busy", "error", "starting", "active", "running"}
    for name in valid_names:
        entry = raw_instances.get(name, {})
        if not isinstance(entry, dict):
            warnings.append(f"state for '{name}' invalid; resetting to defaults")
            entry = {}

        status = str(entry.get("status", "idle") or "idle").strip().lower()
        if status not in allowed_status:
            warnings.append(f"state for '{name}' had invalid status '{status}'; using 'idle'")
            status = "idle"

        message_count = max(0, _coerce_int(entry.get("message_count", 0), 0))
        normalized_instances[name] = {
            "status": status,
            "last_message": str(entry.get("last_message", "") or ""),
            "last_updated": entry.get("last_updated"),
            "message_count": message_count,
            "model_currently_using": str(entry.get("model_currently_using", "") or ""),
        }

    active = active_instance if active_instance in valid_names else (valid_names[0] if valid_names else "guppy-primary")
    active_slots = 0
    for name, item in normalized_instances.items():
        if name == active:
            item["status"] = "active"
            active_slots += 1
            continue
        if item.get("status") in {"active", "running", "busy"}:
            if active_slots < 2:
                if item.get("status") == "active":
                    item["status"] = "running"
                active_slots += 1
            else:
                item["status"] = "idle"
    return {
        "version": 1,
        "active_instance": active,
        "instances": normalized_instances,
    }, warnings


def _upsert_instance_config(
    config: dict[str, Any],
    payload: InstanceConfigRequest,
) -> tuple[dict[str, Any], str]:
    items = list(config.get("instances", [])) if isinstance(config.get("instances"), list) else []
    target = (payload.name or "").strip()
    if not target:
        raise HTTPException(status_code=400, detail="instance name is required")

    existing_idx = -1
    existing_created_at = None
    for idx, item in enumerate(items):
        if isinstance(item, dict) and str(item.get("name", "")).strip() == target:
            existing_idx = idx
            existing_created_at = str(item.get("created_at", "")).strip() or None
            break

    if existing_idx < 0 and len(items) >= 5:
        raise HTTPException(status_code=409, detail="instance limit reached (max 5 configured)")

    entry = _instance_config_entry(
        name=target,
        description=(payload.description or "").strip(),
        mode=(payload.mode or "auto").strip().lower() or "auto",
        persona=(payload.persona or "guppy").strip() or "guppy",
        voice=(payload.voice or "default").strip() or "default",
        enabled=bool(payload.enabled),
        instance_type=(payload.type or "user_instance").strip() or "user_instance",
        created_at=existing_created_at,
    )
    action = "updated" if existing_idx >= 0 else "created"
    if existing_idx >= 0:
        items[existing_idx] = entry
    else:
        items.append(entry)
    config["instances"] = items
    if str(config.get("active_instance", "")).strip() not in _instance_names(config):
        config["active_instance"] = target
    return config, action


def _activate_instance_state(state: dict[str, Any], target: str) -> dict[str, Any]:
    instances = state.get("instances", {}) if isinstance(state.get("instances"), dict) else {}
    current_active = str(state.get("active_instance", "")).strip()
    if current_active and current_active in instances and current_active != target:
        previous = instances.get(current_active)
        if isinstance(previous, dict) and previous.get("status") != "busy":
            previous["status"] = "idle"
    target_entry = instances.get(target)
    if isinstance(target_entry, dict):
        target_entry["status"] = "active"
        target_entry["last_updated"] = datetime.now(timezone.utc).isoformat()
    state["active_instance"] = target
    return state


def _instance_limits_payload(config: dict[str, Any], state: dict[str, Any]) -> dict[str, int]:
    config_items = config.get("instances", []) if isinstance(config.get("instances"), list) else []
    configured = len([item for item in config_items if isinstance(item, dict) and str(item.get("name", "")).strip()])
    runtime_items = state.get("instances", {}) if isinstance(state.get("instances"), dict) else {}
    active_runtime = 0
    for item in runtime_items.values():
        if not isinstance(item, dict):
            continue
        status = str(item.get("status", "idle") or "idle").strip().lower()
        if status in {"active", "running", "busy"}:
            active_runtime += 1
    return {
        "configured": configured,
        "max_configured": 5,
        "active_runtime": active_runtime,
        "max_active_runtime": 2,
    }


def _emit_integration_heartbeat(reason: str) -> None:
    global _last_integration_heartbeat_ts
    now = time.time()
    with _integration_heartbeat_lock:
        if now - _last_integration_heartbeat_ts < max(60.0, _INTEGRATION_HEARTBEAT_SECONDS):
            return
        _last_integration_heartbeat_ts = now

    path = _stream_jsonl_map["integration_events"]
    record = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "ts": datetime.now(timezone.utc).isoformat(),
        "event_type": "integration_heartbeat",
        "event": "integration_heartbeat",
        "level": "info",
        "payload": {
            "state": "idle",
            "reason": reason,
        },
    }
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        rotate_jsonl_file(path)
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=True) + "\n")
    except Exception:
        return


def _read_resource_envelope_status() -> dict[str, Any]:
    path = _runtime_dir / "resource_envelope.status.json"
    if not path.exists():
        return {
            "state": "unknown",
            "message": "resource envelope status not available",
        }
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            return data
    except Exception:
        pass
    return {
        "state": "unknown",
        "message": "resource envelope status unreadable",
    }


def _parse_iso_ts(ts_value: Any) -> datetime | None:
    if not ts_value:
        return None
    try:
        txt = str(ts_value).replace("Z", "+00:00")
        dt = datetime.fromisoformat(txt)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        return None


def _p95(values: list[float]) -> float:
    if not values:
        return 0.0
    vals = sorted(float(v) for v in values)
    idx = max(0, int(len(vals) * 0.95) - 1)
    return vals[idx]


def _query_sqlite_telemetry(
    stream: str | None,
    event: str | None,
    level: str | None,
    since_minutes: int | None,
    limit: int,
) -> list[dict[str, Any]]:
    if not _ops_telemetry_db.exists():
        return []

    where = []
    params: list[Any] = []
    if stream:
        where.append("stream = ?")
        params.append(stream)
    if event:
        where.append("event = ?")
        params.append(event)
    if level:
        where.append("level = ?")
        params.append(level)
    if since_minutes is not None and since_minutes >= 0:
        cutoff = datetime.now(timezone.utc).timestamp() - (int(since_minutes) * 60)
        where.append("strftime('%s', ts) >= ?")
        params.append(cutoff)

    query = "SELECT ts, stream, event, level, payload_json FROM operational_events"
    if where:
        query += " WHERE " + " AND ".join(where)
    query += " ORDER BY id DESC LIMIT ?"
    params.append(limit)

    out: list[dict[str, Any]] = []
    try:
        from utils.db_utils import open_db as _open_db
        conn = _open_db(
            _ops_telemetry_db,
            timeout=_SQLITE_TIMEOUT_SECONDS,
            busy_timeout_ms=_SQLITE_BUSY_TIMEOUT_MS,
        )
        try:
            rows = conn.execute(query, params).fetchall()
        finally:
            conn.close()
    except Exception:
        return []

    for ts, stream_name, event_name, lvl, payload_json in reversed(rows):
        payload: dict[str, Any] | Any
        try:
            payload = json.loads(payload_json)
        except Exception:
            payload = {"raw": str(payload_json), "parse_error": True}
        out.append({
            "ts": ts,
            "stream": stream_name,
            "event": event_name,
            "level": lvl,
            "payload": payload,
        })
    return out


def _query_jsonl_telemetry(
    stream: str | None,
    event: str | None,
    level: str | None,
    since_minutes: int | None,
    limit: int,
) -> list[dict[str, Any]]:
    requested_streams = [stream] if stream else list(_stream_jsonl_map.keys())
    cutoff = None
    if since_minutes is not None and since_minutes >= 0:
        cutoff = datetime.now(timezone.utc).timestamp() - (int(since_minutes) * 60)

    events: list[dict[str, Any]] = []
    for stream_name in requested_streams:
        path = _stream_jsonl_map.get(stream_name)
        if path is None:
            continue
        for row in _read_jsonl_tail(path, limit=max(limit * 3, 120)):
            evt_name = str(row.get("event", row.get("event_type", ""))).strip()
            evt_level = str(row.get("level", "")).strip().lower() or "info"
            ts_txt = row.get("ts", row.get("timestamp"))
            ts_obj = _parse_iso_ts(ts_txt)
            if cutoff is not None:
                if ts_obj is None or ts_obj.timestamp() < cutoff:
                    continue
            if event and evt_name != event:
                continue
            if level and evt_level != level:
                continue
            events.append({
                "ts": ts_txt,
                "stream": stream_name,
                "event": evt_name or "event",
                "level": evt_level,
                "payload": row,
            })

    events.sort(key=lambda item: _parse_iso_ts(item.get("ts")) or datetime.min.replace(tzinfo=timezone.utc))
    if len(events) > limit:
        events = events[-limit:]
    return events


def _build_telemetry_report(events: list[dict[str, Any]]) -> dict[str, Any]:
    stream_counts = Counter()
    event_counts = Counter()
    level_counts = Counter()
    latencies: list[float] = []
    slow_count = 0

    for item in events:
        stream_counts[str(item.get("stream", "unknown"))] += 1
        event_counts[str(item.get("event", "event"))] += 1
        level_counts[str(item.get("level", "info"))] += 1

        payload = item.get("payload")
        if isinstance(payload, dict):
            raw_latency = payload.get("latency_ms", payload.get("elapsed_ms"))
            if isinstance(raw_latency, (int, float)):
                lat = float(raw_latency)
                latencies.append(lat)
                if lat >= SLOW_REQUEST_MS:
                    slow_count += 1

    latest_ts = None
    if events:
        latest_ts = events[-1].get("ts")

    return {
        "count": len(events),
        "latest_ts": latest_ts,
        "streams": dict(stream_counts),
        "events": dict(event_counts.most_common(20)),
        "levels": dict(level_counts),
        "latency": {
            "samples": len(latencies),
            "avg_ms": round(sum(latencies) / len(latencies), 2) if latencies else 0.0,
            "p95_ms": round(_p95(latencies), 2) if latencies else 0.0,
            "slow_count": slow_count,
            "slow_threshold_ms": SLOW_REQUEST_MS,
        },
    }


