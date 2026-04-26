"""
tool_status_copy.py

Lane: TR54-C5
Responsibilities:
  - Evidence-backed status label generation
  - No label without EvidenceRecord backing
  - Past-tense copy: what happened, not what might happen
  - Timestamps: ISO 8601, human-readable relative form
  - All output is bounded, never speculative
"""

from __future__ import annotations

import time
from typing import Optional

from .tool_evidence_builder import EvidenceRecord, EvidenceStrength, EvidenceSource


def status_label(evidence: EvidenceRecord) -> str:
    """Return the primary one-line status label for a tool card."""
    if evidence.strength == EvidenceStrength.ABSENT:
        return "No connection data"

    raw = evidence.raw_state.lower()

    if raw in ("connected", "ok", "running", "active", "verified"):
        ts = _relative_time(evidence.observed_at_ts)
        return f"Connected {ts}"

    if raw in ("error", "failed"):
        if evidence.error_message:
            return f"Failed: {_truncate(evidence.error_message, 60)}"
        return "Connection failed"

    if raw in ("expired",):
        ts = _relative_time(evidence.observed_at_ts)
        return f"Session expired {ts}"

    if raw in ("blocked",):
        return "Access blocked — see details"

    if raw in ("connecting", "reconnecting", "verifying"):
        return _present_for_transient(raw)

    if evidence.detail:
        return _truncate(evidence.detail, 80)

    return "Status unknown"


def status_sublabel(evidence: EvidenceRecord) -> str:
    """Return a secondary detail line (source + timestamp)."""
    source_label = _source_label(evidence.source)
    ts = _absolute_time(evidence.observed_at)
    return f"{source_label} · {ts}"


def recovery_copy(evidence: EvidenceRecord) -> str:
    """Return the recovery suggestion, if any."""
    if evidence.recovery_suggestion:
        return evidence.recovery_suggestion
    raw = evidence.raw_state.lower()
    if raw in ("expired",):
        return "Reconnect to restore access."
    if raw in ("error", "failed", "blocked"):
        return "Open Settings > Device & Accounts to diagnose."
    return ""


def is_actionable(evidence: EvidenceRecord) -> bool:
    """True when the evidence suggests user action is needed."""
    return evidence.raw_state.lower() in (
        "error", "failed", "expired", "blocked", "auth_missing",
    ) or evidence.strength == EvidenceStrength.ABSENT


def availability_line(
    available: int,
    setup_required: int,
    restricted: int,
) -> str:
    parts: list[str] = []
    if available > 0:
        parts.append(f"Available now: {available}")
    if setup_required > 0:
        parts.append(f"Set up first: {setup_required}")
    if restricted > 0:
        parts.append(f"Restricted here: {restricted}")
    return " | ".join(parts) if parts else "No tools in this workspace"


def last_run_copy(observed_at_iso: Optional[str], success: bool) -> str:
    if not observed_at_iso:
        return "No run recorded"
    verb = "Completed" if success else "Failed"
    return f"Last run {verb}: {observed_at_iso}"


def _relative_time(ts: float) -> str:
    if ts <= 0:
        return "at an unknown time"
    age_s = time.time() - ts
    if age_s < 60:
        return "just now"
    if age_s < 3600:
        minutes = int(age_s / 60)
        return f"{minutes} minute{'s' if minutes != 1 else ''} ago"
    if age_s < 86400:
        hours = int(age_s / 3600)
        return f"{hours} hour{'s' if hours != 1 else ''} ago"
    days = int(age_s / 86400)
    return f"{days} day{'s' if days != 1 else ''} ago"


def _absolute_time(iso: str) -> str:
    if not iso:
        return "unknown time"
    # Strip sub-second precision for display: 2024-01-15T14:22:00+00:00 → 2024-01-15 14:22 UTC
    try:
        date_part, time_part = iso[:19].split("T")
        return f"{date_part} {time_part[:5]} UTC"
    except (ValueError, IndexError):
        return iso


def _source_label(source: EvidenceSource) -> str:
    mapping = {
        EvidenceSource.HEALTH_CHECK: "Health check",
        EvidenceSource.LOG_ENTRY: "Log entry",
        EvidenceSource.API_CALL: "API call",
        EvidenceSource.USER_REPORT: "User report",
        EvidenceSource.WORKER_STATUS: "Worker status",
        EvidenceSource.CONNECTOR_STATE: "Connector state",
        EvidenceSource.NONE: "No source",
    }
    return mapping.get(source, "Unknown source")


def _present_for_transient(raw: str) -> str:
    mapping = {
        "connecting": "Connecting...",
        "reconnecting": "Reconnecting...",
        "verifying": "Verifying...",
    }
    return mapping.get(raw, "Working...")


def _truncate(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    return text[: limit - 1] + "…"
