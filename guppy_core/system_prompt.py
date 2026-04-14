"""
guppy_core/system_prompt.py
SYSTEM prompt, REPORTS_DIR, memory-context helpers, and Ollama format converter.
Import from here instead of guppy_core directly when you only need the prompt.
"""
from __future__ import annotations

import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)

REPORTS_DIR = Path.home() / "Documents" / "Guppy Reports"

try:
    import guppy_memory as _mem
    _MEM = True
except ImportError:
    _mem = None  # type: ignore[assignment]
    _MEM = False

try:
    from guppy_semantic_memory import build_semantic_prompt_context as _build_semantic_prompt_context
except Exception:
    _build_semantic_prompt_context = None

try:
    from guppy_daemon import get_daemon_manager, get_window_context  # noqa: F401
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

        if _MEM:
            try:
                needs_memory = _needs_memory_context(query_context)
                if needs_memory:
                    briefing = _mem.get_startup_context(exclude_session=session_id)
                    system += "\n\n" + briefing
            except Exception:
                pass

        if query_context and callable(_build_semantic_prompt_context):
            try:
                semantic_context = _build_semantic_prompt_context(query_context, n=4)
                if semantic_context:
                    system += "\n\n" + semantic_context
            except Exception:
                pass

        if DAEMON:
            try:
                from guppy_daemon import get_daemon_manager as _gdm
                daemon = _gdm()
                if daemon.is_running:
                    context = daemon.window_watcher.get_enhanced_context()
                    if context.get("app") and context["app"] != "unknown":
                        system += f"\n\nCurrent context: Master Ryan is currently focused on {context['app']}."
                        if context.get("title"):
                            system += f" The active window is titled '{context['title']}'."
                        if context.get("help"):
                            system += f" {context['help']}"
            except Exception as e:
                logger.debug("Window context error: %s", e)

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
