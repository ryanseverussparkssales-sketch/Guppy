from __future__ import annotations

from pathlib import Path
from typing import Any

from src.guppy.api.server_paths import ServerPathConfig


def apply_path_config(owner: Any, path_config: ServerPathConfig) -> ServerPathConfig:
    owner._path_config = path_config
    owner._runtime_dir = path_config.runtime_dir
    owner._config_dir = path_config.config_dir
    owner._instances_path = path_config.instances_path
    owner._connector_bindings_path = path_config.connector_bindings_path
    owner._instance_state_path = path_config.instance_state_path
    owner._REPAIR_TOKEN_FILE = path_config.repair_token_file
    owner._ops_telemetry_db = path_config.ops_telemetry_db
    owner._stream_jsonl_map = dict(path_config.stream_jsonl_map)
    if hasattr(owner, "_server_context"):
        owner._server_context.paths = path_config
    return path_config


def set_path_config_for_tests(
    owner: Any,
    *,
    config_dir: Path | None = None,
    runtime_dir: Path | None = None,
    instances_path: Path | None = None,
    connector_bindings_path: Path | None = None,
    instance_state_path: Path | None = None,
    repair_token_file: Path | None = None,
    ops_telemetry_db: Path | None = None,
) -> ServerPathConfig:
    current = owner._path_config
    next_root_config = ServerPathConfig.from_roots(
        Path(config_dir) if config_dir is not None else current.config_dir,
        Path(runtime_dir) if runtime_dir is not None else current.runtime_dir,
    )
    next_config = next_root_config.clone_with(
        instances_path=instances_path if instances_path is not None else next_root_config.instances_path,
        connector_bindings_path=connector_bindings_path
        if connector_bindings_path is not None
        else next_root_config.connector_bindings_path,
        instance_state_path=instance_state_path
        if instance_state_path is not None
        else next_root_config.instance_state_path,
        repair_token_file=repair_token_file
        if repair_token_file is not None
        else next_root_config.repair_token_file,
        ops_telemetry_db=ops_telemetry_db
        if ops_telemetry_db is not None
        else next_root_config.ops_telemetry_db,
    )
    return apply_path_config(owner, next_config)
