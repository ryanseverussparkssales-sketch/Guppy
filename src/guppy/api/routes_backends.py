"""
Llamacpp backend lifecycle management.

POST /api/backends/llamacpp/{name}/start  — launch the server process
POST /api/backends/llamacpp/{name}/stop   — terminate the server + children
GET  /api/backends/llamacpp               — list all backends with live probe status

VRAM budget is enforced server-side:
  Mode A  Pepe (8082) + Gemma (8080) + MiniCPM (8084)  any combination  ~8-26 GB total
           Pepe+MiniCPM = ~17 GB ✓   Pepe+Gemma = ~17 GB ✓
           All three together = ~26 GB (tight on 24 GB card)
  Mode B  Qwen3 (8083) alone                            ~19 GB

Starting a Mode B server while a Mode A server is alive (or vice versa) returns
HTTP 409 with a clear explanation.

MiniCPM-o 4.5 note: requires TWO files — main GGUF + mmproj-model-f16.gguf.
Launch script: C:\\llama-cpp\\launch-minicpm.bat
Download from: https://huggingface.co/openbmb/MiniCPM-o-4_5-gguf
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
        "bat":     r"C:\llama-cpp\launch-pepe.bat",
        "port":    8082,
        "label":   "Assistant Pepe 8B",
        "mode":    "A",
        "note":    "Fast · ~8.5 GB VRAM",
        "vram_gb": 8.5,
    },
    "llamacpp-gemma": {
        "bat":     r"C:\llama-cpp\launch-gemma.bat",
        "port":    8080,
        "label":   "Gemma 4 E4B Heretic",
        "mode":    "A",
        "note":    "Vision · ~8.5 GB VRAM",
        "vram_gb": 8.5,
    },
    "llamacpp-qwen3": {
        "bat":     r"C:\llama-cpp\launch-qwen3.bat",
        "port":    8083,
        "label":   "Qwen3 35B Uncensored",
        "mode":    "B",
        "note":    "Reasoning · ~19 GB VRAM — run alone",
        "vram_gb": 19.0,
    },
    "llamacpp-minicpm": {
        "bat":     r"C:\llama-cpp\launch-minicpm.bat",
        "port":    8084,
        "label":   "MiniCPM-o 4.5 Omni",
        "mode":    "A",
        "note":    "Vision+Speech · ~9 GB VRAM — needs mmproj file",
        "vram_gb": 9.0,
    },
    "llamacpp-dispatch": {
        "bat":     r"C:\llama-cpp\launch-dispatch.bat",
        "port":    8085,
        "label":   "Qwen2.5-3B-Instruct Dispatcher",
        "mode":    "A",
        "note":    "Orchestrator · ~2 GB VRAM — auto-starts with Guppy",
        "vram_gb": 2.0,
        "auto_start": True,
    },
    "llamacpp-hermes4": {
        "bat":     r"C:\llama-cpp\launch-hermes-4-14b.bat",
        "port":    8086,
        "label":   "Hermes 4 14B",
        "mode":    "A",
        "note":    "Tools · ~11 GB VRAM — uncensored — always-on workspace agent",
        "vram_gb": 11.0,
        "auto_start": True,
    },
    "llamacpp-hermes3": {
        "bat":     r"C:\llama-cpp\launch-hermes-3-8b.bat",
        "port":    8087,
        "label":   "Hermes 3 8B Lorablated",
        "mode":    "A",
        "note":    "Companion voice · ~9 GB VRAM — uncensored — always-on",
        "vram_gb": 9.0,
        "auto_start": True,
    },
    "llamacpp-rocinante": {
        "bat":     r"C:\llama-cpp\launch-rocinante-12b.bat",
        "port":    8088,
        "label":   "Rocinante X 12B",
        "mode":    "A",
        "note":    "Creative · ~10 GB VRAM — roleplay/writing",
        "vram_gb": 10.0,
    },
    # xLAM-2-8B-fc-r: Salesforce function-calling specialist, #1 BFCL V4 ≤8B.
    # On-demand (not always-on) — starts on first tool_call task, unloads when idle.
    # Freed 5 GB VRAM slot to Hermes 3 for always-on companion voice.
    "llamacpp-xlam": {
        "bat":     r"C:\llama-cpp\launch-xlam.bat",
        "port":    8089,
        "label":   "xLAM-2-8B Function-Calling",
        "mode":    "A",
        "note":    "Tool-call specialist · ~5 GB VRAM · #1 BFCL V4 ≤8B — on-demand",
        "vram_gb": 5.0,
    },
    # Llama 3.3 70B Instruct Q4_K_M: CPU-only flagship chat (zero VRAM).
    # Runs entirely in RAM (~42 GB) alongside the GPU workspace agent stack.
    # ~4-6 tok/s on Ryzen 9 9900X — acceptable for conversation, uncensored.
    "llamacpp-chat": {
        "bat":     r"C:\llama-cpp\launch-chat-70b.bat",
        "port":    8090,
        "label":   "Llama 3.3 70B Chat (CPU)",
        "mode":    "A",
        "note":    "Flagship CPU-only chat · ~42 GB RAM · zero VRAM · ~4-6 tok/s",
        "vram_gb": 0.0,
    },
    # Phi-4-mini-instruct: true JSON tool_call dispatch orchestrator.
    # Replaces Qwen2.5-3B when upgraded: emits structured {"tool_calls": [...]} JSON
    # to route subtasks to xLAM for execution. ~2.5 GB VRAM (Q4_K_M).
    # Model: download from https://huggingface.co/microsoft/Phi-4-mini-instruct-GGUF
    "llamacpp-phi4-mini": {
        "bat":     r"C:\llama-cpp\launch-phi4-mini.bat",
        "port":    8091,
        "label":   "Phi-4-mini-instruct",
        "mode":    "A",
        "note":    "True dispatch orchestrator · ~2.5 GB VRAM · JSON tool_call routing",
        "vram_gb": 2.5,
    },
}

# Total VRAM budget for the installed GPU (RX 7900 XTX)
_GPU_VRAM_GB: float = float(os.environ.get("GUPPY_GPU_VRAM_GB", "24"))

_MODE_A = {
    "llamacpp-pepe", "llamacpp-gemma", "llamacpp-minicpm", "llamacpp-dispatch",
    "llamacpp-hermes4", "llamacpp-hermes3", "llamacpp-rocinante", "llamacpp-xlam",
    "llamacpp-chat", "llamacpp-phi4-mini",
}
_MODE_B = {"llamacpp-qwen3"}

# ── process registry (in-memory, survives API requests but not restarts) ──────

_procs: Dict[str, subprocess.Popen] = {}
_procs_lock = threading.Lock()


# ── helpers ───────────────────────────────────────────────────────────────────

# TTL cache for port liveness — avoids 1.5 s timeout on every request for dead ports.
# Keyed by port number, value is (is_alive: bool, expires_at: float).
_port_alive_cache: Dict[int, tuple] = {}
_PORT_ALIVE_TTL_OK  = 10.0   # cache "alive"  for 10 s
_PORT_ALIVE_TTL_DEAD =  5.0   # cache "dead"   for  5 s (re-check sooner so startup is detected)

def _port_alive(port: int, timeout: float = 0.5) -> bool:
    """Return True if something is answering on the given port.

    Results are cached for a short TTL so rapid consecutive calls (e.g. fallback
    chains) don't each incur a full connection timeout.
    """
    import time
    import urllib.request

    now = time.monotonic()
    cached = _port_alive_cache.get(port)
    if cached and now < cached[1]:
        return cached[0]

    try:
        urllib.request.urlopen(f"http://127.0.0.1:{port}/v1/models", timeout=timeout)
        alive = True
    except Exception:
        alive = False

    ttl = _PORT_ALIVE_TTL_OK if alive else _PORT_ALIVE_TTL_DEAD
    _port_alive_cache[port] = (alive, now + ttl)
    return alive


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


def _alive_names(names: set) -> List[str]:
    """Return the labels of backends in *names* that are currently alive."""
    return [
        _LLAMACPP_CONFIG[n]["label"]
        for n in names
        if n in _LLAMACPP_CONFIG and _port_alive(_LLAMACPP_CONFIG[n]["port"])
    ]


# ── business logic ────────────────────────────────────────────────────────────

def _do_start(name: str) -> Dict[str, Any]:
    cfg = _LLAMACPP_CONFIG.get(name)
    if not cfg:
        raise HTTPException(status_code=404, detail=f"Unknown backend: {name!r}")

    # VRAM conflict guard — build error messages that name the actual running backends
    if name in _MODE_B:
        blocking = _alive_names(_MODE_A - {name})
        if blocking:
            names_str = ", ".join(blocking)
            raise HTTPException(
                status_code=409,
                detail=(
                    f"Mode B ({cfg['label']}, ~{cfg['vram_gb']:.0f} GB) needs the full GPU — "
                    f"stop these first: {names_str}."
                ),
            )
    if name in _MODE_A:
        blocking = _alive_names(_MODE_B - {name})
        if blocking:
            names_str = ", ".join(blocking)
            raise HTTPException(
                status_code=409,
                detail=(
                    f"{names_str} (Mode B) is using the full GPU — "
                    f"stop it before starting Mode A servers."
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
            "name":       name,
            "label":      cfg["label"],
            "port":       cfg["port"],
            "mode":       cfg["mode"],
            "note":       cfg["note"],
            "vram_gb":    cfg.get("vram_gb", 0.0),
            "auto_start": cfg.get("auto_start", False),
            "alive":      alive,
            "tracked":    tracked,
            "pid":        proc.pid if tracked else None,
        })
    return result


# ── auto-start ────────────────────────────────────────────────────────────────

def _run_auto_starts() -> None:
    """Background thread: start any backend marked auto_start=True.

    Waits 5 s after server boot to let the HTTP server bind, then iterates
    over all configs with auto_start=True and calls _do_start().  Errors are
    logged but never raised — a missing bat file or VRAM conflict just skips.
    """
    import time
    time.sleep(5)
    for name, cfg in _LLAMACPP_CONFIG.items():
        if not cfg.get("auto_start"):
            continue
        if _port_alive(cfg["port"]):
            logger.info("[backends] auto-start: %s already alive on port %d — skip", name, cfg["port"])
            continue
        bat = cfg.get("bat", "")
        if not os.path.exists(bat):
            logger.warning("[backends] auto-start: %s — bat not found: %s", name, bat)
            continue
        try:
            result = _do_start(name)
            logger.info("[backends] auto-start %s → %s", name, result.get("status"))
        except Exception as exc:
            logger.warning("[backends] auto-start %s failed: %s", name, exc)


# ── watchdog ──────────────────────────────────────────────────────────────────
# The always-on stack is: dispatch(8085) + Hermes3(8087) + Hermes4(8086).
# If any of these crash the watchdog restarts them automatically.

_WATCHDOG_ALWAYS_ON = {
    "llamacpp-dispatch": 8085,
    "llamacpp-hermes3":  8087,
    "llamacpp-hermes4":  8086,
}


def _run_watchdog() -> None:
    """Background thread: restart always-on backends if they crash.

    Waits 90 s after boot (auto-starts need ~60 s to come up), then polls
    every 60 s.  Only restarts if the bat file exists — skips gracefully if
    a model hasn't been downloaded yet.
    """
    import time
    time.sleep(90)  # let auto-starts fully come up before first watchdog check

    while True:
        for name in list(_WATCHDOG_ALWAYS_ON.keys()):
            cfg = _LLAMACPP_CONFIG.get(name)
            if not cfg:
                continue
            bat = cfg.get("bat", "")
            if not os.path.exists(bat):
                continue
            if not _port_alive(cfg["port"]):
                logger.warning("[watchdog] %s (port %d) down — restarting", name, cfg["port"])
                try:
                    result = _do_start(name)
                    logger.info("[watchdog] restart %s → %s", name, result.get("status"))
                except Exception as exc:
                    logger.error("[watchdog] restart %s failed: %s", name, exc)
        time.sleep(60)


# ── router ────────────────────────────────────────────────────────────────────

def build_backends_router(ctx: ServerContext) -> APIRouter:
    # Kick off auto-starts in the background (daemon so it doesn't block shutdown)
    t = threading.Thread(target=_run_auto_starts, daemon=True, name="backends-auto-start")
    t.start()

    # Watchdog: restart always-on backends if they crash
    wt = threading.Thread(target=_run_watchdog, daemon=True, name="backends-watchdog")
    wt.start()

    router = APIRouter(prefix="/api/backends")

    @router.get("/llamacpp")
    async def list_llamacpp(_u: str = Depends(ctx.require_rate_limit)):
        """Return live probe status for all llamacpp backends."""
        return await asyncio.to_thread(_do_status_all)

    @router.get("/llamacpp/vram")
    async def vram_budget(_u: str = Depends(ctx.require_rate_limit)):
        """Return GPU VRAM budget and current allocation by running backends."""
        statuses = await asyncio.to_thread(_do_status_all)
        used = sum(s["vram_gb"] for s in statuses if s["alive"])
        return {
            "total_gb":   _GPU_VRAM_GB,
            "used_gb":    used,
            "free_gb":    max(0.0, _GPU_VRAM_GB - used),
            "pct_used":   round(used / _GPU_VRAM_GB * 100, 1) if _GPU_VRAM_GB else 0,
            "backends":   [
                {"name": s["name"], "label": s["label"], "vram_gb": s["vram_gb"], "alive": s["alive"]}
                for s in statuses
            ],
        }

    @router.post("/llamacpp/{name}/start")
    async def start_llamacpp(name: str, _u: str = Depends(ctx.require_rate_limit)):
        """Start a llamacpp server.  Enforces VRAM mode conflict rules."""
        return await asyncio.to_thread(_do_start, name)

    @router.post("/llamacpp/{name}/stop")
    async def stop_llamacpp(name: str, _u: str = Depends(ctx.require_rate_limit)):
        """Stop a llamacpp server (kills process tree + any external listener on the port)."""
        return await asyncio.to_thread(_do_stop, name)

    @router.get("/llamacpp/agents/probe")
    async def probe_tool_agents(
        agents: str = "dispatch,xlam,hermes4",
        precondition: bool = True,
        _u: str = Depends(ctx.require_rate_limit),
    ):
        """Run tool-capability probe + optional KV-cache preconditioner on the workspace agents.

        Query params:
          agents        Comma-separated subset: dispatch,xlam,hermes4  (default: all three)
          precondition  Whether to run the KV-cache warm-up pass after tests (default: true)

        Returns a per-agent report with liveness, chat, and tool_call results.
        """
        import sys as _sys
        from pathlib import Path as _Path
        _tools_dir = str(_Path(__file__).resolve().parents[3] / "tools")
        if _tools_dir not in _sys.path:
            _sys.path.insert(0, _tools_dir)

        try:
            import verify_tool_agents as _vta
        except ImportError as _ie:
            raise HTTPException(status_code=500, detail=f"verify_tool_agents not found: {_ie}")

        requested = [a.strip() for a in agents.split(",") if a.strip() in _vta._AGENTS]
        if not requested:
            raise HTTPException(status_code=400, detail="No valid agent names. Choose from: dispatch, xlam, hermes4")

        def _run_all():
            results = []
            for name in requested:
                r = _vta.run_agent(name, skip_precondition=not precondition)
                results.append(r)
            return _vta.results_to_dict(results)

        report = await asyncio.to_thread(_run_all)
        passed = sum(1 for v in report.values() if v["ok"])
        return {
            "summary": f"{passed}/{len(requested)} agents fully operational",
            "agents": report,
            "precondition_ran": precondition,
        }

    return router
