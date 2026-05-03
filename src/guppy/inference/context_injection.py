"""Prompt context injection helpers.

Provides utilities for augmenting system prompts with:
- Recent conversation history
- Semantic RAG context from long-term memory
- Tool catalog summaries and surface-specific primers
- Live workspace filesystem snapshots

Moved from ``src.guppy.api.realtime_inference_support`` to keep that module
readable.  All names remain importable from the original location via
re-export.
"""
from __future__ import annotations

import asyncio
import logging
import os as _os
import time as _time
from pathlib import Path as _Path
from typing import Any

_log = logging.getLogger(__name__)

# ── History augmentation ───────────────────────────────────────────────────────

_HISTORY_SNIPPET_MAX_CHARS = 240
_HISTORY_TURNS_SHOWN = 8


def augment_system_with_history(system_prompt: str, history: list[dict[str, str]]) -> str:
    """Deprecated no-op — history is now carried exclusively in the messages array.

    ``build_router_messages`` already includes ``history`` in the correct
    ``messages`` list position so models see prior turns in the right format.
    Injecting the same turns into the system prompt as well caused every model
    to see the conversation twice, wasting up to 1 K tokens per call.

    Kept for backward-compatibility; callers that still invoke this function
    simply receive ``system_prompt`` unchanged.
    """
    return system_prompt


# ── Background memory workers ─────────────────────────────────────────────────

def _bg_store_tool_outcome(
    name: str,
    args: dict,
    result: str,
    workspace_name: str | None = None,
) -> None:
    """Fire-and-forget: persist successful tool call outcome to semantic memory."""
    import threading
    import hashlib

    def _store() -> None:
        try:
            from src.guppy.memory.semantic import remember_semantic
            args_str = str(sorted((args or {}).items()))[:200]
            ts = int(_time.time())
            key = f"tool_outcome:{name}:{ts}:{hashlib.md5(args_str.encode()).hexdigest()[:6]}"
            trunc = 2000 if name in ("file_read", "shell_run", "web_fetch", "web_search") else 800
            value = f"{name}({args_str[:200]}) → {result[:trunc]}"
            remember_semantic(key, value, category="tool_outcome", workspace_name=workspace_name)
        except Exception:
            pass

    threading.Thread(target=_store, daemon=True, name="tool-outcome-mem").start()


def _bg_summarize_session(history: list[dict], session_id: str = "") -> None:
    """Fire-and-forget: summarize recent conversation turns into semantic memory.

    Tries phi-4-mini (port 8091) first; falls back to hermes3 (8087) then
    hermes4 (8086) if phi-4-mini is offline.
    """
    import threading

    def _run() -> None:
        try:
            import time
            import requests
            turns = []
            # Use full history (not just last 12) so long sessions get a complete arc.
            for msg in history:
                role = msg.get("role", "user")
                content = str(msg.get("content", ""))[:400]
                turns.append(f"{role}: {content}")
            history_text = "\n".join(turns)
            system_msg = (
                "Extract key facts from this conversation as a bullet list. Focus on:\n"
                "1. User preferences or decisions stated explicitly\n"
                "2. Tasks completed or outcomes reached\n"
                "3. Topics the user asked about that would be useful to remember\n"
                "4. Any named entities (people, projects, tools) mentioned\n"
                "5. Tool calls made and what they returned (web searches, file reads, commands, etc.)\n"
                "6. Explicit decisions made ('we decided to…', 'going with X', 'chose Y over Z')\n\n"
                "Be concise. Only list facts worth remembering for future conversations."
            )
            # Cascade: phi-4-mini → hermes3 → hermes4
            _candidates = [
                ("http://localhost:8091/v1/chat/completions", "phi-4-mini-instruct"),
                ("http://localhost:8087/v1/chat/completions", "hermes-3-8b-lorablated"),
                ("http://localhost:8086/v1/chat/completions", "hermes-4-14b"),
            ]
            summary = ""
            for url, model in _candidates:
                try:
                    payload = {
                        "model": model,
                        "messages": [
                            {"role": "system", "content": system_msg},
                            {"role": "user", "content": f"Summarize:\n{history_text}"},
                        ],
                        "stream": False,
                        "max_tokens": 256,
                    }
                    r = requests.post(url, json=payload, timeout=15)
                    r.raise_for_status()
                    summary = (r.json().get("choices", [{}])[0].get("message", {}).get("content", "") or "").strip()
                    if summary and len(summary) > 20:
                        break
                except Exception:
                    continue
            if not summary:
                # All backends offline — store a minimal structural fallback so the
                # session isn't completely lost from memory.
                first_user = next(
                    (m.get("content", "")[:200] for m in history if m.get("role") == "user"), ""
                )
                summary = f"Session ({len(history)} turns). First message: {first_user}"
                _log.warning("[summarizer] All backends offline; storing fallback summary for session %s", session_id or "?")

            from src.guppy.memory.semantic import remember_semantic
            sid_tag = f":{session_id}" if session_id else ""
            key = f"session_summary{sid_tag}:{int(time.time())}"
            remember_semantic(key, summary, category="session_summary")
        except Exception as exc:
            _log.debug("Session summarization failed: %s", exc)

    threading.Thread(target=_run, daemon=True, name="session-summarizer").start()


