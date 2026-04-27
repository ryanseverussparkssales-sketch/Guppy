"""
Llamacpp backend lifecycle management.

POST /api/backends/llamacpp/{name}/start  — launch the server process
POST /api/backends/llamacpp/{name}/stop   — terminate the server + children
GET  /api/backends/llamacpp               — list all backends with live probe status

VRAM budget is enforced server-side:
  Mode A  Pepe (8082) + Gemma (8080)  together  ~17 GB
  Mode B  Qwen3 (8083) alone          ~19 GB

Starting a Mode B server while a Mode A server is alive (or vice versa) returns
HTTP 409 with a clear explanation.
"""
from __future__ import annotations

import asyncio
import logging
import os
import subprocess
import threading
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException

from src.guppy.api.server_context import ServerContext

logger = logging.getLogger(__name__)

# ── static config ─────────────────────────────────────────────────────────────

_LLAMACPP_CONFIG: Dict[str, Dict[str, Any]] = {
    "llamacpp-pepe": {
        "bat":   r"C:\llama-cpp\launch-pepe.bat",
        "port":  8082,
        "label": "Assistant Pepe 8B",
        "mode":  "A",
        "note":  "Fast · ~8.5 GB VRAM",
    },
    "llamacpp-gemma": {
        "bat":   r"C:\llama-cpp\launch-gemma.bat",
        "port":  8080,
        "label": "Gemma 4 E4B Heretic",
        "mode":  "A",
        "note":  "Vision · ~8.5 GB VRAM",
    },
    "llamacpp-qwen3": {
        "bat":   r"C:\llama-cpp\launch-qwen3.bat",
        "port":  8083,
        "label": "Qwen3 35B Uncensored",
        "mode":  "B",
        "note":  "Reasoning · ~19 GB VRAM — run alone",
    },
}

_MODE_A = {"llamacpp-pepe", "llamacpp-gemma"}
_MODE_B = {"llamacpp-qwen3"}

# ── process registry (in-memory, survives API requests but not restarts) ──────

_procs: Dict[str, subprocess.Popen] = {}
_procs_lock = threading.Lock()


# ── helpers ───────────────────────────────────────────────────────────────────

def _port_alive(port: int, timeout: float = 1.5) -> bool:
    """Return True if something is answering on the given port."""
    import urllib.request
    import urllib.error
    try:
        urllib.request.urlopen(f"http://127.0.0.1:{port}/v1/models", timeout=timeout)
        return True
    except Exception:
        return False


def _kill_tree(pid: int) -> None:
    """Kill a process and all its children (using psutil)."""
    try:
        import psutil
        parent = psutil.Process(pid)
        children = parent.children(recursive=True)
        for child in children:
            try:
                child.kill()
            except psutil.NoSuchProcess:
                pass
        parent.kill()
        logger.debug(f"[backends] killed tree rooted at pid {pid}")
    except Exception as exc:
        logger.warning(f"[backends] kill_tree({pid}) failed: {exc}")


def _find_pid_by_port(port: int) -> Optional[int]:
    """Return the PID of whichever process is LISTENing on `port`, or None."""
    try:
        import psutil
        for proc in psutil.process_iter(["pid"]):
            try:
                for conn in proc.net_connections():
                    if (
                        conn.laddr.port == port
                        and conn.status in {"LISTEN", "ESTABLISHED"}
                    ):
                        return proc.pid
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
    except Exception as exc:
        logger.warning(f"[backends] find_pid_by_port({port}) failed: {exc}")
    return None


def _any_alive(names: set) -> bool:
    return any(
        _port_alive(_LLAMACPP_CONFIG[n]["port"])
        for n in names
        if n in _LLAMACPP_CONFIG
    )


# ── business logic ────────────────────────────────────────────────────────────

