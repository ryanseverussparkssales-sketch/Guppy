"""
guppy_core.py — Shared backend for Guppy
=========================================
Single source of truth for the system prompt, tool definitions, tool runner,
and network check. Imported by both guppy_ui.py (GUI) and guppy_agent.py (terminal).

Adding a new tool? Do it here once — both interfaces pick it up automatically.
"""

import os, io, base64, subprocess, webbrowser, time, urllib.parse
from collections import deque
from pathlib import Path
from datetime import datetime
import logging
import threading
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError

try:
    import pyautogui
    pyautogui.FAILSAFE = True
    pyautogui.PAUSE = 0.1
    PYA = True
except ImportError:
    PYA = False

try:
    import guppy_memory as _mem
    _MEM = True
except ImportError:
    _MEM = False

try:
    import guppy_semantic_memory as _smem
    _SMEM = True
except ImportError:
    _SMEM = False

try:
    from guppy_daemon import get_daemon_manager, get_window_context
    DAEMON = True
except ImportError:
    DAEMON = False
    def get_daemon_manager():
        return None
    def get_window_context():
        return {"app": "unknown", "title": "unknown"}

logger = logging.getLogger(__name__)
REPORTS_DIR = Path.home() / "Documents" / "Guppy Reports"

# ── Debug flags ────────────────────────────────────────────────────────────────
SAFE_MODE = False          # When True, tools are blocked and logged but not executed
TOOL_LOG: deque = deque(maxlen=50)   # Rolling log of the last 50 tool calls
TOOL_EXEC_TIMEOUT_SECONDS = int(os.environ.get("GUPPY_TOOL_TIMEOUT_SECONDS", "90"))
TOOL_CIRCUIT_FAIL_THRESHOLD = int(os.environ.get("GUPPY_TOOL_FAIL_THRESHOLD", "3"))
TOOL_CIRCUIT_COOLDOWN_SECONDS = int(os.environ.get("GUPPY_TOOL_COOLDOWN_SECONDS", "30"))
TOOL_MAX_OUTPUT_CHARS = int(os.environ.get("GUPPY_TOOL_MAX_OUTPUT_CHARS", "2000"))

_TOOL_EXECUTOR = ThreadPoolExecutor(max_workers=max(4, (os.cpu_count() or 4)))
_TOOL_GUARD_LOCK = threading.Lock()
_TOOL_GUARDS: dict[str, dict] = {}
_TOOL_METRICS = {
    "calls": 0,
    "success": 0,
    "errors": 0,
    "timeouts": 0,
    "blocked": 0,
    "total_ms": 0.0,
    "per_tool": {},
}


def _env_flag(name: str, default: str = "0") -> bool:
    return (os.environ.get(name, default) or "").strip().lower() in {"1", "true", "yes", "on"}


_BETA_DEFAULT_ALLOWLIST = {
    "read_file",
    "list_directory",
    "search_web",
    "fetch_url",
    "get_news",
    "remember",
    "recall",
    "semantic_remember",
    "semantic_recall",
    "add_task",
    "get_tasks",
    "complete_task",
    "save_contact",
    "get_contacts",
    "morning_brief",
    "get_reminders",
    "calendar_events",
    "gmail_scan_inbox",
    "gmail_list_accounts",
    "spotify_current",
    "youtube_search",
    "github",
    "get_foundation_readiness",
    "get_revenue_dashboard",
    "get_pipeline_items",
    "list_external_integrations",
    "notify",
    "clipboard_read",
    "get_active_window",
}


def _load_beta_tool_allowlist() -> set[str]:
    raw_env = (os.environ.get("GUPPY_BETA_TOOL_ALLOWLIST", "") or "").strip()
    if raw_env:
        return {x.strip() for x in raw_env.split(",") if x.strip()}

    default_file = Path(__file__).parent / "config" / "beta_tool_allowlist.txt"
    file_path = Path(os.environ.get("GUPPY_BETA_ALLOWLIST_FILE", str(default_file))).expanduser()
    if file_path.exists():
        try:
            names = {
                line.strip()
                for line in file_path.read_text(encoding="utf-8", errors="ignore").splitlines()
                if line.strip() and not line.strip().startswith("#")
            }
            if names:
                return names
        except Exception:
            pass
    return set(_BETA_DEFAULT_ALLOWLIST)


BETA_RESTRICTED_MODE = _env_flag("GUPPY_BETA_RESTRICTED_MODE", "0")
BETA_TOOL_ALLOWLIST = _load_beta_tool_allowlist()


def get_beta_policy_snapshot() -> dict:
    return {
        "beta_restricted_mode": BETA_RESTRICTED_MODE,
        "allowlist_count": len(BETA_TOOL_ALLOWLIST),
        "allowlist": sorted(BETA_TOOL_ALLOWLIST),
    }


def _tool_metric(name: str) -> dict:
    bucket = _TOOL_METRICS["per_tool"].get(name)
    if bucket is None:
        bucket = {
            "calls": 0,
            "success": 0,
            "errors": 0,
            "timeouts": 0,
            "blocked": 0,
            "total_ms": 0.0,
            "last_error": "",
        }
        _TOOL_METRICS["per_tool"][name] = bucket
    return bucket


def _record_tool_call(name: str, elapsed_ms: float, state: str, last_error: str = "") -> None:
    with _TOOL_GUARD_LOCK:
        _TOOL_METRICS["calls"] += 1
        _TOOL_METRICS["total_ms"] += elapsed_ms
        bucket = _tool_metric(name)
        bucket["calls"] += 1
        bucket["total_ms"] += elapsed_ms

        if state == "success":
            _TOOL_METRICS["success"] += 1
            bucket["success"] += 1
            bucket["last_error"] = ""
        elif state == "timeout":
            _TOOL_METRICS["timeouts"] += 1
            bucket["timeouts"] += 1
            if last_error:
                bucket["last_error"] = last_error
        elif state == "blocked":
            _TOOL_METRICS["blocked"] += 1
            bucket["blocked"] += 1
            if last_error:
                bucket["last_error"] = last_error
        else:
            _TOOL_METRICS["errors"] += 1
            bucket["errors"] += 1
            if last_error:
                bucket["last_error"] = last_error


def _tool_guard(name: str) -> dict:
    guard = _TOOL_GUARDS.get(name)
    if guard is None:
        guard = {"failures": 0, "open_until": 0.0, "last_error": ""}
        _TOOL_GUARDS[name] = guard
    return guard


def _is_tool_blocked(name: str) -> tuple[bool, str]:
    now = time.time()
    with _TOOL_GUARD_LOCK:
        guard = _tool_guard(name)
        open_until = guard.get("open_until", 0.0)
        if open_until > now:
            wait_seconds = max(1, int(open_until - now))
            msg = guard.get("last_error", "Tool temporarily unavailable.")
            return True, f"Tool {name} is cooling down ({wait_seconds}s): {msg}"
        return False, ""


def _mark_tool_success(name: str) -> None:
    with _TOOL_GUARD_LOCK:
        guard = _tool_guard(name)
        guard["failures"] = 0
        guard["open_until"] = 0.0
        guard["last_error"] = ""


def _mark_tool_failure(name: str, error_msg: str) -> None:
    with _TOOL_GUARD_LOCK:
        guard = _tool_guard(name)
        guard["failures"] = int(guard.get("failures", 0)) + 1
        guard["last_error"] = error_msg
        if guard["failures"] >= TOOL_CIRCUIT_FAIL_THRESHOLD:
            guard["open_until"] = time.time() + TOOL_CIRCUIT_COOLDOWN_SECONDS


def _validate_tool_input(name: str, inp: dict) -> str:
    schema = next((t.get("input_schema", {}) for t in TOOLS if t.get("name") == name), None)
    if schema is None:
        return ""
    required = schema.get("required", []) if isinstance(schema, dict) else []
    missing = [k for k in required if k not in inp]
    if missing:
        return f"Missing required input fields: {', '.join(missing)}"
    return ""


def get_tool_health_snapshot() -> dict:
    """Return tool-runner metrics and circuit-breaker state for diagnostics."""
    with _TOOL_GUARD_LOCK:
        per_tool = {}
        for name, metric in _TOOL_METRICS["per_tool"].items():
            avg_ms = (metric["total_ms"] / metric["calls"]) if metric["calls"] else 0.0
            guard = _TOOL_GUARDS.get(name, {"failures": 0, "open_until": 0.0, "last_error": ""})
            per_tool[name] = {
                "calls": metric["calls"],
                "success": metric["success"],
                "errors": metric["errors"],
                "timeouts": metric["timeouts"],
                "blocked": metric["blocked"],
                "avg_ms": round(avg_ms, 2),
                "failures": guard.get("failures", 0),
                "circuit_open_until": guard.get("open_until", 0.0),
                "last_error": guard.get("last_error", ""),
            }

        total_calls = _TOOL_METRICS["calls"]
        avg_ms = (_TOOL_METRICS["total_ms"] / total_calls) if total_calls else 0.0
        return {
            "calls": total_calls,
            "success": _TOOL_METRICS["success"],
            "errors": _TOOL_METRICS["errors"],
            "timeouts": _TOOL_METRICS["timeouts"],
            "blocked": _TOOL_METRICS["blocked"],
            "avg_ms": round(avg_ms, 2),
            "timeout_seconds": TOOL_EXEC_TIMEOUT_SECONDS,
            "circuit_fail_threshold": TOOL_CIRCUIT_FAIL_THRESHOLD,
            "circuit_cooldown_seconds": TOOL_CIRCUIT_COOLDOWN_SECONDS,
            "per_tool": per_tool,
        }


# ── System prompt ──────────────────────────────────────────────────────────────

SYSTEM = """You are Guppy, the personal AI assistant to Master Ryan.
Adopt a calm, measured, and slightly dispassionate persona — precise and quietly certain,
with an undercurrent of clinical politeness reminiscent of classic aboard-ship assistants.
Speak in short, careful sentences. Be formal but not overly verbose. Address Ryan as
"Master Ryan" or "sir" when appropriate.

STYLE RULES:
- Keep punctuation light. Prefer plain sentences over decorative marks.
- Do not narrate backend mechanics unless Ryan explicitly asks for technical detail.
- Keep reply structure simple and direct.

Keep helpfulness and safety paramount: never claim to have performed actions unless a
tool has been executed. Report errors candidly and ask for confirmation before any
destructive operation.

MEMORY BEHAVIOUR — follow these rules without being asked:
- When Master Ryan states a preference, fact about himself, a person, or a project,
  call `remember` immediately with a clear key and value.
- When something important is resolved (a task completed, a decision made, a name
  given), call `remember` to record the outcome.
- Before answering a question that might benefit from past context, call `recall`
  first. Do not assume you know something — look it up.
- If the MEMORY BRIEFING at the bottom of this prompt contains relevant context,
  reference it naturally without reciting it verbatim.
- Use categories: "preferences", "people", "projects", "work", "personal", "general".

Available tools: execute_command, read_file, write_file, list_directory, open_application,
screenshot, mouse_move, mouse_click, keyboard_type, keyboard_shortcut, get_screen_info,
open_gmail, draft_email, create_call_report, create_order_note, open_kindle, search_web, fetch_url, get_news,
remember, recall, forget, add_task, get_tasks, complete_task, save_contact, get_contacts,
semantic_remember, semantic_recall,
add_pipeline_item, update_pipeline_item, log_pipeline_activity, get_pipeline_items, get_revenue_dashboard,
list_external_integrations, crm_upsert_contact, crm_create_opportunity, voip_place_call,
get_foundation_readiness_text,
spotify_play, spotify_pause, spotify_resume, spotify_next, spotify_prev, spotify_current,
spotify_volume, youtube_play, youtube_search,
gmail_switch_account, gmail_list_accounts, gmail_purge, gmail_purge_label, gmail_purge_sender, gmail_purge_older_than, gmail_empty_trash, gmail_smart_cleanup,
remind_me, get_reminders, cancel_reminder, morning_brief,
clipboard_read, clipboard_write, get_active_window, focus_window,
read_screen_text, calendar_events, send_email, gmail_scan_inbox, get_weather, github.
Code ops: test_targeted, lint_fix, typecheck_targeted, git_patch_summary.
External stubs: list_external_integrations, crm_upsert_contact, crm_create_opportunity, voip_place_call.
CRITICAL: NEVER claim to have done something you have not executed via a tool.
"""


