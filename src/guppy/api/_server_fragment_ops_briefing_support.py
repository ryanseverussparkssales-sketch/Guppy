from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path
from typing import Any


_MORNING_BRIEF_DIRECT_PHRASES = (
    "morning brief",
    "morning briefing",
    "daily brief",
    "daily briefing",
)
_MORNING_BRIEF_AFFIRMATIONS = (
    "yes",
    "yes please",
    "yeah",
    "yep",
    "sure",
    "ok",
    "okay",
    "please",
    "do it",
    "go ahead",
    "lets",
    "let's",
    "sounds good",
)


def resolve_runtime_dir(owner: Any) -> Path:
    runtime_dir = getattr(owner, "_runtime_dir", None)
    if runtime_dir is None:
        path_config = getattr(owner, "_path_config", None)
        runtime_dir = getattr(path_config, "runtime_dir", None)
    if runtime_dir is None:
        runtime_dir = getattr(owner, "runtime_dir", None)
    if runtime_dir is None:
        raise AttributeError("owner must expose _runtime_dir, _path_config.runtime_dir, or runtime_dir")
    return Path(runtime_dir)


def normalize_brief_text(text: Any) -> str:
    raw = str(text or "").strip().lower()
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9']+", " ", raw)).strip()


def looks_like_brief_affirmation(text: Any) -> bool:
    compact = normalize_brief_text(text)
    if not compact:
        return False
    if compact in _MORNING_BRIEF_AFFIRMATIONS:
        return True
    return any(compact.startswith(f"{phrase} ") for phrase in _MORNING_BRIEF_AFFIRMATIONS)


def history_offered_morning_brief(history: Any) -> bool:
    if not isinstance(history, list):
        return False
    for item in reversed(history[-6:]):
        if not isinstance(item, dict):
            continue
        if str(item.get("role", "")).strip().lower() != "assistant":
            continue
        content = normalize_brief_text(item.get("content", ""))
        if "morning brief" not in content:
            continue
        if any(phrase in content for phrase in ("shall i", "i can", "prepare", "proceed", "give you")):
            return True
    return False


def request_is_morning_brief(request: Any) -> bool:
    message = normalize_brief_text(request.message)
    if any(phrase in message for phrase in _MORNING_BRIEF_DIRECT_PHRASES):
        return True
    return looks_like_brief_affirmation(message) and history_offered_morning_brief(request.history)


def latest_daily_report_path(owner: Any) -> Path | None:
    reports_dir = resolve_runtime_dir(owner) / "daily_reports"
    if not reports_dir.exists():
        return None
    today_name = f"{datetime.now().strftime('%Y-%m-%d')}.md"
    today_path = reports_dir / today_name
    if today_path.exists():
        return today_path
    reports = sorted(reports_dir.glob("*.md"), key=lambda p: p.stat().st_mtime, reverse=True)
    return reports[0] if reports else None


def strip_markdown_prefix(text: str) -> str:
    cleaned = text.strip()
    cleaned = re.sub(r"^\s*(?:[-*]|\d+\.)\s*", "", cleaned)
    cleaned = cleaned.replace("**", "").replace("`", "")
    return cleaned.strip()


def parse_markdown_sections(markdown_text: str) -> dict[str, list[str]]:
    sections: dict[str, list[str]] = {}
    current = ""
    for raw_line in markdown_text.splitlines():
        line = raw_line.rstrip()
        if line.startswith("## "):
            current = line[3:].strip().lower()
            sections.setdefault(current, [])
            continue
        if current:
            sections[current].append(line)
    return sections


def preview_markdown_section(lines: list[str], limit: int = 3) -> list[str]:
    preview: list[str] = []
    for raw in lines:
        line = raw.strip()
        if not line:
            continue
        if line.startswith("|"):
            if line.startswith("|-"):
                continue
            cols = [part.strip() for part in line.strip("|").split("|")]
            if len(cols) >= 2 and cols[0].lower() != "topic":
                preview.append(strip_markdown_prefix(f"{cols[0]}: {cols[1]}"))
            continue
        preview.append(strip_markdown_prefix(line))
        if len(preview) >= limit:
            break
    return preview[:limit]


def preview_plain_block(text: str, limit: int = 3) -> list[str]:
    lines = [strip_markdown_prefix(line) for line in str(text or "").splitlines() if str(line).strip()]
    return [line for line in lines if line][:limit]


def build_morning_brief_response(owner: Any) -> str:
    now_local = datetime.now().astimezone()
    lines = [f"Morning brief for {now_local.strftime('%A, %B %d, %Y')}."]

    report_path = latest_daily_report_path(owner)
    report_sections: dict[str, list[str]] = {}
    if report_path is not None:
        try:
            report_sections = parse_markdown_sections(report_path.read_text(encoding="utf-8", errors="ignore"))
        except Exception:
            report_sections = {}

    key_actions = preview_markdown_section(report_sections.get("key actions", []), limit=3)
    carry_forward = preview_markdown_section(report_sections.get("carry-forward items", []), limit=3)
    world_news = preview_markdown_section(report_sections.get("world news", []), limit=3)

    if key_actions:
        lines.append("")
        lines.append("Top priorities:")
        lines.extend(f"- {item}" for item in key_actions)

    pending_tasks = ""
    if owner.GUPPY_MEMORY_AVAILABLE and hasattr(owner.memory, "get_tasks"):
        try:
            pending_tasks = str(owner.memory.get_tasks("pending") or "").strip()
        except Exception:
            pending_tasks = ""
    task_preview = []
    if pending_tasks and not pending_tasks.lower().startswith("no pending tasks"):
        task_preview = preview_plain_block(pending_tasks, limit=3)
    if task_preview:
        lines.append("")
        lines.append("Pending tasks:")
        lines.extend(f"- {item}" for item in task_preview)

    if world_news:
        lines.append("")
        lines.append("World watch:")
        lines.extend(f"- {item}" for item in world_news)

    if carry_forward:
        lines.append("")
        lines.append("Carry-forward:")
        lines.extend(f"- {item}" for item in carry_forward)

    resource = owner._read_resource_envelope_status()
    startup = owner._startup_readiness_cached_or_unknown()
    resource_state = str(resource.get("state", "unknown")).strip().lower() or "unknown"
    resource_message = str(resource.get("message", "resource envelope status unavailable")).strip()
    startup_state = str(startup.get("overall", "UNKNOWN")).strip().lower() or "unknown"
    lines.append("")
    lines.append(f"System status: resource envelope {resource_state}; startup readiness {startup_state}.")
    if resource_message:
        lines.append(f"Runtime note: {resource_message.rstrip('.')}.")

    if report_path is not None:
        report_label = f"today's report" if report_path.name == f"{now_local.strftime('%Y-%m-%d')}.md" else "latest report"
        lines.append(f"Full details are in {report_label}: runtime/daily_reports/{report_path.name}.")
    elif len(lines) == 3:
        lines.append("No saved daily report is available yet, so this brief is using live runtime context only.")

    return "\n".join(lines)
