"""Codespace API — Docker sandbox lifecycle + self-triage.

Sandbox endpoints:
    GET    /api/codespace/sandbox            — list active sandboxes
    POST   /api/codespace/sandbox            — create sandbox (docker run)
    POST   /api/codespace/sandbox/{id}/exec  — exec command, SSE stream output
    DELETE /api/codespace/sandbox/{id}       — stop + remove container

Triage endpoints:
    GET    /api/codespace/triage/runs        — recent triage runs (list)
    GET    /api/codespace/triage/runs/{id}   — single run detail + full output
    POST   /api/codespace/triage/trigger     — trigger a triage run now
    GET    /api/codespace/triage/status      — watchdog status
"""
from __future__ import annotations

import asyncio
import logging
import subprocess
import sys
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from src.guppy.api.server_context import ServerContext

logger = logging.getLogger(__name__)

# ── Docker helpers ─────────────────────────────────────────────────────────────

_SANDBOX_LABEL = "guppy-sandbox"
_DEFAULT_IMAGE = "python:3.12-slim"


def _docker(*args: str, timeout: int = 30) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["docker", *args],
        capture_output=True,
        text=True,
        timeout=timeout,
    )


def _docker_available() -> bool:
    try:
        r = _docker("info", timeout=5)
        return r.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def _list_sandboxes() -> list[dict[str, Any]]:
    r = _docker(
        "ps", "--filter", f"label={_SANDBOX_LABEL}=1",
        "--format",
        "{{.ID}}\t{{.Names}}\t{{.Image}}\t{{.Status}}\t{{.CreatedAt}}",
    )
    if r.returncode != 0:
        return []
    sandboxes = []
    for line in r.stdout.strip().splitlines():
        if not line.strip():
            continue
        parts = line.split("\t")
        if len(parts) >= 5:
            sandboxes.append({
                "id":         parts[0],
                "name":       parts[1],
                "image":      parts[2],
                "status":     parts[3],
                "created_at": parts[4],
            })
    return sandboxes


def _create_sandbox(name: str, image: str) -> dict[str, Any]:
    r = _docker(
        "run", "-d",
        "--name", name,
        "--label", f"{_SANDBOX_LABEL}=1",
        "--memory", "512m",
        "--cpus", "1.0",
        "--network", "none",   # no outbound network by default (security)
        image,
        "sleep", "infinity",
        timeout=60,
    )
    if r.returncode != 0:
        raise RuntimeError(r.stderr.strip() or "docker run failed")
    container_id = r.stdout.strip()
    return {"id": container_id, "name": name, "image": image, "status": "running"}


async def _exec_stream(container_id: str, command: str):
    """Async generator that streams docker exec output line by line (SSE)."""
    try:
        proc = await asyncio.create_subprocess_exec(
            "docker", "exec", container_id,
            "sh", "-c", command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
    except FileNotFoundError:
        yield "data: [docker not found]\n\n"
        return

    if proc.stdout is None:
        yield "data: [no output stream]\n\n"
        return

    try:
        async for line in proc.stdout:
            text = line.decode(errors="replace").rstrip("\n")
            yield f"data: {text}\n\n"
        await proc.wait()
        yield f"event: done\ndata: exit:{proc.returncode}\n\n"
    except asyncio.CancelledError:
        proc.kill()
        raise


# ── Pydantic models ────────────────────────────────────────────────────────────

class SandboxCreate(BaseModel):
    name:  str = ""
    image: str = _DEFAULT_IMAGE


class ExecRequest(BaseModel):
    command: str


# ── Router ─────────────────────────────────────────────────────────────────────

def build_codespace_router(ctx: ServerContext) -> APIRouter:
    router = APIRouter(prefix="/api/codespace", tags=["codespace"])

    # ── Sandbox ────────────────────────────────────────────────────────────────

    @router.get("/sandbox")
    def list_sandboxes(_uid: str = Depends(ctx.require_rate_limit)):
        if not _docker_available():
            return {"sandboxes": [], "docker_available": False}
        return {"sandboxes": _list_sandboxes(), "docker_available": True}

    @router.post("/sandbox")
    def create_sandbox(body: SandboxCreate, _uid: str = Depends(ctx.require_rate_limit)):
        if not _docker_available():
            raise HTTPException(503, "Docker is not available on this host")
        import uuid as _uuid
        name = body.name.strip() or f"guppy-sandbox-{_uuid.uuid4().hex[:8]}"
        try:
            result = _create_sandbox(name, body.image)
            return {"ok": True, **result}
        except RuntimeError as e:
            raise HTTPException(400, str(e))
        except subprocess.TimeoutExpired:
            raise HTTPException(504, "docker run timed out")

    @router.post("/sandbox/{container_id}/exec")
    async def exec_in_sandbox(
        container_id: str,
        body: ExecRequest,
        _uid: str = Depends(ctx.require_rate_limit),
    ):
        if not _docker_available():
            raise HTTPException(503, "Docker is not available")
        if not body.command.strip():
            raise HTTPException(400, "command is required")

        return StreamingResponse(
            _exec_stream(container_id, body.command),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",
            },
        )

    @router.delete("/sandbox/{container_id}")
    def delete_sandbox(container_id: str, _uid: str = Depends(ctx.require_rate_limit)):
        if not _docker_available():
            raise HTTPException(503, "Docker is not available")
        r = _docker("rm", "-f", container_id)
        if r.returncode != 0 and "No such container" not in r.stderr:
            raise HTTPException(400, r.stderr.strip() or "docker rm failed")
        return {"ok": True, "removed": container_id}

    # ── Triage ─────────────────────────────────────────────────────────────────

    @router.get("/triage/runs")
    def list_triage_runs(
        limit: int = 20,
        _uid: str = Depends(ctx.require_rate_limit),
    ):
        from src.guppy.codespace.codespace_triage import get_runs
        return get_runs(limit=min(limit, 100))

    @router.get("/triage/runs/{run_id}")
    def get_triage_run(run_id: str, _uid: str = Depends(ctx.require_rate_limit)):
        from src.guppy.codespace.codespace_triage import get_runs, get_run_output
        runs = get_runs(limit=200)
        match = next((r for r in runs if r["id"] == run_id), None)
        if not match:
            raise HTTPException(404, "Run not found")
        match["output"] = get_run_output(run_id) or ""
        return match

    @router.post("/triage/trigger")
    def trigger_triage(_uid: str = Depends(ctx.require_rate_limit)):
        from src.guppy.codespace.codespace_triage import trigger_triage_async
        run_id = trigger_triage_async(trigger="manual")
        return {"ok": True, "run_id": run_id}

    @router.get("/triage/status")
    def triage_status(_uid: str = Depends(ctx.require_rate_limit)):
        from src.guppy.codespace.codespace_triage import (
            _watchdog_thread, _watchdog_stop, get_runs,
        )
        recent = get_runs(limit=1)
        return {
            "watchdog_running": bool(_watchdog_thread and _watchdog_thread.is_alive()),
            "last_run": recent[0] if recent else None,
        }

    return router