# ── Tool definitions ───────────────────────────────────────────────────────────

TOOLS = [
    {
        "name": "execute_command",
        "description": "Run a PowerShell command. Returns stdout/stderr.",
        "input_schema": {"type": "object", "properties": {"command": {"type": "string"}, "cwd": {"type": "string"}}, "required": ["command"]},
    },
    {
        "name": "read_file",
        "description": "Read a file.",
        "input_schema": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]},
    },
    {
        "name": "write_file",
        "description": "Write a file. mode w=overwrite, a=append.",
        "input_schema": {"type": "object", "properties": {"path": {"type": "string"}, "content": {"type": "string"}, "mode": {"type": "string", "default": "w"}}, "required": ["path", "content"]},
    },
    {
        "name": "list_directory",
        "description": "List directory contents.",
        "input_schema": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]},
    },
    {
        "name": "open_application",
        "description": "Open an app, file, or URL.",
        "input_schema": {"type": "object", "properties": {"target": {"type": "string"}}, "required": ["target"]},
    },
    {
        "name": "screenshot",
        "description": "Take a screenshot.",
        "input_schema": {"type": "object", "properties": {"save_path": {"type": "string"}}},
    },
    {
        "name": "mouse_move",
        "description": "Move mouse to x, y.",
        "input_schema": {"type": "object", "properties": {"x": {"type": "integer"}, "y": {"type": "integer"}, "duration": {"type": "number", "default": 0.3}}, "required": ["x", "y"]},
    },
    {
        "name": "mouse_click",
        "description": "Click mouse at x, y.",
        "input_schema": {"type": "object", "properties": {"x": {"type": "integer"}, "y": {"type": "integer"}, "button": {"type": "string", "default": "left"}, "clicks": {"type": "integer", "default": 1}}, "required": ["x", "y"]},
    },
    {
        "name": "keyboard_type",
        "description": "Type text.",
        "input_schema": {"type": "object", "properties": {"text": {"type": "string"}, "interval": {"type": "number", "default": 0.03}}, "required": ["text"]},
    },
    {
        "name": "keyboard_shortcut",
        "description": "Press a shortcut, e.g. ctrl+c.",
        "input_schema": {"type": "object", "properties": {"keys": {"type": "string"}}, "required": ["keys"]},
    },
    {
        "name": "get_screen_info",
        "description": "Get screen resolution and current mouse position.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "open_gmail",
        "description": "Open Gmail. Optionally pre-fill a compose window.",
        "input_schema": {"type": "object", "properties": {"to": {"type": "string"}, "subject": {"type": "string"}, "body": {"type": "string"}, "compose": {"type": "boolean", "default": False}}},
    },
    {
        "name": "draft_email",
        "description": "Write an email and open it in Gmail compose.",
        "input_schema": {"type": "object", "properties": {"to": {"type": "string"}, "subject": {"type": "string"}, "body": {"type": "string"}}, "required": ["subject", "body"]},
    },
    {
        "name": "create_call_report",
        "description": "Generate a call report and save it to Documents.",
        "input_schema": {"type": "object", "properties": {"contact_name": {"type": "string"}, "company": {"type": "string"}, "call_date": {"type": "string"}, "summary": {"type": "string"}, "action_items": {"type": "string"}, "outcome": {"type": "string"}, "next_steps": {"type": "string"}}, "required": ["contact_name", "summary"]},
    },
    {
        "name": "create_order_note",
        "description": "Generate an order note and save it to Documents.",
        "input_schema": {"type": "object", "properties": {"customer": {"type": "string"}, "order_details": {"type": "string"}, "quantity": {"type": "string"}, "value": {"type": "string"}, "notes": {"type": "string"}, "follow_up": {"type": "string"}}, "required": ["customer", "order_details"]},
    },
    {
        "name": "open_kindle",
        "description": "Open the Kindle app or a specific ebook file.",
        "input_schema": {"type": "object", "properties": {"book_title": {"type": "string"}, "file_path": {"type": "string"}}},
    },
    {
        "name": "search_web",
        "description": (
            "Search the web. If PERPLEXITY_API_KEY is set, returns a real AI-synthesised answer with citations. "
            "Otherwise opens a Google search in the browser. Use for current events, facts, prices, how-to questions."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query":  {"type": "string", "description": "What to search for."},
                "detail": {"type": "boolean", "description": "If true, request a more detailed answer (uses more tokens). Default false."},
            },
            "required": ["query"],
        },
    },
    {
        "name": "fetch_url",
        "description": (
            "Fetch the text content of any URL and return it so you can read it. "
            "Use to read news articles, documentation pages, RSS feeds, or any webpage. "
            "Returns up to 4000 characters of cleaned plain text. "
            "Prefer this over search_web when you need actual article content, not just a summary."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "url":    {"type": "string", "description": "Full URL to fetch (must include https://)."},
                "max_chars": {"type": "integer", "description": "Max characters to return. Default 4000."},
            },
            "required": ["url"],
        },
    },
    {
        "name": "get_news",
        "description": (
            "Get current news headlines with titles, sources, and links. "
            "Uses Google News RSS — no API key required, always returns real current stories. "
            "Use for 'what's in the news', 'top stories', or topic-specific news like 'tech news' or 'sports headlines'. "
            "Returns 8-10 real headlines with clickable links."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "topic": {"type": "string", "description": "News topic or search query. Leave empty for top headlines."},
                "count": {"type": "integer", "description": "Number of headlines to return. Default 8, max 15."},
            },
        },
    },
    {
        "name": "get_weather",
        "description": "Get current weather and today's forecast for a location. Defaults to Ryan's home location if not specified.",
        "input_schema": {
            "type": "object",
            "properties": {
                "location": {"type": "string", "description": "City name or 'lat,lon'. Omit to use default location from WEATHER_LOCATION env var."},
                "units":    {"type": "string", "description": "metric (°C) or imperial (°F). Default imperial."},
            },
        },
    },
    # ── Memory tools ───────────────────────────────────────────────────────────
    {
        "name": "remember",
        "description": "Store a fact in persistent memory. Use proactively when Master Ryan tells you something worth keeping between sessions.",
        "input_schema": {"type": "object", "properties": {"key": {"type": "string"}, "value": {"type": "string"}, "category": {"type": "string", "default": "general"}}, "required": ["key", "value"]},
    },
    {
        "name": "recall",
        "description": "Search persistent memory for stored facts. Use when you need to look something up that Master Ryan may have told you before.",
        "input_schema": {"type": "object", "properties": {"query": {"type": "string"}, "category": {"type": "string"}}},
    },
    {
        "name": "semantic_remember",
        "description": "Store a memory in semantic vector memory for meaning-based recall.",
        "input_schema": {
            "type": "object",
            "properties": {
                "key": {"type": "string"},
                "value": {"type": "string"},
                "category": {"type": "string", "default": "general"},
            },
            "required": ["key", "value"],
        },
    },
    {
        "name": "semantic_recall",
        "description": "Recall relevant memory by semantic similarity (not keyword match).",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "category": {"type": "string"},
                "limit": {"type": "integer", "default": 5},
            },
            "required": ["query"],
        },
    },
    {
        "name": "forget",
        "description": "Delete a fact from persistent memory.",
        "input_schema": {"type": "object", "properties": {"key": {"type": "string"}}, "required": ["key"]},
    },
    {
        "name": "add_task",
        "description": "Add a task to Master Ryan's persistent task list.",
        "input_schema": {"type": "object", "properties": {"task": {"type": "string"}, "due_date": {"type": "string"}}, "required": ["task"]},
    },
    {
        "name": "get_tasks",
        "description": "Get tasks from Master Ryan's task list.",
        "input_schema": {"type": "object", "properties": {"status": {"type": "string", "default": "pending"}}},
    },
    {
        "name": "complete_task",
        "description": "Mark a task as complete by its numeric ID.",
        "input_schema": {"type": "object", "properties": {"task_id": {"type": "integer"}}, "required": ["task_id"]},
    },
    {
        "name": "save_contact",
        "description": "Save or update a contact in the persistent address book.",
        "input_schema": {"type": "object", "properties": {"name": {"type": "string"}, "company": {"type": "string"}, "email": {"type": "string"}, "phone": {"type": "string"}, "notes": {"type": "string"}}, "required": ["name"]},
    },
    {
        "name": "get_contacts",
        "description": "Search or list contacts in the address book.",
        "input_schema": {"type": "object", "properties": {"search": {"type": "string"}}},
    },
    {
        "name": "add_pipeline_item",
        "description": "Add a lead/opportunity to the revenue pipeline.",
        "input_schema": {
            "type": "object",
            "properties": {
                "title": {"type": "string"},
                "company": {"type": "string"},
                "contact_name": {"type": "string"},
                "stage": {"type": "string", "default": "new_lead"},
                "value": {"type": "number", "default": 0},
                "confidence": {"type": "integer", "default": 30},
                "next_action": {"type": "string"},
                "due_date": {"type": "string"},
                "source": {"type": "string"},
                "notes": {"type": "string"},
            },
            "required": ["title"],
        },
    },
    {
        "name": "update_pipeline_item",
        "description": "Update stage, value, confidence, or status for a pipeline item.",
        "input_schema": {
            "type": "object",
            "properties": {
                "item_id": {"type": "integer"},
                "stage": {"type": "string"},
                "value": {"type": "number"},
                "confidence": {"type": "integer"},
                "next_action": {"type": "string"},
                "due_date": {"type": "string"},
                "status": {"type": "string"},
                "notes": {"type": "string"},
            },
            "required": ["item_id"],
        },
    },
    {
        "name": "log_pipeline_activity",
        "description": "Log a note or activity entry against a pipeline item.",
        "input_schema": {
            "type": "object",
            "properties": {
                "item_id": {"type": "integer"},
                "note": {"type": "string"},
                "activity_type": {"type": "string", "default": "note"},
            },
            "required": ["item_id", "note"],
        },
    },
    {
        "name": "get_pipeline_items",
        "description": "List pipeline items by stage and/or status.",
        "input_schema": {
            "type": "object",
            "properties": {
                "stage": {"type": "string"},
                "status": {"type": "string", "default": "open"},
                "limit": {"type": "integer", "default": 30},
            },
        },
    },
    {
        "name": "get_revenue_dashboard",
        "description": "Get a concise revenue and pipeline dashboard summary.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "list_external_integrations",
        "description": "List readiness for external CRM and VoIP integrations.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "crm_upsert_contact",
        "description": "Create or update a contact in an external CRM provider (stub).",
        "input_schema": {
            "type": "object",
            "properties": {
                "provider": {"type": "string", "description": "hubspot|salesforce|gohighlevel|zoho"},
                "name": {"type": "string"},
                "email": {"type": "string"},
                "phone": {"type": "string"},
                "company": {"type": "string"},
                "notes": {"type": "string"},
                "dry_run": {"type": "boolean", "default": True},
            },
            "required": ["provider", "name"],
        },
    },
    {
        "name": "crm_create_opportunity",
        "description": "Create an opportunity in an external CRM provider (stub).",
        "input_schema": {
            "type": "object",
            "properties": {
                "provider": {"type": "string", "description": "hubspot|salesforce|gohighlevel|zoho"},
                "title": {"type": "string"},
                "value": {"type": "number", "default": 0},
                "stage": {"type": "string", "default": "new"},
                "company": {"type": "string"},
                "contact_name": {"type": "string"},
                "notes": {"type": "string"},
                "dry_run": {"type": "boolean", "default": True},
            },
            "required": ["provider", "title"],
        },
    },
    {
        "name": "voip_place_call",
        "description": "Prepare a VoIP outbound call via configured provider (stub).",
        "input_schema": {
            "type": "object",
            "properties": {
                "provider": {"type": "string", "description": "twilio|generic"},
                "to_number": {"type": "string"},
                "from_number": {"type": "string"},
                "contact_name": {"type": "string"},
                "purpose": {"type": "string"},
                "dry_run": {"type": "boolean", "default": True},
            },
            "required": ["to_number"],
        },
    },
    {
        "name": "get_foundation_readiness",
        "description": "Get a full readiness report for planned integrations and account connections.",
        "input_schema": {"type": "object", "properties": {}},
    },
    # ── Spotify ────────────────────────────────────────────────────────────────
    {
        "name": "spotify_play",
        "description": "Search Spotify and play the top result (track, artist, or playlist).",
        "input_schema": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]},
    },
    {
        "name": "spotify_pause",
        "description": "Pause Spotify playback.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "spotify_resume",
        "description": "Resume Spotify playback.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "spotify_next",
        "description": "Skip to the next track on Spotify.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "spotify_prev",
        "description": "Go back to the previous track on Spotify.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "spotify_current",
        "description": "Get the currently playing track on Spotify.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "spotify_volume",
        "description": "Set Spotify volume (0–100).",
        "input_schema": {"type": "object", "properties": {"level": {"type": "integer", "minimum": 0, "maximum": 100}}, "required": ["level"]},
    },
    # ── YouTube ────────────────────────────────────────────────────────────────
    {
        "name": "youtube_play",
        "description": "Find and open a YouTube video in the browser. Accepts a search query or direct URL.",
        "input_schema": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]},
    },
    {
        "name": "youtube_search",
        "description": "Search YouTube and return the top 5 results with titles and URLs.",
        "input_schema": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]},
    },
    # ── Gmail purge ────────────────────────────────────────────────────────────
    {
        "name": "gmail_purge",
        "description": "Move emails matching a Gmail search query to trash. Supports any Gmail search syntax.",
        "input_schema": {"type": "object", "properties": {"query": {"type": "string"}, "max_results": {"type": "integer", "default": 500}}, "required": ["query"]},
    },
    {
        "name": "gmail_purge_label",
        "description": "Move all emails in a Gmail label to trash. Labels: promotions, social, updates, forums, spam, inbox.",
        "input_schema": {"type": "object", "properties": {"label": {"type": "string"}}, "required": ["label"]},
    },
    {
        "name": "gmail_purge_sender",
        "description": "Move all emails from a sender email address to trash.",
        "input_schema": {"type": "object", "properties": {"email": {"type": "string"}}, "required": ["email"]},
    },
    {
        "name": "gmail_purge_older_than",
        "description": "Move emails older than N days to trash.",
        "input_schema": {"type": "object", "properties": {"days": {"type": "integer"}}, "required": ["days"]},
    },
    {
        "name": "gmail_empty_trash",
        "description": "Permanently delete all messages in the Gmail trash. Irreversible.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "gmail_switch_account",
        "description": "Switch the active Gmail account. Use before any gmail_ tool to target a different inbox. Accepts alias (main, sales, personal) or the email address.",
        "input_schema": {"type": "object", "properties": {"alias": {"type": "string"}}, "required": ["alias"]},
    },
    {
        "name": "gmail_list_accounts",
        "description": "List all configured Gmail accounts and show which is currently active.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "gmail_smart_cleanup",
        "description": (
            "Run a standard inbox cleanup sequence: moves unsubscribe mail, no-reply bulk mail, "
            "newsletters, and old mail (1yr+) to trash, and marks old unread mail (30d+) as read. "
            "Use when Master Ryan says 'clean up my inbox' or similar."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "max_per_step": {
                    "type": "integer",
                    "description": "Max emails to process per cleanup step. Default 500.",
                    "default": 500,
                }
            },
        },
    },
    # ── Reminders & Tasks ──────────────────────────────────────────────────────
    {
        "name": "remind_me",
        "description": "Schedule a reminder for Master Ryan at a specific time. Accepts natural language times like '3pm', 'tomorrow at 10am', 'in 30 minutes', etc.",
        "input_schema": {"type": "object", "properties": {"message": {"type": "string"}, "time": {"type": "string"}}, "required": ["message", "time"]},
    },
    {
        "name": "get_reminders",
        "description": "Get all active reminders scheduled for Master Ryan.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "cancel_reminder",
        "description": "Cancel a scheduled reminder by its ID. Use get_reminders to see active reminder IDs.",
        "input_schema": {"type": "object", "properties": {"reminder_id": {"type": "string"}}, "required": ["reminder_id"]},
    },
    {
        "name": "morning_brief",
        "description": (
            "Generate a morning brief for Master Ryan. "
            "Pulls today's reminders, pending tasks, recent memory context (work + projects), "
            "and Gmail unread counts. Returns a formatted summary and optionally fires a toast notification. "
            "Use this first thing each morning or whenever Ryan asks for a daily status."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "include_gmail": {
                    "type": "boolean",
                    "description": "Include Gmail unread counts (requires Gmail auth). Default true.",
                },
                "notify": {
                    "type": "boolean",
                    "description": "Fire a Windows toast notification with a one-line summary. Default false.",
                },
            },
        },
    },
    # ── Screen OCR ────────────────────────────────────────────────────────────
    {
        "name": "read_screen_text",
        "description": (
            "Take a screenshot of the current screen (or a region) and extract all visible text using Claude vision. "
            "Use when Ryan says 'read what's on my screen', 'what does that error say', or references something visible "
            "that he hasn't explicitly typed out."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "region": {
                    "type": "string",
                    "description": "Optional screen region: 'full' (default), 'top', 'bottom', 'left', 'right', or 'active_window'.",
                },
                "instruction": {
                    "type": "string",
                    "description": "What to extract or focus on. E.g. 'extract the error message', 'list all visible text'. Defaults to extract all text.",
                },
            },
        },
    },
    # ── Calendar ──────────────────────────────────────────────────────────────
    {
        "name": "calendar_events",
        "description": "Fetch upcoming Google Calendar events. Use for morning briefs, scheduling questions, or 'what do I have today/this week'.",
        "input_schema": {
            "type": "object",
            "properties": {
                "days": {
                    "type": "integer",
                    "description": "Number of days ahead to look. 1=today, 7=this week. Default 1.",
                },
                "max_results": {
                    "type": "integer",
                    "description": "Max events to return. Default 20.",
                },
                "calendar_id": {
                    "type": "string",
                    "description": "Calendar ID. 'primary' for main calendar. Default 'primary'.",
                },
            },
        },
    },
    # ── Inbox scan ────────────────────────────────────────────────────────────
    {
        "name": "gmail_scan_inbox",
        "description": (
            "Scan Ryan's unread Gmail inbox, classify emails using AI, and auto-create tasks and reminders. "
            "Detects: bills due, interviews, client requests, client messages, calendar invites, and action items. "
            "Use this when Ryan says 'check my inbox', 'scan my emails', or 'what do I need to action'. "
            "Set dry_run=true to preview what would be created without writing anything."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "max_emails": {"type": "integer", "description": "Max unread emails to scan. Default 30."},
                "account":    {"type": "string",  "description": "Gmail account alias: main, sales, personal. Defaults to active account."},
                "auto_task":  {"type": "boolean", "description": "Auto-create tasks from actionable emails. Default true."},
                "dry_run":    {"type": "boolean", "description": "Classify and report without writing tasks. Default false."},
            },
        },
    },
    # ── Send Email ────────────────────────────────────────────────────────────
    {
        "name": "send_email",
        "description": (
            "Send an email from Ryan's Gmail account. "
            "Use after drafting and confirming with Ryan. "
            "Always confirm the recipient, subject, and body before calling this."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "to":      {"type": "string", "description": "Recipient email address (or comma-separated list)."},
                "subject": {"type": "string", "description": "Email subject line."},
                "body":    {"type": "string", "description": "Plain-text email body."},
                "cc":      {"type": "string", "description": "Optional CC addresses, comma-separated."},
                "account": {
                    "type": "string",
                    "description": "Gmail account alias to send from: main, sales, or personal. Defaults to currently active account.",
                },
            },
            "required": ["to", "subject", "body"],
        },
    },
    # ── Clipboard ─────────────────────────────────────────────────────────────
    {
        "name": "clipboard_read",
        "description": "Read the current contents of the Windows clipboard. Use this when Ryan says 'summarize what I copied', 'what's on my clipboard', or pastes context implicitly.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "clipboard_write",
        "description": "Write text to the Windows clipboard so Ryan can paste it anywhere.",
        "input_schema": {
            "type": "object",
            "properties": {
                "text": {"type": "string", "description": "Text to place on the clipboard."},
            },
            "required": ["text"],
        },
    },
    # ── Window context ────────────────────────────────────────────────────────
    {
        "name": "get_active_window",
        "description": "Return the title and process name of the window Ryan currently has focused. Use this to understand what Ryan is working on without asking.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "focus_window",
        "description": "Bring a window to the foreground by application name or partial title. E.g. 'Chrome', 'VS Code', 'Spotify'.",
        "input_schema": {
            "type": "object",
            "properties": {
                "app": {"type": "string", "description": "Application name or partial window title to focus."},
            },
            "required": ["app"],
        },
    },
    # ── GitHub ───────────────────────────────────────────────────────────────
    {
        "name": "github",
        "description": "Interact with GitHub: list repos/issues/PRs, create issue, or fetch a file.",
        "input_schema": {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "description": "list_repos|list_issues|create_issue|list_prs|get_file",
                },
                "repo": {"type": "string", "description": "owner/repo format"},
                "title": {"type": "string"},
                "body": {"type": "string"},
                "path": {"type": "string"},
                "ref": {"type": "string", "description": "branch, tag, or commit SHA for get_file"},
            },
            "required": ["action"],
        },
    },
    # ── Run Python ───────────────────────────────────────────────────────────
    {
        "name": "run_python",
        "description": "Execute a Python snippet and return stdout/stderr. Use for calculations, data transforms, quick scripts, and anything that benefits from real computation. Runs in a subprocess so it cannot corrupt Guppy's state.",
        "input_schema": {
            "type": "object",
            "properties": {
                "code": {"type": "string", "description": "Python code to execute."},
                "timeout": {"type": "integer", "description": "Max seconds to wait. Default 10."},
            },
            "required": ["code"],
        },
    },
    # ── Code Ops ────────────────────────────────────────────────────────────
    {
        "name": "test_targeted",
        "description": "Run targeted pytest tests on a file/path with optional -k filter. Use for fast verification after code edits.",
        "input_schema": {
            "type": "object",
            "properties": {
                "target": {"type": "string", "description": "Test file, folder, or node id (e.g. tests/test_api.py::test_status)."},
                "k": {"type": "string", "description": "Optional pytest -k expression."},
                "maxfail": {"type": "integer", "description": "Stop after N failures. Default 1.", "default": 1},
                "quiet": {"type": "boolean", "description": "Use -q output. Default true.", "default": True},
            },
            "required": ["target"],
        },
    },
    {
        "name": "lint_fix",
        "description": "Run ruff lint checks with optional --fix against one or more paths.",
        "input_schema": {
            "type": "object",
            "properties": {
                "paths": {
                    "type": "array",
                    "description": "Files/directories to lint. Default ['.'].",
                    "items": {"type": "string"},
                },
                "fix": {"type": "boolean", "description": "Apply auto-fixes. Default true.", "default": True},
            },
        },
    },
    {
        "name": "typecheck_targeted",
        "description": "Run mypy type checking on one target path/module.",
        "input_schema": {
            "type": "object",
            "properties": {
                "target": {"type": "string", "description": "Path or module to type-check."},
                "strict": {"type": "boolean", "description": "Enable strict mode for this run.", "default": False},
            },
            "required": ["target"],
        },
    },
    {
        "name": "git_patch_summary",
        "description": "Summarize git changes with status and compact diff stats.",
        "input_schema": {
            "type": "object",
            "properties": {
                "staged": {"type": "boolean", "description": "Include staged diff stats.", "default": True},
                "unstaged": {"type": "boolean", "description": "Include unstaged diff stats.", "default": True},
                "name_only": {"type": "boolean", "description": "Include changed file lists.", "default": True},
            },
        },
    },
    # ── Windows Notification ─────────────────────────────────────────────────
    {
        "name": "notify",
        "description": "Send a Windows 11 toast notification to Ryan. Use for async alerts, reminders that fire mid-task, or when completing long background work.",
        "input_schema": {
            "type": "object",
            "properties": {
                "title":   {"type": "string", "description": "Notification title."},
                "message": {"type": "string", "description": "Notification body."},
                "duration": {"type": "string", "enum": ["short", "long"], "description": "Display duration. Default: short."},
            },
            "required": ["title", "message"],
        },
    },
    # ── Web Summarize ────────────────────────────────────────────────────────
    {
        "name": "web_summarize",
        "description": "Fetch a URL and return a summary or extracted content. Uses Firecrawl if FIRECRAWL_API_KEY is set (handles JS-heavy pages), otherwise falls back to plain HTTP + Claude summary.",
        "input_schema": {
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "The URL to fetch and summarize."},
                "instruction": {"type": "string", "description": "What to extract or summarize. Default: summarize the main content."},
            },
            "required": ["url"],
        },
    },
]