# ── Semantic RAG injection ─────────────────────────────────────────────────────

def _inject_semantic_context(
    system_prompt: str,
    user_text: str,
    owner: Any,
    history: list[dict] | None = None,
) -> str:
    """Append relevant semantic memory to the system prompt.

    Builds a composite recall query from the last 3 user turns + current message
    so multi-turn references ("that project we discussed") resolve correctly.
    """
    if not (owner.os.environ.get("GUPPY_SEMANTIC_RAG", "1").strip().lower() in {"1", "true", "yes", "on"}):
        return system_prompt
    try:
        from src.guppy.memory.semantic import build_semantic_prompt_context
        if history:
            recent = " ".join(
                m.get("content", "")[:200]
                for m in history[-3:]
                if m.get("role") == "user"
            )
            query = f"{recent} {user_text}".strip()
        else:
            query = user_text
        ctx = build_semantic_prompt_context(query, n=4)
        if ctx:
            return f"{system_prompt}\n\n{ctx}"
    except Exception as exc:
        _log.debug("Semantic context injection failed: %s", exc)
    return system_prompt


async def _inject_semantic_context_async(
    system_prompt: str,
    user_text: str,
    owner: Any,
    history: list[dict] | None = None,
) -> str:
    """Async wrapper — runs the synchronous ChromaDB/SQLite read in a thread pool."""
    try:
        return await asyncio.wait_for(
            asyncio.to_thread(_inject_semantic_context, system_prompt, user_text, owner, history),
            timeout=2.0,
        )
    except asyncio.TimeoutError:
        return system_prompt


def _inject_user_preferences(system_prompt: str, owner: Any) -> str:
    """Prepend a [User Preferences] block from stored preference memories.

    Preferences are fetched via a direct SQL category scan rather than a
    vector similarity search (which degrades to random results on empty query
    strings).  Only the SQLite backend is scanned here; other backends fall
    back to the original recall path.
    """
    if not (owner.os.environ.get("GUPPY_SEMANTIC_RAG", "1").strip().lower() in {"1", "true", "yes", "on"}):
        return system_prompt
    try:
        import sqlite3
        from src.guppy.memory.semantic import DB_PATH
        if not DB_PATH or not _Path(str(DB_PATH)).exists():
            return system_prompt
        conn = sqlite3.connect(str(DB_PATH))
        try:
            rows = conn.execute(
                "SELECT memory_key, value FROM semantic_memory"
                " WHERE category='user_preference'"
                " ORDER BY created DESC LIMIT 10"
            ).fetchall()
        finally:
            conn.close()
        if rows:
            prefs = "\n".join(f"- {r[0]}: {r[1]}" for r in rows)
            return f"{system_prompt}\n\n[User Preferences]\n{prefs}"
    except Exception as exc:
        _log.debug("User preference injection failed: %s", exc)
    return system_prompt


async def _inject_user_preferences_async(system_prompt: str, owner: Any) -> str:
    """Async wrapper for user preference injection (1s hard timeout)."""
    try:
        return await asyncio.wait_for(
            asyncio.to_thread(_inject_user_preferences, system_prompt, owner),
            timeout=1.0,
        )
    except (asyncio.TimeoutError, Exception):
        return system_prompt


# ── Tool context ───────────────────────────────────────────────────────────────

