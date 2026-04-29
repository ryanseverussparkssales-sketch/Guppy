"""Control panel API routes.

GET  /api/control/status          — full stack health (API + all models)
GET  /api/control/logs/{key}      — last N lines from a model's log file
POST /api/control/models/{key}/restart — kill + relaunch a model server
"""
from __future__ import annotations

import logging
import os
import subprocess
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse

from src.guppy.api.server_context import ServerContext

logger = logging.getLogger(__name__)

_LOG_DIR = Path(r"C:\llama-cpp\logs")

# Map model key → log file stem (matches what Start-Process redirects create)
_LOG_FILES: dict[str, str] = {
    "llamacpp-dispatch":  "dispatch-phi4",
    "llamacpp-hermes3":   "hermes3",
    "llamacpp-hermes4":   "hermes4",
    "llamacpp-pepe":      "pepe",
    "llamacpp-rocinante": "rocinante",
    "llamacpp-minicpm":   "minicpm",
    "llamacpp-xlam":      "xlam",
    "llamacpp-chat":      "llama70b",
}


def _tail(path: Path, lines: int = 80) -> list[str]:
    if not path.exists():
        return []
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
        return text.splitlines()[-lines:]
    except Exception:
        return []


def build_control_router(ctx: ServerContext) -> APIRouter:
    router = APIRouter()

    @router.get("/status")
    def get_status(_uid: str = Depends(ctx.require_rate_limit)) -> dict[str, Any]:
        from src.guppy.api.routes_backends import _LLAMACPP_CONFIG, _port_alive
        models = []
        for key, cfg in _LLAMACPP_CONFIG.items():
            port  = cfg.get("port")
            alive = _port_alive(port) if port else False
            models.append({
                "key":     key,
                "label":   cfg.get("label", key),
                "port":    port,
                "alive":   alive,
                "vram_gb": cfg.get("vram_gb", 0),
                "note":    cfg.get("note", ""),
                "auto_start": cfg.get("auto_start", False),
            })
        return {"models": models}

    @router.get("/logs/{key}")
    def get_logs(
        key: str,
        lines: int = 80,
        _uid: str = Depends(ctx.require_rate_limit),
    ) -> dict[str, Any]:
        stem = _LOG_FILES.get(key)
        if not stem:
            return {"lines": [], "found": False}
        out_path = _LOG_DIR / f"{stem}.log"
        err_path = _LOG_DIR / f"{stem}.err"
        out_lines = _tail(out_path, lines)
        err_lines = _tail(err_path, lines)
        # Merge stdout + stderr, prefer err (llama.cpp writes progress to stderr)
        combined = err_lines if err_lines else out_lines
        return {"lines": combined, "found": bool(combined), "path": str(err_path if err_lines else out_path)}

    @router.post("/models/{key}/restart")
    def restart_model(key: str, _uid: str = Depends(ctx.require_rate_limit)) -> dict[str, Any]:
        from src.guppy.api.routes_backends import _LLAMACPP_CONFIG, _port_alive, _procs, _procs_lock
        cfg = _LLAMACPP_CONFIG.get(key)
        if not cfg:
            raise HTTPException(404, f"Unknown model key: {key}")

        port = cfg["port"]

        # Kill existing process on port
        if os.name == "nt":
            try:
                out = subprocess.check_output(
                    ["netstat", "-ano"],
                    text=True,
                    creationflags=subprocess.CREATE_NO_WINDOW,
                )
                for line in out.splitlines():
                    if f":{port} " in line and "LISTENING" in line:
                        pid = line.strip().split()[-1]
                        if pid and pid != "0":
                            subprocess.run(
                                ["taskkill", "/F", "/PID", pid],
                                creationflags=subprocess.CREATE_NO_WINDOW,
                                capture_output=True,
                            )
            except Exception as e:
                logger.warning("[control] kill port %d: %s", port, e)

        # Clean up proc registry
        with _procs_lock:
            _procs.pop(key, None)

        # Relaunch via bat file
        bat = cfg.get("bat", "")
        if not bat or not Path(bat).exists():
            raise HTTPException(400, f"No launch script for {key}: {bat}")

        stem = _LOG_FILES.get(key, key)
        log_out = str(_LOG_DIR / f"{stem}.log")
        log_err = str(_LOG_DIR / f"{stem}.err")
        _LOG_DIR.mkdir(parents=True, exist_ok=True)

        proc = subprocess.Popen(
            ["cmd.exe", "/c", bat],
            stdout=open(log_out, "w"),
            stderr=open(log_err, "w"),
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        )
        with _procs_lock:
            _procs[key] = proc

        return {"ok": True, "key": key, "pid": proc.pid}

    return router