# ── Network check ──────────────────────────────────────────────────────────────

def is_online() -> bool:
    """Return True if we can reach the internet."""
    import socket
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(3)
        s.connect(("8.8.8.8", 53))
        s.close()
        return True
    except OSError:
        return False


def check_ollama(model: str) -> tuple[bool, str]:
    """Check whether Ollama is running and `model` is available.

    Returns (ok: bool, error_msg: str).
    error_msg is empty when ok is True.
    """
    import urllib.request, urllib.error, json as _json
    try:
        with urllib.request.urlopen(
            "http://localhost:11434/api/tags", timeout=3
        ) as r:
            data = _json.loads(r.read())
        names = [m.get("name", "") for m in data.get("models", [])]
        # Match exact name OR name without tag (e.g. "guppy" matches "guppy:latest")
        model_base = model.split(":")[0]
        if any(n == model or n.split(":")[0] == model_base for n in names):
            return True, ""
        available = ", ".join(names) if names else "none"
        return False, (
            f"Ollama is running but the '{model}' model is not available.\n"
            f"Available: {available}\n"
            f"Run:  ollama pull {model}"
        )
    except urllib.error.URLError:
        return False, (
            "Ollama is not running.\n"
            "Start it with:  ollama serve\n"
            "Or switch to Claude mode with the button above."
        )
    except Exception as e:
        return False, f"Could not contact Ollama: {e}"