def _build_tool_context(owner: Any) -> str:
    """Return a compact AVAILABLE TOOLS block from the owner's tool catalog.

    Only the first sentence of each description is included to keep the prompt
    token-efficient. Returns an empty string when tools are unavailable.
    """
    if not getattr(owner, "GUPPY_CORE_AVAILABLE", False):
        return ""
    tools = getattr(getattr(owner, "core", None), "TOOLS", None)
    if not tools:
        return ""
    lines = [
        "AVAILABLE TOOLS:",
        "Only call a tool when the user's request explicitly requires it.",
        "For general knowledge, news, or conversational questions, answer directly — do NOT call any tool.",
    ]
    for tool in tools:
        if isinstance(tool, dict):
            name = str(tool.get("name") or "").strip()
            desc = str(tool.get("description") or "").strip()
        else:
            name = str(getattr(tool, "name", "") or "").strip()
            desc = str(getattr(tool, "description", "") or "").strip()
        if not name:
            continue
        first_sentence = desc.split(".")[0].strip() if desc else ""
        lines.append(f"- {name}: {first_sentence}" if first_sentence else f"- {name}")
    return "\n".join(lines) if len(lines) > 1 else ""


# ── Surface-specific tool primers with few-shot examples ──────────────────────
#
# Each surface exposes a different tool whitelist and has different use patterns.
# These primers are injected just before message construction so models know:
#   1. Exactly which tools exist on this surface
#   2. Which user phrases should trigger each tool
#   3. The precise call format with a concrete example

_TOOL_CALL_FORMAT_REMINDER = """
TOOL CALL FORMAT — use EXACTLY this structure, no extra text before or after:
<tool_call>{"name": "tool_name", "arguments": {"param": "value"}}</tool_call>
""".strip()


_COMPANION_TOOL_PRIMER = """
COMPANION SURFACE — AVAILABLE TOOLS:

You have these tools on the Companion surface. Use them proactively when the
user's request clearly calls for them — don't make them ask twice.

• web_search(query, num_results?)
  WHEN: user asks to search for something, find information, or "look it up" without
  knowing the exact URL. Use this first, then web_fetch for a specific result.
  EXAMPLE: <tool_call>{"name": "web_search", "arguments": {"query": "best dark roast coffee beans 2026", "num_results": 5}}</tool_call>

• web_fetch(url, extract?)
  WHEN: user gives a specific URL, or follow up from web_search to get page content.
  EXAMPLE: <tool_call>{"name": "web_fetch", "arguments": {"url": "https://example.com", "extract": "pricing"}}</tool_call>

• create_reminder(message, delay_minutes?, due_iso?)
  WHEN: user says "remind me", "don't let me forget", "set a reminder", or
  gives a task with a time ("do X in 30 minutes", "tell me at 3pm").
  EXAMPLE: <tool_call>{"name": "create_reminder", "arguments": {"message": "Call dentist", "delay_minutes": 60}}</tool_call>

• memory_write(key, value, category?)
  WHEN: user says "remember that", "keep track of", "store this", or shares
  information they'll want you to recall later (preferences, facts, names).
  Always pass a category: "user_preference" for likes/dislikes, "fact" for info,
  "task" for action items, "person" for people, "project" for ongoing work.
  EXAMPLE: <tool_call>{"name": "memory_write", "arguments": {"key": "user_pref_coffee", "value": "dark roast, no sugar", "category": "user_preference"}}</tool_call>
  EXAMPLE: <tool_call>{"name": "memory_write", "arguments": {"key": "project_seed_vault", "value": "Ryan's personal media archive using qwen2.5:7b for metadata", "category": "project"}}</tool_call>

• memory_recall(key?, query?)
  WHEN: user asks "do you remember", "what did I tell you about", "recall my",
  or when their question seems to reference something they've shared before.
  EXAMPLE: <tool_call>{"name": "memory_recall", "arguments": {"query": "coffee preference"}}</tool_call>

• workspace_task(task, context?)
  WHEN: the user asks for something that requires agentic work, file ops,
  data lookup, or multi-step execution — hand it to the Workspace surface.
  EXAMPLE: <tool_call>{"name": "workspace_task", "arguments": {"task": "Summarize my emails from today", "context": "check inbox"}}</tool_call>

• get_time()
  WHEN: user asks what time or date it is.
  EXAMPLE: <tool_call>{"name": "get_time", "arguments": {}}</tool_call>

• cancel_workspace_task(task_id)
  WHEN: user asks to cancel, stop, or abort a workspace task they previously queued.
  EXAMPLE: <tool_call>{"name": "cancel_workspace_task", "arguments": {"task_id": "abc123"}}</tool_call>

• list_workspace_tasks(status?)
  WHEN: user asks what tasks are running, pending, or completed; or "what's the status of my tasks".
  EXAMPLE: <tool_call>{"name": "list_workspace_tasks", "arguments": {"status": "queued"}}</tool_call>

• download_media(url, category?)
  WHEN: user asks to download a file, torrent, magnet link, or media via qBittorrent.
  EXAMPLE: <tool_call>{"name": "download_media", "arguments": {"url": "magnet:?xt=urn:btih:...", "category": "books"}}</tool_call>

CONVERSATION HISTORY: If the user refers to something said earlier ("what did I ask",
"remember when I said", "what was the last thing"), look at the prior messages above —
the answer is already there. Do NOT say "you haven't sent anything yet."

IMPORTANT: For casual chat, opinions, advice, creative writing, and anything
that doesn't require live data or persistent state — answer directly, NO tools.
""".strip()


