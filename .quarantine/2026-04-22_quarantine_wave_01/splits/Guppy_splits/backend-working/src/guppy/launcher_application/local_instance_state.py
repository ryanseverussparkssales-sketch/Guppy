from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from utils.safe_io import read_json_dict, write_json_atomic


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not write_json_atomic(path, payload):
        raise OSError(f"Atomic write failed for {path}")


def default_instance_runtime_state(mode: str = "auto") -> dict[str, object]:
    return {
        "status": "idle",
        "last_message": "",
        "last_updated": None,
        "message_count": 0,
        "model_currently_using": str(mode or "auto").strip().lower() or "auto",
    }


def local_upsert_instance(config_path: Path, state_path: Path, payload: dict) -> str:
    target = str(payload.get("name", "")).strip()
    if not target:
        raise ValueError("instance name is required")
    config = read_json_dict(config_path)
    if not isinstance(config, dict):
        config = {"version": 1, "active_instance": "guppy-primary", "instances": []}
    items = list(config.get("instances", [])) if isinstance(config.get("instances"), list) else []
    existing_idx = -1
    existing_created_at = None
    for idx, item in enumerate(items):
        if not isinstance(item, dict):
            continue
        if str(item.get("name", "")).strip() == target:
            existing_idx = idx
            existing_created_at = str(item.get("created_at", "")).strip() or None
            break
    configured_count = len([item for item in items if isinstance(item, dict) and str(item.get("name", "")).strip()])
    if existing_idx < 0 and configured_count >= 5:
        raise RuntimeError("instance limit reached (max 5 configured)")
    mode = str(payload.get("mode", "auto") or "auto").strip().lower() or "auto"
    entry = {
        "name": target,
        "description": str(payload.get("description", "") or "").strip(),
        "mode": mode,
        "persona": str(payload.get("persona", "guppy") or "guppy").strip() or "guppy",
        "voice": str(payload.get("voice", "default") or "default").strip() or "default",
        "enabled": bool(payload.get("enabled", True)),
        "type": str(payload.get("type", "user_instance") or "user_instance").strip() or "user_instance",
        "created_at": existing_created_at or datetime.now(timezone.utc).isoformat(),
    }
    action = "updated" if existing_idx >= 0 else "created"
    if existing_idx >= 0:
        items[existing_idx] = entry
    else:
        items.append(entry)
    config["version"] = int(config.get("version", 1) or 1)
    config["instances"] = items
    config["active_instance"] = target

    state = read_json_dict(state_path)
    if not isinstance(state, dict):
        state = {"version": 1, "active_instance": "guppy-primary", "instances": {}}
    state_items = state.get("instances", {}) if isinstance(state.get("instances"), dict) else {}
    for key, item in state_items.items():
        if not isinstance(item, dict):
            continue
        if key != target and item.get("status") != "busy":
            item["status"] = "idle"
    runtime_state = state_items.get(target, {})
    if not isinstance(runtime_state, dict):
        runtime_state = {}
    merged_state = default_instance_runtime_state(mode)
    merged_state.update(runtime_state)
    merged_state["status"] = "active"
    merged_state["model_currently_using"] = mode
    merged_state["last_updated"] = datetime.now(timezone.utc).isoformat()
    state_items[target] = merged_state
    state["version"] = int(state.get("version", 1) or 1)
    state["active_instance"] = target
    state["instances"] = state_items

    _write_json(config_path, config)
    _write_json(state_path, state)
    return action


def local_delete_instance(config_path: Path, state_path: Path, name: str) -> str:
    target = str(name or "").strip()
    if not target:
        raise ValueError("instance name is required")
    config = read_json_dict(config_path)
    if not isinstance(config, dict):
        config = {"version": 1, "active_instance": "guppy-primary", "instances": []}
    items = list(config.get("instances", [])) if isinstance(config.get("instances"), list) else []
    kept_items: list[dict[str, object]] = []
    removed = False
    for item in items:
        if not isinstance(item, dict):
            continue
        if str(item.get("name", "")).strip() == target:
            removed = True
            continue
        kept_items.append(item)
    if not removed:
        raise RuntimeError(f"workspace not found: {target}")
    if not kept_items:
        kept_items = [
            {
                "name": "guppy-primary",
                "description": "Primary foreground assistant instance",
                "mode": "auto",
                "persona": "guppy",
                "voice": "default",
                "enabled": True,
                "type": "user_instance",
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
        ]
    active_names = [str(item.get("name", "")).strip() for item in kept_items if isinstance(item, dict)]
    new_active = str(config.get("active_instance", "")).strip()
    if new_active == target or new_active not in active_names:
        new_active = active_names[0] if active_names else "guppy-primary"
    config["version"] = int(config.get("version", 1) or 1)
    config["instances"] = kept_items
    config["active_instance"] = new_active

    state = read_json_dict(state_path)
    if not isinstance(state, dict):
        state = {"version": 1, "active_instance": new_active, "instances": {}}
    state_items = state.get("instances", {}) if isinstance(state.get("instances"), dict) else {}
    state_items.pop(target, None)
    for key, item in state_items.items():
        if not isinstance(item, dict):
            continue
        if key == new_active:
            item["status"] = "active"
            item["last_updated"] = datetime.now(timezone.utc).isoformat()
        elif item.get("status") != "busy":
            item["status"] = "idle"
    if new_active not in state_items:
        active_entry = next((item for item in kept_items if str(item.get("name", "")).strip() == new_active), {})
        mode = str(active_entry.get("mode", "auto") or "auto").strip().lower() or "auto"
        fallback_state = default_instance_runtime_state(mode)
        fallback_state["status"] = "active"
        fallback_state["last_updated"] = datetime.now(timezone.utc).isoformat()
        state_items[new_active] = fallback_state
    state["version"] = int(state.get("version", 1) or 1)
    state["active_instance"] = new_active
    state["instances"] = state_items

    _write_json(config_path, config)
    _write_json(state_path, state)
    return new_active