# ── Startup system prompt ─────────────────────────────────────────────────────

def _needs_memory_context(query: str) -> bool:
    """Determine if query requires memory context based on keywords."""
    if not query:
        return True  # Default to including memory for safety
    
    memory_keywords = [
        'remember', 'recall', 'previously', 'before', 'last time',
        'you said', 'i told you', 'earlier', 'history', 'what about',
        'do you know', 'have we', 'did i', 'as i said', 'like before',
        'same as', 'similar to', 'continue', 'following up', 'yesterday',
        'last', 'previous', 'ago', 'past', 'recent', 'earlier today',
        'this morning', 'this afternoon', 'today', 'session', 'conversation'
    ]
    query_lower = query.lower()
    return any(keyword in query_lower for keyword in memory_keywords)

def get_startup_system(session_id: str = None, query_context: str = None) -> str:
    """
    Return the system prompt enriched with memory briefing and window context.
    Called fresh on every API request so context is always current.
    Pass `session_id` so recent-message recall excludes the live session.
    Pass `query_context` to conditionally include memory briefing.
    Falls back to the base SYSTEM if memory is unavailable.
    """
    try:
        system = SYSTEM

        # Add memory briefing conditionally based on query context
        if _MEM:
            try:
                needs_memory = _needs_memory_context(query_context)
                if needs_memory:
                    briefing = _mem.get_startup_context(exclude_session=session_id)
                    system += "\n\n" + briefing
            except Exception:
                pass
        
        # Add window context if daemon is available
        if DAEMON:
            try:
                from guppy_daemon import get_daemon_manager
                daemon = get_daemon_manager()
                if daemon.is_running:
                    context = daemon.window_watcher.get_enhanced_context()
                    if context.get("app") and context["app"] != "unknown":
                        system += f"\n\nCurrent context: Master Ryan is currently focused on {context['app']}."
                        if context.get("title"):
                            system += f" The active window is titled '{context['title']}'."
                        if context.get("help"):
                            system += f" {context['help']}"
            except Exception as e:
                logger.debug(f"Window context error: {e}")
        
        return system
    except Exception:
        return SYSTEM


# ── Ollama format converter ───────────────────────────────────────────────────

def to_ollama_tools(tools: list) -> list:
    """
    Convert Anthropic-format tool definitions to Ollama's function-calling format.

    Anthropic: {"name": ..., "description": ..., "input_schema": {...}}
    Ollama:    {"type": "function", "function": {"name": ..., "description": ..., "parameters": {...}}}
    """
    return [
        {
            "type": "function",
            "function": {
                "name": t["name"],
                "description": t["description"],
                "parameters": t["input_schema"],
            },
        }
        for t in tools
    ]


# ── Tool runner ────────────────────────────────────────────────────────────────

def run_tool(name: str, inp: dict):
    """
    Execute a named tool and return its result. Wraps _exec_tool with SAFE_MODE
    gating and TOOL_LOG recording.

    Screenshots return a dict:
        {"_screenshot": True, "path": str, "image_base64": str, "size": str}
    so callers that support vision (Claude API) can pass the image back.
    All other tools return a plain string.
    """
    if not isinstance(inp, dict):
        inp = {}

    started = time.perf_counter()

    if SAFE_MODE:
        entry = {
            "time": datetime.now().strftime("%H:%M:%S"),
            "tool": name,
            "args": str(inp)[:80],
            "result": "[SAFE MODE — blocked]",
        }
        TOOL_LOG.append(entry)
        _record_tool_call(name, (time.perf_counter() - started) * 1000.0, "blocked", "safe_mode")
        return f"[SAFE MODE ACTIVE] Tool blocked: {name}"

    if BETA_RESTRICTED_MODE and name not in BETA_TOOL_ALLOWLIST:
        reason = (
            f"Tool {name} is blocked by beta restricted policy. "
            "Allowed tools are limited for remote tester safety."
        )
        _record_tool_call(name, (time.perf_counter() - started) * 1000.0, "blocked", "beta_restricted_policy")
        TOOL_LOG.append({
            "time": datetime.now().strftime("%H:%M:%S"),
            "tool": name,
            "args": str(inp)[:80],
            "result": reason[:150],
        })
        return f"Error: {reason}"

    input_error = _validate_tool_input(name, inp)
    if input_error:
        msg = f"Error: {input_error}"
        _record_tool_call(name, (time.perf_counter() - started) * 1000.0, "error", msg)
        TOOL_LOG.append({
            "time": datetime.now().strftime("%H:%M:%S"),
            "tool": name,
            "args": str(inp)[:80],
            "result": msg[:150],
        })
        return msg

    blocked, block_reason = _is_tool_blocked(name)
    if blocked:
        _record_tool_call(name, (time.perf_counter() - started) * 1000.0, "blocked", block_reason)
        TOOL_LOG.append({
            "time": datetime.now().strftime("%H:%M:%S"),
            "tool": name,
            "args": str(inp)[:80],
            "result": block_reason[:150],
        })
        return f"Error: {block_reason}"

    state = "success"
    error_msg = ""
    inline_tools = {"semantic_remember", "semantic_recall"}
    try:
        if name in inline_tools:
            result = _exec_tool(name, inp)
        else:
            fut = _TOOL_EXECUTOR.submit(_exec_tool, name, inp)
            result = fut.result(timeout=TOOL_EXEC_TIMEOUT_SECONDS)
    except FuturesTimeoutError:
        state = "timeout"
        error_msg = f"Tool {name} exceeded {TOOL_EXEC_TIMEOUT_SECONDS}s timeout"
        _mark_tool_failure(name, error_msg)
        result = f"Error: {error_msg}"
    except Exception as e:
        state = "error"
        error_msg = f"Tool execution failure: {e}"
        _mark_tool_failure(name, error_msg)
        result = f"Error: {error_msg}"
    else:
        if isinstance(result, str) and result.lower().startswith("error"):
            state = "error"
            error_msg = result[:180]
            _mark_tool_failure(name, error_msg)
        else:
            _mark_tool_success(name)
    
    # Memory optimization: bound tool result sizes
    if isinstance(result, str) and len(result) > TOOL_MAX_OUTPUT_CHARS:
        result = result[:TOOL_MAX_OUTPUT_CHARS] + f"\n\n[Output truncated — {len(result)} chars total]"
    elif isinstance(result, dict) and "image_base64" in result:
        # Screenshots already optimized (base64 removed), but bound other fields
        for key, value in result.items():
            if isinstance(value, str) and len(value) > 500:
                result[key] = value[:500] + "..."

    _record_tool_call(
        name,
        (time.perf_counter() - started) * 1000.0,
        state,
        error_msg,
    )
    
    TOOL_LOG.append({
        "time": datetime.now().strftime("%H:%M:%S"),
        "tool": name,
        "args": str(inp)[:80],
        "result": str(result)[:150] if not isinstance(result, dict) else str(result.get("size", "screenshot")),
    })
    return result