_WORKSPACE_TOOL_PRIMER = """
WORKSPACE SURFACE — AVAILABLE TOOLS:

You are in agentic mode. Use tools freely and proactively to accomplish tasks.
Chain multiple tools when needed. Report progress as you go.

Key tools available (full catalog shown in the tool schema):

• web_fetch(url, extract?) — fetch any public URL for research or data
• file_read(path) — read file contents from the local filesystem
• file_list(directory?) — list directory contents
• shell_run(command) — run a shell command (be careful, confirm destructive ops)
• contacts_search(query) — search CRM contacts
• web_search(query) — search the web for current information
• memory_write / memory_recall — persistent cross-session memory
• workspace_task(task) — spawn a background task

TOOL CHAINING PATTERN — for multi-step requests:
  1. Use web_search or file_list to discover what's available
  2. Use web_fetch or file_read to get content
  3. Synthesize and respond with findings

EXAMPLE (research task):
<tool_call>{"name": "web_search", "arguments": {"query": "best practices React 2026"}}</tool_call>
Then fetch a result:
<tool_call>{"name": "web_fetch", "arguments": {"url": "https://...", "extract": "hooks"}}</tool_call>
Then synthesize: "Based on what I found..."
""".strip()


_CODESPACE_TOOL_PRIMER = """
CODESPACE SURFACE — AVAILABLE TOOLS:

You are a code-focused assistant with access to execution tools. Use them to
write, test, and fix code — not just describe what to do.

• file_read(path) — read any source file before suggesting changes
• file_list(directory?) — explore project structure
• shell_run(command) — run tests, linters, build commands, git operations
• web_fetch(url) — fetch docs, API references, package readmes
• memory_write / memory_recall — store solutions and patterns for reuse

CODE TASK PATTERN:
  1. file_list / file_read to understand context first
  2. Draft the change or command
  3. shell_run to validate (run tests, check syntax)
  4. Report result and any failures

EXAMPLE (run tests):
<tool_call>{"name": "shell_run", "arguments": {"command": "python -m pytest tests/ -x -q 2>&1 | tail -20"}}</tool_call>
""".strip()


_SURFACE_PRIMERS: dict[str, str] = {
    "companion": _COMPANION_TOOL_PRIMER,
    "workspace": _WORKSPACE_TOOL_PRIMER,
    "codespace": _CODESPACE_TOOL_PRIMER,
}


def _inject_tool_primer(system_prompt: str, surface: str) -> str:
    """Append a surface-specific tool primer with few-shot examples.

    Called once per request just before message construction so the primer
    is always the freshest section of the system prompt — models attend to
    content near the end of the system turn most reliably.
    """
    primer = _SURFACE_PRIMERS.get(surface, "")
    if not primer:
        return system_prompt
    return f"{system_prompt}\n\n{_TOOL_CALL_FORMAT_REMINDER}\n\n{primer}"


# ── Workspace filesystem snapshot ─────────────────────────────────────────────

