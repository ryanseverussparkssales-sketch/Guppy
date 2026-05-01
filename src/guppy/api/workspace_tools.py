from __future__ import annotations

import asyncio
import re
from pathlib import Path
from typing import Any


_REPO_ROOT = Path(__file__).resolve().parents[3]


def looks_destructive(description: str) -> bool:
    text = f" {description.lower()} "
    markers = (" delete ", " remove ", " rm ", " overwrite ", " drop ", " wipe ", " send ")
    return any(marker in text for marker in markers)


def extract_delay_minutes(description: str) -> float:
    text = description.lower()
    match = re.search(r"\bin\s+(\d+(?:\.\d+)?)\s*(minute|minutes|min|hour|hours|hr|hrs)\b", text)
    if not match:
        return 30.0
    value = float(match.group(1))
    unit = match.group(2)
    return value * 60 if unit.startswith(("hour", "hr")) else value


def extract_path(description: str) -> str:
    quoted = re.search(r"['\"]([^'\"]+)['\"]", description)
    if quoted:
        return quoted.group(1)
    pathish = re.search(r"((?:[A-Za-z]:)?[./\\]?[A-Za-z0-9_. -]+(?:[/\\][A-Za-z0-9_. -]+)+)", description)
    return pathish.group(1).strip() if pathish else "."


def planned_steps(description: str) -> list[tuple[str, dict[str, Any]]]:
    lower = description.lower()
    steps: list[tuple[str, dict[str, Any]]] = [
        ("task_plan", {"task_description": description}),
    ]

    if any(token in lower for token in ("what was i", "screen", "screenpipe", "working on", "recent activity")):
        steps.append(("screenpipe_search", {"query": description, "limit": 5}))

    if any(token in lower for token in ("remind me", "reminder", "todo", "follow up")):
        steps.append(
            (
                "create_reminder",
                {"message": description, "delay_minutes": extract_delay_minutes(description)},
            )
        )

    if any(token in lower for token in ("list files", "show files", "directory", "folder")):
        steps.append(("file_list", {"path": extract_path(description)}))
    elif any(token in lower for token in ("read file", "open file", "inspect file")):
        steps.append(("file_read", {"path": extract_path(description), "max_chars": 6000}))

    if any(token in lower for token in ("connector", "gmail", "calendar", "crm", "hubspot", "voip")):
        steps.append(("connector_snapshot", {"query": description}))

    if looks_destructive(description):
        steps.append(("confirm_action", {"action": description}))

    steps.append(("workspace_summary", {"task_description": description}))
    return steps


def safe_repo_path(path_value: str) -> Path:
    candidate = Path(path_value).expanduser()
    if not candidate.is_absolute():
        candidate = _REPO_ROOT / candidate
    resolved = candidate.resolve()
    try:
        resolved.relative_to(_REPO_ROOT)
    except ValueError as exc:
        raise ValueError(f"path must stay inside the repository: {resolved}") from exc
    return resolved


async def execute_workspace_tool(tool_name: str, tool_args: dict[str, Any]) -> dict[str, Any]:
    """Execute one workspace tool and return an observable result."""

    if tool_name == "task_plan":
        description = str(tool_args.get("task_description", "")).strip()
        planned = [
            name
            for name, _args in planned_steps(description)
            if name not in {"task_plan"}
        ]
        return {
            "ok": True,
            "plan": planned,
            "task_description": description,
        }

    if tool_name == "workspace_summary":
        description = str(tool_args.get("task_description", "")).strip()
        return {
            "ok": True,
            "summary": f"Workspace task run complete for: {description[:160]}",
        }

    if tool_name == "file_read":
        path = str(tool_args.get("path", "")).strip()
        max_chars = int(tool_args.get("max_chars", 6000) or 6000)
        try:
            resolved = safe_repo_path(path)
            if not resolved.is_file():
                return {"ok": False, "path": str(resolved), "error": "file not found"}
            content = await asyncio.to_thread(
                resolved.read_text,
                encoding="utf-8",
                errors="replace",
            )
            truncated = len(content) > max_chars
            return {
                "ok": True,
                "path": str(resolved),
                "content": content[:max_chars],
                "truncated": truncated,
            }
        except Exception as exc:
            return {"ok": False, "path": path, "error": str(exc)}

    if tool_name == "file_list":
        path = str(tool_args.get("path", "")).strip()
        try:
            resolved = safe_repo_path(path)
            if not resolved.exists():
                return {"ok": False, "path": str(resolved), "error": "path not found"}
            if resolved.is_file():
                return {"ok": True, "path": str(resolved), "files": [resolved.name]}
            entries = sorted(resolved.iterdir(), key=lambda item: (item.is_file(), item.name.lower()))
            return {
                "ok": True,
                "path": str(resolved),
                "files": [
                    {
                        "name": entry.name,
                        "path": str(entry.relative_to(_REPO_ROOT)),
                        "type": "file" if entry.is_file() else "directory",
                    }
                    for entry in entries[:100]
                ],
                "truncated": len(entries) > 100,
            }
        except Exception as exc:
            return {"ok": False, "path": path, "error": str(exc)}

    if tool_name == "connector_snapshot":
        try:
            from utils.connector_manager import connector_inventory

            connectors = await asyncio.to_thread(connector_inventory)
            return {"ok": True, "connectors": connectors, "count": len(connectors)}
        except Exception as exc:
            return {"ok": False, "error": f"connector inventory unavailable: {exc}"}

    if tool_name == "create_reminder":
        try:
            from src.guppy.api.routes_reminders import create_reminder

            message = str(tool_args.get("message", "")).strip()
            delay_minutes = float(tool_args.get("delay_minutes", 30) or 30)
            reminder = await asyncio.to_thread(
                create_reminder,
                message,
                None,
                delay_minutes,
            )
            return {"ok": True, "reminder": reminder}
        except Exception as exc:
            return {"ok": False, "error": f"could not create reminder: {exc}"}

    if tool_name == "screenpipe_search":
        query = str(tool_args.get("query", "")).strip()
        limit = int(tool_args.get("limit", 5) or 5)
        try:
            from src.guppy.api.routes_screenpipe import _search

            results = await asyncio.to_thread(_search, query, min(limit, 20), "all", None, None, None)
            return {"ok": True, "query": query, "results": results, "count": len(results), "available": True}
        except Exception as exc:
            return {
                "ok": True,
                "query": query,
                "results": [],
                "count": 0,
                "available": False,
                "detail": f"Screenpipe unavailable: {exc}",
            }

    if tool_name == "confirm_action":
        action = str(tool_args.get("action", "")).strip()
        return {
            "ok": False,
            "requires_confirmation": True,
            "action": action,
            "note": "This task appears to affect external state and requires user confirmation before continuing.",
        }

    return {"ok": False, "error": f"Unknown tool: {tool_name}"}