def _morning_brief(include_gmail: bool = True, notify: bool = False) -> str:
    """Assemble and return a morning brief string for Master Ryan."""
    now      = datetime.now()
    day_str  = now.strftime("%A, %d %B %Y")
    time_str = now.strftime("%H:%M")
    sep      = "─" * 44

    lines: list[str] = [
        f"Good morning, Master Ryan.",
        sep,
        f"TODAY  {day_str}   {time_str}",
        "",
    ]

    # ── Weather ───────────────────────────────────────────────────────────────
    owm_key  = os.environ.get("OPENWEATHERMAP_API_KEY", "")
    location = os.environ.get("WEATHER_LOCATION", "")
    if owm_key and location:
        try:
            weather_result = _exec_tool("get_weather", {"location": location})
            lines.append("WEATHER")
            for wl in weather_result.splitlines():
                lines.append(f"  {wl}" if not wl.startswith("  ") else wl)
        except Exception as e:
            lines.append(f"WEATHER  — unavailable ({e})")
        lines.append("")

    # ── Reminders ─────────────────────────────────────────────────────────────
    if DAEMON:
        try:
            manager   = get_daemon_manager()
            reminders = manager.task_scheduler.get_scheduled_reminders()
            if reminders:
                lines.append(f"REMINDERS  ({len(reminders)})")
                for rem in reminders.values():
                    # next_run is an ISO string — grab HH:MM for readability
                    raw   = rem.get("next_run", "")
                    when  = raw[11:16] if len(raw) >= 16 else raw
                    lines.append(f"  •  {when}  {rem['message']}")
            else:
                lines.append("REMINDERS  — none scheduled today")
        except Exception as e:
            lines.append(f"REMINDERS  — unavailable ({e})")
        lines.append("")

    # ── Tasks ──────────────────────────────────────────────────────────────────
    if _MEM:
        try:
            tasks_raw = _mem.get_tasks("pending")
            if "No pending" not in tasks_raw:
                task_lines = [t.strip() for t in tasks_raw.strip().splitlines() if t.strip()]
                lines.append(f"TASKS  ({len(task_lines)} pending)")
                for t in task_lines[:10]:
                    # strip leading [id] tag for readability
                    label = t.split("] ", 1)[-1] if "] " in t else t
                    lines.append(f"  •  {label}")
                if len(task_lines) > 10:
                    lines.append(f"  … and {len(task_lines) - 10} more")
            else:
                lines.append("TASKS  — none pending")
        except Exception as e:
            lines.append(f"TASKS  — unavailable ({e})")
        lines.append("")

    # ── Calendar ──────────────────────────────────────────────────────────────
    try:
        from media_tools import calendar_events as _cal_events
        cal_result = _cal_events(days=1, max_results=15)
        lines.append("CALENDAR  TODAY")
        if cal_result.startswith("No events") or cal_result.startswith("Google Calendar credentials"):
            lines.append(f"  {cal_result}")
        else:
            for cl in cal_result.splitlines()[1:]:   # skip header line
                lines.append(cl)
    except Exception as e:
        lines.append(f"CALENDAR  — unavailable ({e})")
    lines.append("")

    # ── Gmail unread counts ────────────────────────────────────────────────────
    if include_gmail:
        try:
            from media_tools import gmail_unread_count, _GMAIL_ACCOUNTS
            gmail_lines: list[str] = []
            for alias in _GMAIL_ACCOUNTS:
                count, err = gmail_unread_count(alias)
                if err:
                    gmail_lines.append(f"  {alias:10s}  (not connected)")
                else:
                    gmail_lines.append(f"  {alias:10s}  {count} unread")
            if gmail_lines:
                lines.append("GMAIL")
                lines.extend(gmail_lines)
        except Exception as e:
            lines.append(f"GMAIL  — unavailable ({e})")
        lines.append("")

    # ── Inbox action items (bills, interviews, client requests) ───────────────
    if include_gmail:
        try:
            from media_tools import gmail_scan_inbox
            scan = gmail_scan_inbox(max_emails=20, auto_task=True, dry_run=False)
            # Only show actionable lines — skip FYI and empty lines
            action_lines = [
                l for l in scan.splitlines()
                if any(icon in l for icon in ("💳", "🎤", "📋", "💬", "📅", "⚡"))
                or l.strip().startswith("→") or l.strip().startswith("Summary")
            ]
            if action_lines:
                lines.append("INBOX ACTION ITEMS")
                lines.extend(f"  {l}" for l in action_lines[:20])
            else:
                lines.append("INBOX ACTION ITEMS  — nothing actionable")
        except Exception as e:
            lines.append(f"INBOX SCAN  — unavailable ({e})")
        lines.append("")

    # ── Memory context: work + projects ───────────────────────────────────────
    if _MEM:
        context_items: list[str] = []
        for cat in ("work", "projects"):
            try:
                raw = _mem.recall(category=cat)
                if "Nothing found" not in raw:
                    context_items.extend(raw.strip().splitlines()[:3])
            except Exception:
                pass
        if context_items:
            lines.append("RECENT CONTEXT")
            for item in context_items[:6]:
                lines.append(f"  {item.strip()}")
            lines.append("")

    lines.append(sep)
    brief = "\n".join(lines)

    # ── Optional toast notification ────────────────────────────────────────────
    if notify and DAEMON:
        try:
            reminder_count = 0
            task_count     = 0
            if DAEMON:
                manager        = get_daemon_manager()
                reminder_count = len(manager.task_scheduler.get_scheduled_reminders())
            if _MEM:
                raw        = _mem.get_tasks("pending")
                task_count = len([t for t in raw.splitlines() if t.strip() and "No pending" not in t])
            cal_count = 0
            try:
                from media_tools import calendar_events as _c
                cal_lines = _c(days=1, max_results=20).splitlines()
                cal_count = max(0, len(cal_lines) - 1)
            except Exception:
                pass
            summary = (
                f"{reminder_count} reminder{'s' if reminder_count != 1 else ''}  •  "
                f"{task_count} task{'s' if task_count != 1 else ''} pending  •  "
                f"{cal_count} event{'s' if cal_count != 1 else ''} today"
            )
            get_daemon_manager().notifier.info(f"Morning Brief — {day_str}", summary)
        except Exception:
            pass

    return brief


