from __future__ import annotations

from copy import deepcopy

from src.guppy.memory import memory as memory_facade


def build_workspace_continuity_snapshot(
    workspace_name: str,
    *,
    last_message: str = "",
) -> dict[str, object]:
    name = str(workspace_name or "").strip()
    if not name:
        return {
            "workspace_name": "",
            "message_count": 0,
            "session_count": 0,
            "latest_message": str(last_message or "").strip(),
            "latest_timestamp": "",
            "latest_session_id": "",
            "latest_role": "",
            "used_legacy_fallback": False,
            "continuity_hint": "",
            "continuity_summary": "",
        }
    raw_snapshot = memory_facade.get_workspace_memory_snapshot(name)
    snapshot = raw_snapshot if isinstance(raw_snapshot, dict) else {}
    message_count = int(snapshot.get("message_count", 0) or 0)
    session_count = int(snapshot.get("session_count", 0) or 0)
    latest_message = str(last_message or snapshot.get("latest_message", "") or "").strip()
    used_legacy_fallback = bool(snapshot.get("used_legacy_fallback", False))

    if session_count > 1:
        continuity_hint = f"Continuity: {session_count} recent sessions are saved here."
    elif session_count == 1:
        continuity_hint = "Continuity: 1 recent session is saved here."
    elif message_count > 0:
        continuity_hint = f"Continuity: {message_count} saved messages are available here."
    else:
        continuity_hint = "Continuity: this workspace is ready to build its rhythm."

    if used_legacy_fallback and message_count > 0:
        continuity_hint = f"{continuity_hint} Using legacy saved context until this workspace builds its own thread."

    if latest_message:
        snippet = latest_message[:120] + ("..." if len(latest_message) > 120 else "")
        continuity_summary = f"{continuity_hint} Last saved thread: {snippet}"
    else:
        continuity_summary = continuity_hint

    return {
        **snapshot,
        "workspace_name": name,
        "latest_message": latest_message,
        "continuity_hint": continuity_hint,
        "continuity_summary": continuity_summary,
    }


def annotate_workspace_snapshot(snapshot: dict[str, object] | None) -> dict[str, object]:
    raw_snapshot = snapshot if isinstance(snapshot, dict) else {}
    cloned = deepcopy(raw_snapshot)
    items = cloned.get("instances", [])
    if not isinstance(items, list):
        return cloned

    annotated_items: list[dict[str, object]] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        annotated = dict(item)
        name = str(annotated.get("name", "") or "").strip()
        last_message = str(annotated.get("last_message", "") or "").strip()
        continuity = build_workspace_continuity_snapshot(name, last_message=last_message)
        annotated["continuity"] = continuity
        if not last_message and str(continuity.get("latest_message", "") or "").strip():
            annotated["last_message"] = str(continuity.get("latest_message", "") or "").strip()
        annotated_items.append(annotated)
    cloned["instances"] = annotated_items
    return cloned
