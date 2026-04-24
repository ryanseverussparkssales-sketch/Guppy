"""
src/guppy/launcher_application/tool_action_registry.py

Shared tool action registry. Single source of truth for tool labels,
voice/type command hints, Home starter prompts, category, and dry_run
status. All UI surfaces (Tools hub cards, Home starters, launcher wiring)
pull from here so wording never drifts across surfaces.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ToolActionEntry:
    label: str
    command_hint: str
    home_starter_prompt: str
    category: str
    dry_run: bool
    availability_status: str = "available"  # "available" | "planned"


TOOL_ACTION_REGISTRY: dict[str, ToolActionEntry] = {
    "read_file": ToolActionEntry(
        label="READ FILE",
        command_hint="Read this file",
        home_starter_prompt=(
            "Prime the read-file workspace tool for this task. "
            "Start by asking which file or folder Guppy should inspect, "
            "then confirm the exact read-only scope."
        ),
        category="READ",
        dry_run=False,
    ),
    "screenshot": ToolActionEntry(
        label="SCREENSHOT",
        command_hint="Capture the screen",
        home_starter_prompt=(
            "Prime the screenshot workspace tool for this task. "
            "Ask what screen or app the user wants Guppy to inspect."
        ),
        category="READ",
        dry_run=False,
    ),
    "query_instance": ToolActionEntry(
        label="QUERY INSTANCE",
        command_hint="Ask another workspace",
        home_starter_prompt=(
            "Prime the cross-workspace query tool for this task. "
            "Ask which workspace Guppy should consult and what question to send."
        ),
        category="QUERY",
        dry_run=False,
    ),
    "debug_console": ToolActionEntry(
        label="DEBUG CONSOLE",
        command_hint="Inspect runtime state",
        home_starter_prompt=(
            "Prime the debug-console workspace tool for this task. "
            "Start by asking what runtime detail the user wants to inspect."
        ),
        category="DEBUG",
        dry_run=False,
    ),
    "run_python": ToolActionEntry(
        label="RUN PYTHON",
        command_hint="Run a Python snippet",
        home_starter_prompt=(
            "Prime the Python workspace tool for this task. "
            "Start by confirming the smallest safe snippet to run."
        ),
        category="CODE",
        dry_run=True,
    ),
    "write_file": ToolActionEntry(
        label="WRITE FILE",
        command_hint="Write changes to this file",
        home_starter_prompt=(
            "Prime the write-file workspace tool for this task. "
            "Start by asking what file should change, what outcome is expected, "
            "and what scope is safe."
        ),
        category="WRITE",
        dry_run=True,
    ),
    "execute_command": ToolActionEntry(
        label="EXECUTE COMMAND",
        command_hint="Run a shell command",
        home_starter_prompt=(
            "Prime the command workspace tool for this task. "
            "Start by asking which command should run, why it is needed, "
            "and what safe scope applies."
        ),
        category="WRITE",
        dry_run=True,
    ),
    "send_email": ToolActionEntry(
        label="GMAIL",
        command_hint="Send or manage Gmail",
        home_starter_prompt=(
            "Prime the Gmail workspace tool for this task. "
            "Start by asking what email action is needed and which workspace "
            "account should be used."
        ),
        category="CONNECTOR",
        dry_run=False,
    ),
    "calendar_events": ToolActionEntry(
        label="CALENDAR",
        command_hint="Show my calendar events",
        home_starter_prompt=(
            "Prime the Calendar workspace tool for this task. "
            "Start by asking which date range or calendar scope to retrieve."
        ),
        category="CONNECTOR",
        dry_run=False,
    ),
    "spotify_current": ToolActionEntry(
        label="SPOTIFY",
        command_hint="Check or control Spotify",
        home_starter_prompt=(
            "Prime the Spotify workspace tool for this task. "
            "Start by asking what the user wants to inspect or control in Spotify."
        ),
        category="CONNECTOR",
        dry_run=False,
    ),
    "youtube_search": ToolActionEntry(
        label="YOUTUBE",
        command_hint="Search YouTube",
        home_starter_prompt=(
            "Prime the YouTube workspace tool for this task. "
            "Start by asking what topic or query the user wants to search for."
        ),
        category="CONNECTOR",
        dry_run=False,
    ),
    "crm_upsert_contact": ToolActionEntry(
        label="CRM",
        command_hint="Update a CRM contact",
        home_starter_prompt=(
            "Prime the CRM workspace tool for this task. "
            "Start by asking which contact or record should be prepared and "
            "what fields need updating."
        ),
        category="CONNECTOR",
        dry_run=True,
    ),
    "voip_place_call": ToolActionEntry(
        label="VOIP",
        command_hint="Place an outbound call",
        home_starter_prompt=(
            "Prime the VoIP workspace tool for this task. "
            "Start by asking what number or contact should be called and "
            "which workspace VoIP provider to use."
        ),
        category="CONNECTOR",
        dry_run=True,
        availability_status="planned",
    ),
}


def get_action_for_tool(tool_key: str) -> ToolActionEntry | None:
    """Return the ToolActionEntry for the given key, or None if not found."""
    return TOOL_ACTION_REGISTRY.get((tool_key or "").strip().lower())


def get_home_starter_prompt(tool_key: str) -> str:
    """Return the Home starter prompt for the given tool key.

    Falls back to a generic prompt so callers never get an empty string.
    """
    entry = get_action_for_tool(tool_key)
    if entry is not None:
        return entry.home_starter_prompt
    key = (tool_key or "").strip()
    return f"Prime the {key} workspace tool for this task: "


def get_tool_starters() -> list[dict[str, str]]:
    """Return starter dicts for tools that are currently available (not planned).

    Each dict has: tool_key, label, command_hint, home_starter_prompt, category,
    availability_status. Planned tools are excluded so Home starters only surface
    tools users can actually use today.
    """
    return [
        {
            "tool_key": key,
            "label": entry.label,
            "command_hint": entry.command_hint,
            "home_starter_prompt": entry.home_starter_prompt,
            "category": entry.category,
            "availability_status": entry.availability_status,
        }
        for key, entry in TOOL_ACTION_REGISTRY.items()
        if entry.availability_status != "planned"
    ]


def get_canonical_action_line(tool_key: str) -> str:
    """Return the plain-language user action line for a tool."""
    entry = get_action_for_tool(tool_key)
    if entry is None:
        key = (tool_key or "").strip().replace("_", " ")
        return f'Say or type: "{key}"'
    return f'Say or type: "{entry.command_hint}"'


__all__ = [
    "ToolActionEntry",
    "TOOL_ACTION_REGISTRY",
    "get_action_for_tool",
    "get_canonical_action_line",
    "get_home_starter_prompt",
    "get_tool_starters",
]