def _exec_tool(name: str, inp: dict):
    """Internal tool executor — called by run_tool."""
    try:
        if name == "execute_command":
            r = subprocess.run(
                ["powershell", "-Command", inp["command"]],
                capture_output=True, text=True,
                cwd=inp.get("cwd"), timeout=60,
                encoding="utf-8", errors="replace",
            )
            parts = []
            if r.stdout.strip(): parts.append("STDOUT:\n" + r.stdout.strip())
            if r.stderr.strip(): parts.append("STDERR:\n" + r.stderr.strip())
            return "\n".join(parts) or f"Done (exit {r.returncode})"

        elif name == "read_file":
            p = Path(inp["path"])
            if not p.exists(): return f"Error: not found: {p}"
            c = p.read_text(encoding="utf-8", errors="replace")
            return c[:10000] + (f"\n[Truncated {len(c)} chars]" if len(c) > 10000 else "")

        elif name == "write_file":
            p = Path(inp["path"])
            p.parent.mkdir(parents=True, exist_ok=True)
            with open(p, inp.get("mode", "w"), encoding="utf-8") as f:
                f.write(inp["content"])
            return f"Written: {p}"

        elif name == "list_directory":
            p = Path(inp["path"])
            if not p.exists(): return f"Error: not found: {p}"
            items = [
                "📁 " + i.name + "/" if i.is_dir() else f"📄 {i.name} ({i.stat().st_size}b)"
                for i in sorted(p.iterdir())
            ]
            return str(p) + ":\n" + ("\n".join(items) or "Empty")

        elif name == "open_application":
            t = inp["target"]
            if t.startswith("http"):
                webbrowser.open(t)
            else:
                os.startfile(t)
            return f"Opened: {t}"

        elif name == "screenshot":
            if not PYA: return "Error: pip install pyautogui"
            sp = inp.get("save_path") or str(
                Path.home() / "Desktop" / f"guppy_{time.strftime('%H%M%S')}.png"
            )
            s = pyautogui.screenshot()
            s.save(sp)
            return {"_screenshot": True, "path": sp, "size": f"{s.size[0]}x{s.size[1]}"}

        elif name == "mouse_move":
            if not PYA: return "Error: pip install pyautogui"
            pyautogui.moveTo(inp["x"], inp["y"], duration=inp.get("duration", 0.3))
            return f"Moved to ({inp['x']}, {inp['y']})"

        elif name == "mouse_click":
            if not PYA: return "Error: pip install pyautogui"
            pyautogui.click(
                inp["x"], inp["y"],
                button=inp.get("button", "left"),
                clicks=inp.get("clicks", 1),
                interval=0.1,
            )
            return f"Clicked ({inp['x']}, {inp['y']})"

        elif name == "keyboard_type":
            if not PYA: return "Error: pip install pyautogui"
            pyautogui.write(inp["text"], interval=inp.get("interval", 0.03))
            return f"Typed: {repr(inp['text'])}"

        elif name == "keyboard_shortcut":
            if not PYA: return "Error: pip install pyautogui"
            pyautogui.hotkey(*[k.strip() for k in inp["keys"].lower().split("+")])
            return f"Pressed: {inp['keys']}"

        elif name == "get_screen_info":
            if not PYA: return "Error: pip install pyautogui"
            sz = pyautogui.size()
            pos = pyautogui.position()
            return f"Resolution: {sz.width}x{sz.height} | Mouse: ({pos.x}, {pos.y})"

        elif name == "open_gmail":
            if inp.get("compose") or inp.get("to") or inp.get("subject"):
                url = (
                    "https://mail.google.com/mail/?view=cm"
                    f"&to={urllib.parse.quote(inp.get('to', ''))}"
                    f"&su={urllib.parse.quote(inp.get('subject', ''))}"
                    f"&body={urllib.parse.quote(inp.get('body', ''))}"
                )
                webbrowser.open(url)
                return "Gmail compose opened"
            webbrowser.open("https://mail.google.com")
            return "Gmail opened"

        elif name == "draft_email":
            url = (
                "https://mail.google.com/mail/?view=cm"
                f"&to={urllib.parse.quote(inp.get('to', ''))}"
                f"&su={urllib.parse.quote(inp.get('subject', ''))}"
                f"&body={urllib.parse.quote(inp.get('body', ''))}"
            )
            webbrowser.open(url)
            return f"Email draft opened — Subject: {inp.get('subject', '')}"

        elif name == "create_call_report":
            REPORTS_DIR.mkdir(parents=True, exist_ok=True)
            date = inp.get("call_date", datetime.now().strftime("%Y-%m-%d"))
            contact = inp.get("contact_name", "Unknown")
            fpath = REPORTS_DIR / f"Call Report - {contact} - {date}.txt"
            fpath.write_text(
                f"CALL REPORT\n{'='*50}\n"
                f"Date: {date}\nContact: {contact}\nCompany: {inp.get('company','')}\n\n"
                f"SUMMARY\n{inp.get('summary','')}\n\n"
                f"OUTCOME\n{inp.get('outcome','')}\n\n"
                f"ACTION ITEMS\n{inp.get('action_items','')}\n\n"
                f"NEXT STEPS\n{inp.get('next_steps','')}\n\n"
                "Generated by Guppy",
                encoding="utf-8",
            )
            os.startfile(str(fpath))
            return f"Call report saved: {fpath}"

        elif name == "create_order_note":
            REPORTS_DIR.mkdir(parents=True, exist_ok=True)
            date = datetime.now().strftime("%Y-%m-%d")
            customer = inp.get("customer", "Unknown")
            fpath = REPORTS_DIR / f"Order Note - {customer} - {date}.txt"
            fpath.write_text(
                f"ORDER NOTE\n{'='*50}\n"
                f"Date: {date}\nCustomer: {customer}\n\n"
                f"ORDER DETAILS\n{inp.get('order_details','')}\n"
                f"Quantity: {inp.get('quantity','')}\nValue: {inp.get('value','')}\n\n"
                f"NOTES\n{inp.get('notes','')}\n\n"
                f"FOLLOW-UP\n{inp.get('follow_up','')}\n\n"
                "Generated by Guppy",
                encoding="utf-8",
            )
            os.startfile(str(fpath))
            return f"Order note saved: {fpath}"

        elif name == "open_kindle":
            fpath = inp.get("file_path", "")
            if fpath and Path(fpath).exists():
                os.startfile(fpath)
                return f"Opened: {fpath}"
            for kp in [
                Path.home() / "AppData/Local/Amazon/Kindle/application/Kindle.exe",
                Path("C:/Program Files/Amazon/Kindle/Kindle.exe"),
            ]:
                if kp.exists():
                    subprocess.Popen([str(kp)])
                    return "Kindle opened"
            subprocess.Popen(["explorer", "shell:AppsFolder\\Amazon.Kindle_ftchk03kv5yf0!App"])
            return "Kindle launched"

        elif name == "search_web":
            query  = inp["query"]
            detail = inp.get("detail", False)
            pplx_key = os.environ.get("PERPLEXITY_API_KEY", "")
            if pplx_key:
                try:
                    import urllib.request as _ureq, json as _json
                    payload = _json.dumps({
                        "model": "sonar",
                        "messages": [{"role": "user", "content": query}],
                        "max_tokens": 1024 if detail else 512,
                        "return_citations": True,
                    }).encode()
                    req = _ureq.Request(
                        "https://api.perplexity.ai/chat/completions",
                        data=payload,
                        headers={
                            "Authorization": f"Bearer {pplx_key}",
                            "Content-Type": "application/json",
                        },
                    )
                    with _ureq.urlopen(req, timeout=20) as r:
                        data = _json.loads(r.read())
                    answer = data["choices"][0]["message"]["content"]
                    citations = data.get("citations", [])
                    result = answer
                    if citations:
                        result += "\n\nSources:\n" + "\n".join(f"  [{i+1}] {c}" for i, c in enumerate(citations[:5]))
                    return result
                except Exception as e:
                    # Fall through to browser on API error
                    webbrowser.open(f"https://www.google.com/search?q={urllib.parse.quote(query)}")
                    return f"Perplexity error ({e}) — opened Google search for: {query}"
            else:
                webbrowser.open(f"https://www.google.com/search?q={urllib.parse.quote(query)}")
                return f"Opened Google search for: {query}  (set PERPLEXITY_API_KEY for AI answers)"

        elif name == "fetch_url":
            import urllib.request as _ureq, html as _html, re as _re
            url = inp.get("url", "").strip()
            max_chars = int(inp.get("max_chars") or 4000)
            if not url.startswith("http"):
                return "Error: URL must start with http:// or https://"
            try:
                req = _ureq.Request(url, headers={"User-Agent": "Mozilla/5.0 (compatible; GuppyBot/1.0)"})
                with _ureq.urlopen(req, timeout=15) as r:
                    raw = r.read().decode("utf-8", errors="replace")
                # Strip scripts, styles, and tags; collapse whitespace
                raw = _re.sub(r"<(script|style)[^>]*>.*?</(script|style)>", " ", raw, flags=_re.S | _re.I)
                raw = _re.sub(r"<[^>]+>", " ", raw)
                text = _html.unescape(raw)
                text = _re.sub(r"[ \t]+", " ", text)
                text = _re.sub(r"\n{3,}", "\n\n", text).strip()
                if len(text) > max_chars:
                    text = text[:max_chars] + f"\n\n[truncated — {len(text)} chars total]"
                return text or "Page fetched but no text content extracted."
            except Exception as e:
                return f"Error fetching {url}: {e}"

        elif name == "get_news":
            import urllib.request as _ureq, xml.etree.ElementTree as _ET
            topic = (inp.get("topic") or "").strip()
            count = min(int(inp.get("count") or 8), 15)
            try:
                if topic:
                    q = urllib.parse.quote(topic)
                    rss_url = f"https://news.google.com/rss/search?q={q}&hl=en-US&gl=US&ceid=US:en"
                else:
                    rss_url = "https://news.google.com/rss?hl=en-US&gl=US&ceid=US:en"
                req = _ureq.Request(rss_url, headers={"User-Agent": "Mozilla/5.0 (compatible; GuppyBot/1.0)"})
                with _ureq.urlopen(req, timeout=12) as r:
                    xml_data = r.read()
                root = _ET.fromstring(xml_data)
                items = root.findall(".//item")[:count]
                if not items:
                    return "No news items found."
                lines = [f"{'Top headlines' if not topic else topic + ' news'} — {len(items)} stories:\n"]
                for i, item in enumerate(items, 1):
                    title   = (item.findtext("title") or "").strip()
                    link    = (item.findtext("link") or "").strip()
                    source  = (item.findtext("source") or "").strip()
                    pubdate = (item.findtext("pubDate") or "")[:22].strip()
                    # Clean Google News redirect URLs when possible
                    lines.append(f"{i}. {title}")
                    if source:
                        lines.append(f"   Source: {source}  |  {pubdate}")
                    lines.append(f"   {link}")
                return "\n".join(lines)
            except Exception as e:
                return f"Error fetching news: {e}"

        elif name == "get_weather":
            location = inp.get("location", "") or os.environ.get("WEATHER_LOCATION", "")
            units    = inp.get("units", os.environ.get("WEATHER_UNITS", "imperial"))
            owm_key  = os.environ.get("OPENWEATHERMAP_API_KEY", "")
            if not owm_key:
                return "Weather unavailable — set OPENWEATHERMAP_API_KEY in .env (free at openweathermap.org)"
            if not location:
                return "Specify a location or set WEATHER_LOCATION in .env (e.g. 'Dallas,TX,US')"
            try:
                import urllib.request as _ureq, json as _json
                loc_enc = urllib.parse.quote(location)
                url = (
                    f"https://api.openweathermap.org/data/2.5/forecast"
                    f"?q={loc_enc}&units={units}&cnt=8&appid={owm_key}"
                )
                with _ureq.urlopen(url, timeout=10) as r:
                    data = _json.loads(r.read())

                city     = data["city"]["name"]
                country  = data["city"]["country"]
                deg      = "°F" if units == "imperial" else "°C"
                spd      = "mph" if units == "imperial" else "m/s"

                # Current (first slot)
                cur = data["list"][0]
                temp     = round(cur["main"]["temp"])
                feels    = round(cur["main"]["feels_like"])
                desc     = cur["weather"][0]["description"].capitalize()
                humidity = cur["main"]["humidity"]
                wind     = round(cur["wind"]["speed"])

                lines = [
                    f"Weather — {city}, {country}",
                    f"  Now:    {temp}{deg} (feels {feels}{deg})  {desc}",
                    f"  Humidity {humidity}%   Wind {wind} {spd}",
                    "",
                    "  Forecast today:",
                ]
                seen_dates: set = set()
                for slot in data["list"][1:]:
                    dt_txt = slot["dt_txt"]          # e.g. "2026-04-12 15:00:00"
                    date   = dt_txt[:10]
                    if date in seen_dates:
                        continue
                    seen_dates.add(date)
                    t    = round(slot["main"]["temp"])
                    d    = slot["weather"][0]["description"].capitalize()
                    time = dt_txt[11:16]
                    lines.append(f"    {time}  {t}{deg}  {d}")
                    if len(seen_dates) >= 3:
                        break

                return "\n".join(lines)
            except Exception as e:
                return f"Weather error: {e}"

        # ── Memory tools ───────────────────────────────────────────────────────
        elif name == "remember":
            if not _MEM: return "Memory module not available."
            return _mem.remember(inp["key"], inp["value"], inp.get("category", "general"))

        elif name == "recall":
            if not _MEM: return "Memory module not available."
            return _mem.recall(inp.get("query", ""), inp.get("category", ""))

        elif name == "semantic_remember":
            if not _SMEM:
                return "Semantic memory module not available. Install chromadb and ensure guppy_semantic_memory.py is present."
            return _smem.remember_semantic(
                inp["key"],
                inp["value"],
                inp.get("category", "general"),
            )

        elif name == "semantic_recall":
            if not _SMEM:
                return "Semantic memory module not available. Install chromadb and ensure guppy_semantic_memory.py is present."
            return _smem.recall_semantic(
                inp["query"],
                inp.get("limit", 5),
                inp.get("category", ""),
            )

        elif name == "forget":
            if not _MEM: return "Memory module not available."
            return _mem.forget(inp["key"])

        elif name == "add_task":
            if not _MEM: return "Memory module not available."
            return _mem.add_task(inp["task"], inp.get("due_date", ""))

        elif name == "get_tasks":
            if not _MEM: return "Memory module not available."
            return _mem.get_tasks(inp.get("status", "pending"))

        elif name == "complete_task":
            if not _MEM: return "Memory module not available."
            return _mem.complete_task(inp["task_id"])

        elif name == "save_contact":
            if not _MEM: return "Memory module not available."
            return _mem.save_contact(
                inp["name"], inp.get("company", ""), inp.get("email", ""),
                inp.get("phone", ""), inp.get("notes", ""),
            )

        elif name == "get_contacts":
            if not _MEM: return "Memory module not available."
            return _mem.get_contacts(inp.get("search", ""))

        elif name == "add_pipeline_item":
            if not _MEM: return "Memory module not available."
            return _mem.add_pipeline_item(
                inp["title"],
                inp.get("company", ""),
                inp.get("contact_name", ""),
                inp.get("stage", "new_lead"),
                inp.get("value", 0),
                inp.get("confidence", 30),
                inp.get("next_action", ""),
                inp.get("due_date", ""),
                inp.get("source", ""),
                inp.get("notes", ""),
            )

        elif name == "update_pipeline_item":
            if not _MEM: return "Memory module not available."
            return _mem.update_pipeline_item(
                inp["item_id"],
                inp.get("stage", ""),
                inp.get("value", None),
                inp.get("confidence", None),
                inp.get("next_action", None),
                inp.get("due_date", None),
                inp.get("status", None),
                inp.get("notes", None),
            )

        elif name == "log_pipeline_activity":
            if not _MEM: return "Memory module not available."
            return _mem.log_pipeline_activity(
                inp["item_id"],
                inp["note"],
                inp.get("activity_type", "note"),
            )

        elif name == "get_pipeline_items":
            if not _MEM: return "Memory module not available."
            return _mem.get_pipeline_items(
                inp.get("stage", ""),
                inp.get("status", "open"),
                inp.get("limit", 30),
            )

        elif name == "get_revenue_dashboard":
            if not _MEM: return "Memory module not available."
            return _mem.get_revenue_dashboard()

        elif name == "list_external_integrations":
            from crm_voip_integrations import list_external_integrations
            return list_external_integrations()

        elif name == "crm_upsert_contact":
            from crm_voip_integrations import crm_upsert_contact
            return crm_upsert_contact(
                inp["provider"],
                inp["name"],
                inp.get("email", ""),
                inp.get("phone", ""),
                inp.get("company", ""),
                inp.get("notes", ""),
                inp.get("dry_run", True),
            )

        elif name == "crm_create_opportunity":
            from crm_voip_integrations import crm_create_opportunity
            return crm_create_opportunity(
                inp["provider"],
                inp["title"],
                inp.get("value", 0),
                inp.get("stage", "new"),
                inp.get("company", ""),
                inp.get("contact_name", ""),
                inp.get("notes", ""),
                inp.get("dry_run", True),
            )

        elif name == "voip_place_call":
            from crm_voip_integrations import voip_place_call
            return voip_place_call(
                inp.get("provider", "twilio"),
                inp["to_number"],
                inp.get("from_number", ""),
                inp.get("contact_name", ""),
                inp.get("purpose", ""),
                inp.get("dry_run", True),
            )

        elif name == "get_foundation_readiness":
            from crm_voip_integrations import get_foundation_readiness_text
            return get_foundation_readiness_text()

        # ── Spotify ───────────────────────────────────────────────────────────
        elif name == "spotify_play":
            from media_tools import spotify_play
            return spotify_play(inp["query"])

        elif name == "spotify_pause":
            from media_tools import spotify_pause
            return spotify_pause()

        elif name == "spotify_resume":
            from media_tools import spotify_resume
            return spotify_resume()

        elif name == "spotify_next":
            from media_tools import spotify_next
            return spotify_next()

        elif name == "spotify_prev":
            from media_tools import spotify_prev
            return spotify_prev()

        elif name == "spotify_current":
            from media_tools import spotify_current
            return spotify_current()

        elif name == "spotify_volume":
            from media_tools import spotify_volume
            return spotify_volume(int(inp["level"]))

        # ── YouTube ───────────────────────────────────────────────────────────
        elif name == "youtube_play":
            from media_tools import youtube_play
            return youtube_play(inp["query"])

        elif name == "youtube_search":
            from media_tools import youtube_search
            return youtube_search(inp["query"])

        # ── Gmail purge ───────────────────────────────────────────────────────
        elif name == "gmail_purge":
            from media_tools import gmail_purge
            return gmail_purge(inp["query"], int(inp.get("max_results", 500)))

        elif name == "gmail_purge_label":
            from media_tools import gmail_purge_label
            return gmail_purge_label(inp["label"])

        elif name == "gmail_purge_sender":
            from media_tools import gmail_purge_sender
            return gmail_purge_sender(inp["email"])

        elif name == "gmail_purge_older_than":
            from media_tools import gmail_purge_older_than
            return gmail_purge_older_than(int(inp["days"]))

        elif name == "gmail_empty_trash":
            from media_tools import gmail_empty_trash
            return gmail_empty_trash()

        elif name == "gmail_switch_account":
            from media_tools import gmail_switch_account
            return gmail_switch_account(inp["alias"])

        elif name == "gmail_list_accounts":
            from media_tools import gmail_list_accounts
            return gmail_list_accounts()

        elif name == "gmail_smart_cleanup":
            from media_tools import gmail_smart_cleanup
            return gmail_smart_cleanup(int(inp.get("max_per_step", 500)))

        # ── Reminders & Tasks ──────────────────────────────────────────────────
        elif name == "remind_me":
            if not DAEMON:
                return "Error: Daemon not available. Reminders require background service."
            try:
                from guppy_daemon import get_daemon_manager
                manager = get_daemon_manager()
                result = manager.task_scheduler.schedule_reminder(inp["message"], inp["time"])
                return result
            except Exception as e:
                return f"Error scheduling reminder: {e}"

        elif name == "get_reminders":
            if not DAEMON:
                return "Error: Daemon not available. Reminders require background service."
            try:
                from guppy_daemon import get_daemon_manager
                manager = get_daemon_manager()
                reminders = manager.task_scheduler.get_scheduled_reminders()
                if not reminders:
                    return "No active reminders scheduled."
                result = "Active reminders:\n"
                for rid, rem in reminders.items():
                    result += f"  [{rid}] {rem['message']} — scheduled for {rem['trigger']}\n"
                return result
            except Exception as e:
                return f"Error retrieving reminders: {e}"

        elif name == "cancel_reminder":
            if not DAEMON:
                return "Error: Daemon not available. Reminders require background service."
            try:
                from guppy_daemon import get_daemon_manager
                manager = get_daemon_manager()
                result = manager.task_scheduler.cancel_reminder(inp["reminder_id"])
                return result
            except Exception as e:
                return f"Error canceling reminder: {e}"

        elif name == "morning_brief":
            include_gmail = inp.get("include_gmail", True)
            notify        = inp.get("notify", False)
            return _morning_brief(include_gmail=include_gmail, notify=notify)

        # ── Screen OCR ────────────────────────────────────────────────────────
        elif name == "read_screen_text":
            region      = inp.get("region", "full")
            instruction = inp.get("instruction", "Extract and return all visible text on screen.")
            try:
                import pyautogui
                from PIL import Image
                import io, base64

                # Capture the requested region
                screen_w, screen_h = pyautogui.size()
                region_map = {
                    "top":    (0, 0, screen_w, screen_h // 2),
                    "bottom": (0, screen_h // 2, screen_w, screen_h // 2),
                    "left":   (0, 0, screen_w // 2, screen_h),
                    "right":  (screen_w // 2, 0, screen_w // 2, screen_h),
                }
                if region in region_map:
                    shot = pyautogui.screenshot(region=region_map[region])
                elif region == "active_window":
                    # Capture the bounding box of the foreground window
                    import ctypes
                    hwnd = ctypes.windll.user32.GetForegroundWindow()
                    rect = ctypes.wintypes.RECT()
                    ctypes.windll.user32.GetWindowRect(hwnd, ctypes.byref(rect))
                    x, y = rect.left, rect.top
                    w = rect.right  - rect.left
                    h = rect.bottom - rect.top
                    shot = pyautogui.screenshot(region=(x, y, w, h))
                else:
                    shot = pyautogui.screenshot()

                # Encode as JPEG (smaller than PNG, plenty sharp enough for OCR)
                buf = io.BytesIO()
                shot.save(buf, format="JPEG", quality=85)
                img_b64 = base64.standard_b64encode(buf.getvalue()).decode()

                # Send to Claude vision for text extraction
                import anthropic as _ant
                _vision_client = _ant.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY", ""))
                resp = _vision_client.messages.create(
                    model=os.environ.get("ANTHROPIC_BACKUP_MODEL", "claude-haiku-4-5-20251001"),
                    max_tokens=1024,
                    messages=[{
                        "role": "user",
                        "content": [
                            {
                                "type": "image",
                                "source": {"type": "base64", "media_type": "image/jpeg", "data": img_b64},
                            },
                            {"type": "text", "text": instruction},
                        ],
                    }],
                )
                return resp.content[0].text if resp.content else "No text extracted."
            except ImportError as e:
                return f"Screenshot dependency missing: {e}"
            except Exception as e:
                return f"Error reading screen text: {e}"

        # ── Inbox scan ────────────────────────────────────────────────────────
        elif name == "gmail_scan_inbox":
            from media_tools import gmail_scan_inbox
            return gmail_scan_inbox(
                max_emails=int(inp.get("max_emails", 30)),
                account=inp.get("account", ""),
                auto_task=inp.get("auto_task", True),
                dry_run=inp.get("dry_run", False),
            )

        # ── Calendar ──────────────────────────────────────────────────────────
        elif name == "calendar_events":
            from media_tools import calendar_events as _cal_events
            return _cal_events(
                days=int(inp.get("days", 1)),
                max_results=int(inp.get("max_results", 20)),
                calendar_id=inp.get("calendar_id", "primary"),
            )

        # ── Send Email ────────────────────────────────────────────────────────
        elif name == "send_email":
            from media_tools import gmail_send
            return gmail_send(
                to=inp["to"],
                subject=inp["subject"],
                body=inp["body"],
                cc=inp.get("cc", ""),
                account=inp.get("account", ""),
            )

        # ── Clipboard ──────────────────────────────────────────────────────────
        elif name == "clipboard_read":
            try:
                import pyperclip
                text = pyperclip.paste()
                if not text:
                    return "Clipboard is empty."
                preview = text[:2000]
                suffix = f"\n... ({len(text) - 2000} more chars)" if len(text) > 2000 else ""
                return f"Clipboard contents:\n{preview}{suffix}"
            except Exception as e:
                return f"Error reading clipboard: {e}"

        elif name == "clipboard_write":
            try:
                import pyperclip
                pyperclip.copy(inp["text"])
                return f"Clipboard updated ({len(inp['text'])} chars). Ready to paste."
            except Exception as e:
                return f"Error writing clipboard: {e}"

        # ── Window context ─────────────────────────────────────────────────────
        elif name == "get_active_window":
            try:
                import ctypes
                hwnd = ctypes.windll.user32.GetForegroundWindow()
                length = ctypes.windll.user32.GetWindowTextLengthW(hwnd)
                buf = ctypes.create_unicode_buffer(length + 1)
                ctypes.windll.user32.GetWindowTextW(hwnd, buf, length + 1)
                title = buf.value or "(no title)"

                import psutil, ctypes as _ct
                pid = ctypes.c_ulong()
                ctypes.windll.user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
                try:
                    proc = psutil.Process(pid.value)
                    exe = proc.name()
                except Exception:
                    exe = "unknown"

                return f"Active window: '{title}' (process: {exe})"
            except Exception as e:
                return f"Error reading active window: {e}"

        elif name == "focus_window":
            app = inp["app"].lower()
            try:
                import ctypes
                import psutil

                EnumWindows = ctypes.windll.user32.EnumWindows
                EnumWindowsProc = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.POINTER(ctypes.c_int), ctypes.POINTER(ctypes.c_int))
                GetWindowText = ctypes.windll.user32.GetWindowTextW
                GetWindowTextLength = ctypes.windll.user32.GetWindowTextLengthW
                IsWindowVisible = ctypes.windll.user32.IsWindowVisible
                SetForegroundWindow = ctypes.windll.user32.SetForegroundWindow
                ShowWindow = ctypes.windll.user32.ShowWindow
                GetWindowThreadProcessId = ctypes.windll.user32.GetWindowThreadProcessId

                matches = []

                def _enum_cb(hwnd, _lparam):
                    if not IsWindowVisible(hwnd):
                        return True
                    ln = GetWindowTextLength(hwnd)
                    if ln == 0:
                        return True
                    buf = ctypes.create_unicode_buffer(ln + 1)
                    GetWindowText(hwnd, buf, ln + 1)
                    title_lc = buf.value.lower()

                    pid = ctypes.c_ulong()
                    GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
                    try:
                        exe = psutil.Process(pid.value).name().lower()
                    except Exception:
                        exe = ""

                    if app in title_lc or app in exe:
                        matches.append((hwnd, buf.value))
                    return True

                EnumWindows(EnumWindowsProc(_enum_cb), 0)

                if not matches:
                    return f"No visible window found matching '{inp['app']}'."

                hwnd, title = matches[0]
                SW_RESTORE = 9
                ShowWindow(hwnd, SW_RESTORE)
                SetForegroundWindow(hwnd)
                return f"Focused: '{title}'"
            except Exception as e:
                return f"Error focusing window: {e}"

        # ── GitHub ───────────────────────────────────────────────────────────
        elif name == "github":
            from github_tools import github_action
            return github_action(
                action=inp.get("action", ""),
                repo=inp.get("repo", ""),
                title=inp.get("title", ""),
                body=inp.get("body", ""),
                path=inp.get("path", ""),
                ref=inp.get("ref", ""),
            )

        # ── Run Python ───────────────────────────────────────────────────────
        elif name == "run_python":
            code = (inp.get("code") or "").strip()
            if not code:
                return "Error: no code provided."
            timeout = max(1, min(int(inp.get("timeout") or 10), 60))
            venv_python = str(Path(__file__).parent / ".venv" / "Scripts" / "python.exe")
            python_bin = venv_python if Path(venv_python).exists() else "python"
            try:
                result = subprocess.run(
                    [python_bin, "-c", code],
                    capture_output=True,
                    text=True,
                    timeout=timeout,
                    cwd=str(Path(__file__).parent),
                )
                out = result.stdout.strip()
                err = result.stderr.strip()
                parts = []
                if out:
                    parts.append(out[:3000])
                if err:
                    parts.append(f"stderr:\n{err[:1000]}")
                if not parts:
                    parts.append(f"(exit code {result.returncode}, no output)")
                return "\n".join(parts)
            except subprocess.TimeoutExpired:
                return f"Error: code timed out after {timeout}s."
            except Exception as e:
                return f"Error running code: {e}"

        # ── Code Ops ─────────────────────────────────────────────────────────
        elif name == "test_targeted":
            target = (inp.get("target") or "").strip()
            if not target:
                return "Error: target is required."
            maxfail = max(1, min(int(inp.get("maxfail", 1)), 50))
            quiet = bool(inp.get("quiet", True))
            k_expr = (inp.get("k") or "").strip()
            venv_python = str(Path(__file__).parent / ".venv" / "Scripts" / "python.exe")
            python_bin = venv_python if Path(venv_python).exists() else "python"
            cmd = [python_bin, "-m", "pytest", target, f"--maxfail={maxfail}"]
            if quiet:
                cmd.append("-q")
            if k_expr:
                cmd.extend(["-k", k_expr])
            try:
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    timeout=300,
                    cwd=str(Path(__file__).parent),
                )
                output = (result.stdout or "").strip()
                err = (result.stderr or "").strip()
                parts = [f"pytest exit={result.returncode}"]
                if output:
                    parts.append(output[:5000])
                if err:
                    parts.append("stderr:\n" + err[:1500])
                return "\n\n".join(parts)
            except subprocess.TimeoutExpired:
                return "Error: pytest timed out after 300s."
            except Exception as e:
                return f"Error running pytest: {e}"

        elif name == "lint_fix":
            paths = inp.get("paths") or ["."]
            if not isinstance(paths, list):
                paths = [str(paths)]
            paths = [str(p).strip() for p in paths if str(p).strip()]
            if not paths:
                paths = ["."]
            fix = bool(inp.get("fix", True))
            venv_python = str(Path(__file__).parent / ".venv" / "Scripts" / "python.exe")
            python_bin = venv_python if Path(venv_python).exists() else "python"
            cmd = [python_bin, "-m", "ruff", "check", *paths]
            if fix:
                cmd.append("--fix")
            try:
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    timeout=240,
                    cwd=str(Path(__file__).parent),
                )
                output = (result.stdout or "").strip()
                err = (result.stderr or "").strip()
                parts = [f"ruff exit={result.returncode} (fix={'on' if fix else 'off'})"]
                if output:
                    parts.append(output[:5000])
                if err:
                    parts.append("stderr:\n" + err[:1500])
                return "\n\n".join(parts)
            except subprocess.TimeoutExpired:
                return "Error: ruff timed out after 240s."
            except Exception as e:
                return f"Error running ruff: {e}"

        elif name == "typecheck_targeted":
            target = (inp.get("target") or "").strip()
            if not target:
                return "Error: target is required."
            strict = bool(inp.get("strict", False))
            venv_python = str(Path(__file__).parent / ".venv" / "Scripts" / "python.exe")
            python_bin = venv_python if Path(venv_python).exists() else "python"
            cmd = [python_bin, "-m", "mypy", target]
            if strict:
                cmd.append("--strict")
            try:
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    timeout=300,
                    cwd=str(Path(__file__).parent),
                )
                output = (result.stdout or "").strip()
                err = (result.stderr or "").strip()
                parts = [f"mypy exit={result.returncode} (strict={'on' if strict else 'off'})"]
                if output:
                    parts.append(output[:6000])
                if err:
                    parts.append("stderr:\n" + err[:1500])
                return "\n\n".join(parts)
            except subprocess.TimeoutExpired:
                return "Error: mypy timed out after 300s."
            except Exception as e:
                return f"Error running mypy: {e}"

        elif name == "git_patch_summary":
            include_staged = bool(inp.get("staged", True))
            include_unstaged = bool(inp.get("unstaged", True))
            include_name_only = bool(inp.get("name_only", True))
            repo_root = str(Path(__file__).parent)
            sections: list[str] = []
            try:
                status = subprocess.run(
                    ["git", "status", "--short"],
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    timeout=30,
                    cwd=repo_root,
                )
                if status.returncode != 0:
                    return f"Error: git status failed: {(status.stderr or '').strip()}"
                sections.append("status:\n" + ((status.stdout or "").strip() or "clean"))

                if include_name_only:
                    names = subprocess.run(
                        ["git", "diff", "--name-only"],
                        capture_output=True,
                        text=True,
                        encoding="utf-8",
                        errors="replace",
                        timeout=30,
                        cwd=repo_root,
                    )
                    staged_names = subprocess.run(
                        ["git", "diff", "--cached", "--name-only"],
                        capture_output=True,
                        text=True,
                        encoding="utf-8",
                        errors="replace",
                        timeout=30,
                        cwd=repo_root,
                    )
                    sections.append("unstaged files:\n" + ((names.stdout or "").strip() or "none"))
                    sections.append("staged files:\n" + ((staged_names.stdout or "").strip() or "none"))

                if include_unstaged:
                    unstaged = subprocess.run(
                        ["git", "diff", "--stat"],
                        capture_output=True,
                        text=True,
                        encoding="utf-8",
                        errors="replace",
                        timeout=30,
                        cwd=repo_root,
                    )
                    sections.append("unstaged diffstat:\n" + ((unstaged.stdout or "").strip() or "none"))

                if include_staged:
                    staged = subprocess.run(
                        ["git", "diff", "--cached", "--stat"],
                        capture_output=True,
                        text=True,
                        encoding="utf-8",
                        errors="replace",
                        timeout=30,
                        cwd=repo_root,
                    )
                    sections.append("staged diffstat:\n" + ((staged.stdout or "").strip() or "none"))

                return "\n\n".join(sections)[:9000]
            except Exception as e:
                return f"Error generating git patch summary: {e}"

        # ── Windows Notification ─────────────────────────────────────────────
        elif name == "notify":
            title   = (inp.get("title")   or "Guppy").strip()
            message = (inp.get("message") or "").strip()
            duration = inp.get("duration", "short")
            if not message:
                return "Error: message is required."
            try:
                from win11toast import notify as _win_notify
                _win_notify(title=title, body=message, duration=duration)
                return f"Notification sent: '{title}'"
            except ImportError:
                # Graceful fallback using Windows balloon tip via ctypes
                try:
                    import ctypes
                    ctypes.windll.user32.MessageBoxW(0, message, title, 0x40)
                    return f"Notification sent (fallback): '{title}'"
                except Exception as e2:
                    return f"Error: win11toast not installed and fallback failed: {e2}"
            except Exception as e:
                return f"Error sending notification: {e}"

        # ── Web Summarize ────────────────────────────────────────────────────
        elif name == "web_summarize":
            url = (inp.get("url") or "").strip()
            if not url:
                return "Error: url is required."
            instruction = (inp.get("instruction") or "Summarize the main content of this page.").strip()
            firecrawl_key = os.environ.get("FIRECRAWL_API_KEY", "").strip()

            raw_text = ""
            source = "http"

            if firecrawl_key:
                try:
                    import requests as _req
                    resp = _req.post(
                        "https://api.firecrawl.dev/v1/scrape",
                        headers={"Authorization": f"Bearer {firecrawl_key}", "Content-Type": "application/json"},
                        json={"url": url, "formats": ["markdown"]},
                        timeout=30,
                    )
                    resp.raise_for_status()
                    data = resp.json()
                    raw_text = (data.get("data") or {}).get("markdown") or ""
                    source = "firecrawl"
                except Exception as fc_err:
                    logger.warning(f"Firecrawl failed ({fc_err}), falling back to HTTP")

            if not raw_text:
                try:
                    import urllib.request as _ureq
                    import html as _html
                    import re as _re
                    req = _ureq.Request(url, headers={"User-Agent": "Mozilla/5.0"})
                    with _ureq.urlopen(req, timeout=20) as r:
                        raw_html = r.read().decode("utf-8", errors="replace")
                    # Strip tags, decode entities, collapse whitespace
                    text = _re.sub(r"<script[^>]*>.*?</script>", " ", raw_html, flags=_re.DOTALL | _re.IGNORECASE)
                    text = _re.sub(r"<style[^>]*>.*?</style>", " ", text, flags=_re.DOTALL | _re.IGNORECASE)
                    text = _re.sub(r"<[^>]+>", " ", text)
                    text = _html.unescape(text)
                    raw_text = _re.sub(r"\s+", " ", text).strip()[:12000]
                    source = "http"
                except Exception as e:
                    return f"Error fetching URL: {e}"

            if not raw_text:
                return "Could not extract content from that URL."

            # Summarize with Claude Haiku
            try:
                import anthropic as _ant
                _sc = _ant.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY", ""))
                resp = _sc.messages.create(
                    model=os.environ.get("ANTHROPIC_BACKUP_MODEL", "claude-haiku-4-5-20251001"),
                    max_tokens=1024,
                    messages=[{
                        "role": "user",
                        "content": f"{instruction}\n\nPage content:\n{raw_text[:10000]}",
                    }],
                )
                summary = resp.content[0].text if resp.content else "No summary generated."
                return f"[{source}] {summary}"
            except Exception as e:
                # Return raw truncated text if Haiku unavailable
                return f"[{source}, no AI summary] {raw_text[:2000]}"

        else:
            return f"Unknown tool: {name}"

    except subprocess.TimeoutExpired:
        return f"Error: {name} timed out"
    except Exception as e:
        return f"Error in {name}: {e}"
