"""Process lifecycle management for Guppy services.

Tracks running processes in memory and persists PIDs to
runtime/launcher_registry.json so the registry survives launcher restarts.
"""
from __future__ import annotations

import json
import logging
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from .service_config import ROOT, SERVICES

logger = logging.getLogger(__name__)
REGISTRY_FILE = ROOT / "runtime" / "launcher_registry.json"


def _is_pid_alive(pid: int) -> bool:
    if sys.platform == "win32":
        try:
            result = subprocess.run(
                ["tasklist", "/FI", f"PID eq {pid}", "/NH", "/FO", "CSV"],
                capture_output=True, text=True, timeout=3,
            )
            return f'"{pid}"' in result.stdout
        except Exception:
            return False
    else:
        try:
            os.kill(pid, 0)
            return True
        except (ProcessLookupError, PermissionError):
            return False


def _kill_pid(pid: int, force: bool = False) -> None:
    if sys.platform == "win32":
        flags = ["/F"] if force else []
        subprocess.run(
            ["taskkill", "/PID", str(pid), "/T"] + flags,
            capture_output=True, timeout=3,
        )
    else:
        import signal
        try:
            os.kill(pid, signal.SIGKILL if force else signal.SIGTERM)
        except ProcessLookupError:
            pass


class _RunningService:
    def __init__(
        self,
        name: str,
        pid: int,
        started_at: str,
        log_file: Optional[str],
        proc: Optional[subprocess.Popen] = None,
    ):
        self.name = name
        self.pid = pid
        self.started_at = started_at
        self.log_file = log_file
        self._proc = proc

    def is_alive(self) -> bool:
        if self._proc is not None:
            return self._proc.poll() is None
        return _is_pid_alive(self.pid)

    def to_dict(self) -> dict:
        return {
            "name":       self.name,
            "pid":        self.pid,
            "started_at": self.started_at,
            "log_file":   self.log_file,
        }


class ProcessRegistry:
    """Manages the lifecycle of all Guppy services."""

    def __init__(self) -> None:
        self._services: dict[str, _RunningService] = {}
        self._load()

    # ── persistence ──────────────────────────────────────────────────────────

    def _load(self) -> None:
        if not REGISTRY_FILE.exists():
            return
        try:
            data = json.loads(REGISTRY_FILE.read_text())
            for name, entry in data.items():
                sp = _RunningService(
                    name=name,
                    pid=entry["pid"],
                    started_at=entry["started_at"],
                    log_file=entry.get("log_file"),
                )
                if sp.is_alive():
                    self._services[name] = sp
                    logger.debug("[REGISTRY] Recovered %s (PID %d)", name, sp.pid)
        except Exception as exc:
            logger.warning("[REGISTRY] Could not restore registry: %s", exc)

    def _save(self) -> None:
        REGISTRY_FILE.parent.mkdir(parents=True, exist_ok=True)
        data = {k: v.to_dict() for k, v in self._services.items()}
        REGISTRY_FILE.write_text(json.dumps(data, indent=2))

    # ── lifecycle ─────────────────────────────────────────────────────────────

    def start(self, service_name: str) -> dict:
        cfg = SERVICES.get(service_name)
        if not cfg:
            return {"ok": False, "error": f"Unknown service: {service_name}"}
        if cfg.get("cmd") is None:
            return {"ok": False, "error": f"'{service_name}' is external — start it manually"}

        existing = self._services.get(service_name)
        if existing and existing.is_alive():
            return {"ok": False, "error": f"{service_name} already running (PID {existing.pid})"}

        log_file = cfg.get("log_file")
        log_fh = None
        if log_file:
            Path(log_file).parent.mkdir(parents=True, exist_ok=True)
            log_fh = open(log_file, "a")  # noqa: SIM115

        env = os.environ.copy()
        creation_flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0

        try:
            proc = subprocess.Popen(
                cfg["cmd"],
                cwd=cfg.get("cwd") or str(ROOT),
                stdout=log_fh or subprocess.DEVNULL,
                stderr=log_fh or subprocess.DEVNULL,
                env=env,
                creationflags=creation_flags,
            )
        except Exception as exc:
            if log_fh:
                log_fh.close()
            return {"ok": False, "error": str(exc)}

        sp = _RunningService(
            name=service_name,
            pid=proc.pid,
            started_at=datetime.now(timezone.utc).isoformat(),
            log_file=log_file,
            proc=proc,
        )
        self._services[service_name] = sp
        self._save()
        logger.info("[REGISTRY] Started %s (PID %d)", service_name, proc.pid)
        return {"ok": True, "pid": proc.pid}

    def stop(self, service_name: str, timeout: float = 8.0) -> dict:
        sp = self._services.get(service_name)
        if not sp or not sp.is_alive():
            self._services.pop(service_name, None)
            self._save()
            return {"ok": True, "note": "already stopped"}

        # Graceful terminate
        if sp._proc:
            sp._proc.terminate()
        else:
            _kill_pid(sp.pid, force=False)

        # Wait, then force-kill
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if not sp.is_alive():
                break
            time.sleep(0.2)

        if sp.is_alive():
            _kill_pid(sp.pid, force=True)
            time.sleep(0.3)

        self._services.pop(service_name, None)
        self._save()
        logger.info("[REGISTRY] Stopped %s", service_name)
        return {"ok": True}

    def restart(self, service_name: str) -> dict:
        self.stop(service_name)
        return self.start(service_name)

    def reset(self, service_name: str) -> dict:
        """Stop service, clean state files, restart."""
        self.stop(service_name)

        cfg = SERVICES.get(service_name, {})
        log_file = cfg.get("log_file")
        if log_file:
            try:
                Path(log_file).write_text("")
            except Exception:
                pass

        if service_name == "api":
            _clear_api_state()

        return self.start(service_name)

    # ── status ────────────────────────────────────────────────────────────────

    def status(self, service_name: str) -> dict:
        cfg = SERVICES.get(service_name, {})
        sp = self._services.get(service_name)

        if sp and sp.is_alive():
            return {
                "name":        service_name,
                "label":       cfg.get("label", service_name),
                "description": cfg.get("description", ""),
                "state":       "running",
                "pid":         sp.pid,
                "started_at":  sp.started_at,
                "port":        cfg.get("port"),
                "type":        cfg.get("type", "managed"),
                "icon":        cfg.get("icon", "server"),
                "has_logs":    bool(cfg.get("log_file")),
            }

        if sp:
            self._services.pop(service_name, None)
            self._save()

        return {
            "name":        service_name,
            "label":       cfg.get("label", service_name),
            "description": cfg.get("description", ""),
            "state":       "stopped",
            "pid":         None,
            "started_at":  None,
            "port":        cfg.get("port"),
            "type":        cfg.get("type", "managed"),
            "icon":        cfg.get("icon", "server"),
            "has_logs":    bool(cfg.get("log_file")),
        }

    def all_statuses(self) -> list[dict]:
        return [self.status(name) for name in SERVICES]


def _clear_api_state() -> None:
    for fname in ["runtime/hub.starting", "runtime/guppy.status", "runtime/guppy.pid"]:
        try:
            Path(ROOT / fname).unlink(missing_ok=True)
        except Exception:
            pass
