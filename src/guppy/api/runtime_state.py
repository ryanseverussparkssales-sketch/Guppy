from __future__ import annotations

import threading
from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class ServerRuntimeState:
    started_at: str
    status_cache: dict[str, Any] = field(
        default_factory=lambda: {"expires_at": 0.0, "payload": None}
    )
    startup_check_cache: dict[str, Any] = field(
        default_factory=lambda: {"expires_at": 0.0, "payload": None}
    )
    startup_check_cache_lock: Any = field(default_factory=threading.Lock)
    startup_check_refresh_inflight: bool = False
    local_runtime_warm_cache: dict[str, Any] = field(
        default_factory=lambda: {
            "backend": "",
            "model": "",
            "checked_at": 0.0,
            "expires_at": 0.0,
            "chat_ready": False,
            "chat_state": "UNKNOWN",
            "chat_detail": "local runtime warmup not checked yet",
        }
    )
    local_runtime_warm_lock: Any = field(default_factory=threading.Lock)
    local_runtime_warm_refresh_inflight: bool = False
    api_metrics_lock: Any = field(default_factory=threading.Lock)
    api_metrics: dict[str, Any] = field(default_factory=dict)
    last_integration_heartbeat_ts: float = 0.0
    integration_heartbeat_lock: Any = field(default_factory=threading.Lock)
    repair_token: str = ""
    daemon_runtime: dict[str, Any] = field(
        default_factory=lambda: {
            "state": "UNKNOWN",
            "detail": "daemon runtime not checked yet",
            "available": False,
            "owns_daemon": False,
            "running": False,
            "last_changed_at": "",
        }
    )

    def __post_init__(self) -> None:
        if not self.api_metrics:
            self.api_metrics = {
                "started_at": self.started_at,
                "requests_total": 0,
                "errors_total": 0,
                "slow_requests": 0,
                "latency_total_ms": 0.0,
                "path_counts": {},
                "status_counts": {},
            }