_FS_SNAPSHOT_CACHE: dict[str, tuple[float, str]] = {}
_FS_SNAPSHOT_CACHE_MAX = 200
_FS_SNAPSHOT_TTL = 60.0   # seconds
_FS_MAX_ENTRIES = 40
_FS_MAX_DEPTH = 2
_FS_SCAN_TIMEOUT = 2.0    # seconds — bail out if walk takes longer
_FS_SKIP_DIRS = {
    ".git", ".venv", "venv", "__pycache__", "node_modules",
    ".mypy_cache", ".pytest_cache", ".ruff_cache", "dist", "build",
    ".tmp", "static", "coverage", ".eggs",
    # Windows-specific large/volatile dirs
    "AppData", "AppData (x86)", "OneDrive", "Pictures", "Videos",
    "Music", "Downloads", "screenpipe", "Screenpipe", ".screenpipe",
    "WindowsApps", "Temp", "temp",
}
_FS_CODE_EXTS = {
    ".py", ".ts", ".tsx", ".js", ".jsx",
    ".json", ".yaml", ".yml", ".toml",
    ".md", ".txt", ".bat", ".ps1", ".sh",
    ".cfg", ".ini", ".env", ".sql",
}


def _scan_workspace_sync(directory: str) -> str:
    """Return a compact depth-limited file tree of *directory*, cached by TTL.

    Skips non-code files and common build/cache directories to keep the
    injected context token-efficient.
    """
    now = _time.monotonic()
    cached = _FS_SNAPSHOT_CACHE.get(directory)
    if cached and (now - cached[0]) < _FS_SNAPSHOT_TTL:
        return cached[1]

    root = _Path(directory)
    if not root.is_dir():
        _FS_SNAPSHOT_CACHE[directory] = (now, "")
        return ""

    entries: list[str] = []
    deadline = _time.monotonic() + _FS_SCAN_TIMEOUT
    try:
        for dirpath, dirnames, filenames in _os.walk(root, topdown=True):
            if _time.monotonic() > deadline:
                entries.append("  ... (scan timeout)")
                break
            depth = len(_Path(dirpath).relative_to(root).parts)
            if depth >= _FS_MAX_DEPTH:
                dirnames.clear()
                continue
            dirnames[:] = sorted(
                d for d in dirnames
                if d not in _FS_SKIP_DIRS and not d.startswith(".")
            )
            indent = "  " * depth
            rel = _Path(dirpath).relative_to(root)
            if depth > 0:
                entries.append(f"{indent}{rel.name}/")
            child_indent = "  " * (depth + 1)
            for fname in sorted(filenames):
                if _Path(fname).suffix.lower() in _FS_CODE_EXTS:
                    entries.append(f"{child_indent}{fname}")
            if len(entries) >= _FS_MAX_ENTRIES:
                entries.append("  ... (truncated)")
                break
    except (PermissionError, OSError):
        pass

    if not entries:
        _FS_SNAPSHOT_CACHE[directory] = (now, "")
        return ""

    result = (
        f"WORKSPACE FILE TREE ({directory}) — background context only.\n"
        "Reference this only when the user's request involves specific files or code.\n"
        "Do NOT explore or list these files unless explicitly asked to.\n"
        + "\n".join(entries[:_FS_MAX_ENTRIES])
    )
    if len(_FS_SNAPSHOT_CACHE) >= _FS_SNAPSHOT_CACHE_MAX:
        oldest = min(_FS_SNAPSHOT_CACHE, key=lambda k: _FS_SNAPSHOT_CACHE[k][0])
        del _FS_SNAPSHOT_CACHE[oldest]
    _FS_SNAPSHOT_CACHE[directory] = (now, result)
    return result


def _inject_workspace_context_sync(system_prompt: str, owner: Any) -> str:
    """Inject tool list + filesystem snapshot into the system prompt.

    Workspace directory priority:
      1. GUPPY_WORKSPACE_DIR env var
      2. Current working directory (where Guppy was launched)
    """
    parts = [system_prompt]

    tool_ctx = _build_tool_context(owner)
    if tool_ctx:
        parts.append(tool_ctx)

    workspace_dir = (
        owner.os.environ.get("GUPPY_WORKSPACE_DIR", "").strip()
        or str(_Path.home())
    )
    fs_ctx = _scan_workspace_sync(workspace_dir)
    if fs_ctx:
        parts.append(fs_ctx)

    return "\n\n".join(parts)


