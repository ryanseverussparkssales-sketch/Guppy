"""Model management API: list, pull, delete local models via Ollama.

GET  /api/models              — list installed models + backend status
GET  /api/models/backends     — probe all backends, show which are alive
POST /api/models/pull         — start an Ollama pull job (returns job_id)
GET  /api/models/pull/{job_id}— poll pull progress
DELETE /api/models/{name}     — delete an Ollama model
"""
from __future__ import annotations

import json
import threading
import urllib.error
import urllib.request
import uuid
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from src.guppy.api.server_context import ServerContext
from src.guppy.inference.local_client import (
    active_backend,
    list_local_models,
    probe_backends,
)


class PullRequest(BaseModel):
    name: str


_pull_jobs: Dict[str, Dict[str, Any]] = {}
_pull_lock = threading.Lock()


def _ollama_base() -> str:
    import os
    return (os.environ.get("GUPPY_OLLAMA_BASE_URL", "http://127.0.0.1:11434") or "http://127.0.0.1:11434").rstrip("/")


def build_models_router(ctx: ServerContext) -> APIRouter:
    router = APIRouter(prefix="/api/models")

    @router.get("")
    async def list_models(user_id: str = Depends(ctx.require_rate_limit)):
        del user_id
        backend = active_backend()
        models = list_local_models(backend)
        return {
            "backend": backend,
            "models": models,
            "count": len(models),
        }

    @router.get("/backends")
    async def backend_status(user_id: str = Depends(ctx.require_rate_limit)):
        del user_id
        liveness = probe_backends(timeout=2.0)
        detected = active_backend()
        return {
            "active": detected,
            "backends": {
                name: {
                    "alive": alive,
                    "models": list_local_models(name, timeout=2.0) if alive else [],
                }
                for name, alive in liveness.items()
            },
        }

    @router.post("/pull")
    async def pull_model(body: PullRequest, user_id: str = Depends(ctx.require_rate_limit)):
        del user_id
        name = body.name.strip()
        if not name:
            raise HTTPException(status_code=400, detail="model name required")

        job_id = uuid.uuid4().hex[:8]
        with _pull_lock:
            _pull_jobs[job_id] = {
                "job_id": job_id,
                "name": name,
                "status": "queued",
                "progress": 0,
                "detail": "",
                "done": False,
                "error": None,
            }

        def _run() -> None:
            try:
                payload = json.dumps({"name": name, "stream": True}).encode()
                req = urllib.request.Request(
                    f"{_ollama_base()}/api/pull",
                    data=payload,
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                with urllib.request.urlopen(req, timeout=3600) as r:
                    for raw_line in r:
                        line = raw_line.strip()
                        if not line:
                            continue
                        try:
                            evt = json.loads(line)
                        except Exception:
                            continue
                        status = evt.get("status", "")
                        completed = int(evt.get("completed") or 0)
                        total = int(evt.get("total") or 0)
                        pct = int(completed / total * 100) if total > 0 else 0
                        with _pull_lock:
                            _pull_jobs[job_id].update({
                                "status": status,
                                "progress": pct,
                                "detail": f"{completed}/{total}" if total else status,
                            })
                with _pull_lock:
                    _pull_jobs[job_id].update({"status": "done", "progress": 100, "done": True})
            except Exception as exc:
                with _pull_lock:
                    _pull_jobs[job_id].update({"status": "error", "done": True, "error": str(exc)})

        threading.Thread(target=_run, daemon=True).start()
        return {"job_id": job_id, "name": name, "status": "queued"}

    @router.get("/pull/{job_id}")
    async def pull_status(job_id: str, user_id: str = Depends(ctx.require_rate_limit)):
        del user_id
        with _pull_lock:
            job = _pull_jobs.get(job_id)
        if not job:
            raise HTTPException(status_code=404, detail="pull job not found")
        return job

    @router.delete("/{name:path}")
    async def delete_model(name: str, user_id: str = Depends(ctx.require_rate_limit)):
        del user_id
        name = name.strip()
        if not name:
            raise HTTPException(status_code=400, detail="model name required")
        try:
            payload = json.dumps({"name": name}).encode()
            req = urllib.request.Request(
                f"{_ollama_base()}/api/delete",
                data=payload,
                headers={"Content-Type": "application/json"},
                method="DELETE",
            )
            with urllib.request.urlopen(req, timeout=10.0) as r:
                r.read()
            return {"deleted": name}
        except urllib.error.HTTPError as e:
            if e.code == 404:
                raise HTTPException(status_code=404, detail=f"model not found: {name}")
            raise HTTPException(status_code=502, detail=f"Ollama error: {e}")
        except Exception as e:
            raise HTTPException(status_code=503, detail=f"Ollama unreachable: {e}")

    return router
