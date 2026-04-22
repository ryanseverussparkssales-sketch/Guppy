from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Optional


def ensure_instance_scaffold(
    *,
    config_dir: Path,
    runtime_dir: Path,
    instances_path: Path,
    instance_state_path: Path,
) -> None:
    config_dir.mkdir(parents=True, exist_ok=True)
    runtime_dir.mkdir(parents=True, exist_ok=True)

    if not instances_path.exists():
        instances_path.write_text(
            json.dumps(
                {
                    "version": 1,
                    "active_instance": "guppy-primary",
                    "instances": [
                        instance_config_entry(
                            name="guppy-primary",
                            description="Primary foreground assistant instance",
                            mode="auto",
                            persona="guppy",
                            voice="default",
                            enabled=True,
                            instance_type="user_instance",
                        ),
                        instance_config_entry(
                            name="builder-collab",
                            description="Background collaborator instance",
                            mode="teaching",
                            persona="guppy",
                            voice="default",
                            enabled=False,
                            instance_type="builder_instance",
                        ),
                    ],
                },
                indent=2,
            ),
            encoding="utf-8",
        )

    if not instance_state_path.exists():
        instance_state_path.write_text(
            json.dumps(
                {
                    "version": 1,
                    "active_instance": "guppy-primary",
                    "instances": {
                        "guppy-primary": default_instance_state("auto"),
                        "builder-collab": default_instance_state("teaching"),
                    },
                },
                indent=2,
            ),
            encoding="utf-8",
        )


def load_instances_config(*, ensure_scaffold: Callable[[], None], instances_path: Path) -> dict[str, Any]:
    ensure_scaffold()
    try:
        data = json.loads(instances_path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def load_instance_state(
    *,
    ensure_scaffold: Callable[[], None],
    instance_state_path: Path,
    config: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    del config
    ensure_scaffold()
    try:
        data = json.loads(instance_state_path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def save_instance_state(
    state: dict[str, Any],
    *,
    instance_state_path: Path,
    atomic_json_io: bool,
    write_json_atomic: Callable[[Path, dict[str, Any]], bool],
) -> None:
    instance_state_path.parent.mkdir(parents=True, exist_ok=True)
    if atomic_json_io:
        if not write_json_atomic(instance_state_path, state):
            raise OSError(f"Failed to write instance state atomically: {instance_state_path}")
    else:
        instance_state_path.write_text(json.dumps(state, indent=2), encoding="utf-8")


def save_instances_config(
    config: dict[str, Any],
    *,
    instances_path: Path,
    atomic_json_io: bool,
    write_json_atomic: Callable[[Path, dict[str, Any]], bool],
) -> None:
    instances_path.parent.mkdir(parents=True, exist_ok=True)
    if atomic_json_io:
        if not write_json_atomic(instances_path, config):
            raise OSError(f"Failed to write instances config atomically: {instances_path}")
    else:
        instances_path.write_text(json.dumps(config, indent=2), encoding="utf-8")


def load_normalized_instance_bundle(
    *,
    persist_repairs: bool,
    load_instances_config_fn: Callable[[], dict[str, Any]],
    normalize_instances_config_fn: Callable[[dict[str, Any]], tuple[dict[str, Any], list[str]]],
    save_instances_config_fn: Callable[[dict[str, Any]], None],
    load_instance_state_fn: Callable[[Optional[dict[str, Any]]], dict[str, Any]],
    normalize_instance_state_fn: Callable[..., tuple[dict[str, Any], list[str]]],
    instance_names_fn: Callable[[dict[str, Any]], list[str]],
    save_instance_state_fn: Callable[[dict[str, Any]], None],
) -> tuple[dict[str, Any], dict[str, Any], list[str], list[str]]:
    raw_config = load_instances_config_fn()
    config, config_warnings = normalize_instances_config_fn(raw_config)
    if persist_repairs and raw_config != config:
        save_instances_config_fn(config)
        config_warnings = list(config_warnings) + ["persisted normalized instances config"]

    raw_state = load_instance_state_fn(config)
    state, state_warnings = normalize_instance_state_fn(
        raw_state,
        valid_names=instance_names_fn(config),
        active_instance=str(config.get("active_instance", "guppy-primary")),
    )
    if persist_repairs and raw_state != state:
        save_instance_state_fn(state)
        state_warnings = list(state_warnings) + ["persisted normalized instance runtime state"]

    return config, state, config_warnings, state_warnings


def instance_config_entry(
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
    return {
        "name": name,
        "description": description,
        "mode": mode,
        "persona": persona,
        "voice": voice,
        "enabled": enabled,
        "type": instance_type,
        "created_at": created_at or datetime.now(timezone.utc).isoformat(),
    }


def default_instance_state(mode: str = "auto") -> dict[str, Any]:
    return {
        "status": "idle",
        "last_message": "",
        "last_updated": None,
        "message_count": 0,
        "model_currently_using": mode,
    }


def instance_names(config: dict[str, Any]) -> list[str]:
    names: list[str] = []
    for item in config.get("instances", []):
        if isinstance(item, dict):
            name = str(item.get("name", "")).strip()
            if name:
                names.append(name)
    return names


def get_instance_entry(config: dict[str, Any], name: str) -> dict[str, Any] | None:
    target = str(name or "").strip()
    for item in config.get("instances", []):
        if isinstance(item, dict) and str(item.get("name", "")).strip() == target:
            return item
    return None


def get_active_instance_context(
    *,
    load_normalized_instance_bundle_fn: Callable[..., tuple[dict[str, Any], dict[str, Any], list[str], list[str]]],
    get_instance_entry_fn: Callable[[dict[str, Any], str], dict[str, Any] | None],
) -> tuple[str | None, str | None, str | None, str | None]:
    config, _state, _warnings, _state_warnings = load_normalized_instance_bundle_fn(persist_repairs=True)
    active_name = str(config.get("active_instance", "")).strip()
    entry = get_instance_entry_fn(config, active_name)
    instance_type = str((entry or {}).get("type", "user_instance") or "user_instance").strip() or "user_instance"
    persona = str((entry or {}).get("persona", "guppy") or "guppy").strip() or "guppy"
    voice = str((entry or {}).get("voice", "default") or "default").strip() or "default"
    return (active_name or None, instance_type, persona, voice)
