"""Standalone launcher platform server — runs on port 8082.

Start with:  python launch_platform.py
Or:          python -m src.guppy.launcher_platform
"""
from __future__ import annotations

import asyncio
import logging
import os
import sys
import webbrowser
import threading
from pathlib import Path
from typing import Any

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse

from . import get_registry
from .health_monitor import check_service, check_all
from .service_config import SERVICES, ROOT

logger = logging.getLogger(__name__)
_STATIC = Path(__file__).parent / "static"

app = FastAPI(title="Guppy Launcher Platform", docs_url=None, redoc_url=None)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000",
                   "http://localhost:8081", "http://127.0.0.1:8081"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/", response_class=HTMLResponse)
async def serve_ui() -> HTMLResponse:
    return HTMLResponse((_STATIC / "index.html").read_text(encoding="utf-8"))


@app.get("/api/services")
async def get_services() -> list[dict]:
    registry = get_registry()
    statuses = registry.all_statuses()
    health_results = await check_all(timeout=2.5)
    health_map = {h["name"]: h for h in health_results}
    combined = []
    for s in statuses:
        h = health_map.get(s["name"], {"health": "unknown", "latency_ms": None, "detail": ""})
        combined.append({**s, "health": h["health"], "latency_ms": h["latency_ms"], "health_detail": h["detail"]})
    return combined


@app.post("/api/services/{name}/start")
async def start_service(name: str) -> dict:
    registry = get_registry()
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(None, registry.start, name)
    if not result["ok"]:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@app.post("/api/services/{name}/stop")
async def stop_service(name: str) -> dict:
    registry = get_registry()
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, registry.stop, name)


@app.post("/api/services/{name}/restart")
async def restart_service(name: str) -> dict:
    registry = get_registry()
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(None, registry.restart, name)
    if not result["ok"]:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@app.post("/api/services/{name}/reset")
async def reset_service(name: str) -> dict:
    registry = get_registry()
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(None, registry.reset, name)
    if not result["ok"]:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@app.get("/api/services/{name}/health")
async def service_health(name: str) -> dict:
    return await check_service(name)


@app.get("/api/services/{name}/logs")
async def service_logs(name: str, lines: int = 150) -> dict:
    cfg = SERVICES.get(name, {})
    log_file = cfg.get("log_file")
    if not log_file:
        return {"lines": [], "note": "No log file for this service"}
    p = Path(log_file)
    if not p.exists():
        return {"lines": [], "note": "Log file not yet created"}
    try:
        content = p.read_text(encoding="utf-8", errors="replace")
        all_lines = content.splitlines()
        return {"lines": all_lines[-lines:], "total": len(all_lines)}
    except Exception as exc:
        return {"lines": [], "error": str(exc)}


@app.delete("/api/services/{name}/logs")
async def clear_logs(name: str) -> dict:
    cfg = SERVICES.get(name, {})
    log_file = cfg.get("log_file")
    if not log_file:
        return {"ok": False, "note": "No log file"}
    try:
        Path(log_file).write_text("")
        return {"ok": True}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


@app.get("/api/health")
async def overall_health() -> dict:
    all_health = await check_all(timeout=2.5)
    up = sum(1 for h in all_health if h["health"] == "up")
    total = len(all_health)
    if up == total:
        status = "healthy"
    elif up > 0:
        status = "degraded"
    else:
        status = "down"
    return {"status": status, "up": up, "total": total, "services": all_health}


@app.get("/api/debug")
async def debug_info() -> dict:
    import platform, socket

    def port_open(port: int) -> bool:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.3):
                return True
        except OSError:
            return False

    ports = {str(cfg["port"]): port_open(cfg["port"]) for cfg in SERVICES.values() if cfg.get("port")}

    def _mask(v: str) -> str:
        return (v[:4] + "***") if len(v) > 4 else ("set" if v else "not set")

    env_keys = [
        "GUPPY_DEV_MODE", "GUPPY_DEFAULT_MODE", "GUPPY_LOCAL_RUNTIME_BACKEND",
        "GUPPY_JWT_SECRET", "ANTHROPIC_API_KEY", "OPENAI_API_KEY",
        "COHERE_API_KEY", "MISTRAL_API_KEY", "GUPPY_LMSTUDIO_API_KEY",
    ]
    env = {k: _mask(os.environ.get(k, "")) for k in env_keys}

    # Read recent error lines from API log
    api_log = SERVICES.get("api", {}).get("log_file", "")
    recent_errors: list[str] = []
    if api_log and Path(api_log).exists():
        try:
            lines = Path(api_log).read_text(errors="replace").splitlines()
            recent_errors = [l for l in lines if "ERROR" in l or "CRITICAL" in l][-20:]
        except Exception:
            pass

    return {
        "platform":       platform.platform(),
        "python":         sys.version.split()[0],
        "cwd":            str(ROOT),
        "ports":          ports,
        "env":            env,
        "registry_file":  str(ROOT / "runtime" / "launcher_registry.json"),
        "recent_errors":  recent_errors,
    }


@app.post("/api/start-all")
async def start_all() -> dict:
    registry = get_registry()
    loop = asyncio.get_event_loop()
    results = {}
    for name, cfg in SERVICES.items():
        if cfg.get("type") == "managed" and cfg.get("cmd"):
            results[name] = await loop.run_in_executor(None, registry.start, name)
    return results


@app.post("/api/stop-all")
async def stop_all() -> dict:
    registry = get_registry()
    loop = asyncio.get_event_loop()
    results = {}
    for name in reversed(list(SERVICES)):
        if SERVICES[name].get("type") == "managed":
            results[name] = await loop.run_in_executor(None, registry.stop, name)
    return results


def run(host: str = "127.0.0.1", port: int = 8082, open_browser: bool = True) -> None:
    if open_browser:
        def _open() -> None:
            import time
            time.sleep(1.2)
            webbrowser.open(f"http://{host}:{port}/")
        threading.Thread(target=_open, daemon=True).start()

    uvicorn.run(app, host=host, port=port, log_level="warning")


if __name__ == "__main__":
    run()
