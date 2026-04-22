"""Typed runtime-facing contracts for readiness and health snapshots."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping


def _as_text(value: object, default: str = "") -> str:
    return str(value or default).strip()


def _as_dict(value: object) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _as_string_tuple(values: object) -> tuple[str, ...]:
    if not isinstance(values, (list, tuple, set)):
        return ()
    result: list[str] = []
    for item in values:
        text = str(item or "").strip()
        if text:
            result.append(text)
    return tuple(result)


@dataclass(slots=True)
class RuntimeCheckStatus:
    """One runtime component status row."""

    name: str
    state: str = "UNKNOWN"
    detail: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_mapping(cls, name: str, payload: Mapping[str, Any] | None) -> "RuntimeCheckStatus":
        data = _as_dict(payload)
        return cls(
            name=name,
            state=_as_text(data.get("state"), "UNKNOWN").upper(),
            detail=_as_text(data.get("detail")),
            metadata=data,
        )


@dataclass(slots=True)
class LocalRuntimeSnapshot:
    """Structured local runtime status shared by API and launcher seams."""

    state: str = "UNKNOWN"
    detail: str = ""
    backend: str = ""
    base_url: str = ""
    model: str = ""
    chat_model: str = ""
    chat_state: str = "UNKNOWN"
    chat_detail: str = ""
    chat_ready: bool = False
    available: bool = False
    available_roles: tuple[str, ...] = ()
    missing_roles: tuple[str, ...] = ()
    checked_at: float = 0.0
    expires_at: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_mapping(cls, payload: Mapping[str, Any] | None) -> "LocalRuntimeSnapshot":
        data = _as_dict(payload)
        return cls(
            state=_as_text(data.get("state"), "UNKNOWN").upper(),
            detail=_as_text(data.get("detail")),
            backend=_as_text(data.get("backend")).lower(),
            base_url=_as_text(data.get("base_url")),
            model=_as_text(data.get("model")),
            chat_model=_as_text(data.get("chat_model")),
            chat_state=_as_text(data.get("chat_state"), "UNKNOWN").upper(),
            chat_detail=_as_text(data.get("chat_detail")),
            chat_ready=bool(data.get("chat_ready", False)),
            available=bool(data.get("available", False)),
            available_roles=_as_string_tuple(data.get("available_roles")),
            missing_roles=_as_string_tuple(data.get("missing_roles")),
            checked_at=float(data.get("checked_at", 0.0) or 0.0),
            expires_at=float(data.get("expires_at", 0.0) or 0.0),
            metadata=data,
        )


@dataclass(slots=True)
class StartupReadinessSnapshot:
    """Typed startup readiness payload."""

    overall: str = "UNKNOWN"
    auth: RuntimeCheckStatus = field(default_factory=lambda: RuntimeCheckStatus(name="auth"))
    ollama: RuntimeCheckStatus = field(default_factory=lambda: RuntimeCheckStatus(name="ollama"))
    local_runtime: LocalRuntimeSnapshot = field(default_factory=LocalRuntimeSnapshot)
    voice: RuntimeCheckStatus = field(default_factory=lambda: RuntimeCheckStatus(name="voice"))
    daemon: RuntimeCheckStatus = field(default_factory=lambda: RuntimeCheckStatus(name="daemon"))
    memory: RuntimeCheckStatus = field(default_factory=lambda: RuntimeCheckStatus(name="memory"))
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_mapping(cls, payload: Mapping[str, Any] | None) -> "StartupReadinessSnapshot":
        data = _as_dict(payload)
        checks = _as_dict(data.get("checks"))
        return cls(
            overall=_as_text(data.get("overall"), "UNKNOWN").upper(),
            auth=RuntimeCheckStatus.from_mapping("auth", checks.get("auth")),
            ollama=RuntimeCheckStatus.from_mapping("ollama", checks.get("ollama")),
            local_runtime=LocalRuntimeSnapshot.from_mapping(checks.get("local_runtime")),
            voice=RuntimeCheckStatus.from_mapping("voice", checks.get("voice")),
            daemon=RuntimeCheckStatus.from_mapping("daemon", checks.get("daemon")),
            memory=RuntimeCheckStatus.from_mapping("memory", checks.get("memory")),
            metadata=data,
        )


@dataclass(slots=True)
class RuntimeHealthSnapshot:
    """Top-level runtime health payload for launcher/API seams."""

    overall: str = "UNKNOWN"
    startup_readiness: StartupReadinessSnapshot = field(default_factory=StartupReadinessSnapshot)
    local_runtime: LocalRuntimeSnapshot = field(default_factory=LocalRuntimeSnapshot)
    resource_envelope: dict[str, Any] = field(default_factory=dict)
    voice_status: dict[str, Any] = field(default_factory=dict)
    voice_tts_backend: str = ""
    voice_stt_backend: str = ""
    daemon_available: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_mapping(cls, payload: Mapping[str, Any] | None) -> "RuntimeHealthSnapshot":
        data = _as_dict(payload)
        startup = StartupReadinessSnapshot.from_mapping(data.get("startup_readiness"))
        local_runtime = LocalRuntimeSnapshot.from_mapping(data.get("local_runtime"))
        overall = startup.overall if startup.overall != "UNKNOWN" else local_runtime.state
        return cls(
            overall=overall,
            startup_readiness=startup,
            local_runtime=local_runtime,
            resource_envelope=_as_dict(data.get("resource_envelope")),
            voice_status=_as_dict(data.get("voice_status")),
            voice_tts_backend=_as_text(data.get("voice_tts_backend")),
            voice_stt_backend=_as_text(data.get("voice_stt_backend")),
            daemon_available=bool(data.get("daemon_available", False)),
            metadata=data,
        )
