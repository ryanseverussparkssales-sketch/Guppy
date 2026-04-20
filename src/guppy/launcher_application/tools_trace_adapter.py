"""Read-only adapter for launcher/tool trace data used by the Tools hub."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Callable, Mapping

from .storage_io import read_json_dict, read_jsonl_tail


_ToolStatesGetter = Callable[[], Mapping[str, object]]


def _coerce_bool_states(states: Mapping[str, object] | None) -> dict[str, bool]:
    if not isinstance(states, Mapping):
        return {}
    return {
        str(key): bool(value)
        for key, value in states.items()
        if str(key).strip()
    }


def _coerce_text_states(states: Mapping[str, object] | None) -> dict[str, str]:
    if not isinstance(states, Mapping):
        return {}
    normalized: dict[str, str] = {}
    for key, value in states.items():
        name = str(key).strip()
        if not name:
            continue
        text = str(value or "").strip()
        normalized[name] = text or "unknown"
    return normalized


class LauncherToolsTraceAdapter:
    """Thin read/debug seam over the launcher's persisted trace files."""

    def __init__(
        self,
        runtime_dir: Path,
        *,
        tool_state_path: Path | None = None,
        live_tool_states_getter: _ToolStatesGetter | None = None,
        live_tool_statuses_getter: _ToolStatesGetter | None = None,
    ) -> None:
        self._runtime_dir = Path(runtime_dir)
        self._events_path = self._runtime_dir / "launcher_events.jsonl"
        self._tool_state_path = (
            Path(tool_state_path)
            if tool_state_path is not None
            else self._runtime_dir / "tool_states.json"
        )
        self._live_tool_states_getter = live_tool_states_getter
        self._live_tool_statuses_getter = live_tool_statuses_getter

    @property
    def launcher_events_path(self) -> Path:
        return self._events_path

    @property
    def tool_state_path(self) -> Path:
        return self._tool_state_path

    def read_tool_states(self) -> dict[str, bool]:
        if not self._tool_state_path.exists():
            return {}
        return _coerce_bool_states(read_json_dict(self._tool_state_path))

    def read_live_tool_states(self) -> dict[str, bool]:
        if not callable(self._live_tool_states_getter):
            return {}
        try:
            return _coerce_bool_states(self._live_tool_states_getter())
        except Exception:
            return {}

    def read_live_tool_statuses(self) -> dict[str, str]:
        if not callable(self._live_tool_statuses_getter):
            return {}
        try:
            return _coerce_text_states(self._live_tool_statuses_getter())
        except Exception:
            return {}

    def read_recent_tool_events(self, *, limit: int = 12, tool_key: str | None = None) -> list[dict[str, object]]:
        target_key = str(tool_key or "").strip().lower()
        records: list[dict[str, object]] = []
        for item in reversed(read_jsonl_tail(self._events_path, limit=max(limit * 8, 40))):
            normalized = self._normalize_event(item)
            if normalized is None or not normalized.get("tool_related", False):
                continue
            normalized_tool = str(normalized.get("tool", "") or "").strip().lower()
            if target_key and normalized_tool != target_key:
                continue
            records.append(normalized)
            if len(records) >= limit:
                break
        return records

    def read_recent_launcher_events(self, *, limit: int = 12) -> list[dict[str, object]]:
        records: list[dict[str, object]] = []
        for item in reversed(read_jsonl_tail(self._events_path, limit=max(limit * 4, 24))):
            normalized = self._normalize_event(item)
            if normalized is None:
                continue
            records.append(normalized)
            if len(records) >= limit:
                break
        return records

    def read_debug_snapshot(self, *, tool_key: str | None = None, limit: int = 12) -> dict[str, object]:
        persisted_states = self.read_tool_states()
        live_states = self.read_live_tool_states()
        live_statuses = self.read_live_tool_statuses()
        recent_tool_events = self.read_recent_tool_events(limit=limit, tool_key=tool_key)
        recent_launcher_events = self.read_recent_launcher_events(limit=limit)
        return {
            "paths": {
                "launcher_events": str(self._events_path),
                "tool_states": str(self._tool_state_path),
            },
            "tool_key": str(tool_key or "").strip(),
            "persisted_tool_states": persisted_states,
            "live_tool_states": live_states,
            "live_tool_statuses": live_statuses,
            "recent_tool_events": recent_tool_events,
            "recent_launcher_events": recent_launcher_events,
            "event_counts": {
                "recent_tool_events": len(recent_tool_events),
                "recent_launcher_events": len(recent_launcher_events),
            },
            "state_drift": self._state_drift(persisted_states, live_states),
        }

    @staticmethod
    def _normalize_event(item: object) -> dict[str, object] | None:
        if not isinstance(item, dict):
            return None
        event = str(item.get("event", "") or "").strip()
        if not event:
            return None
        tool = str(item.get("tool", "") or "").strip()
        summary = (
            str(item.get("summary", "") or "").strip()
            or str(item.get("status", "") or "").strip()
            or str(item.get("action", "") or "").strip()
            or str(item.get("command", "") or "").strip()
            or str(item.get("instance", "") or "").strip()
        )
        level = LauncherToolsTraceAdapter._event_level(item)
        return {
            "ts": str(item.get("ts", "") or "").strip(),
            "event": event,
            "source": str(item.get("source", "") or "").strip(),
            "level": level,
            "tool": tool,
            "enabled": bool(item.get("enabled")) if "enabled" in item else None,
            "summary": summary,
            "tool_related": bool(tool) or event.startswith("tool_") or "tool" in event,
            "raw": dict(item),
        }

    @staticmethod
    def _event_level(item: Mapping[str, object]) -> str:
        event = str(item.get("event", "") or "").lower()
        summary = json.dumps(item, ensure_ascii=True).lower()
        if "error" in event or "error" in summary or "failed" in summary:
            return "ERROR"
        if "warn" in event or "warning" in summary or "over_budget" in event:
            return "WARN"
        return "INFO"

    @staticmethod
    def _state_drift(
        persisted_states: Mapping[str, bool],
        live_states: Mapping[str, bool],
    ) -> list[dict[str, object]]:
        drift: list[dict[str, object]] = []
        all_keys = sorted(set(persisted_states.keys()) | set(live_states.keys()))
        for key in all_keys:
            persisted = persisted_states.get(key)
            live = live_states.get(key)
            if persisted == live:
                continue
            drift.append(
                {
                    "tool": key,
                    "persisted": persisted,
                    "live": live,
                }
            )
        return drift
