from __future__ import annotations

import os
import threading
import time
from typing import Callable

from src.guppy.daemon.support import WIN32_AVAILABLE, logger, win32gui


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

    def get_context(self) -> dict[str, str]:
        """Get current window/app context."""
        if not WIN32_AVAILABLE:
            return {"app": "unknown", "title": "unknown"}

        try:
            hwnd = win32gui.GetForegroundWindow()
            title = win32gui.GetWindowText(hwnd)
            class_name = win32gui.GetClassName(hwnd)
            app_name = self._identify_app(hwnd, class_name, title)
            return {"app": app_name, "title": title}
        except Exception as e:
            logger.debug(f"Window context error: {e}")
            return {"app": "unknown", "title": "unknown"}

    def get_context_help(self, app_name: str, window_title: str) -> str:
        """Get context-specific help suggestions based on current app."""
        app_lower = app_name.lower()
        title_lower = window_title.lower()

        if "visual studio code" in app_lower or "vscode" in app_lower:
            return "I can help with coding, debugging, file operations, and Git commands."
        if "visual studio" in app_lower:
            return "I can assist with .NET development, debugging, and project management."
        if "pycharm" in app_lower or "intellij" in app_lower:
            return "I can help with Python/Java development, refactoring, and IDE features."
        if "outlook" in app_lower:
            return "I can help with email management, scheduling, and contact organization."
        if "excel" in app_lower:
            return "I can assist with spreadsheet formulas, data analysis, and chart creation."
        if "word" in app_lower:
            return "I can help with document formatting, templates, and writing assistance."
        if "powerpoint" in app_lower:
            return "I can assist with presentation design, slide layouts, and content creation."
        if "chrome" in app_lower or "firefox" in app_lower or "edge" in app_lower:
            if "gmail" in title_lower:
                return "I can help with email composition, organization, and Gmail automation."
            if "github" in title_lower:
                return "I can assist with Git operations, pull requests, and repository management."
            if "stackoverflow" in title_lower:
                return "I can help with programming questions and code debugging."
            if "youtube" in title_lower:
                return "I can help find videos, playlists, and YouTube content."
            return "I can help with web browsing, research, and online tasks."
        if "slack" in app_lower:
            return "I can help with team communication, channel management, and productivity."
        if "teams" in app_lower:
            return "I can assist with meeting scheduling, file sharing, and collaboration."
        if "discord" in app_lower:
            return "I can help with community management and server organization."
        if "file explorer" in app_lower:
            return "I can help with file organization, search, and system navigation."
        if "spotify" in app_lower:
            return "I can help control music playback, create playlists, and find songs."
        return f"I can help with general tasks while you're using {app_name}."

    def get_enhanced_context(self) -> dict[str, str]:
        base_context = self.get_context()
        help_text = self.get_context_help(base_context["app"], base_context["title"])
        return {**base_context, "help": help_text}

    def _identify_app(self, hwnd: int, class_name: str, title: str) -> str:
        app_map = {
            "Chrome_WidgetWin": "Google Chrome",
            "Mozilla Firefox": "Mozilla Firefox",
            "MSEdge": "Microsoft Edge",
            "Safari": "Safari",
            "OUTLOOK": "Microsoft Outlook",
            "EXCEL": "Microsoft Excel",
            "WINWORD": "Microsoft Word",
            "POWERPNT": "Microsoft PowerPoint",
            "MSACCESS": "Microsoft Access",
            "VsCode": "Visual Studio Code",
            "Code": "Visual Studio Code",
            "devenv": "Visual Studio",
            "Notepad++": "Notepad++",
            "notepad": "Notepad",
            "PyCharm": "PyCharm",
            "IntelliJ": "IntelliJ IDEA",
            "Teams": "Microsoft Teams",
            "Slack": "Slack",
            "Discord": "Discord",
            "WhatsApp": "WhatsApp",
            "Telegram": "Telegram",
            "CabinetWClass": "File Explorer",
            "ExploreWClass": "File Explorer",
            "WMPlayerApp": "Windows Media Player",
            "SpotifyMainWindow": "Spotify",
            "iTunes": "iTunes",
            "ApplicationFrameWindow": "Windows Store App",
            "Shell_TrayWnd": "Taskbar",
            "Progman": "Desktop",
            "AcrobatSDIWindow": "Adobe Acrobat",
            "Photoshop": "Adobe Photoshop",
            "Illustrator": "Adobe Illustrator",
        }

        for key, app_name in app_map.items():
            if key in class_name:
                return app_name

        for key, app_name in app_map.items():
            if key in title:
                return app_name

        if "Chrome" in class_name or "Firefox" in class_name or "Edge" in class_name:
            title_lower = title.lower()
            if "gmail" in title_lower or "mail.google" in title_lower:
                return "Gmail"
            if "youtube" in title_lower:
                return "YouTube"
            if "github" in title_lower:
                return "GitHub"
            if "stackoverflow" in title_lower:
                return "Stack Overflow"
            if "docs.google" in title_lower:
                return "Google Docs"
            if "sheets.google" in title_lower:
                return "Google Sheets"
            if "slack" in title_lower:
                return "Slack"
            if "notion" in title_lower:
                return "Notion"
            if "discord" in title_lower:
                return "Discord"

        if title:
            parts = title.split(" - ")
            candidate = parts[-1][:50] if parts else class_name[:50]
            candidate = candidate.replace(" - Google Chrome", "").replace(" - Mozilla Firefox", "")
            return candidate

        return class_name[:50] if class_name else "unknown"

    def start(self):
        if self._running:
            return

        self._running = True
        self._thread = threading.Thread(target=self._watch_loop, daemon=True)
        self._thread.start()
        logger.info("Window watcher started")

    def stop(self):
        self._running = False
        if self._thread:
            self._thread.join(timeout=2)
        logger.info("Window watcher stopped")

    def _watch_loop(self):
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
