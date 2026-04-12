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

import threading
import time
import logging
from pathlib import Path
from typing import Callable, Optional, Dict, Any
from datetime import datetime, timedelta

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
        self.poll_interval = poll_interval
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
            job_id = f"reminder_{int(time.time() * 1000)}"

            def notify():
                if self.notifier:
                    self.notifier.reminder(text)
                logger.info(f"Reminder: {text}")

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
                if job_id in self.scheduler.get_jobs():
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


# ── Daemon Manager (Lifecycle) ─────────────────────────────────────────────────

class DaemonManager:
    """Lifecycle manager for background services."""

    def __init__(self):
        self.notifier = GuppyNotifier()
        self.window_watcher = WindowWatcher()
        self.task_scheduler = TaskScheduler(notifier=self.notifier)
        self.is_running = False

    def start(self):
        """Start all daemons."""
        if self.is_running:
            return

        self.is_running = True
        try:
            self.window_watcher.start()
            self.task_scheduler.start()
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
