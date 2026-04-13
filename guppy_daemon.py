"""
guppy_daemon.py — Background services, notifications, scheduling
==================================================================
Provides:
  - Toast notifications (Windows 10+)
  - Daemon thread management (graceful shutdown)
  - Window/app awareness (foreground app context)
  - Scheduled tasks (APScheduler)
  - Natural language time parsing
"""

import subprocess
import os
import threading
import time
import logging
import json
import urllib.request
import xml.etree.ElementTree as ET
from uuid import uuid4
from pathlib import Path
from typing import Callable, Optional, Dict, Any
from datetime import datetime, timedelta

try:
    import psutil
    PSUTIL_AVAILABLE = True
except Exception:
    PSUTIL_AVAILABLE = False

try:
    from utils.operational_telemetry import log_operational_event
except Exception:
    def log_operational_event(*_args, **_kwargs):
        return

try:
    from utils.runtime_profile import get_runtime_envelope_config
except Exception:
    def get_runtime_envelope_config(profile: str | None = None) -> Dict[str, Any]:
        active = (profile or os.environ.get("GUPPY_RUNTIME_PROFILE", "standard") or "standard").strip().lower()
        return {
            "profile": active,
            "cpu_max_pct": float(os.environ.get("GUPPY_ENVELOPE_CPU_MAX_PCT", "80")),
            "ram_max_pct": float(os.environ.get("GUPPY_ENVELOPE_RAM_MAX_PCT", "88")),
            "check_interval_s": int(os.environ.get("GUPPY_ENVELOPE_CHECK_S", "60")),
        }

try:
    from win11toast import toast as win11_toast
    TOAST_AVAILABLE = True
except ImportError:
    TOAST_AVAILABLE = False

try:
    import win32gui
    import win32api
    WIN32_AVAILABLE = True
except ImportError:
    WIN32_AVAILABLE = False

from apscheduler.schedulers.background import BackgroundScheduler
from dateutil import parser as dateutil_parser


logger = logging.getLogger(__name__)


# ── Toast Notifications ────────────────────────────────────────────────────────

class GuppyNotifier:
    """Windows 11 toast notification system."""

    def __init__(self):
        self._toast = win11_toast if TOAST_AVAILABLE else None
        self.app_id = "Guppy"

    def show(self, title: str, msg: str, duration: int = 5, icon: Optional[str] = None):
        """Show a toast notification.

        Args:
            title: Notification title
            msg: Notification body
            duration: Display duration (seconds)
            icon: Path to icon file (.ico)
        """
        if not TOAST_AVAILABLE:
            logger.warning(f"Toast unavailable: {title} — {msg}")
            return

        try:
            kwargs = {"app_id": self.app_id, "duration": str(duration)}
            if icon and Path(icon).exists():
                kwargs["icon"] = icon
            self._toast(title, msg, **kwargs)
        except Exception as e:
            logger.error(f"Toast failed: {e}")

    def reminder(self, text: str):
        """Show a reminder toast."""
        self.show("⏰ Guppy Reminder", text, duration=10)

    def task_done(self, task_name: str):
        """Show task completion toast."""
        self.show("✓ Task Complete", task_name, duration=5)

    def error(self, msg: str):
        """Show error toast."""
        self.show("⚠️ Error", msg, duration=10)

    def info(self, title: str, msg: str):
        """Show info toast."""
        self.show(title, msg, duration=5)


# ── Window/App Awareness ───────────────────────────────────────────────────────

