"""Qt desktop app — native window wrapper for the Guppy web UI.

Embeds the React web UI (served by the main API at port 8081) in a
QWebEngineView so the desktop app is always a pixel-perfect clone of
the web UI with no separate codebase to maintain.

Startup sequence:
  1. Check if API is already listening on :8081
  2. If not, spawn guppy_api.py as a managed subprocess
  3. Show animated loading screen while polling for readiness
  4. Load http://localhost:8081 once the API responds
  5. On close: minimise to system tray (API keeps running)
"""
from __future__ import annotations

import subprocess
import sys
import urllib.request
from pathlib import Path
from typing import Optional

from PySide6.QtCore import QTimer, QUrl, Qt
from PySide6.QtWebEngineCore import QWebEngineSettings
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QToolBar, QLabel, QWidget,
    QSizePolicy, QSystemTrayIcon, QMenu,
)

ROOT = Path(__file__).resolve().parents[3]
API_URL = "http://127.0.0.1:8081"
_LOADING_CSS = (
    "background:#0a0a10;color:#dde1f0;font-family:system-ui;"
    "display:flex;align-items:center;justify-content:center;"
    "height:100vh;flex-direction:column;gap:16px;margin:0"
)


def _api_alive() -> bool:
    try:
        with urllib.request.urlopen(f"{API_URL}/", timeout=1) as r:
            return r.status < 500
    except Exception:
        return False


class DesktopWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Guppy")
        self.resize(1280, 840)
        self._api_proc: Optional[subprocess.Popen] = None
        self._poll_attempts = 0

        # ── WebEngineView ─────────────────────────────────────────────────────
        self._web = QWebEngineView()
        settings = self._web.settings()
        settings.setAttribute(QWebEngineSettings.WebAttribute.LocalStorageEnabled, True)
        settings.setAttribute(QWebEngineSettings.WebAttribute.JavascriptEnabled, True)
        settings.setAttribute(QWebEngineSettings.WebAttribute.FullScreenSupportEnabled, True)
        self._web.titleChanged.connect(self._on_title_changed)
        self.setCentralWidget(self._web)

        # ── Minimal nav toolbar ───────────────────────────────────────────────
        bar = QToolBar()
        bar.setMovable(False)
        bar.setStyleSheet(
            "QToolBar{background:#12121a;border-bottom:1px solid #252535;padding:3px 10px;spacing:4px}"
            "QToolButton{background:#1e1e2a;border:1px solid #252535;border-radius:5px;"
            "            padding:3px 10px;color:#dde1f0;font-size:13px;min-width:28px}"
            "QToolButton:hover{background:#252535}"
            "QToolButton:disabled{color:#52526a}"
        )
        bar.addAction("←", self._web.back)
        bar.addAction("→", self._web.forward)
        bar.addAction("↻", self._web.reload)
        bar.addAction("⌂", self._go_home)
        sp = QWidget()
        sp.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        bar.addWidget(sp)
        self._status_lbl = QLabel("  Connecting...")
        self._status_lbl.setStyleSheet("color:#52526a;font-size:12px;padding-right:6px")
        bar.addWidget(self._status_lbl)
        self.addToolBar(bar)

        # ── System tray ───────────────────────────────────────────────────────
        self._tray = QSystemTrayIcon(self)
        tray_menu = QMenu()
        tray_menu.addAction("Show", self._show_window)
        tray_menu.addAction("Reload", self._web.reload)
        tray_menu.addSeparator()
        tray_menu.addAction("Quit Guppy", self._quit)
        self._tray.setContextMenu(tray_menu)
        self._tray.activated.connect(self._on_tray_click)
        self._tray.show()

        # ── Poll timer ────────────────────────────────────────────────────────
        self._poll = QTimer(self)
        self._poll.timeout.connect(self._poll_api)

        self._boot()

    # ── startup ───────────────────────────────────────────────────────────────

    def _boot(self) -> None:
        if _api_alive():
            self._on_api_ready()
            return
        self._set_loading("Starting Guppy API…")
        py = ROOT / ".venv" / "Scripts" / "python.exe"
        if not py.exists():
            py = Path(sys.executable)
        self._api_proc = subprocess.Popen(
            [str(py), str(ROOT / "guppy_api.py")],
            cwd=str(ROOT),
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
        )
        self._poll.start(500)

    def _poll_api(self) -> None:
        self._poll_attempts += 1
        if _api_alive():
            self._poll.stop()
            self._on_api_ready()
            return
        if self._poll_attempts > 80:          # 40 second timeout
            self._poll.stop()
            self._set_error("API did not start within 40 seconds. Check logs.")
            return
        elapsed = self._poll_attempts * 0.5
        self._set_loading(f"Starting Guppy API… ({elapsed:.0f}s)")

    def _on_api_ready(self) -> None:
        self._status_lbl.setText("  ● Connected")
        self._status_lbl.setStyleSheet("color:#22c55e;font-size:12px;padding-right:6px")
        self._web.load(QUrl(f"{API_URL}/"))

    def _go_home(self) -> None:
        self._web.load(QUrl(f"{API_URL}/"))

    # ── loading / error screens ───────────────────────────────────────────────

    def _set_loading(self, msg: str) -> None:
        self._web.setHtml(f"""<!DOCTYPE html><html><body style="{_LOADING_CSS}">
            <div style="font-size:36px;animation:pulse 1.4s ease-in-out infinite"
                 >🐟</div>
            <div style="font-size:16px;font-weight:700;color:#7c6cff;letter-spacing:-.3px">Guppy</div>
            <div style="font-size:13px;color:#52526a">{msg}</div>
            <style>@keyframes pulse{{0%,100%{{opacity:.4}}50%{{opacity:1}}}}</style>
        </body></html>""")

    def _set_error(self, msg: str) -> None:
        self._status_lbl.setText("  ● Error")
        self._status_lbl.setStyleSheet("color:#ef4444;font-size:12px;padding-right:6px")
        self._web.setHtml(f"""<!DOCTYPE html><html><body style="{_LOADING_CSS}">
            <div style="font-size:32px">⚠</div>
            <div style="color:#ef4444;font-size:14px;max-width:400px;text-align:center">{msg}</div>
            <button onclick="location.reload()"
              style="background:#7c6cff;color:#fff;border:none;padding:8px 24px;
                     border-radius:6px;cursor:pointer;font-size:13px;margin-top:8px">
              Retry</button>
        </body></html>""")

    # ── window behaviour ──────────────────────────────────────────────────────

    def _on_title_changed(self, title: str) -> None:
        self.setWindowTitle(f"Guppy — {title}" if title else "Guppy")

    def closeEvent(self, event) -> None:     # noqa: N802
        event.ignore()
        self.hide()
        self._tray.showMessage(
            "Guppy", "Running in system tray — right-click to quit.",
            QSystemTrayIcon.MessageIcon.Information, 2000,
        )

    def _show_window(self) -> None:
        self.show()
        self.raise_()
        self.activateWindow()

    def _on_tray_click(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self._show_window()

    def _quit(self) -> None:
        if self._api_proc and self._api_proc.poll() is None:
            self._api_proc.terminate()
        QApplication.quit()


def main() -> None:
    app = QApplication(sys.argv)
    app.setApplicationName("Guppy")
    app.setQuitOnLastWindowClosed(False)
    window = DesktopWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
