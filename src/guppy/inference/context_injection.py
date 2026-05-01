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

def _bg_store_tool_outcome(name: str, args: dict, result: str) -> None:
    """Fire-and-forget: persist successful tool call outcome to semantic memory."""
    import threading
    import hashlib

    def _store() -> None:
        try:
            from src.guppy.memory.semantic import remember_semantic
            args_str = str(sorted((args or {}).items()))[:200]
            key = f"tool_outcome:{name}:{hashlib.md5(args_str.encode()).hexdigest()[:8]}"
            value = f"{name}({args_str[:150]}) → {result[:500]}"
            remember_semantic(key, value, category="tool_outcome")
        except Exception:
            pass

    threading.Thread(target=_store, daemon=True, name="tool-outcome-mem").start()


def _bg_summarize_session(history: list[dict]) -> None:
    """Fire-and-forget: summarize recent conversation turns into semantic memory.

    Called when history reaches every 10th turn. Uses phi-4-mini (port 8091)
    so summarization is cheap, non-blocking, and Ollama-free.
    """
    import threading

    def _run() -> None:
        try:
            import time
            import requests
            turns = []
            for msg in history[-12:]:
                role = msg.get("role", "user")
                content = str(msg.get("content", ""))[:300]
                turns.append(f"{role}: {content}")
            history_text = "\n".join(turns)
            payload = {
                "model": "phi-4-mini-instruct",
                "messages": [
                    {
                        "role": "system",
                        "content": (
                            "Summarize this conversation in 2-3 compact sentences. "
                            "Focus on: what the user asked, which tools were used, and what outcomes occurred. "
                            "Be specific about facts, file names, and results. No preamble."
                        ),
                    },
                    {"role": "user", "content": f"Summarize:\n{history_text}"},
                ],
                "stream": False,
            }
            r = requests.post("http://localhost:8091/v1/chat/completions", json=payload, timeout=30)
            r.raise_for_status()
            summary = (r.json().get("choices", [{}])[0].get("message", {}).get("content", "") or "").strip()
            if summary and len(summary) > 30:
                from src.guppy.memory.semantic import remember_semantic
                key = f"session_summary:{int(time.time())}"
                remember_semantic(key, summary, category="session_summary")
        except Exception as exc:
            _log.debug("Session summarization failed: %s", exc)

    threading.Thread(target=_run, daemon=True, name="session-summarizer").start()


# ── Semantic RAG injection ─────────────────────────────────────────────────────

def _inject_semantic_context(system_prompt: str, user_text: str, owner: Any) -> str:
    """Append relevant ChromaDB/SQLite semantic memory to the system prompt."""
    if not (owner.os.environ.get("GUPPY_SEMANTIC_RAG", "1").strip().lower() in {"1", "true", "yes", "on"}):
        return system_prompt
    try:
        from src.guppy.memory.semantic import build_semantic_prompt_context
        ctx = build_semantic_prompt_context(user_text, n=4)
        if ctx:
            return f"{system_prompt}\n\n{ctx}"
    except Exception as exc:
        _log.debug("Semantic context injection failed: %s", exc)
    return system_prompt


async def _inject_semantic_context_async(system_prompt: str, user_text: str, owner: Any) -> str:
    """Async wrapper — runs the synchronous ChromaDB/SQLite read in a thread pool."""
    try:
        return await asyncio.wait_for(
            asyncio.to_thread(_inject_semantic_context, system_prompt, user_text, owner),
            timeout=2.0,
        )
    except asyncio.TimeoutError:
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

• web_fetch(url, extract?)
  WHEN: user asks to look something up, fetch a page, check a site, get content
  from a URL, or research a topic that needs live data.
  EXAMPLE: <tool_call>{"name": "web_fetch", "arguments": {"url": "https://example.com", "extract": "pricing"}}</tool_call>

• create_reminder(message, delay_minutes?, due_iso?)
  WHEN: user says "remind me", "don't let me forget", "set a reminder", or
  gives a task with a time ("do X in 30 minutes", "tell me at 3pm").
  EXAMPLE: <tool_call>{"name": "create_reminder", "arguments": {"message": "Call dentist", "delay_minutes": 60}}</tool_call>

• memory_write(key, value)
  WHEN: user says "remember that", "keep track of", "store this", or shares
  information they'll want you to recall later (preferences, facts, names).
  EXAMPLE: <tool_call>{"name": "memory_write", "arguments": {"key": "user_pref_coffee", "value": "oat milk no sugar"}}</tool_call>

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
