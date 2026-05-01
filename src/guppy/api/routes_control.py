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
    "llamacpp-phi4-mini": "phi4-mini",
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

    @router.get("/pc")
    def get_pc_health(_uid: str = Depends(ctx.require_rate_limit)) -> dict[str, Any]:
        import psutil
        cpu   = psutil.cpu_percent(interval=0.1)
        ram   = psutil.virtual_memory()
        disk  = psutil.disk_usage("C:/")
        temps: dict[str, Any] = {}
        try:
            raw = psutil.sensors_temperatures() or {}
            for k, entries in raw.items():
                if entries:
                    temps[k] = round(entries[0].current, 1)
        except Exception:
            pass
        gpu = _gpu_stats()
        return {
            "cpu_pct":      round(cpu, 1),
            "ram_used_gb":  round(ram.used  / 1e9, 1),
            "ram_total_gb": round(ram.total / 1e9, 1),
            "ram_pct":      round(ram.percent, 1),
            "disk_used_gb": round(disk.used  / 1e9, 1),
            "disk_total_gb":round(disk.total / 1e9, 1),
            "disk_pct":     round(disk.percent, 1),
            "temps":        temps,
            "gpu":          gpu,
        }

    return router


def _gpu_stats() -> dict[str, Any] | None:
    try:
        out = subprocess.check_output(
            ["rocm-smi", "--showmemuse", "--showuse", "--csv"],
            text=True, timeout=3,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        )
        vram_used = vram_total = gpu_use = None
        for line in out.splitlines():
            line = line.strip()
            if not line or line.startswith("device") or line.startswith("GPU"):
                continue
            parts = [p.strip() for p in line.split(",")]
            if len(parts) >= 2:
                try:
                    # columns vary by rocm-smi version; try common positions
                    for p in parts:
                        if "%" in p:
                            gpu_use = float(p.replace("%", ""))
                        elif p.isdigit():
                            val = int(p)
                            if vram_used is None:
                                vram_used = val
                            elif vram_total is None:
                                vram_total = val
                except Exception:
                    pass
        if vram_total:
            return {
                "vram_used_mb":  vram_used,
                "vram_total_mb": vram_total,
                "vram_pct": round(vram_used / vram_total * 100, 1) if vram_used else None,
                "gpu_use_pct": gpu_use,
                "label": "RX 7900 XTX",
            }
    except Exception:
        pass
    # Fallback: try nvidia-smi
    try:
        out = subprocess.check_output(
            ["nvidia-smi", "--query-gpu=memory.used,memory.total,utilization.gpu",
             "--format=csv,noheader,nounits"],
            text=True, timeout=3,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        )
        parts = [p.strip() for p in out.strip().split(",")]
        if len(parts) >= 3:
            return {
                "vram_used_mb":  int(parts[0]),
                "vram_total_mb": int(parts[1]),
                "vram_pct": round(int(parts[0]) / int(parts[1]) * 100, 1),
                "gpu_use_pct": float(parts[2]),
                "label": "GPU",
            }
    except Exception:
        pass
    return None
