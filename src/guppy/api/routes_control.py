"""Control panel API routes.

GET  /api/control/status                 — full stack health (API + all models)
GET  /api/control/services               — API/Web UI lifecycle status
GET  /api/control/services/{key}/health  — API/Web UI health probe
POST /api/control/services/{key}/on      — start a managed service
POST /api/control/services/{key}/off     — stop a managed service
POST /api/control/services/{key}/reset   — reset/restart a managed service
GET  /api/control/logs/{key}             — last N lines from a model's log file
GET  /api/control/models/{key}/health    — single model health probe
POST /api/control/models/{key}/on        — start a model server
POST /api/control/models/{key}/off       — stop a model server
POST /api/control/models/{key}/reset     — kill + relaunch a model server
POST /api/control/models/{key}/restart   — legacy alias for reset
"""
from __future__ import annotations

import asyncio
import logging
import os
import subprocess
import time
from pathlib import Path
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException

from src.guppy.api.server_context import ServerContext

logger = logging.getLogger(__name__)

_LOG_DIR = Path(r"C:\llama-cpp\logs")
_ROOT = Path(__file__).resolve().parents[3]

_SERVICE_ALIASES: dict[str, str] = {
    "api": "api",
    "web": "web-dev",
    "web-ui": "web-dev",
    "webui": "web-dev",
    "web-dev": "web-dev",
}

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


def _resolve_service_key(key: str) -> str:
    service = _SERVICE_ALIASES.get(key.strip().lower())
    if not service:
        raise HTTPException(404, f"Unknown control service: {key}")
    return service


def _service_alias(service: str) -> str:
    return "web-ui" if service == "web-dev" else service


async def _service_status(service: str) -> dict[str, Any]:
    from src.guppy.launcher_platform import get_registry
    from src.guppy.launcher_platform.health_monitor import check_service

    registry_status = get_registry().status(service)
    if service == "api":
        return {
            **registry_status,
            "state": "running",
            "pid": os.getpid(),
            "port": 8081,
            "key": "api",
            "service_name": "api",
            "health": "up",
            "latency_ms": 0.0,
            "health_detail": "Current API process",
        }

    health = await check_service(service, timeout=2.5)
    return {
        **registry_status,
        "key": _service_alias(service),
        "service_name": service,
        "health": health.get("health", "unknown"),
        "latency_ms": health.get("latency_ms"),
        "health_detail": health.get("detail", ""),
    }


def _launch_api_supervisor() -> dict[str, Any]:
    script = _ROOT / "bin" / "launch_api_supervised.bat"
    if not script.exists():
        return {"ok": False, "error": f"launch_api_supervised.bat not found: {script}"}

    kwargs: dict[str, Any] = {
        "cwd": str(_ROOT),
        "stdin": subprocess.DEVNULL,
        "stdout": subprocess.DEVNULL,
        "stderr": subprocess.DEVNULL,
    }
    if os.name == "nt":
        kwargs["creationflags"] = (
            getattr(subprocess, "CREATE_NO_WINDOW", 0)
            | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
            | getattr(subprocess, "DETACHED_PROCESS", 0)
        )
        proc = subprocess.Popen(["cmd.exe", "/c", str(script)], **kwargs)
    else:
        proc = subprocess.Popen([str(script)], **kwargs)
    return {"ok": True, "pid": proc.pid}


def _exit_current_api(exit_code: int) -> None:
    time.sleep(0.6)
    os._exit(exit_code)


def _model_health_payload(key: str) -> dict[str, Any]:
    from src.guppy.api.routes_backends import _LLAMACPP_CONFIG, _port_alive

    cfg = _LLAMACPP_CONFIG.get(key)
    if not cfg:
        raise HTTPException(404, f"Unknown model key: {key}")
    port = cfg.get("port")
    alive = bool(_port_alive(port)) if port else False
    return {
        "key": key,
        "label": cfg.get("label", key),
        "port": port,
        "alive": alive,
        "healthy": alive,
        "status": "online" if alive else "offline",
        "vram_gb": cfg.get("vram_gb", 0),
        "note": cfg.get("note", ""),
        "auto_start": cfg.get("auto_start", False),
    }


