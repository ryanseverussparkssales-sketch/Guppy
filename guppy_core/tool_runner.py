"""
guppy_core/tool_runner.py
Tool execution: run_tool(), _morning_brief(), _exec_tool().
Import run_tool from here, or from guppy_core for backward compatibility.
"""
from __future__ import annotations

import io  # noqa: F401
import os
import base64
import subprocess
import webbrowser
import time
import urllib.parse
from collections import deque  # noqa: F401
from pathlib import Path
from datetime import datetime
import logging
import threading  # noqa: F401
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError  # noqa: F401

from guppy_core.debug_flags import (
    SAFE_MODE, TOOL_LOG,
    TOOL_EXEC_TIMEOUT_SECONDS, TOOL_MAX_OUTPUT_CHARS,
    _TOOL_EXECUTOR,
    _TOOL_GUARD_LOCK, _TOOL_GUARDS,
)
from guppy_core.beta_policy import BETA_RESTRICTED_MODE, BETA_TOOL_ALLOWLIST
from guppy_core.tool_metrics import (
    _record_tool_call, _is_tool_blocked, _mark_tool_success, _mark_tool_failure,
)
from guppy_core.tool_registry import _validate_tool_input  # noqa: F401
from guppy_core.system_prompt import REPORTS_DIR
from utils.instance_capabilities import check_instance_tool_permission
from utils.connector_manager import get_workspace_connector_context

try:
    import pyautogui
    pyautogui.FAILSAFE = True
    pyautogui.PAUSE = 0.1
    PYA = True
except ImportError:
    PYA = False

try:
    from src.guppy.memory import memory as _mem
    _MEM = True
except ImportError:
    _mem = None
    _MEM = False

try:
    from src.guppy.memory import semantic as _smem
    _SMEM = True
except ImportError:
    _smem = None
    _SMEM = False

try:
    from src.guppy.daemon.daemon import get_daemon_manager, get_window_context
    DAEMON = True
except ImportError:
    DAEMON = False

    def get_daemon_manager():
        return None

    def get_window_context():
        return {"app": "unknown", "title": "unknown"}

logger = logging.getLogger(__name__)

# Compatibility export for legacy callers that still reference these module globals
# through guppy_core.tool_runner during the metrics refactor.
_TOOL_GUARD_LOCK = _TOOL_GUARD_LOCK
_TOOL_GUARDS = _TOOL_GUARDS


def _apply_workspace_connector_runtime_context(
    tool_name: str,
    inp: dict,
    *,
    instance_name: str | None = None,
) -> tuple[dict, str, str]:
    if not instance_name:
        return inp, "", ""
    try:
        context = get_workspace_connector_context(tool_name, instance_name, metadata=inp)
    except Exception:
        return inp, "", ""
    connector_id = str(context.get("connector_id", "") or "")
    provider = str(context.get("provider", "") or "").strip()
    account_id = str(context.get("account_id", "") or "").strip()
    if provider and not str(inp.get("provider", "") or "").strip():
        inp["provider"] = provider
    if account_id and not str(inp.get("account", "") or "").strip():
        inp["account"] = account_id
    return inp, connector_id, account_id


def _apply_workspace_connector_runtime_side_effects(
    tool_name: str,
    connector_id: str,
    account_id: str,
) -> None:
    if connector_id != "gmail" or not account_id:
        return
    if str(tool_name or "").strip().lower() == "gmail_switch_account":
        return
    try:
        from src.guppy.tools.media import gmail_switch_account

        gmail_switch_account(account_id)
    except Exception:
        return


def _safe_tool_metric_call(label: str, fn, *args, **kwargs):
    try:
        return fn(*args, **kwargs)
    except Exception as exc:
        logger.warning("Tool metrics update failed during %s: %s", label, exc)
        return None


# ── Tool runner ────────────────────────────────────────────────────────────────