def _do_start(name: str) -> Dict[str, Any]:
    cfg = _LLAMACPP_CONFIG.get(name)
    if not cfg:
        raise HTTPException(status_code=404, detail=f"Unknown backend: {name!r}")

    # VRAM conflict guard
    if name in _MODE_B and _any_alive(_MODE_A):
        raise HTTPException(
            status_code=409,
            detail=(
                "Mode B (Qwen3 ~19 GB) needs the full GPU.  "
                "Stop Mode A servers (Pepe / Gemma) first."
            ),
        )
    if name in _MODE_A and _any_alive(_MODE_B):
        raise HTTPException(
            status_code=409,
            detail=(
                "Qwen3 (Mode B, ~19 GB) is currently using the full GPU.  "
                "Stop Qwen3 before starting Mode A servers."
            ),
        )

    # Already responding on the port?
    if _port_alive(cfg["port"]):
        return {"status": "already_running", "port": cfg["port"]}

    # Launch script must exist
    bat = cfg["bat"]
    if not os.path.exists(bat):
        raise HTTPException(
            status_code=503,
            detail=f"Launch script not found: {bat}",
        )

    with _procs_lock:
        existing = _procs.get(name)
        if existing and existing.poll() is None:
            # We already launched it and it hasn't exited yet — still starting
            return {"status": "starting", "pid": existing.pid, "port": cfg["port"]}

        proc = subprocess.Popen(
            ["cmd", "/c", bat],
            creationflags=(
                subprocess.CREATE_NEW_PROCESS_GROUP  # type: ignore[attr-defined]
                | subprocess.CREATE_NO_WINDOW        # type: ignore[attr-defined]
            ),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        _procs[name] = proc
        logger.info(f"[backends] launched {name} (bat={bat}, pid={proc.pid})")

    return {"status": "starting", "pid": proc.pid, "port": cfg["port"]}


def _do_stop(name: str) -> Dict[str, Any]:
    cfg = _LLAMACPP_CONFIG.get(name)
    if not cfg:
        raise HTTPException(status_code=404, detail=f"Unknown backend: {name!r}")

    killed_pids: List[int] = []

    # Kill our tracked process (+ its full child tree)
    with _procs_lock:
        proc = _procs.pop(name, None)

    if proc and proc.poll() is None:
        _kill_tree(proc.pid)
        killed_pids.append(proc.pid)
        logger.info(f"[backends] stopped tracked proc pid={proc.pid} for {name}")

    # Also kill anything listening on the port (launched outside Guppy)
    pid = _find_pid_by_port(cfg["port"])
    if pid and pid not in killed_pids:
        _kill_tree(pid)
        killed_pids.append(pid)
        logger.info(f"[backends] killed external proc pid={pid} on port {cfg['port']} for {name}")

    return {
        "status": "stopped" if killed_pids else "not_running",
        "killed_pids": killed_pids,
    }


def _do_status_all() -> List[Dict[str, Any]]:
    result = []
    for name, cfg in _LLAMACPP_CONFIG.items():
        with _procs_lock:
            proc = _procs.get(name)
        tracked = proc is not None and proc.poll() is None
        alive = _port_alive(cfg["port"])
        result.append({
            "name":    name,
            "label":   cfg["label"],
            "port":    cfg["port"],
            "mode":    cfg["mode"],
            "note":    cfg["note"],
            "alive":   alive,
            "tracked": tracked,
            "pid":     proc.pid if tracked else None,
        })
    return result


# ── router ────────────────────────────────────────────────────────────────────

def build_backends_router(ctx: ServerContext) -> APIRouter:
    router = APIRouter(prefix="/api/backends")

    @router.get("/llamacpp")
    async def list_llamacpp(_u: str = Depends(ctx.require_rate_limit)):
        """Return live probe status for all llamacpp backends."""
        return await asyncio.to_thread(_do_status_all)

    @router.post("/llamacpp/{name}/start")
    async def start_llamacpp(name: str, _u: str = Depends(ctx.require_rate_limit)):
        """Start a llamacpp server.  Enforces VRAM mode conflict rules."""
        return await asyncio.to_thread(_do_start, name)

    @router.post("/llamacpp/{name}/stop")
    async def stop_llamacpp(name: str, _u: str = Depends(ctx.require_rate_limit)):
        """Stop a llamacpp server (kills process tree + any external listener on the port)."""
        return await asyncio.to_thread(_do_stop, name)

    return router