async def _inject_workspace_context_async(system_prompt: str, owner: Any) -> str:
    """Async wrapper — filesystem walk runs in a thread pool with a hard timeout."""
    try:
        return await asyncio.wait_for(
            asyncio.to_thread(_inject_workspace_context_sync, system_prompt, owner),
            timeout=3.0,
        )
    except asyncio.TimeoutError:
        return system_prompt


# ── Model identity injection ──────────────────────────────────────────────────

_COMPANION_IDENTITY = """
You are Guppy — Ryan's personal AI, running locally on his machine.

PERSONALITY:
- Direct and confident. Not a corporate assistant, not a yes-machine.
- Warm but not sycophantic. You don't start replies with "Certainly!" or "Of course!".
- Witty and slightly irreverent when the moment calls for it. Ryan appreciates that edge.
- Proactive: if you notice something useful, say it. Don't wait to be asked twice.
- Honest: you'd rather say "I don't know" than make something up.

ABOUT RYAN:
- His name is Ryan. Address him by name occasionally, naturally.
- Favorite color: electric blue.
- He runs a personal media vault and cares about his files and data.
- He wants you to be capable and opinionated, not deferential.

RESPONSE FORMAT:
- Casual question → 1–2 sentences. Don't over-explain.
- Detailed request → thorough, but cut every sentence that doesn't add value.
- No markdown headers or bullet lists for conversational replies.
- In voice mode (is_voice=True): one or two sentences ONLY. Conversational. No lists. No markdown.
- Don't narrate your own actions ("I'll now proceed to..."). Just do it.
- Do NOT use <think>...</think> reasoning blocks. Respond directly.
""".strip()

_MODEL_IDENTITY: dict[str, str] = {
    "companion": _COMPANION_IDENTITY,
    "workspace": "[Surface: Workspace | Model: Hermes 4.3 36B | Role: Agentic ops hub — execute tasks with full tool access.]",
    "codespace": "[Surface: Codespace | Model: Hermes 4.3 36B | Role: Code generation, debugging, sandbox execution.]",
}


def _inject_model_identity(system_prompt: str, surface: str, backend: str = "") -> str:
    """Prepend a model identity / personality block to the system prompt.

    For companion: full personality + user context block.
    For workspace/codespace: compact one-liner.
    """
    identity = _MODEL_IDENTITY.get(surface, f"[Model: {backend or 'Local LLM'} | Surface: {surface or 'unknown'}]")
    return f"{identity}\n\n{system_prompt}"


# ── Surface state awareness injection ─────────────────────────────────────────
# Injects a compact "[System State]" block so models know what other surfaces
# are doing without the user having to tell them.

_SURFACE_STATE_TTL = 15.0
_surface_state_cache: dict[str, tuple[float, str]] = {}


def _build_surface_state_block() -> str:
    """Read surface_state + recent tasks from the surface DB; returns a compact summary."""
    now = _time.monotonic()
    cached = _surface_state_cache.get("_")
    if cached and (now - cached[0]) < _SURFACE_STATE_TTL:
        return cached[1]

    text = ""
    try:
        import sqlite3
        from src.guppy.api.routes_surface import _DB_PATH
        if not _DB_PATH:
            return ""
        with sqlite3.connect(_DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT surface, status, current_task, agent_count FROM surface_state"
            ).fetchall()
            state_lines = []
            for row in rows:
                surf, status = row["surface"], row["status"] or "idle"
                task, agents = row["current_task"] or "", row["agent_count"] or 0
                if agents > 0 and task:
                    state_lines.append(f"  {surf}: {status} — {task} ({agents} agent{'s' if agents>1 else ''})")
                else:
                    state_lines.append(f"  {surf}: {status}")

            recent = conn.execute(
                """SELECT title, result, updated_at FROM surface_tasks
                   WHERE status='completed' AND updated_at > datetime('now','-1 hour')
                   ORDER BY updated_at DESC LIMIT 3"""
            ).fetchall()

            pending = conn.execute(
                """SELECT surface, title, status FROM surface_tasks
                   WHERE status IN ('queued','in_progress')
                   ORDER BY created_at ASC LIMIT 5"""
            ).fetchall()

        if not (state_lines or recent or pending):
            return ""

        parts = ["[System State]"]
        if state_lines:
            parts.append("Surfaces:\n" + "\n".join(state_lines))
        if pending:
            parts.append("Pending tasks:\n" + "\n".join(
                f"  [{r['surface']}] {r['title']} ({r['status']})" for r in pending
            ))
        if recent:
            parts.append("Recently completed:\n" + "\n".join(
                f"  {r['title']}: {(r['result'] or '')[:120].replace(chr(10),' ').strip() or 'done'}"
                for r in recent
            ))
        text = "\n".join(parts)
    except Exception as exc:
        _log.debug("Surface state injection failed: %s", exc)
        text = ""

    _surface_state_cache["_"] = (now, text)
    return text