def run_tool(
    name: str,
    inp: dict,
    *,
    instance_name: str | None = None,
    instance_type: str | None = None,
):
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
    inp, connector_id, connector_account_id = _apply_workspace_connector_runtime_context(
        name,
        dict(inp),
        instance_name=instance_name,
    )

    started = time.perf_counter()

    if SAFE_MODE:
        entry = {
            "time": datetime.now().strftime("%H:%M:%S"),
            "tool": name,
            "args": str(inp)[:80],
            "result": "[SAFE MODE — blocked]",
        }
        TOOL_LOG.append(entry)
        _safe_tool_metric_call(
            f"{name}:safe_mode",
            _record_tool_call,
            name,
            (time.perf_counter() - started) * 1000.0,
            "blocked",
            "safe_mode",
        )
        return f"[SAFE MODE ACTIVE] Tool blocked: {name}"

    if BETA_RESTRICTED_MODE and name not in BETA_TOOL_ALLOWLIST:
        reason = (
            f"Tool {name} is blocked by beta restricted policy. "
            "Allowed tools are limited for remote tester safety."
        )
        _safe_tool_metric_call(
            f"{name}:beta_policy",
            _record_tool_call,
            name,
            (time.perf_counter() - started) * 1000.0,
            "blocked",
            "beta_restricted_policy",
        )
        TOOL_LOG.append({
            "time": datetime.now().strftime("%H:%M:%S"),
            "tool": name,
            "args": str(inp)[:80],
            "result": reason[:150],
        })
        return f"Error: {reason}"

    permission_endpoint = str(
        inp.get("endpoint")
        or inp.get("url")
        or inp.get("base_url")
        or inp.get("host")
        or ""
    ).strip()
    permission_metadata = {
        "url": inp.get("url"),
        "endpoint_target": inp.get("target_instance") or inp.get("instance"),
        "workspace_auth": bool(inp.get("workspace_auth")),
        "provider": inp.get("provider"),
        "account": inp.get("account"),
        "account_id": inp.get("account_id"),
        "calendar_id": inp.get("calendar_id"),
    }
    permitted, permission_reason, _permissions = check_instance_tool_permission(
        name,
        instance_name=instance_name,
        instance_type=instance_type,
        endpoint=permission_endpoint or None,
        metadata=permission_metadata,
    )
    if not permitted:
        _safe_tool_metric_call(
            f"{name}:instance_capability_block",
            _record_tool_call,
            name,
            (time.perf_counter() - started) * 1000.0,
            "blocked",
            permission_reason,
        )
        TOOL_LOG.append({
            "time": datetime.now().strftime("%H:%M:%S"),
            "tool": name,
            "args": str(inp)[:80],
            "result": permission_reason[:150],
        })
        return f"Error: {permission_reason}"

    _apply_workspace_connector_runtime_side_effects(name, connector_id, connector_account_id)

    input_error = _validate_tool_input(name, inp)
    if input_error:
        msg = f"Error: {input_error}"
        _safe_tool_metric_call(
            f"{name}:input_error",
            _record_tool_call,
            name,
            (time.perf_counter() - started) * 1000.0,
            "error",
            msg,
        )
        TOOL_LOG.append({
            "time": datetime.now().strftime("%H:%M:%S"),
            "tool": name,
            "args": str(inp)[:80],
            "result": msg[:150],
        })
        return msg

    blocked, block_reason = _is_tool_blocked(name)
    if blocked:
        _safe_tool_metric_call(
            f"{name}:blocked",
            _record_tool_call,
            name,
            (time.perf_counter() - started) * 1000.0,
            "blocked",
            block_reason,
        )
        TOOL_LOG.append({
            "time": datetime.now().strftime("%H:%M:%S"),
            "tool": name,
            "args": str(inp)[:80],
            "result": block_reason[:150],
        })
        return f"Error: {block_reason}"

    state = "success"
    error_msg = ""
    inline_tools = {"semantic_remember", "semantic_recall", "query_instance"}
    try:
        if name in inline_tools:
            result = _exec_tool(name, inp, instance_name=instance_name)
        else:
            fut = _TOOL_EXECUTOR.submit(_exec_tool, name, inp, instance_name=instance_name)
            result = fut.result(timeout=TOOL_EXEC_TIMEOUT_SECONDS)
    except FuturesTimeoutError:
        state = "timeout"
        error_msg = f"Tool {name} exceeded {TOOL_EXEC_TIMEOUT_SECONDS}s timeout"
        _safe_tool_metric_call(f"{name}:timeout", _mark_tool_failure, name, error_msg)
        result = f"Error: {error_msg}"
    except Exception as e:
        state = "error"
        error_msg = f"Tool execution failure: {e}"
        _safe_tool_metric_call(f"{name}:error", _mark_tool_failure, name, error_msg)
        result = f"Error: {error_msg}"
    else:
        if isinstance(result, str) and result.lower().startswith("error"):
            state = "error"
            error_msg = result[:180]
            _safe_tool_metric_call(f"{name}:result_error", _mark_tool_failure, name, error_msg)
        else:
            _safe_tool_metric_call(f"{name}:success", _mark_tool_success, name)

    # Memory optimization: bound tool result sizes
    if isinstance(result, str) and len(result) > TOOL_MAX_OUTPUT_CHARS:
        result = result[:TOOL_MAX_OUTPUT_CHARS] + f"\n\n[Output truncated — {len(result)} chars total]"
    elif isinstance(result, dict) and "image_base64" in result:
        # Screenshots already optimized (base64 removed), but bound other fields
        for key, value in result.items():
            if isinstance(value, str) and len(value) > 500:
                result[key] = value[:500] + "..."

    _safe_tool_metric_call(
        f"{name}:final_record",
        _record_tool_call,
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


def _make_internal_query_token() -> str:
    """Generate a short-lived HS256 JWT for internal instance-to-instance queries.

    Uses GUPPY_JWT_SECRET from the environment — the same secret the API uses.
    Returns an empty string if the secret is unavailable (API will still accept
    the call from localhost in dev mode via the DEV_MODE bypass).
    """
    secret = os.environ.get("GUPPY_JWT_SECRET", "").strip()
    if not secret:
        return ""
    try:
        from jose import jwt as _jose_jwt
        return str(
            _jose_jwt.encode(
                {
                    "sub": "internal_tool_runner",
                    "iat": int(time.time()),
                    "exp": int(time.time()) + 60,
                },
                secret,
                algorithm="HS256",
            )
        )
    except Exception:
        return ""


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
        from src.guppy.tools.media import calendar_events as _cal_events
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
            from src.guppy.tools.media import gmail_unread_count, _GMAIL_ACCOUNTS
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
            from src.guppy.tools.media import gmail_scan_inbox
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
                from src.guppy.tools.media import calendar_events as _c
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


def _exec_tool(name: str, inp: dict, *, instance_name: str | None = None):
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

        elif name == "apply_patch":
            import shutil
            import tempfile
            patch_content = inp["patch"]
            if not shutil.which("git"):
                return "Error: git not found on PATH — cannot apply patch"
            with tempfile.NamedTemporaryFile(
                mode="w", suffix=".patch", delete=False, encoding="utf-8"
            ) as pf:
                pf.write(patch_content)
                patch_file = pf.name
            try:
                r = subprocess.run(
                    ["git", "apply", "--whitespace=fix", patch_file],
                    capture_output=True, text=True, timeout=15,
                )
                if r.returncode == 0:
                    return f"Patch applied successfully.{(' ' + r.stdout.strip()) if r.stdout.strip() else ''}"
                return f"Patch failed (exit {r.returncode}): {(r.stderr or r.stdout).strip()}"
            except Exception as e:
                return f"Error applying patch: {e}"
            finally:
                try:
                    os.unlink(patch_file)
                except Exception:
                    pass

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
                # Fallback: DuckDuckGo programmatic search (no API key needed)
                try:
                    from ddgs import DDGS as _DDGS
                except ImportError:
                    try:
                        from duckduckgo_search import DDGS as _DDGS  # type: ignore
                    except ImportError:
                        _DDGS = None  # type: ignore
                if _DDGS is not None:
                    try:
                        max_r = int(inp.get("max_results", 8))
                        _results = list(_DDGS().text(query, max_results=max_r))
                        if _results:
                            lines = [f"Search results for: {query!r}\n"]
                            for i, r in enumerate(_results, 1):
                                lines.append(
                                    f"{i}. {r.get('title', '')}\n"
                                    f"   URL: {r.get('href') or r.get('url', '')}\n"
                                    f"   {r.get('body') or r.get('snippet', '')}\n"
                                )
                            return "\n".join(lines)
                    except Exception:
                        pass  # fall through to browser
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
            from src.guppy.integrations.crm_voip import list_external_integrations
            return list_external_integrations()

        elif name == "crm_upsert_contact":
            from src.guppy.integrations.crm_voip import crm_upsert_contact
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
            from src.guppy.integrations.crm_voip import crm_create_opportunity
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
            from src.guppy.integrations.crm_voip import voip_place_call
            return voip_place_call(
                inp.get("provider", "twilio"),
                inp["to_number"],
                inp.get("from_number", ""),
                inp.get("contact_name", ""),
                inp.get("purpose", ""),
                inp.get("dry_run", True),
            )

        elif name == "get_foundation_readiness":
            from src.guppy.integrations.crm_voip import get_foundation_readiness_text
            return get_foundation_readiness_text()

        # ── Spotify ───────────────────────────────────────────────────────────
        elif name == "spotify_play":
            from src.guppy.tools.media import spotify_play
            return spotify_play(inp["query"])

        elif name == "spotify_pause":
            from src.guppy.tools.media import spotify_pause
            return spotify_pause()

        elif name == "spotify_resume":
            from src.guppy.tools.media import spotify_resume
            return spotify_resume()

        elif name == "spotify_next":
            from src.guppy.tools.media import spotify_next
            return spotify_next()

        elif name == "spotify_prev":
            from src.guppy.tools.media import spotify_prev
            return spotify_prev()

        elif name == "spotify_current":
            from src.guppy.tools.media import spotify_current
            return spotify_current()

        elif name == "spotify_volume":
            from src.guppy.tools.media import spotify_volume
            return spotify_volume(int(inp["level"]))

        # ── YouTube ───────────────────────────────────────────────────────────
        elif name == "youtube_play":
            from src.guppy.tools.media import youtube_play
            return youtube_play(inp["query"])

        elif name == "youtube_search":
            from src.guppy.tools.media import youtube_search
            return youtube_search(inp["query"])

        # ── Gmail purge ───────────────────────────────────────────────────────
        elif name == "gmail_purge":
            from src.guppy.tools.media import gmail_purge
            return gmail_purge(inp["query"], int(inp.get("max_results", 500)))

        elif name == "gmail_purge_label":
            from src.guppy.tools.media import gmail_purge_label
            return gmail_purge_label(inp["label"])

        elif name == "gmail_purge_sender":
            from src.guppy.tools.media import gmail_purge_sender
            return gmail_purge_sender(inp["email"])

        elif name == "gmail_purge_older_than":
            from src.guppy.tools.media import gmail_purge_older_than
            return gmail_purge_older_than(int(inp["days"]))

        elif name == "gmail_empty_trash":
            from src.guppy.tools.media import gmail_empty_trash
            return gmail_empty_trash()

        elif name == "gmail_switch_account":
            from src.guppy.tools.media import gmail_switch_account
            return gmail_switch_account(inp["alias"])

        elif name == "gmail_list_accounts":
            from src.guppy.tools.media import gmail_list_accounts
            return gmail_list_accounts()

        elif name == "gmail_smart_cleanup":
            from src.guppy.tools.media import gmail_smart_cleanup
            return gmail_smart_cleanup(int(inp.get("max_per_step", 500)))

        # ── Reminders & Tasks ──────────────────────────────────────────────────
        elif name == "remind_me":
            # Always use the persistent DB-backed reminder system so the web UI can deliver it
            try:
                from src.guppy.api.routes_reminders import create_reminder as _create_reminder
                msg = str(inp.get("message", "")).strip()
                if not msg:
                    return "Error: 'message' is required for reminders."
                # Accept either 'time' (natural like '30 minutes') or 'delay_minutes'
                delay_raw = inp.get("delay_minutes") or inp.get("time", "30")
                delay_minutes = 30.0
                if delay_raw:
                    import re as _re
                    m = _re.search(r"(\d+(?:\.\d+)?)", str(delay_raw))
                    if m:
                        delay_minutes = float(m.group(1))
                        # If the value looks like hours (e.g. "2 hours"), multiply
                        if "hour" in str(delay_raw).lower():
                            delay_minutes *= 60
                result = _create_reminder(msg, delay_minutes=delay_minutes)
                from datetime import datetime, timezone
                due_local = result["due_at"][:16].replace("T", " ")
                return (
                    f"Reminder set! I'll ping you in {int(delay_minutes)} minute(s) via browser notification.\n"
                    f"Message: \"{msg}\"\nDue at: {due_local} UTC\nID: {result['id']}"
                )
            except Exception as e:
                return f"Error scheduling reminder: {e}"

        elif name == "get_reminders":
            try:
                import sqlite3 as _sq, os as _os
                _os.makedirs("runtime", exist_ok=True)
                conn = _sq.connect("runtime/reminders.db")
                conn.row_factory = _sq.Row
                try:
                    conn.execute("CREATE TABLE IF NOT EXISTS reminders (id TEXT, message TEXT, due_at TEXT, delivered INTEGER, created_at TEXT)")
                    rows = conn.execute("SELECT * FROM reminders WHERE delivered=0 ORDER BY due_at").fetchall()
                finally:
                    conn.close()
                if not rows:
                    return "No active reminders scheduled."
                result = "Active reminders:\n"
                for row in rows:
                    result += f"  [{row['id'][:8]}] {row['message']} — due {row['due_at'][:16]} UTC\n"
                return result
            except Exception as e:
                return f"Error retrieving reminders: {e}"

        elif name == "cancel_reminder":
            try:
                import sqlite3 as _sq, os as _os
                _os.makedirs("runtime", exist_ok=True)
                rid = str(inp.get("reminder_id", "")).strip()
                if not rid:
                    return "Error: reminder_id required."
                conn = _sq.connect("runtime/reminders.db")
                try:
                    r = conn.execute("DELETE FROM reminders WHERE id=? OR id LIKE ?", (rid, f"{rid}%"))
                    conn.commit()
                    deleted = r.rowcount
                finally:
                    conn.close()
                return f"Reminder {'cancelled' if deleted else 'not found (may have already fired)'}."
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

                # Prefer local vision model; fall back to Claude if key available
                _local_vision = os.environ.get("GUPPY_VISION_MODEL", "guppy-vision")
                _ollama_base = os.environ.get("GUPPY_OLLAMA_BASE_URL", "http://127.0.0.1:11434").rstrip("/")
                import urllib.request as _urlreq, json as _json
                _payload = _json.dumps({
                    "model": _local_vision,
                    "messages": [{
                        "role": "user",
                        "content": instruction,
                        "images": [img_b64],
                    }],
                    "stream": False,
                    "options": {"num_predict": 1024},
                }).encode()
                try:
                    _req = _urlreq.Request(
                        f"{_ollama_base}/api/chat",
                        data=_payload,
                        headers={"Content-Type": "application/json"},
                        method="POST",
                    )
                    with _urlreq.urlopen(_req, timeout=60) as _r:
                        _data = _json.loads(_r.read())
                    return (_data.get("message", {}).get("content") or "No text extracted.").strip()
                except Exception:
                    pass
                # Claude fallback
                _api_key = os.environ.get("ANTHROPIC_API_KEY", "")
                if not _api_key:
                    return "Vision unavailable: local model unreachable and no ANTHROPIC_API_KEY set."
                import anthropic as _ant
                _vision_client = _ant.Anthropic(api_key=_api_key)
                resp = _vision_client.messages.create(
                    model=os.environ.get("ANTHROPIC_BACKUP_MODEL", "claude-haiku-4-5-20251001"),
                    max_tokens=1024,
                    messages=[{
                        "role": "user",
                        "content": [
                            {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": img_b64}},
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
            from src.guppy.tools.media import gmail_scan_inbox
            return gmail_scan_inbox(
                max_emails=int(inp.get("max_emails", 30)),
                account=inp.get("account", ""),
                auto_task=inp.get("auto_task", True),
                dry_run=inp.get("dry_run", False),
            )

        # ── Calendar ──────────────────────────────────────────────────────────
        elif name == "calendar_events":
            from src.guppy.tools.media import calendar_events as _cal_events
            return _cal_events(
                days=int(inp.get("days", 1)),
                max_results=int(inp.get("max_results", 20)),
                calendar_id=inp.get("calendar_id", "primary"),
            )

        # ── Send Email ────────────────────────────────────────────────────────
        elif name == "send_email":
            from src.guppy.tools.media import gmail_send
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
            from src.guppy.tools.github import github_action
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

        # ── Cross-instance query ──────────────────────────────────────────────
        elif name == "query_instance":
            import json as _json
            import urllib.request as _ureq
            target = (inp.get("instance") or inp.get("target") or "").strip()
            message = (inp.get("message") or "").strip()
            timeout_s = float(inp.get("timeout_s") or 30.0)
            timeout_s = max(1.0, min(timeout_s, 120.0))
            # Optional routing mode: "auto", "local", "claude", "code"
            routing_mode = (inp.get("mode") or "").strip().lower() or None
            source = (instance_name or "tool_runner").strip()
            if not target:
                return "Error: 'instance' is required. Example: query_instance(instance='guppy-primary', message='...')"
            if not message:
                return "Error: 'message' is required."
            api_port = int(os.environ.get("GUPPY_API_PORT", "8081"))
            api_url = f"http://127.0.0.1:{api_port}/instances/{urllib.parse.quote(target)}/query"
            token = _make_internal_query_token()
            headers: dict = {"Content-Type": "application/json"}
            if token:
                headers["Authorization"] = f"Bearer {token}"
            body: dict = {
                "message": message,
                "source_instance": source,
                "timeout_s": timeout_s,
            }
            if routing_mode:
                body["mode"] = routing_mode
            payload = _json.dumps(body).encode()
            try:
                req = _ureq.Request(api_url, data=payload, headers=headers, method="POST")
                with _ureq.urlopen(req, timeout=int(timeout_s) + 5) as r:
                    data = _json.loads(r.read().decode())
                status = data.get("status", "unknown")
                if status == "busy":
                    return f"Instance '{target}' is currently busy handling another query. Retry in a moment."
                if status == "timeout":
                    return f"Instance '{target}' did not respond within {timeout_s:.0f}s."
                response = str(data.get("response", "") or "").strip()
                if not response:
                    return f"Instance '{target}' returned an empty response."
                ms = int(data.get("duration_ms", 0) or 0)
                model = str(data.get("model", "") or "")
                suffix = f" [model={model}, {ms}ms]" if model else f" [{ms}ms]"
                return f"[{target}]{suffix}\n{response}"
            except _ureq.HTTPError as e:
                body = e.read().decode("utf-8", errors="replace")[:300]
                return f"Error querying '{target}': HTTP {e.code} — {body}"
            except _ureq.URLError as e:
                return f"Error: Guppy API not reachable on port {api_port}. Is the server running? ({e.reason})"
            except Exception as e:
                return f"Error querying instance '{target}': {e}"

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
