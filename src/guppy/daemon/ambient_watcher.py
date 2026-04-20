from __future__ import annotations

import os
import subprocess
import threading
import time
from datetime import datetime
from typing import Optional

from src.guppy.daemon.notifier import GuppyNotifier
from src.guppy.daemon.support import RUNTIME_DIR, get_operator, is_quiet_hours_now, logger
from src.guppy.daemon.window_watcher import WindowWatcher


class AmbientWatcher:
    """
    Phase 11 skeleton - Ambient Awareness.

    Polls clipboard + active window title at low frequency (60 s default).
    Fires callbacks when interesting content is detected.
    """

    POLL_INTERVAL = 60

    def __init__(self, notifier: GuppyNotifier, window_watcher: WindowWatcher):
        self.notifier = notifier
        self.window_watcher = window_watcher
        self._operator = None
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._last_clipboard: str = ""
        self._callbacks: list = []
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
            self._operator = get_operator()
        return self._operator

    def register_callback(self, fn) -> None:
        self._callbacks.append(fn)

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._loop, daemon=True, name="AmbientWatcher")
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
        if self._is_quiet_hours_now():
            return
        try:
            act = (RUNTIME_DIR / "guppy.activity").read_text(encoding="utf-8").strip().lower()
            if act in {"thinking", "speaking"}:
                return
        except Exception:
            pass

        text = self._read_clipboard()
        if text and text != self._last_clipboard and self._looks_interesting(text):
            now_ts = time.time()
            if now_ts - self._last_offer_ts < self._offer_cooldown_s:
                return
            interesting, action = self._haiku_interesting_check(text)
            if not interesting:
                self._last_clipboard = text
                return
            self._last_clipboard = text
            op = self.operator
            if op is not None:
                payload = {"type": "clipboard", "preview": text[:220], "length": len(text), "action": action}
                op.send_command("guppy", "ambient_offer", payload)
                op.record_event("guppy", "ambient_offer", "clipboard", "sent")
                self._last_offer_ts = now_ts
            for fn in self._callbacks:
                try:
                    fn("clipboard", text)
                except Exception as e:
                    logger.error(f"AmbientWatcher callback error: {e}")

    def _haiku_interesting_check(self, text: str) -> tuple[bool, str]:
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
            if raw.startswith("```"):
                raw = raw.split("```")[1]
                if raw.startswith("json"):
                    raw = raw[4:]
            data = _json.loads(raw)
            return bool(data.get("interesting", False)), str(data.get("action", text[:120]))
        except Exception as e:
            logger.debug(f"AmbientWatcher Haiku check failed: {e}")
            return True, text[:120]

    def _read_clipboard(self) -> str:
        try:
            import sys as _sys

            extra = {"creationflags": subprocess.CREATE_NO_WINDOW} if _sys.platform == "win32" else {}
            result = subprocess.run(
                ["powershell", "-command", "Get-Clipboard"],
                capture_output=True,
                text=True,
                timeout=2,
                **extra,
            )
            return result.stdout.strip()[:2000]
        except Exception:
            return ""

    def _looks_interesting(self, text: str) -> bool:
        if len(text) < 50:
            return False
        if text.startswith(("http://", "https://")):
            return True
        return len(text) >= 300

    def _is_quiet_hours_now(self) -> bool:
        return is_quiet_hours_now(self._quiet_hours, self._quiet_hours_enabled)