class WindowWatcher:
    """Monitor foreground window changes and app context."""

    def __init__(self, poll_interval: float = 0.5):
        env_poll = os.environ.get("GUPPY_WINDOW_POLL_INTERVAL_S", "").strip()
        if env_poll:
            try:
                poll_interval = float(env_poll)
            except Exception:
                pass
        self.poll_interval = max(0.5, min(float(poll_interval), 5.0))
        self._current_app = None
        self._running = False
        self._thread = None
        self._callbacks = []

    def register_callback(self, fn: Callable[[str, str], None]):
        """Register a callback: fn(app_name, window_title)"""
        self._callbacks.append(fn)

    def get_context(self) -> Dict[str, str]:
        """Get current window/app context."""
        if not WIN32_AVAILABLE:
            return {"app": "unknown", "title": "unknown"}

        try:
            hwnd = win32gui.GetForegroundWindow()
            title = win32gui.GetWindowText(hwnd)
            class_name = win32gui.GetClassName(hwnd)

            # Simple heuristic: class name often contains app identifier
            app_name = self._identify_app(hwnd, class_name, title)
            return {"app": app_name, "title": title}
        except Exception as e:
            logger.debug(f"Window context error: {e}")
            return {"app": "unknown", "title": "unknown"}

    def get_context_help(self, app_name: str, window_title: str) -> str:
        """Get context-specific help suggestions based on current app."""
        app_lower = app_name.lower()
        title_lower = window_title.lower()
        
        # Development tools
        if "visual studio code" in app_lower or "vscode" in app_lower:
            return "I can help with coding, debugging, file operations, and Git commands."
        elif "visual studio" in app_lower:
            return "I can assist with .NET development, debugging, and project management."
        elif "pycharm" in app_lower or "intellij" in app_lower:
            return "I can help with Python/Java development, refactoring, and IDE features."
        
        # Microsoft Office
        elif "outlook" in app_lower:
            return "I can help with email management, scheduling, and contact organization."
        elif "excel" in app_lower:
            return "I can assist with spreadsheet formulas, data analysis, and chart creation."
        elif "word" in app_lower:
            return "I can help with document formatting, templates, and writing assistance."
        elif "powerpoint" in app_lower:
            return "I can assist with presentation design, slide layouts, and content creation."
        
        # Browsers and web apps
        elif "chrome" in app_lower or "firefox" in app_lower or "edge" in app_lower:
            if "gmail" in title_lower:
                return "I can help with email composition, organization, and Gmail automation."
            elif "github" in title_lower:
                return "I can assist with Git operations, pull requests, and repository management."
            elif "stackoverflow" in title_lower:
                return "I can help with programming questions and code debugging."
            elif "youtube" in title_lower:
                return "I can help find videos, playlists, and YouTube content."
            else:
                return "I can help with web browsing, research, and online tasks."
        
        # Communication
        elif "slack" in app_lower:
            return "I can help with team communication, channel management, and productivity."
        elif "teams" in app_lower:
            return "I can assist with meeting scheduling, file sharing, and collaboration."
        elif "discord" in app_lower:
            return "I can help with community management and server organization."
        
        # File management
        elif "file explorer" in app_lower:
            return "I can help with file organization, search, and system navigation."
        
        # Media
        elif "spotify" in app_lower:
            return "I can help control music playback, create playlists, and find songs."
        
        # Default help
        else:
            return f"I can help with general tasks while you're using {app_name}."

    def get_enhanced_context(self) -> Dict[str, str]:
        """Get current window/app context with help suggestions."""
        base_context = self.get_context()
        help_text = self.get_context_help(base_context["app"], base_context["title"])
        return {
            **base_context,
            "help": help_text
        }

    def _identify_app(self, hwnd: int, class_name: str, title: str) -> str:
        """Identify app from class name and title with comprehensive mapping."""
        # Expanded map of common class names to app names
        app_map = {
            # Browsers
            "Chrome_WidgetWin": "Google Chrome",
            "Mozilla Firefox": "Mozilla Firefox",
            "MSEdge": "Microsoft Edge",
            "Safari": "Safari",
            
            # Microsoft Office
            "OUTLOOK": "Microsoft Outlook",
            "EXCEL": "Microsoft Excel", 
            "WINWORD": "Microsoft Word",
            "POWERPNT": "Microsoft PowerPoint",
            "MSACCESS": "Microsoft Access",
            
            # Development Tools
            "VsCode": "Visual Studio Code",
            "Code": "Visual Studio Code",
            "devenv": "Visual Studio",
            "Notepad++": "Notepad++",
            "notepad": "Notepad",
            "PyCharm": "PyCharm",
            "IntelliJ": "IntelliJ IDEA",
            
            # Communication
            "Teams": "Microsoft Teams",
            "Slack": "Slack",
            "Discord": "Discord",
            "WhatsApp": "WhatsApp",
            "Telegram": "Telegram",
            
            # File Managers
            "CabinetWClass": "File Explorer",
            "ExploreWClass": "File Explorer",
            
            # Media
            "WMPlayerApp": "Windows Media Player",
            "SpotifyMainWindow": "Spotify",
            "iTunes": "iTunes",
            
            # System
            "ApplicationFrameWindow": "Windows Store App",
            "Shell_TrayWnd": "Taskbar",
            "Progman": "Desktop",
            
            # Other common apps
            "AcrobatSDIWindow": "Adobe Acrobat",
            "Photoshop": "Adobe Photoshop",
            "Illustrator": "Adobe Illustrator",
        }

        # Check class name first
        for key, app_name in app_map.items():
            if key in class_name:
                return app_name

        # Check title for additional patterns
        for key, app_name in app_map.items():
            if key in title:
                return app_name

        # Special handling for web apps and browser tabs
        if "Chrome" in class_name or "Firefox" in class_name or "Edge" in class_name:
            # Try to extract app name from title
            title_lower = title.lower()
            if "gmail" in title_lower or "mail.google" in title_lower:
                return "Gmail"
            elif "youtube" in title_lower:
                return "YouTube"
            elif "github" in title_lower:
                return "GitHub"
            elif "stackoverflow" in title_lower:
                return "Stack Overflow"
            elif "docs.google" in title_lower:
                return "Google Docs"
            elif "sheets.google" in title_lower:
                return "Google Sheets"
            elif "slack" in title_lower:
                return "Slack"
            elif "notion" in title_lower:
                return "Notion"
            elif "discord" in title_lower:
                return "Discord"

        # Fall back to title or class name
        if title:
            # Extract first few words from title (often contain app name)
            parts = title.split(" - ")
            candidate = parts[-1][:50] if parts else class_name[:50]
            
            # Clean up common suffixes
            candidate = candidate.replace(" - Google Chrome", "").replace(" - Mozilla Firefox", "")
            return candidate

        return class_name[:50] if class_name else "unknown"

    def start(self):
        """Start background window watching."""
        if self._running:
            return

        self._running = True
        self._thread = threading.Thread(target=self._watch_loop, daemon=True)
        self._thread.start()
        logger.info("Window watcher started")

    def stop(self):
        """Stop window watching."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=2)
        logger.info("Window watcher stopped")

    def _watch_loop(self):
        """Background loop that polls foreground window."""
        while self._running:
            try:
                context = self.get_context()
                if context["app"] != self._current_app:
                    self._current_app = context["app"]
                    for fn in self._callbacks:
                        try:
                            fn(context["app"], context["title"])
                        except Exception as e:
                            logger.error(f"Callback error: {e}")
                time.sleep(self.poll_interval)
            except Exception as e:
                logger.error(f"Watch loop error: {e}")
                time.sleep(1)


# ── Scheduled Tasks & Reminders ────────────────────────────────────────────────

class TaskScheduler:
    """Manage scheduled reminders and tasks (APScheduler wrapper)."""

    def __init__(self, notifier: Optional[GuppyNotifier] = None):
        self.scheduler = BackgroundScheduler()
        self.notifier = notifier
        self.jobs = {}  # id -> {job: Job, text: str} mapping
        self.reminders = {}  # id -> reminder text
        self.runtime_dir = Path(__file__).parent / "runtime"
        self.reminder_events_path = self.runtime_dir / "reminder_events.jsonl"

    def _emit_ipc(self, agent: str, cmd: str, payload: Optional[dict] = None):
        """Write a lightweight IPC command file for a UI agent."""
        try:
            self.runtime_dir.mkdir(parents=True, exist_ok=True)
            cmd_path = self.runtime_dir / f"{agent}.cmd"
            data = {
                "cmd": cmd,
                "payload": payload or {},
                "ts": datetime.now().isoformat(),
            }
            cmd_path.write_text(json.dumps(data, ensure_ascii=True), encoding="utf-8")
        except Exception as e:
            logger.debug(f"IPC emit failed ({agent}:{cmd}): {e}")

    def _record_reminder_event(self, event: str, job_id: str, message: str, trigger_time: Optional[datetime] = None):
        """Append reminder workflow events for schedule/action/confirmation traceability."""
        try:
            self.runtime_dir.mkdir(parents=True, exist_ok=True)
            payload = {
                "ts": datetime.now().isoformat(),
                "event": event,
                "job_id": job_id,
                "short_id": job_id[-8:] if job_id else "",
                "message": message,
            }
            if trigger_time is not None:
                payload["trigger_time"] = trigger_time.isoformat()
            with self.reminder_events_path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(payload, ensure_ascii=True) + "\n")
        except Exception as e:
            logger.debug(f"Reminder event logging failed: {e}")

    def start(self):
        """Start the scheduler."""
        if not self.scheduler.running:
            self.scheduler.start()
            logger.info("Task scheduler started")

    def stop(self):
        """Stop the scheduler and shut down gracefully."""
        if self.scheduler.running:
            self.scheduler.shutdown(wait=False)
            logger.info("Task scheduler stopped")

    def schedule_reminder(self, text: str, run_time: str) -> str:
        """Schedule a reminder.

        Args:
            text: Reminder text
            run_time: Time string (natural language or ISO format)
                e.g. "3pm", "3:00 PM", "2024-04-11 15:00", "in 5 minutes"

        Returns:
            Status message with job ID
        """
        try:
            trigger_time = self._parse_time(run_time)
            # UUID avoids collisions during burst scheduling on coarse clock resolutions.
            job_id = f"reminder_{uuid4().hex}"

            def notify():
                if self.notifier:
                    self.notifier.reminder(text)
                logger.info(f"Reminder: {text}")
                self._record_reminder_event("fired", job_id, text, trigger_time)
                self._emit_ipc(
                    "guppy",
                    "reminder_fired",
                    {
                        "message": text,
                        "job_id": job_id,
                        "short_id": job_id[-8:],
                        "trigger_time": trigger_time.isoformat(),
                    },
                )
                self._emit_ipc(
                    "council",
                    "reminder_fired",
                    {
                        "message": text,
                        "job_id": job_id,
                        "short_id": job_id[-8:],
                        "trigger_time": trigger_time.isoformat(),
                    },
                )
                # Ensure fired reminders are not shown as active.
                self.jobs.pop(job_id, None)
                self.reminders.pop(job_id, None)

            job = self.scheduler.add_job(
                notify,
                "date",
                run_date=trigger_time,
                id=job_id,
                replace_existing=False,
            )
            self.jobs[job_id] = job
            self.reminders[job_id] = text  # Store reminder text
            logger.info(f"Reminder scheduled: {text} at {trigger_time}")
            self._record_reminder_event("scheduled", job_id, text, trigger_time)
            return f"Reminder scheduled: '{text}' at {trigger_time.strftime('%Y-%m-%d %H:%M:%S')} (ID: {job_id[-8:]})"
        except Exception as e:
            logger.error(f"Schedule reminder failed: {e}")
            return f"Error scheduling reminder: {e}"

    def cancel_reminder(self, job_id: str) -> str:
        """Cancel a scheduled reminder.
        
        Returns:
            Status message (str)
        """
        if job_id in self.jobs:
            try:
                self.scheduler.remove_job(job_id)
                del self.jobs[job_id]
                self.reminders.pop(job_id, None)  # Clean up reminder text
                logger.info(f"Reminder cancelled: {job_id}")
                self._record_reminder_event("cancelled", job_id, "cancelled by user")
                return f"Reminder {job_id[-8:]} cancelled."
            except Exception as e:
                logger.error(f"Cancel failed: {e}")
                return f"Error cancelling reminder: {e}"
        return f"Reminder {job_id} not found."

    def get_scheduled_reminders(self) -> Dict[str, Dict[str, str]]:
        """Get all scheduled reminders.
        
        Returns:
            Dict mapping job_id -> {message, trigger, next_run}
        """
        reminders_dict = {}
        for job_id, job in self.jobs.items():
            try:
                # Check if job still exists and hasn't run yet
                if self.scheduler.get_job(job_id) is not None:
                    reminder_text = self.reminders.get(job_id, "Reminder")
                    next_run = getattr(job, 'next_run_time', None)
                    if next_run:
                        reminders_dict[job_id] = {
                            "message": reminder_text,
                            "trigger": str(job.trigger),
                            "next_run": str(next_run),
                        }
            except Exception as e:
                logger.debug(f"Error checking job {job_id}: {e}")
        return reminders_dict

    def list_reminders(self) -> list:
        """List all scheduled reminders."""
        jobs = []
        for job_id, job in self.jobs.items():
            if job.next_run_time:
                jobs.append({"id": job_id, "next_run": str(job.next_run_time)})
        return jobs

    def _parse_time(self, time_str: str) -> datetime:
        """Parse natural language time strings.

        Examples:
            "3pm" → today at 3:00 PM
            "3:00 PM" → today at 3:00 PM
            "tomorrow at 10am" → tomorrow at 10:00 AM
            "in 5 minutes" → 5 minutes from now
            "2024-04-11 15:00" → ISO format
        """
        time_str = time_str.strip().lower()
        now = datetime.now()

        # Handle "in X minutes/hours" format
        if time_str.startswith("in "):
            parts = time_str[3:].split()
            if len(parts) >= 2:
                try:
                    amount = int(parts[0])
                    unit = parts[1].rstrip("s")  # Remove plural
                    if unit == "minute":
                        return now + timedelta(minutes=amount)
                    elif unit == "hour":
                        return now + timedelta(hours=amount)
                    elif unit == "second":
                        return now + timedelta(seconds=amount)
                except (ValueError, IndexError):
                    pass

        # Handle "tomorrow at HH:MM" format
        if time_str.startswith("tomorrow"):
            # Replace "tomorrow" with actual date
            tomorrow = now + timedelta(days=1)
            remainder = time_str.replace("tomorrow", "").strip()
            if remainder:
                # Parse the time part
                if remainder.startswith("at "):
                    remainder = remainder[3:]
                try:
                    parsed_time = dateutil_parser.parse(remainder, default=tomorrow)
                    # Set to tomorrow's date with parsed time
                    return parsed_time.replace(year=tomorrow.year, month=tomorrow.month, day=tomorrow.day)
                except Exception:
                    # If parsing fails, default to tomorrow at noon
                    return tomorrow.replace(hour=12, minute=0, second=0, microsecond=0)
            else:
                # No time specified, default to 10:00 AM tomorrow
                return tomorrow.replace(hour=10, minute=0, second=0, microsecond=0)

        # Try dateutil parser (handles most natural language times)
        try:
            parsed = dateutil_parser.parse(time_str, default=now)
            # If parsed time is in the past, assume next occurrence
            if parsed < now:
                if any(day in time_str for day in ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]):
                    # Schedule for next occurrence of that weekday
                    days_ahead = 0
                    while (now + timedelta(days=days_ahead)).strftime("%a").lower() != parsed.strftime("%a").lower():
                        days_ahead += 1
                    parsed = now + timedelta(days=days_ahead)
                    # Preserve the time from parsed
                    parsed = parsed.replace(hour=parsed.hour, minute=parsed.minute, second=parsed.second)
                else:
                    # Parsed time is today but in the past, move to tomorrow
                    parsed = parsed.replace(year=now.year, month=now.month, day=now.day)
                    if parsed < now:
                        parsed = parsed + timedelta(days=1)
            return parsed
        except Exception as e:
            logger.error(f"Time parse failed: {e}")
            raise ValueError(f"Could not parse time: {time_str}")


# ── Phase 8: Proactive Loop ────────────────────────────────────────────────────

class ProactiveLoop:
    """
    Phase 8 — Proactive / Daemon Mode.

    Background thread that polls for agent health every POLL_INTERVAL seconds.
    - Nudges stale agents; repairs dead ones via HubOperator.
    - Fires upcoming-reminder toasts (≤15 min ahead).
    - Runs daily Haiku "anything important?" summary at GUPPY_DAILY_SUMMARY_HOUR.
    - Refreshes HubOperator pattern analysis (throttled 1/hr).
    """

    POLL_INTERVAL = 60  # seconds

    def __init__(self, notifier: GuppyNotifier, scheduler: "TaskScheduler"):
        self.notifier = notifier
        self.scheduler = scheduler
        self._operator = None  # lazy-loaded to avoid circular import
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._reminder_notice_cache: set[str] = set()
        self._last_pattern_scan: float = 0.0
        self._last_nudge_at: dict[str, float] = {}
        self._last_repair_at: dict[str, float] = {}
        self._report_slots_fired: set[str] = set()
        self._nudge_cooldown_s = int(os.environ.get("GUPPY_NUDGE_COOLDOWN_S", "300"))
        self._repair_cooldown_s = int(os.environ.get("GUPPY_REPAIR_COOLDOWN_S", "900"))
        self._quiet_hours = os.environ.get("GUPPY_QUIET_HOURS", "22-7")
        self._quiet_hours_enabled = os.environ.get("GUPPY_QUIET_HOURS_ENABLED", "1").strip() in {"1", "true", "yes", "on"}
        # Hour (0-23) at which to fire the daily Haiku summary. Default: 8am.
        self._daily_summary_hour = int(os.environ.get("GUPPY_DAILY_SUMMARY_HOUR", "8"))
        try:
            poll_s = int(os.environ.get("GUPPY_PROACTIVE_POLL_S", str(self.POLL_INTERVAL)))
        except Exception:
            poll_s = self.POLL_INTERVAL
        self.POLL_INTERVAL = max(30, min(poll_s, 300))
        news_hours_env = os.environ.get("GUPPY_NEWS_REPORT_HOURS", "12,18,22")
        parsed_hours: list[int] = []
        for raw in news_hours_env.split(","):
            raw = raw.strip()
            if not raw:
                continue
            try:
                h = int(raw)
                if 0 <= h <= 23:
                    parsed_hours.append(h)
            except Exception:
                continue
        self._news_report_hours = sorted(set(parsed_hours)) if parsed_hours else [12, 18, 22]
        self._reports_dir = Path(__file__).parent / "runtime" / "daily_reports"
        self._resource_status_path = Path(__file__).parent / "runtime" / "resource_envelope.status.json"
        envelope_cfg = get_runtime_envelope_config()
        self._envelope_cfg = envelope_cfg
        self._resource_check_every_s = int(envelope_cfg.get("check_interval_s", 60))
        self._last_resource_check = 0.0
        self._last_resource_state = "unknown"
        self._last_resource_alert = 0.0
        self._resource_alert_cooldown_s = int(os.environ.get("GUPPY_ENVELOPE_ALERT_COOLDOWN_S", "600"))

    @staticmethod
    def _tail_lines(path: Path, limit: int = 20) -> list[str]:
        if not path.exists():
            return []
        try:
            lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
            return [ln for ln in lines[-limit:] if ln.strip()]
        except Exception:
            return []

    def _collect_runtime_log_context(self) -> str:
        runtime = Path(__file__).parent / "runtime"
        sources = {
            "agent_performance.jsonl": runtime / "agent_performance.jsonl",
            "session_events.jsonl": runtime / "session_events.jsonl",
            "integration_events.jsonl": runtime / "integration_events.jsonl",
            "hub_patterns.jsonl": runtime / "hub_patterns.jsonl",
        }
        lines: list[str] = []
        max_each = int(os.environ.get("GUPPY_DAILY_LOG_LINES", "8"))
        for label, path in sources.items():
            raw = self._tail_lines(path, limit=max_each)
            if not raw:
                continue
            lines.append(f"{label} (latest {len(raw)}):")
            for ln in raw:
                snippet = ln[:240] + ("..." if len(ln) > 240 else "")
                lines.append(f"- {snippet}")
        return "\n".join(lines) if lines else "No recent runtime logs found."

    def _collect_manual_events(self) -> str:
        runtime = Path(__file__).parent / "runtime"
        candidates = [
            runtime / "manual_events.jsonl",
            runtime / "manual_events.txt",
            runtime / "daily_manual_events.md",
            runtime / "todo.txt",
            runtime / "todo.md",
        ]
        out: list[str] = []
        max_lines = int(os.environ.get("GUPPY_DAILY_MANUAL_LINES", "20"))
        for path in candidates:
            if not path.exists():
                continue
            out.append(f"{path.name}:")
            raw = self._tail_lines(path, limit=max_lines)
            for ln in raw:
                if path.suffix.lower() == ".jsonl":
                    try:
                        obj = json.loads(ln)
                        txt = obj.get("text") or obj.get("event") or obj.get("message") or str(obj)
                        ts = obj.get("ts") or obj.get("timestamp") or ""
                        out.append(f"- {ts} {txt}".strip())
                        continue
                    except Exception:
                        pass
                out.append(f"- {ln[:220]}")
        return "\n".join(out) if out else "No manual events or TODO files found in runtime/."

    def _fetch_rss_feed(self, url: str, limit: int) -> list[dict[str, str]]:
        items: list[dict[str, str]] = []
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Guppy/1.0"})
            with urllib.request.urlopen(req, timeout=8) as resp:
                data = resp.read()
            root = ET.fromstring(data)

            # RSS 2.0
            for item in root.findall(".//channel/item")[:limit]:
                title = (item.findtext("title") or "").strip()
                link = (item.findtext("link") or "").strip()
                if title:
                    items.append({"title": title, "link": link})

            # Atom fallback
            if not items:
                ns = {"atom": "http://www.w3.org/2005/Atom"}
                for entry in root.findall(".//atom:entry", ns)[:limit]:
                    title = (entry.findtext("atom:title", default="", namespaces=ns) or "").strip()
                    link_el = entry.find("atom:link", ns)
                    link = (link_el.get("href") if link_el is not None else "") or ""
                    if title:
                        items.append({"title": title, "link": link})
        except Exception as e:
            logger.debug(f"RSS fetch failed for {url}: {e}")
        return items[:limit]

    def _collect_world_news(self) -> str:
        default_feeds = [
            "https://feeds.bbci.co.uk/news/world/rss.xml",
            "https://rss.nytimes.com/services/xml/rss/nyt/World.xml",
            "https://www.aljazeera.com/xml/rss/all.xml",
            "https://www.reuters.com/world/rss",
            "https://news.google.com/rss?hl=en-US&gl=US&ceid=US:en",
        ]
        feed_env = os.environ.get("GUPPY_DAILY_RSS_FEEDS", "").strip()
        feeds = [f.strip() for f in feed_env.split(",") if f.strip()] if feed_env else default_feeds
        per_feed = int(os.environ.get("GUPPY_DAILY_RSS_ITEMS", "4"))

        lines: list[str] = []
        for url in feeds:
            items = self._fetch_rss_feed(url, per_feed)
            if not items:
                continue
            lines.append(f"Feed: {url}")
            for it in items:
                title = it.get("title", "")
                link = it.get("link", "")
                lines.append(f"- {title}" + (f" ({link})" if link else ""))
        return "\n".join(lines) if lines else "No world news headlines available from configured RSS feeds."

    def _load_yesterday_report(self) -> str:
        yday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
        path = self._reports_dir / f"{yday}.md"
        if not path.exists():
            return "No previous daily report found (first run or file missing)."
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
            lines = [ln for ln in text.splitlines() if ln.strip()]
            snippet = "\n".join(lines[:40])
            return f"Yesterday report: {path.name}\n{snippet}"
        except Exception as e:
            return f"Yesterday report exists but could not be read: {e}"

    def _collect_memory_context(self) -> tuple[str, str]:
        memory_context = []
        tasks_block = "No pending tasks."
        try:
            import guppy_memory
            tasks_block = guppy_memory.get_tasks("pending")
            facts = guppy_memory.recall(limit=10)
            if tasks_block:
                memory_context.append("Pending tasks:\n" + tasks_block)
            if facts:
                memory_context.append("Recent facts:\n" + facts)
        except Exception as e:
            logger.debug(f"ProactiveLoop daily summary: memory load failed: {e}")
        return ("\n\n".join(memory_context) if memory_context else "No pending tasks or notable facts.", tasks_block)

    def _write_daily_report(self, report_text: str, report_kind: str, slot_hour: int) -> Path:
        self._reports_dir.mkdir(parents=True, exist_ok=True)
        today = datetime.now().strftime("%Y-%m-%d")
        if report_kind == "daily":
            out_name = f"{today}.md"
        else:
            out_name = f"{today}-{report_kind}-{slot_hour:02d}00.md"
        out_path = self._reports_dir / out_name
        out_path.write_text(report_text, encoding="utf-8")
        return out_path

    @staticmethod
    def _slot_key(report_kind: str, day: str, hour: int) -> str:
        return f"{day}:{report_kind}:{hour:02d}"

    def _was_slot_fired(self, report_kind: str, hour: int) -> bool:
        day = datetime.now().strftime("%Y-%m-%d")
        return self._slot_key(report_kind, day, hour) in self._report_slots_fired

    def _mark_slot_fired(self, report_kind: str, hour: int) -> None:
        day = datetime.now().strftime("%Y-%m-%d")
        self._report_slots_fired.add(self._slot_key(report_kind, day, hour))
        # Keep only recent slot markers (today + yesterday) to avoid unbounded growth.
        keep_days = {
            day,
            (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d"),
        }
        self._report_slots_fired = {
            key for key in self._report_slots_fired
            if any(key.startswith(f"{d}:") for d in keep_days)
        }

    def _run_scheduled_report(self, report_kind: str, slot_hour: int) -> None:
        memory_context, tasks_block = self._collect_memory_context()
        world_news = self._collect_world_news()
        runtime_logs = self._collect_runtime_log_context()
        manual_events = self._collect_manual_events()
        yesterday_report = self._load_yesterday_report()

        context = (
            "MEMORY CONTEXT:\n"
            f"{memory_context}\n\n"
            "WORLD NEWS (RSS):\n"
            f"{world_news}\n\n"
            "RUNTIME LOGS:\n"
            f"{runtime_logs}\n\n"
            "MANUAL EVENTS / TODO INPUTS:\n"
            f"{manual_events}\n\n"
            "YESTERDAY REPORT REFERENCE:\n"
            f"{yesterday_report}\n"
        )

        summary = ""
        report_md = ""
        heading = "Daily Report" if report_kind == "daily" else "News Report"

        try:
            import anthropic
            client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY", ""))
            intent = (
                "Prioritize top personal actions for today."
                if report_kind == "daily"
                else "Prioritize world-news updates, likely impacts, and what to monitor next."
            )
            resp = client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=900,
                system=(
                    "You are Guppy's scheduled briefing assistant. "
                    "Produce two outputs in this exact format:\n"
                    "SUMMARY:\n"
                    "<under 80 words, bullets, actionable, can be 'nothing urgent'>\n"
                    "REPORT_MD:\n"
                    "<markdown report with sections: Key Actions, World News, Logs Signals, Manual Events & TODOs, Delta vs Yesterday, Carry-Forward Items>"
                ),
                messages=[{
                    "role": "user",
                    "content": (
                        f"Report type: {report_kind}\n"
                        f"Scheduled hour: {slot_hour:02d}:00\n"
                        f"Instruction: {intent}\n\n"
                        f"Compile report from context:\n\n{context}"
                    ),
                }],
            )
            raw = resp.content[0].text.strip() if resp.content else ""
            if "REPORT_MD:" in raw:
                left, right = raw.split("REPORT_MD:", 1)
                summary = left.replace("SUMMARY:", "").strip()
                report_md = right.strip()
            else:
                summary = raw
        except Exception as e:
            logger.warning(f"ProactiveLoop {report_kind} report: Haiku call failed: {e}")
            summary = f"{heading} generated without Haiku (fallback mode)."

        if not report_md:
            report_md = (
                f"# {heading} — {datetime.now().strftime('%Y-%m-%d')} {slot_hour:02d}:00\n\n"
                "## Key Actions\n"
                f"{summary or 'No urgent items detected.'}\n\n"
                "## World News\n"
                f"{world_news}\n\n"
                "## Logs Signals\n"
                f"{runtime_logs}\n\n"
                "## Manual Events & TODOs\n"
                f"{manual_events}\n\n"
                "## Delta vs Yesterday\n"
                f"{yesterday_report}\n\n"
                "## Carry-Forward Items\n"
                f"{tasks_block}\n"
            )

        report_path = None
        try:
            report_path = self._write_daily_report(report_md, report_kind=report_kind, slot_hour=slot_hour)
        except Exception as e:
            logger.warning(f"ProactiveLoop {report_kind} report: failed writing report: {e}")

        actionable = summary and summary.lower() != "nothing urgent"
        if actionable:
            msg = summary[:200]
            if report_path is not None:
                msg = f"{msg} | report: {report_path.name}"
            toast_title = "Guppy Daily Briefing" if report_kind == "daily" else "Guppy News Briefing"
            self.notifier.info(toast_title, msg)
            op = self.operator
            if op:
                try:
                    op.send_command(
                        "guppy",
                        "nudge",
                        {
                            "reason": f"{report_kind}_summary",
                            "summary": summary[:500],
                            "report_path": str(report_path) if report_path is not None else "",
                        },
                    )
                    op.record_event("guppy", f"{report_kind}_summary", "proactive_loop", "sent")
                except Exception as e:
                    logger.debug(f"ProactiveLoop {report_kind} report: IPC nudge failed: {e}")

        logger.info(
            f"ProactiveLoop {report_kind} report fired (actionable={actionable}, hour={slot_hour}, report={report_path.name if report_path else 'none'})"
        )
        self._mark_slot_fired(report_kind, slot_hour)

    @property
    def operator(self):
        if self._operator is None:
            try:
                from utils.hub_operator import get_operator
                self._operator = get_operator()
            except Exception:
                pass
        return self._operator

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(
            target=self._loop, daemon=True, name="ProactiveLoop"
        )
        self._thread.start()
        logger.info("ProactiveLoop started")

    def stop(self) -> None:
        self._running = False
        if self._thread:
            self._thread.join(timeout=3)
        logger.info("ProactiveLoop stopped")

    def _loop(self) -> None:
        while self._running:
            try:
                self._tick()
            except Exception as e:
                logger.error(f"ProactiveLoop tick error: {e}")
            time.sleep(self.POLL_INTERVAL)

    def _tick(self) -> None:
        """
        One proactive poll cycle.

        Checks heartbeat files for all known agents.
        Stale → nudge.  Very stale / crash_count high → repair + toast.
        TODO: calendar query, Haiku summary, TTS trigger.
        """
        op = self.operator
        if op is None:
            return
        runtime = Path(__file__).parent / "runtime"
        now_ts = time.time()
        for hb_file in runtime.glob("*.heartbeat"):
            agent_id = hb_file.stem
            try:
                last_seen = time.time() - hb_file.stat().st_mtime
                rec = op.smart_recommend(
                    agent_id,
                    is_stalled=(last_seen > 30),
                    last_seen_seconds=last_seen,
                )
                if rec == "nudge":
                    if now_ts - self._last_nudge_at.get(agent_id, 0.0) < self._nudge_cooldown_s:
                        continue
                    logger.info(f"ProactiveLoop: nudging stale agent '{agent_id}'")
                    op.nudge_agent(agent_id)
                    op.record_event(agent_id, "auto_nudge", "proactive_loop", "sent")
                    self._last_nudge_at[agent_id] = now_ts
                elif rec == "repair":
                    if now_ts - self._last_repair_at.get(agent_id, 0.0) < self._repair_cooldown_s:
                        continue
                    logger.info(f"ProactiveLoop: repairing dead agent '{agent_id}'")
                    removed = op.repair_agent(agent_id)
                    if removed:
                        if not self._is_quiet_hours_now():
                            self.notifier.info(
                                "Guppy Hub",
                                f"Agent '{agent_id}' repaired — cleared {len(removed)} stale files.",
                            )
                    self._last_repair_at[agent_id] = now_ts
            except Exception as e:
                logger.debug(f"ProactiveLoop: check failed for '{agent_id}': {e}")

        self._check_upcoming_reminders()
        self._check_pattern_learning()
        self._check_daily_summary()
        self._check_news_reports()
        self._check_resource_envelope()

    def _check_resource_envelope(self) -> None:
        """Check CPU/RAM against runtime profile envelope and emit telemetry/status."""
        now = time.time()
        if now - self._last_resource_check < self._resource_check_every_s:
            return
        self._last_resource_check = now

        profile = str(os.environ.get("GUPPY_RUNTIME_PROFILE", self._envelope_cfg.get("profile", "standard"))).strip().lower() or "standard"
        self._envelope_cfg = get_runtime_envelope_config(profile)
        cpu_limit = float(self._envelope_cfg.get("cpu_max_pct", 80.0))
        ram_limit = float(self._envelope_cfg.get("ram_max_pct", 88.0))

        payload: Dict[str, Any] = {
            "ts": datetime.now().isoformat(),
            "profile": profile,
            "limits": {"cpu_max_pct": cpu_limit, "ram_max_pct": ram_limit},
            "metrics": {},
            "state": "unknown",
            "violations": [],
            "message": "resource envelope check unavailable",
        }

        if not PSUTIL_AVAILABLE:
            payload["message"] = "psutil not available"
            self._write_resource_status(payload)
            return

        try:
            cpu_pct = float(psutil.cpu_percent(interval=0.2))
            vm = psutil.virtual_memory()
            ram_pct = float(vm.percent)
            available_gb = round(float(vm.available) / (1024 ** 3), 2)
            total_gb = round(float(vm.total) / (1024 ** 3), 2)
        except Exception as e:
            payload["message"] = f"psutil read failed: {e}"
            self._write_resource_status(payload)
            return

        violations: list[str] = []
        if cpu_pct > cpu_limit:
            violations.append("cpu")
        if ram_pct > ram_limit:
            violations.append("ram")

        state = "violation" if violations else "ok"
        payload.update({
            "state": state,
            "metrics": {
                "cpu_pct": round(cpu_pct, 2),
                "ram_pct": round(ram_pct, 2),
                "available_ram_gb": available_gb,
                "total_ram_gb": total_gb,
            },
            "violations": violations,
            "message": "resource envelope within limits" if not violations else "resource envelope exceeded",
        })

        state_changed = state != self._last_resource_state
        if state_changed or (state == "violation" and now - self._last_resource_alert >= self._resource_alert_cooldown_s):
            evt_level = "warning" if state == "violation" else "info"
            log_operational_event(
                stream="resource_envelope",
                event="resource_violation" if state == "violation" else "resource_ok",
                level=evt_level,
                payload=payload,
            )
            if state == "violation":
                if not self._is_quiet_hours_now():
                    self.notifier.info(
                        "Guppy Resource Envelope",
                        f"Profile {profile}: CPU {cpu_pct:.0f}% / RAM {ram_pct:.0f}% exceeds limits",
                    )
                self._last_resource_alert = now

        self._last_resource_state = state
        self._write_resource_status(payload)

    def _write_resource_status(self, payload: Dict[str, Any]) -> None:
        try:
            self._resource_status_path.parent.mkdir(parents=True, exist_ok=True)
            self._resource_status_path.write_text(json.dumps(payload, ensure_ascii=True, indent=2), encoding="utf-8")
        except Exception as e:
            logger.debug(f"Resource envelope status write failed: {e}")

    def _check_daily_summary(self) -> None:
        """Fire one daily report at the configured morning hour."""
        if self._is_quiet_hours_now():
            return
        now_hour = datetime.now().hour
        if now_hour != self._daily_summary_hour:
            return
        if self._was_slot_fired("daily", now_hour):
            return
        self._run_scheduled_report("daily", now_hour)

    def _check_news_reports(self) -> None:
        """Fire scheduled world-news reports (default: 12:00, 18:00, 22:00)."""
        if self._is_quiet_hours_now():
            return
        now_hour = datetime.now().hour
        if now_hour not in self._news_report_hours:
            return
        if self._was_slot_fired("news", now_hour):
            return
        self._run_scheduled_report("news", now_hour)

    def _check_pattern_learning(self) -> None:
        """Run pattern analysis at most once per hour (Phase 14 automation)."""
        now = time.time()
        if now - self._last_pattern_scan < 3600:
            return
        op = self.operator
        if op is None:
            return
        try:
            insight = op.analyze_patterns(force=False)
            if insight:
                logger.info("ProactiveLoop pattern insight refreshed")
            self._last_pattern_scan = now
        except Exception as e:
            logger.debug(f"ProactiveLoop pattern scan failed: {e}")

    def _check_upcoming_reminders(self) -> None:
        """Proactive reminder nudges for reminders due soon (<= 15 minutes)."""
        if self._is_quiet_hours_now():
            return
        now = datetime.now()
        if not self.scheduler or not getattr(self.scheduler, "jobs", None):
            return
        for job_id, job in list(self.scheduler.jobs.items()):
            try:
                run_at = getattr(job, "next_run_time", None)
                if run_at is None:
                    continue
                run_local = run_at.replace(tzinfo=None)
                mins = (run_local - now).total_seconds() / 60.0
                if 0 <= mins <= 15 and job_id not in self._reminder_notice_cache:
                    msg = self.scheduler.reminders.get(job_id, "Reminder")
                    self.notifier.info(
                        "Guppy Heads Up",
                        f"Reminder in {max(1, int(mins))}m: {msg}",
                    )
                    op = self.operator
                    if op:
                        op.send_command(
                            "guppy",
                            "nudge",
                            {"reason": "upcoming_reminder", "job_id": job_id},
                        )
                        op.record_event("guppy", "proactive_reminder", job_id, "nudged")
                    self._reminder_notice_cache.add(job_id)
            except Exception as e:
                logger.debug(f"ProactiveLoop reminder check failed for '{job_id}': {e}")

    def _is_quiet_hours_now(self) -> bool:
        if not self._quiet_hours_enabled:
            return False
        try:
            parts = self._quiet_hours.split("-", 1)
            start_h = int(parts[0])
            end_h = int(parts[1])
            hour = datetime.now().hour
            if start_h == end_h:
                return False
            if start_h < end_h:
                return start_h <= hour < end_h
            return hour >= start_h or hour < end_h
        except Exception:
            return False


# ── Phase 11: Ambient Watcher ──────────────────────────────────────────────────

class AmbientWatcher:
    """
    Phase 11 skeleton — Ambient Awareness.

    Polls clipboard + active window title at low frequency (60 s default).
    Fires callbacks when interesting content is detected.

    Intentionally stingy:
      - 1 poll/min max
      - Skips if Guppy is already busy (activity file == 'thinking')
      - Only flags substantial content (URLs, long text ≥ 300 chars)

    TODO (Phase 11 full implementation):
      - Haiku "is this interesting?" check on clipboard content
      - Send 'ambient_offer' cmd to running Guppy via HubOperator.send_command()
      - Surface offer in GuppyWindow as a non-intrusive banner
      - Respect user quiet-hours and focus-mode settings
    """

    POLL_INTERVAL = 60  # stingy by design

    def __init__(self, notifier: GuppyNotifier, window_watcher: WindowWatcher):
        self.notifier = notifier
        self.window_watcher = window_watcher
        self._operator = None
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._last_clipboard: str = ""
        self._callbacks: list = []  # fn(context_type: str, content: str)
        self._offer_cooldown_s = int(os.environ.get("GUPPY_AMBIENT_COOLDOWN_S", "600"))
        try:
            poll_s = int(os.environ.get("GUPPY_AMBIENT_POLL_S", str(self.POLL_INTERVAL)))
        except Exception:
            poll_s = self.POLL_INTERVAL
        self.POLL_INTERVAL = max(45, min(poll_s, 600))
        self._last_offer_ts: float = 0.0
        self._quiet_hours = os.environ.get("GUPPY_QUIET_HOURS", "22-7")
        self._quiet_hours_enabled = os.environ.get("GUPPY_QUIET_HOURS_ENABLED", "1").strip() in {"1", "true", "yes", "on"}

    @property
    def operator(self):
        if self._operator is None:
            try:
                from utils.hub_operator import get_operator
                self._operator = get_operator()
            except Exception:
                pass
        return self._operator

    def register_callback(self, fn) -> None:
        """Register fn(context_type: str, content: str) callback."""
        self._callbacks.append(fn)

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(
            target=self._loop, daemon=True, name="AmbientWatcher"
        )
        self._thread.start()
        logger.info("AmbientWatcher started")

    def stop(self) -> None:
        self._running = False
        if self._thread:
            self._thread.join(timeout=3)
        logger.info("AmbientWatcher stopped")

    def _loop(self) -> None:
        while self._running:
            try:
                self._tick()
            except Exception as e:
                logger.error(f"AmbientWatcher tick error: {e}")
            time.sleep(self.POLL_INTERVAL)

    def _tick(self) -> None:
        """
        One ambient poll cycle: detect clipboard change and send ambient_offer.
        """
        if self._is_quiet_hours_now():
            return
        # If Guppy is actively thinking/speaking, skip offers this cycle.
        try:
            act = (Path(__file__).parent / "runtime" / "guppy.activity").read_text(encoding="utf-8").strip().lower()
            if act in {"thinking", "speaking"}:
                return
        except Exception:
            pass

        text = self._read_clipboard()
        if text and text != self._last_clipboard and self._looks_interesting(text):
            now_ts = time.time()
            if now_ts - self._last_offer_ts < self._offer_cooldown_s:
                return
            # Haiku semantic gate: skip content that isn't actionable
            interesting, action = self._haiku_interesting_check(text)
            if not interesting:
                self._last_clipboard = text  # still update so we don't re-check same content
                return
            self._last_clipboard = text
            op = self.operator
            if op is not None:
                payload = {
                    "type": "clipboard",
                    "preview": text[:220],
                    "length": len(text),
                    "action": action,
                }
                op.send_command("guppy", "ambient_offer", payload)
                op.record_event("guppy", "ambient_offer", "clipboard", "sent")
                self._last_offer_ts = now_ts
            for fn in self._callbacks:
                try:
                    fn("clipboard", text)
                except Exception as e:
                    logger.error(f"AmbientWatcher callback error: {e}")

    def _haiku_interesting_check(self, text: str) -> tuple[bool, str]:
        """
        Ask Haiku whether the clipboard content is worth a proactive offer.
        Returns (is_interesting, suggested_action_sentence).
        Falls back to (True, preview) if the API call fails — better to over-offer than silently drop.
        """
        api_key = os.environ.get("ANTHROPIC_API_KEY", "")
        if not api_key:
            return True, text[:120]
        try:
            import anthropic
            import json as _json
            client = anthropic.Anthropic(api_key=api_key)
            snippet = text[:600]
            resp = client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=80,
                system=(
                    "You are a background assistant deciding if clipboard content warrants a proactive offer. "
                    "Reply ONLY with valid JSON: {\"interesting\": true/false, \"action\": \"one short sentence\"} "
                    "interesting=true only for: URLs to read, long text to summarise, code to explain, or clear tasks. "
                    "interesting=false for: random strings, passwords, file paths, numbers, trivial snippets."
                ),
                messages=[{"role": "user", "content": f"Clipboard:\n{snippet}"}],
            )
            raw = resp.content[0].text.strip() if resp.content else "{}"
            # Strip markdown code fences if present
            if raw.startswith("```"):
                raw = raw.split("```")[1]
                if raw.startswith("json"):
                    raw = raw[4:]
            data = _json.loads(raw)
            return bool(data.get("interesting", False)), str(data.get("action", text[:120]))
        except Exception as e:
            logger.debug(f"AmbientWatcher Haiku check failed: {e}")
            return True, text[:120]  # fail open

    def _read_clipboard(self) -> str:
        try:
            result = subprocess.run(
                ["powershell", "-command", "Get-Clipboard"],
                capture_output=True,
                text=True,
                timeout=2,
            )
            return result.stdout.strip()[:2000]
        except Exception:
            return ""

    def _looks_interesting(self, text: str) -> bool:
        """Heuristic: worth offering to analyze?"""
        if len(text) < 50:
            return False
        if text.startswith(("http://", "https://")):
            return True
        return len(text) >= 300

    def _is_quiet_hours_now(self) -> bool:
        if not self._quiet_hours_enabled:
            return False
        try:
            parts = self._quiet_hours.split("-", 1)
            start_h = int(parts[0])
            end_h = int(parts[1])
            hour = datetime.now().hour
            if start_h == end_h:
                return False
            if start_h < end_h:
                return start_h <= hour < end_h
            return hour >= start_h or hour < end_h
        except Exception:
            return False


# ── Daemon Manager (Lifecycle) ─────────────────────────────────────────────────

class DaemonManager:
    """Lifecycle manager for background services."""

    def __init__(self):
        self.notifier = GuppyNotifier()
        self.window_watcher = WindowWatcher()
        self.task_scheduler = TaskScheduler(notifier=self.notifier)
        # Phase 8: proactive agent health + (eventually) calendar/reminder checks
        self.proactive_loop = ProactiveLoop(
            notifier=self.notifier,
            scheduler=self.task_scheduler,
        )
        # Phase 11: ambient clipboard + window-title awareness
        self.ambient_watcher = AmbientWatcher(
            notifier=self.notifier,
            window_watcher=self.window_watcher,
        )
        self.is_running = False

    def start(self):
        """Start all daemons."""
        if self.is_running:
            return

        self.is_running = True
        try:
            self.window_watcher.start()
            self.task_scheduler.start()
            self.proactive_loop.start()
            self.ambient_watcher.start()
            logger.info("✓ All daemons started")
        except Exception as e:
            logger.error(f"Daemon start failed: {e}")
            self.is_running = False

    def stop(self):
        """Stop all daemons gracefully."""
        if not self.is_running:
            return

        try:
            self.window_watcher.stop()
            self.task_scheduler.stop()
            self.proactive_loop.stop()
            self.ambient_watcher.stop()
            self.is_running = False
            logger.info("✓ All daemons stopped")
        except Exception as e:
            logger.error(f"Daemon stop failed: {e}")


# ── Singleton Instance ─────────────────────────────────────────────────────────

_daemon_manager = None


def get_daemon_manager() -> DaemonManager:
    """Get or create the global daemon manager."""
    global _daemon_manager
    if _daemon_manager is None:
        _daemon_manager = DaemonManager()
    return _daemon_manager


def show_notification(title: str, msg: str, duration: int = 5):
    """Convenience function for showing toast notifications."""
    get_daemon_manager().notifier.show(title, msg, duration)


def get_window_context() -> Dict[str, str]:
    """Get current window/app context."""
    return get_daemon_manager().window_watcher.get_context()


def schedule_reminder(text: str, run_time: str) -> str:
    """Schedule a reminder (convenience function)."""
    return get_daemon_manager().task_scheduler.schedule_reminder(text, run_time)
