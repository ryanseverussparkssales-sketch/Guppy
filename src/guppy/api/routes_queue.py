"""Queue management API routes for persistent inference job tracking.

Endpoints for:
    - POST /api/queue/enqueue - Enqueue inference request to persistent queue
    - GET /api/queue/job/{job_id} - Poll job status and results
    - GET /api/queue/job/{job_id}/history - Get retry attempt history
    - GET /api/queue/status - Get overall queue health metrics
    - GET /api/queue/metrics - Get queue performance metrics

These routes integrate with QueueExecutor and QueueScheduler for durable,
retryable inference with exponential backoff.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException, Depends

from src.guppy.api.server_context import ServerContext
from src.guppy.inference.queue_executor import QueueExecutor
from src.guppy.inference.queue_scheduler import QueueScheduler
from src.guppy.inference.provider_registry import get_provider_registry

logger = logging.getLogger(__name__)


def build_queue_router(ctx: ServerContext) -> APIRouter:
    """Build queue management API router.

    Args:
        ctx: Server context with database and auth

    Returns:
        APIRouter with queue endpoints
    """
    router = APIRouter(prefix="/api/queue")

    @router.post("/enqueue")
    async def enqueue_inference(
        request: Dict[str, Any],
        _user_id: str = Depends(ctx.require_rate_limit),
    ) -> Dict[str, Any]:
        """Enqueue an inference request to the persistent queue.

        Request body:
            {
                "prompt": "...",
                "system_prompt": "...",  # optional
                "task_type": "simple|complex|teaching|code|vault",  # optional, default "simple"
                "preferred_provider": "local|anthropic|openai|...",  # optional
                "max_retries": 3,  # optional
                "priority": 100,  # optional, 0=highest, 255=lowest
            }

        Returns:
            {
                "job_id": "...",
                "status": "queued",
                "message": "Inference request enqueued",
                "poll_url": "/api/queue/job/{job_id}",
            }
        """
        try:
            # Validate required fields
            prompt = request.get("prompt")
            if not prompt:
                raise HTTPException(status_code=400, detail="prompt is required")

            system_prompt = request.get("system_prompt")
            task_type = request.get("task_type", "simple")
            preferred_provider = request.get("preferred_provider")
            max_retries = request.get("max_retries", 3)
            priority = request.get("priority", 100)

            # Create executor and enqueue
            executor = QueueExecutor(ctx.db, get_provider_registry())
            job_id = await executor.enqueue(
                prompt=prompt,
                system_prompt=system_prompt,
                task_type=task_type,
                preferred_provider=preferred_provider,
                max_retries=max_retries,
                priority=priority,
                user_id=_user_id,
                session_id=request.get("session_id"),
                metadata=request.get("metadata"),
            )

            logger.info(f"[ROUTES] Enqueued job {job_id} for user {_user_id}")

            return {
                "job_id": job_id,
                "status": "queued",
                "message": "Inference request enqueued",
                "poll_url": f"/api/queue/job/{job_id}",
            }

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"[ROUTES] Failed to enqueue: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    @router.get("/job/{job_id}")
    async def get_job_status(
        job_id: str,
        _user_id: str = Depends(ctx.require_rate_limit),
    ) -> Dict[str, Any]:
        """Poll the status of a queued inference job.

        Returns:
            {
                "job_id": "...",
                "status": "queued|executing|success|failed|timeout",
                "response": "...",  # if status=success
                "error": "...",  # if status=failed
                "provider_used": "anthropic",
                "latency_ms": 245.5,
                "cost_usd": 0.0125,
                "retry_count": 0,
                "next_retry_at": "2026-04-25T10:35:00Z",  # if queued for retry
                "created_at": "2026-04-25T10:30:00Z",
                "completed_at": "2026-04-25T10:30:05Z",  # if complete
                "task_type": "complex",
                "user_id": "...",
                "session_id": "...",
            }
        """
        try:
            executor = QueueExecutor(ctx.db, get_provider_registry())
            status = await executor.get_job_status(job_id)

            if not status:
                raise HTTPException(status_code=404, detail=f"Job {job_id} not found")

            return status

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"[ROUTES] Failed to get job status: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    @router.get("/job/{job_id}/history")
    async def get_job_history(
        job_id: str,
        _user_id: str = Depends(ctx.require_rate_limit),
    ) -> Dict[str, Any]:
        """Get retry attempt history for a job.

        Returns:
            {
                "job_id": "...",
                "attempts": [
                    {
                        "attempt_number": 1,
                        "provider": "local",
                        "model": "guppy-fast",
                        "started_at": "2026-04-25T10:30:00Z",
                        "completed_at": "2026-04-25T10:30:05Z",
                        "latency_ms": 5000,
                        "success": false,
                        "error": "timeout",
                        "cost_usd": 0.0,
                    },
                    {
                        "attempt_number": 2,
                        "provider": "anthropic",
                        "model": "claude-opus-4-6",
                        "started_at": "2026-04-25T10:30:10Z",
                        "completed_at": "2026-04-25T10:30:15Z",
                        "latency_ms": 5000,
                        "success": true,
                        "error": null,
                        "cost_usd": 0.0125,
                    },
                ]
            }
        """
        try:
            executor = QueueExecutor(ctx.db, get_provider_registry())

            # Verify job exists
            status = await executor.get_job_status(job_id)
            if not status:
                raise HTTPException(status_code=404, detail=f"Job {job_id} not found")

            # Get attempts
            attempts = await executor.get_attempt_history(job_id)

            return {
                "job_id": job_id,
                "attempts": attempts,
            }

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"[ROUTES] Failed to get job history: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    _EMPTY_METRICS: Dict[str, Any] = {
        "total_jobs": 0,
        "queued_count": 0,
        "executing_count": 0,
        "success_count": 0,
        "failed_count": 0,
        "timeout_count": 0,
        "avg_latency_ms": 0.0,
        "total_cost_usd": 0.0,
        "oldest_queued_age_seconds": 0,
    }

    @router.get("/status")
    async def get_queue_status(
        _user_id: str = Depends(ctx.require_rate_limit),
    ) -> Dict[str, Any]:
        # QueueScheduler requires an async SQLAlchemy session; ctx.db is the
        # plain settings SQLite wrapper, so the query will fail until a proper
        # async session is wired in.  Return a graceful empty response so the
        # frontend doesn't spam 500-triggered retries.
        try:
            scheduler = QueueScheduler(ctx.db, get_provider_registry())
            metrics = await scheduler.get_queue_metrics()
            if metrics["queued_count"] > 20 or metrics["oldest_queued_age_seconds"] > 600:
                health_status = "degraded"
            elif metrics["queued_count"] > 50:
                health_status = "overloaded"
            else:
                health_status = "healthy"
            return {"status": health_status, "metrics": metrics}
        except Exception as e:
            logger.debug(f"[ROUTES] Queue status unavailable (DB not ready): {e}")
            return {"status": "healthy", "metrics": _EMPTY_METRICS}

    @router.get("/metrics")
    async def get_queue_metrics(
        _user_id: str = Depends(ctx.require_rate_limit),
    ) -> Dict[str, Any]:
        try:
            scheduler = QueueScheduler(ctx.db, get_provider_registry())
            metrics = await scheduler.get_queue_metrics()
            total = metrics["total_jobs"]
            return {
                **metrics,
                "success_rate": metrics["success_count"] / total if total > 0 else 0.0,
                "retry_rate": (metrics["timeout_count"] + metrics["failed_count"]) / total if total > 0 else 0.0,
            }
        except Exception as e:
            logger.debug(f"[ROUTES] Queue metrics unavailable (DB not ready): {e}")
            return {**_EMPTY_METRICS, "success_rate": 0.0, "retry_rate": 0.0}

    return router