def _restart_model_backend(key: str) -> dict[str, Any]:
    from src.guppy.api.routes_backends import _LLAMACPP_CONFIG, _procs, _procs_lock

    cfg = _LLAMACPP_CONFIG.get(key)
    if not cfg:
        raise HTTPException(404, f"Unknown model key: {key}")

    port = cfg["port"]

    # Kill existing process on port.
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

    # Clean up proc registry.
    with _procs_lock:
        _procs.pop(key, None)

    # Relaunch via bat file.
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

    return {"ok": True, "key": key, "pid": proc.pid, "port": port}


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

    @router.get("/services")
    async def get_services(_uid: str = Depends(ctx.require_rate_limit)) -> list[dict[str, Any]]:
        services = ["api", "web-dev"]
        return await asyncio.gather(*(_service_status(service) for service in services))

    @router.get("/services/{key}/health")
    async def get_service_health(
        key: str,
        _uid: str = Depends(ctx.require_rate_limit),
    ) -> dict[str, Any]:
        return await _service_status(_resolve_service_key(key))

    @router.post("/services/{key}/on")
    async def turn_service_on(
        key: str,
        _uid: str = Depends(ctx.require_rate_limit),
    ) -> dict[str, Any]:
        service = _resolve_service_key(key)
        if service == "api":
            status = await _service_status(service)
            if status.get("health") == "up":
                return {"ok": True, "service": "api", "status": "already_running", "health": status}
            launch = await asyncio.to_thread(_launch_api_supervisor)
            if not launch.get("ok"):
                raise HTTPException(status_code=400, detail=launch.get("error", "API start failed"))
            return {"ok": True, "service": "api", "status": "starting", **launch}

        from src.guppy.launcher_platform import get_registry
        result = await asyncio.to_thread(get_registry().start, service)
        if not result.get("ok") and "already running" not in str(result.get("error", "")).lower():
            raise HTTPException(status_code=400, detail=result.get("error", f"{service} start failed"))
        return {"ok": True, "service": _service_alias(service), "result": result}

    @router.post("/services/{key}/off")
    async def turn_service_off(
        key: str,
        background_tasks: BackgroundTasks,
        _uid: str = Depends(ctx.require_rate_limit),
    ) -> dict[str, Any]:
        service = _resolve_service_key(key)
        if service == "api":
            background_tasks.add_task(_exit_current_api, 0)
            return {"ok": True, "service": "api", "status": "shutdown_scheduled"}

        from src.guppy.launcher_platform import get_registry
        result = await asyncio.to_thread(get_registry().stop, service)
        return {"ok": True, "service": _service_alias(service), "result": result}

    @router.post("/services/{key}/reset")
    async def reset_service(
        key: str,
        background_tasks: BackgroundTasks,
        _uid: str = Depends(ctx.require_rate_limit),
    ) -> dict[str, Any]:
        service = _resolve_service_key(key)
        if service == "api":
            launch = await asyncio.to_thread(_launch_api_supervisor)
            if not launch.get("ok"):
                raise HTTPException(status_code=400, detail=launch.get("error", "API reset failed"))
            background_tasks.add_task(_exit_current_api, 1)
            return {"ok": True, "service": "api", "status": "restart_scheduled", **launch}

        from src.guppy.launcher_platform import get_registry
        result = await asyncio.to_thread(get_registry().reset, service)
        if not result.get("ok"):
            raise HTTPException(status_code=400, detail=result.get("error", f"{service} reset failed"))
        return {"ok": True, "service": _service_alias(service), "result": result}

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

    @router.get("/models/{key}/health")
    def get_model_health(key: str, _uid: str = Depends(ctx.require_rate_limit)) -> dict[str, Any]:
        return _model_health_payload(key)

    @router.post("/models/{key}/on")
    def turn_model_on(key: str, _uid: str = Depends(ctx.require_rate_limit)) -> dict[str, Any]:
        from src.guppy.api.routes_backends import ensure_backend_started

        result = ensure_backend_started(key)
        return {"ok": True, "key": key, "result": result, "health": _model_health_payload(key)}

    @router.post("/models/{key}/off")
    def turn_model_off(key: str, _uid: str = Depends(ctx.require_rate_limit)) -> dict[str, Any]:
        from src.guppy.api.routes_backends import _do_stop

        result = _do_stop(key)
        return {"ok": True, "key": key, "result": result, "health": _model_health_payload(key)}

    @router.post("/models/{key}/reset")
    def reset_model(key: str, _uid: str = Depends(ctx.require_rate_limit)) -> dict[str, Any]:
        result = _restart_model_backend(key)
        return {**result, "health": _model_health_payload(key)}

    @router.post("/models/{key}/restart")
    def restart_model(key: str, _uid: str = Depends(ctx.require_rate_limit)) -> dict[str, Any]:
        result = _restart_model_backend(key)
        return {**result, "health": _model_health_payload(key)}

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
