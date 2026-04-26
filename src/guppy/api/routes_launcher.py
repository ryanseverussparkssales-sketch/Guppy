"""Launcher platform routes — mounted on the main API at /api/launcher/*.

Exposes the same service lifecycle operations as the standalone launcher
server (port 8082) so the React web UI can manage services from within
the running app.
"""
from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException

from src.guppy.api.server_context import ServerContext
from src.guppy.launcher_platform import get_registry
from src.guppy.launcher_platform.health_monitor import check_service, check_all
from src.guppy.launcher_platform.service_config import SERVICES

logger = logging.getLogger(__name__)


def build_launcher_router(ctx: ServerContext) -> APIRouter:
    router = APIRouter(prefix="/api/launcher")

    @router.get("/services")
    async def get_services(_uid: str = Depends(ctx.require_rate_limit)) -> list[dict]:
        registry = get_registry()
        statuses = registry.all_statuses()
        health_results = await check_all(timeout=2.5)
        health_map = {h["name"]: h for h in health_results}
        return [
            {
                **s,
                "health":       health_map.get(s["name"], {}).get("health", "unknown"),
                "latency_ms":   health_map.get(s["name"], {}).get("latency_ms"),
                "health_detail":health_map.get(s["name"], {}).get("detail", ""),
            }
            for s in statuses
        ]

    @router.post("/services/{name}/start")
    async def start_service(name: str, _uid: str = Depends(ctx.require_rate_limit)) -> dict:
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, get_registry().start, name)
        if not result["ok"]:
            raise HTTPException(status_code=400, detail=result["error"])
        return result

    @router.post("/services/{name}/stop")
    async def stop_service(name: str, _uid: str = Depends(ctx.require_rate_limit)) -> dict:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, get_registry().stop, name)

    @router.post("/services/{name}/restart")
    async def restart_service(name: str, _uid: str = Depends(ctx.require_rate_limit)) -> dict:
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, get_registry().restart, name)
        if not result["ok"]:
            raise HTTPException(status_code=400, detail=result["error"])
        return result

    @router.post("/services/{name}/reset")
    async def reset_service(name: str, _uid: str = Depends(ctx.require_rate_limit)) -> dict:
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, get_registry().reset, name)
        if not result["ok"]:
            raise HTTPException(status_code=400, detail=result["error"])
        return result

    @router.get("/services/{name}/health")
    async def service_health(name: str, _uid: str = Depends(ctx.require_rate_limit)) -> dict:
        return await check_service(name)

    @router.get("/services/{name}/logs")
    async def service_logs(
        name: str,
        lines: int = 150,
        _uid: str = Depends(ctx.require_rate_limit),
    ) -> dict:
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

    @router.get("/health")
    async def overall_health(_uid: str = Depends(ctx.require_rate_limit)) -> dict:
        all_health = await check_all(timeout=2.5)
        up = sum(1 for h in all_health if h["health"] == "up")
        total = len(all_health)
        return {
            "status":   "healthy" if up == total else ("degraded" if up > 0 else "down"),
            "up":       up,
            "total":    total,
            "services": all_health,
        }

    @router.get("/debug")
    async def debug_info(_uid: str = Depends(ctx.require_rate_limit)) -> dict:
        import os, sys, platform, socket
        from src.guppy.launcher_platform.service_config import ROOT

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

        api_log = SERVICES.get("api", {}).get("log_file", "")
        recent_errors: list[str] = []
        if api_log and Path(api_log).exists():
            try:
                lines_all = Path(api_log).read_text(errors="replace").splitlines()
                recent_errors = [l for l in lines_all if "ERROR" in l or "CRITICAL" in l][-20:]
            except Exception:
                pass

        return {
            "platform":      platform.platform(),
            "python":        sys.version.split()[0],
            "cwd":           str(ROOT),
            "ports":         ports,
            "env":           {k: _mask(os.environ.get(k, "")) for k in env_keys},
            "registry_file": str(ROOT / "runtime" / "launcher_registry.json"),
            "recent_errors": recent_errors,
        }

    @router.post("/start-all")
    async def start_all(_uid: str = Depends(ctx.require_rate_limit)) -> dict:
        loop = asyncio.get_event_loop()
        registry = get_registry()
        results: dict[str, Any] = {}
        for name, cfg in SERVICES.items():
            if cfg.get("type") == "managed" and cfg.get("cmd"):
                results[name] = await loop.run_in_executor(None, registry.start, name)
        return results

    @router.post("/stop-all")
    async def stop_all(_uid: str = Depends(ctx.require_rate_limit)) -> dict:
        loop = asyncio.get_event_loop()
        registry = get_registry()
        results: dict[str, Any] = {}
        for name in reversed(list(SERVICES)):
            if SERVICES[name].get("type") == "managed":
                results[name] = await loop.run_in_executor(None, registry.stop, name)
        return results

    return router