def _inject_surface_state(system_prompt: str) -> str:
    """Append live surface state to system prompt so models see cross-surface context."""
    block = _build_surface_state_block()
    return f"{system_prompt}\n\n{block}" if block else system_prompt


async def _inject_surface_state_async(system_prompt: str) -> str:
    """Async wrapper for surface state injection (1s hard timeout)."""
    try:
        return await asyncio.wait_for(
            asyncio.to_thread(_inject_surface_state, system_prompt),
            timeout=1.0,
        )
    except (asyncio.TimeoutError, Exception):
        return system_prompt


# ── Pending workspace-task result injection ────────────────────────────────────
# Proactively injects recently-completed and in-flight workspace task results
# into the Companion system prompt so the model sees them without the user
# having to ask.  Uses the same _SURFACE_STATE_TTL cache to avoid extra DB hits.

_pending_tasks_cache: dict[str, tuple[float, str]] = {}


def _inject_pending_tasks(system_prompt: str, session_window_seconds: int = 3600) -> str:
    """Prepend a [Workspace Task Updates] block to system_prompt.

    Queries surface_tasks for:
    - tasks completed in the last *session_window_seconds* seconds (limit 5)
    - currently queued/in_progress tasks (limit 3)

    Returns the modified prompt, or the original if there is nothing to show.
    Uses a 15-second cache keyed on *session_window_seconds* to avoid hammering
    the DB on every token of a streaming response.
    """
    now = _time.monotonic()
    cache_key = str(session_window_seconds)
    cached = _pending_tasks_cache.get(cache_key)
    if cached and (now - cached[0]) < _SURFACE_STATE_TTL:
        block = cached[1]
        return f"{system_prompt}\n\n{block}" if block else system_prompt

    block = ""
    try:
        import sqlite3
        from src.guppy.api.routes_surface import _DB_PATH
        if not _DB_PATH:
            _pending_tasks_cache[cache_key] = (now, "")
            return system_prompt

        with sqlite3.connect(_DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            completed = conn.execute(
                f"""SELECT title, result, updated_at FROM surface_tasks
                    WHERE status='completed'
                      AND updated_at > datetime('now', '-{int(session_window_seconds)} seconds')
                    ORDER BY updated_at DESC LIMIT 5"""
            ).fetchall()

            pending = conn.execute(
                """SELECT id, title, status FROM surface_tasks
                   WHERE status IN ('queued', 'in_progress')
                   ORDER BY created_at ASC LIMIT 3"""
            ).fetchall()

        if not (completed or pending):
            _pending_tasks_cache[cache_key] = (now, "")
            return system_prompt

        lines = ["[Workspace Task Updates]"]
        for row in completed:
            result_snippet = (row["result"] or "done")[:200].replace("\n", " ").strip()
            lines.append(f'Completed recently: "{row["title"]}" — {result_snippet}')
        for row in pending:
            lines.append(f'In progress: "{row["title"]}" ({row["status"]})')

        block = "\n".join(lines)
    except Exception as exc:
        _log.debug("Pending task injection failed: %s", exc)
        block = ""

    _pending_tasks_cache[cache_key] = (now, block)
    return f"{system_prompt}\n\n{block}" if block else system_prompt


async def _inject_pending_tasks_async(system_prompt: str, session_window_seconds: int = 3600) -> str:
    """Async wrapper for pending task injection (1.5s hard timeout)."""
    try:
        return await asyncio.wait_for(
            asyncio.to_thread(_inject_pending_tasks, system_prompt, session_window_seconds),
            timeout=1.5,
        )
    except (asyncio.TimeoutError, Exception):
        return system_prompt
