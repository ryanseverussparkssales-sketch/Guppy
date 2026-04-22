"""Bottom system strip and push-to-talk capture helpers for LauncherWindow.

Extracted from LauncherWindow as part of TR54-B1 continuation.
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Callable

from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel


def build_sys_strip(owner: Any, *, tokens: Any) -> QFrame:
    strip = QFrame()
    strip.setFixedHeight(26)
    strip.setObjectName("sys_strip")
    strip.setStyleSheet(
        f"QFrame#sys_strip {{"
        f"  background-color: {tokens.BG0};"
        f"  border-top: 1px solid {tokens.BORDER};"
        f"}}"
    )

    def _chip(text: str, color: str = "") -> QLabel:
        tint = color or tokens.DIM
        lbl = QLabel(text)
        lbl.setStyleSheet(
            f"color: {tint}; font-family: '{tokens.FF_MONO}';"
            f"font-size: {tokens.FS_TINY}pt; letter-spacing: 1px; padding: 0 8px;"
        )
        return lbl

    def _sep() -> QFrame:
        frame = QFrame()
        frame.setFixedSize(1, 14)
        frame.setStyleSheet(f"background: {tokens.BORDER};")
        return frame

    row = QHBoxLayout(strip)
    row.setContentsMargins(12, 0, 12, 0)
    row.setSpacing(0)

    owner._strip_uptime = _chip("UPTIME: —")
    owner._strip_cpu = _chip("CPU: —")
    owner._strip_mem = _chip("MEM: —")
    owner._strip_tokens = _chip("BUFFER: — tok")
    owner._strip_status = _chip("STATUS: NOMINAL", tokens.GREEN)

    row.addWidget(owner._strip_uptime)
    row.addWidget(_sep())
    row.addWidget(owner._strip_cpu)
    row.addWidget(_sep())
    row.addWidget(owner._strip_mem)
    row.addWidget(_sep())
    row.addWidget(owner._strip_tokens)
    row.addStretch()
    row.addWidget(owner._strip_status)

    return strip


def update_sys_strip(owner: Any, *, runtime_path: Path, start_time: float, tokens: Any) -> None:
    elapsed = int(time.monotonic() - start_time)
    hours, minutes = divmod(elapsed // 60, 60)
    seconds = elapsed % 60
    owner._strip_uptime.setText(f"UPTIME: {hours:02d}:{minutes:02d}:{seconds:02d}")

    try:
        import psutil

        cpu = psutil.cpu_percent(interval=None)
        mem = psutil.virtual_memory()
        owner._strip_cpu.setText(f"CPU: {cpu:.0f}%")
        owner._strip_mem.setText(f"MEM: {mem.percent:.0f}%")
        status_ok = cpu < 85 and mem.percent < 85
        owner._strip_status.setText("STATUS: NOMINAL" if status_ok else "STATUS: HIGH LOAD")
        owner._strip_status.setStyleSheet(
            f"color: {tokens.GREEN if status_ok else tokens.ERROR}; font-family: '{tokens.FF_MONO}';"
            f"font-size: {tokens.FS_TINY}pt; letter-spacing: 1px; padding: 0 8px;"
        )
    except Exception:
        pass

    try:
        scorecard = runtime_path / "router_scorecard.jsonl"
        if scorecard.exists():
            lines = scorecard.read_text(encoding="utf-8").strip().splitlines()
            if lines:
                last = json.loads(lines[-1])
                tok = last.get("input_tokens", last.get("total_tokens", "—"))
                owner._strip_tokens.setText(f"BUFFER: {tok} tok")
    except Exception:
        pass

    if not owner._startup_first_poll_ok:
        owner._strip_status.setText("STATUS: STARTING")
        owner._strip_status.setStyleSheet(
            f"color: {tokens.DIM}; font-family: '{tokens.FF_MONO}';"
            f"font-size: {tokens.FS_TINY}pt; letter-spacing: 1px; padding: 0 8px;"
        )
    elif owner._startup_over_budget:
        owner._strip_status.setText("STATUS: STARTUP WARN")
        owner._strip_status.setStyleSheet(
            f"color: {tokens.ERROR}; font-family: '{tokens.FF_MONO}';"
            f"font-size: {tokens.FS_TINY}pt; letter-spacing: 1px; padding: 0 8px;"
        )


def ensure_voice_capture(
    owner: Any,
    *,
    voice_capture_available: bool,
    voice_class: Any,
) -> tuple[bool, str]:
    if not voice_capture_available or voice_class is None:
        return False, "Voice capture backend is unavailable in this launcher build."
    if owner._launcher_voice is not None:
        return True, "ok"
    try:
        owner._launcher_voice = voice_class()
        return True, "ok"
    except Exception as exc:
        owner._launcher_voice = None
        return False, f"Voice capture failed to initialize: {exc}"


def on_mic_requested(owner: Any, *, thread_factory: Callable[..., Any]) -> None:
    if owner._request_in_flight:
        owner._assistant_view.add_system_message("A request is already in progress. Wait for it to finish before using push to talk.")
        return
    if owner._mic_capture_active:
        voice = owner._launcher_voice
        if voice is not None and hasattr(voice, "stop_listening"):
            try:
                voice.stop_listening()
            except Exception:
                pass
        owner._set_daily_activity("Stopping push-to-talk capture...")
        owner._status_panel.append_syslog("voice capture stop requested")
        return

    ok, summary = owner._ensure_voice_capture()
    if not ok:
        owner._assistant_view.add_system_message(summary)
        owner._status_panel.append_syslog(f"voice capture unavailable: {summary}")
        return

    owner._mic_capture_active = True
    owner._assistant_view.set_mic_capture_state(True)
    owner._set_daily_activity("Push-to-talk listening...")
    owner._status_panel.append_syslog("voice capture started")
    owner._log_launcher_event("voice_capture_started")

    def _worker() -> None:
        voice = owner._launcher_voice
        if voice is None:
            owner._assistant_events.put(("voice_error", "Voice capture backend was not available.", 0))
        else:
            try:
                result = voice.listen_once(timeout=10)
                text = str(result.get("text", "") or "").strip() if isinstance(result, dict) else ""
                error = str(result.get("error", "") or "").strip() if isinstance(result, dict) else ""
                if text:
                    owner._assistant_events.put(("voice_input", text, 0))
                    owner._log_launcher_event("voice_capture_result", ok=True, chars=len(text))
                else:
                    owner._assistant_events.put(("voice_error", error or "No speech captured.", 0))
                    owner._log_launcher_event("voice_capture_result", ok=False, error=error or "no_speech")
            except Exception as exc:
                owner._assistant_events.put(("voice_error", f"Voice capture failed: {exc}", 0))
                owner._log_launcher_event("voice_capture_result", ok=False, error=str(exc))
        emitter = getattr(owner, "assistant_event_queued", None)
        if emitter is not None and hasattr(emitter, "emit"):
            emitter.emit()

    thread_factory(target=_worker, daemon=True).start()