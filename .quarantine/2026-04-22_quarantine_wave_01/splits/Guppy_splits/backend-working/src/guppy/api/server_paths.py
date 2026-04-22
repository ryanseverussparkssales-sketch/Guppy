from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(slots=True)
class ServerPathConfig:
    config_dir: Path
    runtime_dir: Path
    instances_path: Path
    connector_bindings_path: Path
    instance_state_path: Path
    repair_token_file: Path
    ops_telemetry_db: Path
    stream_jsonl_map: dict[str, Path]

    @classmethod
    def from_roots(cls, config_dir: Path, runtime_dir: Path) -> "ServerPathConfig":
        return cls(
            config_dir=Path(config_dir),
            runtime_dir=Path(runtime_dir),
            instances_path=Path(config_dir) / "instances.json",
            connector_bindings_path=Path(config_dir) / "connector_bindings.json",
            instance_state_path=Path(runtime_dir) / "instance_state.json",
            repair_token_file=Path(runtime_dir) / "repair_token.txt",
            ops_telemetry_db=Path(runtime_dir) / "ops_telemetry.sqlite3",
            stream_jsonl_map={
                "session_events": Path(runtime_dir) / "session_events.jsonl",
                "router_scorecard": Path(runtime_dir) / "router_scorecard.jsonl",
                "agent_performance": Path(runtime_dir) / "agent_performance.jsonl",
                "integration_events": Path(runtime_dir) / "integration_events.jsonl",
                "reminder_events": Path(runtime_dir) / "reminder_events.jsonl",
            },
        )

    def clone_with(
        self,
        *,
        config_dir: Path | None = None,
        runtime_dir: Path | None = None,
        instances_path: Path | None = None,
        connector_bindings_path: Path | None = None,
        instance_state_path: Path | None = None,
        repair_token_file: Path | None = None,
        ops_telemetry_db: Path | None = None,
        stream_jsonl_map: dict[str, Path] | None = None,
    ) -> "ServerPathConfig":
        return ServerPathConfig(
            config_dir=Path(config_dir) if config_dir is not None else self.config_dir,
            runtime_dir=Path(runtime_dir) if runtime_dir is not None else self.runtime_dir,
            instances_path=Path(instances_path) if instances_path is not None else self.instances_path,
            connector_bindings_path=Path(connector_bindings_path)
            if connector_bindings_path is not None
            else self.connector_bindings_path,
            instance_state_path=Path(instance_state_path)
            if instance_state_path is not None
            else self.instance_state_path,
            repair_token_file=Path(repair_token_file)
            if repair_token_file is not None
            else self.repair_token_file,
            ops_telemetry_db=Path(ops_telemetry_db)
            if ops_telemetry_db is not None
            else self.ops_telemetry_db,
            stream_jsonl_map=dict(stream_jsonl_map) if stream_jsonl_map is not None else dict(self.stream_jsonl_map),
        )
