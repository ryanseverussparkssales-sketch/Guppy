"""Model management API for local llama.cpp/OpenAI-compatible runtimes."""
from __future__ import annotations

import threading
import uuid
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from src.guppy.api.server_context import ServerContext
from src.guppy.inference.local_client import active_backend, list_local_models, probe_backends


class PullRequest(BaseModel):
    name: str


_pull_jobs: Dict[str, Dict[str, Any]] = {}
_pull_lock = threading.Lock()


def build_models_router(ctx: ServerContext) -> APIRouter:
    router = APIRouter(prefix="/api/models")

    @router.get("")
    async def list_models(_user_id: str = Depends(ctx.require_rate_limit)):
        backend = active_backend()
        models = list_local_models(backend)
        return {
            "backend": backend,
            "models": models,
            "count": len(models),
        }

    @router.get("/backends")
    async def backend_status(_user_id: str = Depends(ctx.require_rate_limit)):
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

    @router.post("/download")
    @router.post("/pull")
    async def pull_model(body: PullRequest, _user_id: str = Depends(ctx.require_rate_limit)):
        name = body.name.strip()
        if not name:
            raise HTTPException(status_code=400, detail="model name required")

        job_id = uuid.uuid4().hex[:8]
        with _pull_lock:
            _pull_jobs[job_id] = {
                "job_id": job_id,
                "name": name,
                "status": "unsupported",
                "progress": 0,
                "detail": "llama.cpp models are managed by the local server process, not pulled through the API",
                "done": True,
                "error": "unsupported",
            }
        raise HTTPException(
            status_code=501,
            detail="Model download is not supported for llama.cpp runtimes; start the desired local server instead.",
        )

    @router.get("/pull/{job_id}")
    async def pull_status(job_id: str, _user_id: str = Depends(ctx.require_rate_limit)):
        with _pull_lock:
            job = _pull_jobs.get(job_id)
        if not job:
            raise HTTPException(status_code=404, detail="pull job not found")
        return job

    @router.delete("/{name:path}")
    async def delete_model(name: str, _user_id: str = Depends(ctx.require_rate_limit)):
        if not name.strip():
            raise HTTPException(status_code=400, detail="model name required")
        raise HTTPException(
            status_code=501,
            detail="Model deletion is not supported for llama.cpp runtimes; manage model files outside the API.",
        )

    return router
