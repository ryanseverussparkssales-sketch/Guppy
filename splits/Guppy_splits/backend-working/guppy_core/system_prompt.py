"""
guppy_core/system_prompt.py
SYSTEM prompt, REPORTS_DIR, memory-context helpers, and Ollama format converter.
Import from here instead of guppy_core directly when you only need the prompt.
"""
from __future__ import annotations

import logging
import os
import time
from pathlib import Path

logger = logging.getLogger(__name__)

def _parse_ttl_env(name: str, default: str) -> float:
    raw_value = os.environ.get(name, default)
    try:
        parsed = float(raw_value)
    except (TypeError, ValueError):
        parsed = float(default)
    return max(0.0, parsed)


_STARTUP_CONTEXT_CACHE_TTL_SECONDS = _parse_ttl_env(
    "GUPPY_STARTUP_CONTEXT_CACHE_TTL_SECONDS",
    "15.0",
)
_SEMANTIC_CONTEXT_CACHE_TTL_SECONDS = _parse_ttl_env(
    "GUPPY_SEMANTIC_CONTEXT_CACHE_TTL_SECONDS",
    "45.0",
)
_WINDOW_CONTEXT_CACHE_TTL_SECONDS = _parse_ttl_env(
    "GUPPY_WINDOW_CONTEXT_CACHE_TTL_SECONDS",
    "2.0",
)

_startup_context_cache: dict[str, tuple[float, str]] = {}
_semantic_context_cache: dict[str, tuple[float, str]] = {}
_window_context_cache: tuple[float, str] = (0.0, "")

REPORTS_DIR = Path.home() / "Documents" / "Guppy Reports"

try:
    from src.guppy.memory import memory as _mem
    _MEM = True
except ImportError:
    _mem = None  # type: ignore[assignment]
    _MEM = False

try:
    from src.guppy.memory.semantic import build_semantic_prompt_context as _build_semantic_prompt_context
except Exception:
    _build_semantic_prompt_context = None

try:
    from src.guppy.daemon.daemon import get_daemon_manager, get_window_context  # noqa: F401
    DAEMON = True
except ImportError:
    DAEMON = False

    def get_daemon_manager():  # type: ignore[misc]
        return None

    def get_window_context():  # type: ignore[misc]
        return {"app": "unknown", "title": "unknown"}


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


def _needs_memory_context(query: str) -> bool:
    """Determine if query requires memory context based on keywords."""
    if not query:
        return True
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


def _needs_semantic_context(query: str) -> bool:
    q = (query or "").strip()
    if not q:
        return False
    if _needs_memory_context(q):
        return True
    q_lower = q.lower()
    semantic_keywords = [
        "project", "client", "pipeline", "contact", "task", "todo",
        "follow up", "continue", "builder", "instance", "settings",
        "voice", "model", "persona", "debug", "design", "refactor",
        "compare", "tradeoff", "why", "how",
    ]
    if len(q) >= 72:
        return True
    return any(keyword in q_lower for keyword in semantic_keywords)


def _cache_read(cache: dict[str, tuple[float, str]], key: str, ttl_seconds: float) -> str:
    if ttl_seconds <= 0:
        return ""
    entry = cache.get(key)
    if not entry:
        return ""
    expires_at, value = entry
    if expires_at <= time.monotonic():
        cache.pop(key, None)
        return ""
    return value


def _cache_write(cache: dict[str, tuple[float, str]], key: str, value: str, ttl_seconds: float) -> str:
    if ttl_seconds > 0:
        cache[key] = (time.monotonic() + ttl_seconds, value)
    return value


def _get_memory_briefing(exclude_session: str | None = None) -> str:
    if not _MEM:
        return ""
    cache_key = str(exclude_session or "")
    cached = _cache_read(_startup_context_cache, cache_key, _STARTUP_CONTEXT_CACHE_TTL_SECONDS)
    if cached:
        return cached
    briefing = _mem.get_startup_context(exclude_session=exclude_session)
    return _cache_write(_startup_context_cache, cache_key, briefing, _STARTUP_CONTEXT_CACHE_TTL_SECONDS)


def _get_semantic_context(query: str, n: int = 4, category: str = "") -> str:
    if not query or not callable(_build_semantic_prompt_context):
        return ""
    cache_key = f"{query.strip().lower()}::{int(n)}::{(category or '').strip().lower()}"
    cached = _cache_read(_semantic_context_cache, cache_key, _SEMANTIC_CONTEXT_CACHE_TTL_SECONDS)
    if cached:
        return cached
    semantic_context = _build_semantic_prompt_context(query, n=n)
    return _cache_write(_semantic_context_cache, cache_key, semantic_context, _SEMANTIC_CONTEXT_CACHE_TTL_SECONDS)


def _get_window_context_suffix() -> str:
    global _window_context_cache
    expires_at, cached = _window_context_cache
    if _WINDOW_CONTEXT_CACHE_TTL_SECONDS > 0 and expires_at > time.monotonic() and cached:
        return cached

    suffix = ""
    if DAEMON:
        try:
            from src.guppy.daemon.daemon import get_daemon_manager as _gdm

            daemon = _gdm()
            if daemon.is_running:
                context = daemon.window_watcher.get_enhanced_context()
                if context.get("app") and context["app"] != "unknown":
                    suffix = f"\n\nCurrent context: Master Ryan is currently focused on {context['app']}."
                    if context.get("title"):
                        suffix += f" The active window is titled '{context['title']}'."
                    if context.get("help"):
                        suffix += f" {context['help']}"
        except Exception as e:
            logger.debug("Window context error: %s", e)

    if _WINDOW_CONTEXT_CACHE_TTL_SECONDS > 0:
        _window_context_cache = (time.monotonic() + _WINDOW_CONTEXT_CACHE_TTL_SECONDS, suffix)
    return suffix


def get_startup_system(
    session_id: str = None,
    query_context: str = None,
    include_memory_context: bool | None = None,
    include_semantic_context: bool | None = None,
) -> str:
    """
    Return the system prompt enriched with memory briefing and window context.
    Called fresh on every API request so context is always current.
    Pass `session_id` so recent-message recall excludes the live session.
    Pass `query_context` to conditionally include memory briefing.
    Falls back to the base SYSTEM if memory is unavailable.
    """
    try:
        system = SYSTEM

        use_memory_context = (
            include_memory_context
            if include_memory_context is not None
            else _needs_memory_context(query_context)
        )
        use_semantic_context = (
            include_semantic_context
            if include_semantic_context is not None
            else _needs_semantic_context(query_context)
        )

        if use_memory_context and _MEM:
            try:
                briefing = _get_memory_briefing(exclude_session=session_id)
                if briefing:
                    system += "\n\n" + briefing
            except Exception:
                logger.exception(
                    "get_startup_system/_get_memory_briefing failed session_id=%r query_context=%r",
                    session_id,
                    query_context,
                )

        if use_semantic_context and query_context:
            try:
                semantic_context = _get_semantic_context(query_context, n=4)
                if semantic_context:
                    system += "\n\n" + semantic_context
            except Exception:
                logger.exception(
                    "get_startup_system/_get_semantic_context failed session_id=%r query_context=%r",
                    session_id,
                    query_context,
                )

        system += _get_window_context_suffix()

        return system
    except Exception:
        return SYSTEM


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
