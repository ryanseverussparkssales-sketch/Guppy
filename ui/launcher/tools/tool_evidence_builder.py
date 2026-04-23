"""
tool_evidence_builder.py

Lane: TR54-C5
Responsibilities:
  - Evidence source classification
  - EvidenceRecord collection from worker health and logs
  - No status label without backing evidence
  - All timestamps ISO 8601, timezone-aware
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

logger = logging.getLogger("launcher.tools.evidence")


class EvidenceSource(Enum):
    HEALTH_CHECK = "health_check"
    LOG_ENTRY = "log_entry"
    API_CALL = "api_call"
    USER_REPORT = "user_report"
    WORKER_STATUS = "worker_status"
    CONNECTOR_STATE = "connector_state"
    NONE = "none"


class EvidenceStrength(Enum):
    CONFIRMED = "confirmed"
    INFERRED = "inferred"
    STALE = "stale"
    ABSENT = "absent"


@dataclass
class EvidenceRecord:
    tool_key: str
    source: EvidenceSource
    strength: EvidenceStrength
    observed_at: str
    observed_at_ts: float
    raw_state: str = ""
    detail: str = ""
    error_code: str = ""
    error_message: str = ""
    recovery_suggestion: str = ""
    extra: dict[str, Any] = field(default_factory=dict)


def _iso_now() -> tuple[str, float]:
    now = datetime.now(tz=timezone.utc)
    return now.isoformat(timespec="seconds"), now.timestamp()


def _iso_from_ts(ts: float) -> str:
    return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat(timespec="seconds")


def absent_evidence(tool_key: str) -> EvidenceRecord:
    iso, ts = _iso_now()
    return EvidenceRecord(
        tool_key=tool_key,
        source=EvidenceSource.NONE,
        strength=EvidenceStrength.ABSENT,
        observed_at=iso,
        observed_at_ts=ts,
        raw_state="unknown",
        detail="No evidence available for this tool.",
    )


def from_health_payload(tool_key: str, payload: dict[str, Any]) -> EvidenceRecord:
    iso, ts = _iso_now()
    raw_state = str(payload.get("state", "") or "").strip().lower()
    detail = str(payload.get("detail", "") or payload.get("message", "") or "").strip()
    error_code = str(payload.get("error_code", "") or "").strip()
    error_message = str(payload.get("error_message", "") or "").strip()
    recovery = str(payload.get("recovery_suggestion", "") or payload.get("next_step", "") or "").strip()

    last_ok_ts = payload.get("last_ok_at")
    strength = _health_strength(raw_state, last_ok_ts)

    observed_at = iso
    observed_at_ts = ts
    if isinstance(last_ok_ts, (int, float)) and last_ok_ts > 0:
        observed_at = _iso_from_ts(float(last_ok_ts))
        observed_at_ts = float(last_ok_ts)

    return EvidenceRecord(
        tool_key=tool_key,
        source=EvidenceSource.HEALTH_CHECK,
        strength=strength,
        observed_at=observed_at,
        observed_at_ts=observed_at_ts,
        raw_state=raw_state,
        detail=detail,
        error_code=error_code,
        error_message=error_message,
        recovery_suggestion=recovery,
        extra={k: v for k, v in payload.items() if k not in (
            "state", "detail", "message", "error_code", "error_message",
            "recovery_suggestion", "next_step", "last_ok_at",
        )},
    )


def from_log_entry(tool_key: str, entry: dict[str, Any]) -> EvidenceRecord:
    iso, ts = _iso_now()
    level = str(entry.get("level", "") or "").strip().lower()
    message = str(entry.get("message", "") or entry.get("msg", "") or "").strip()
    entry_ts = entry.get("timestamp") or entry.get("ts")
    if isinstance(entry_ts, (int, float)) and entry_ts > 0:
        iso = _iso_from_ts(float(entry_ts))
        ts = float(entry_ts)

    raw_state = "error" if level in ("error", "critical", "fatal") else "ok"
    strength = EvidenceStrength.INFERRED

    return EvidenceRecord(
        tool_key=tool_key,
        source=EvidenceSource.LOG_ENTRY,
        strength=strength,
        observed_at=iso,
        observed_at_ts=ts,
        raw_state=raw_state,
        detail=message,
        error_code=str(entry.get("error_code", "") or "").strip(),
        error_message=message if raw_state == "error" else "",
    )


def from_connector_state(tool_key: str, connector_payload: dict[str, Any]) -> EvidenceRecord:
    iso, ts = _iso_now()
    raw_state = str(connector_payload.get("state", "") or "").strip().lower()
    auth_state = str(connector_payload.get("auth_state", "") or "").strip().lower()
    last_ok_ts = connector_payload.get("last_ok_at") or connector_payload.get("last_verified_at")
    detail = str(connector_payload.get("summary", "") or connector_payload.get("label", "") or "").strip()

    if isinstance(last_ok_ts, (int, float)) and last_ok_ts > 0:
        iso = _iso_from_ts(float(last_ok_ts))
        ts = float(last_ok_ts)

    strength = _connector_strength(raw_state, auth_state)

    return EvidenceRecord(
        tool_key=tool_key,
        source=EvidenceSource.CONNECTOR_STATE,
        strength=strength,
        observed_at=iso,
        observed_at_ts=ts,
        raw_state=raw_state or auth_state or "unknown",
        detail=detail,
        error_code=str(connector_payload.get("result_code", "") or "").strip(),
        recovery_suggestion=str(connector_payload.get("next_step", "") or "").strip(),
    )


def build_evidence(
    tool_key: str,
    health_payload: Optional[dict[str, Any]] = None,
    log_entries: Optional[list[dict[str, Any]]] = None,
    connector_payload: Optional[dict[str, Any]] = None,
) -> EvidenceRecord:
    candidates: list[EvidenceRecord] = []

    if health_payload:
        try:
            candidates.append(from_health_payload(tool_key, health_payload))
        except Exception:
            logger.exception("evidence_builder: failed to parse health payload for %s", tool_key)

    if connector_payload:
        try:
            candidates.append(from_connector_state(tool_key, connector_payload))
        except Exception:
            logger.exception("evidence_builder: failed to parse connector payload for %s", tool_key)

    if log_entries:
        for entry in log_entries[:1]:
            try:
                candidates.append(from_log_entry(tool_key, entry))
            except Exception:
                logger.exception("evidence_builder: failed to parse log entry for %s", tool_key)

    if not candidates:
        return absent_evidence(tool_key)

    return _best_candidate(candidates)


def _best_candidate(records: list[EvidenceRecord]) -> EvidenceRecord:
    strength_rank = {
        EvidenceStrength.CONFIRMED: 0,
        EvidenceStrength.INFERRED: 1,
        EvidenceStrength.STALE: 2,
        EvidenceStrength.ABSENT: 3,
    }
    return min(records, key=lambda r: (strength_rank[r.strength], -r.observed_at_ts))


def _health_strength(raw_state: str, last_ok_ts: Any) -> EvidenceStrength:
    if raw_state in ("connected", "ok", "running", "active"):
        return EvidenceStrength.CONFIRMED
    if raw_state in ("error", "expired", "blocked", "failed"):
        return EvidenceStrength.CONFIRMED
    if isinstance(last_ok_ts, (int, float)) and last_ok_ts > 0:
        import time
        age_s = time.time() - float(last_ok_ts)
        if age_s < 300:
            return EvidenceStrength.INFERRED
        return EvidenceStrength.STALE
    return EvidenceStrength.ABSENT


def _connector_strength(raw_state: str, auth_state: str) -> EvidenceStrength:
    if raw_state in ("connected", "verified"):
        return EvidenceStrength.CONFIRMED
    if raw_state in ("error", "expired", "failed"):
        return EvidenceStrength.CONFIRMED
    if auth_state in ("authenticated", "valid"):
        return EvidenceStrength.INFERRED
    return EvidenceStrength.STALE
