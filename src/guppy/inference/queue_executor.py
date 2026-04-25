"""Queue executor for persistent inference job processing with retry logic.

Manages dequeuing, execution, retry scheduling, and result persistence for
inference requests stored in the inference_queue table.

Core responsibilities:
    - Dequeue jobs by status and priority
    - Execute via ProviderRegistry with automatic fallback
    - Retry failed jobs with exponential backoff
    - Persist attempt history and metrics
    - Coordinate with queue scheduler for retry timing
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from datetime import datetime, timedelta
from typing import Any, Dict, Optional, Tuple

from sqlalchemy import (
    select,
    update,
    insert,
    and_,
    desc,
)
from sqlalchemy.orm import AsyncSession

from .provider_registry import ProviderRegistry, get_provider_registry
from .provider_client import InferenceMetadata

logger = logging.getLogger(__name__)


class QueueExecutor:
    """Executor for persistent inference queue jobs.

    Dequeues jobs in priority order, executes via ProviderRegistry with
    fallback chain, and manages retry scheduling with exponential backoff.

    Usage:
        executor = QueueExecutor(db_session, registry)
        job_id = await executor.enqueue(
            prompt="...",
            system_prompt="...",
            task_type="complex",
        )
        # Later: in background worker
        success = await executor.process_next_job()
    """

    def __init__(self, db_session: AsyncSession, registry: Optional[ProviderRegistry] = None):
        """Initialize queue executor.

        Args:
            db_session: SQLAlchemy async session for database operations
            registry: ProviderRegistry instance; defaults to global singleton
        """
        self.db = db_session
        self.registry = registry or get_provider_registry()

    async def process_next_job(self) -> bool:
        """Dequeue and process the next available job.

        Jobs are selected by:
            1. status = 'queued'
            2. Ordered by priority ASC (0=highest), then created_at ASC
            3. First match

        Returns:
            True if job was processed (success or final failure), False if no job available
        """
        # Import here to avoid circular imports
        from .._db_models import InferenceQueue, InferenceQueueAttempt

        # Dequeue next job
        job = await self._dequeue_next_job()
        if not job:
            return False

        logger.info(f"[EXECUTOR] Processing job {job.id} (task_type={job.task_type})")

        # Track execution start
        job.status = "executing"
        job.last_attempt_at = datetime.utcnow()
        await self.db.commit()

        try:
            # Execute inference via registry with fallback
            response, metadata = await self.registry.infer_with_fallback(
                prompt=job.prompt,
                system_prompt=job.system_prompt or "",
                task_type=job.task_type,
                preferred_model=job.preferred_provider,
            )

            # Success: record result and mark complete
            job.status = "success"
            job.response = response
            job.provider_used = metadata.provider
            job.execution_ms = metadata.latency_ms
            job.cost_usd = metadata.cost if metadata.cost else 0.0
            job.completed_at = datetime.utcnow()

            # Record attempt
            await self._record_attempt(
                job_id=job.id,
                attempt_number=job.retry_count + 1,
                provider=metadata.provider,
                model=metadata.model,
                success=True,
                latency_ms=metadata.latency_ms,
                cost_usd=metadata.cost if metadata.cost else 0.0,
                prompt_tokens=metadata.prompt_tokens,
                completion_tokens=metadata.completion_tokens,
                error=None,
            )

            await self.db.commit()
            logger.info(
                f"[EXECUTOR] Job {job.id} succeeded via {metadata.provider} "
                f"({metadata.latency_ms:.0f}ms, ${metadata.cost:.4f})"
            )
            return True

        except Exception as e:
            logger.error(f"[EXECUTOR] Job {job.id} failed: {e}")
            job.error_message = str(e)

            # Record failed attempt
            await self._record_attempt(
                job_id=job.id,
                attempt_number=job.retry_count + 1,
                provider=self.registry.build_fallback_chain(job.task_type)[0] if self.registry.build_fallback_chain(job.task_type) else "unknown",
                model=None,
                success=False,
                latency_ms=None,
                cost_usd=0.0,
                prompt_tokens=None,
                completion_tokens=None,
                error=str(e),
            )

            # Check if we should retry
            if job.retry_count < job.max_retries:
                # Schedule next retry with exponential backoff
                job.retry_count += 1
                backoff_seconds = 2 ** job.retry_count * job.backoff_multiplier
                job.next_retry_at = job.last_attempt_at + timedelta(seconds=backoff_seconds)
                job.status = "queued"  # Return to queue

                await self.db.commit()
                logger.info(
                    f"[EXECUTOR] Job {job.id} scheduled for retry #{job.retry_count} "
                    f"at {job.next_retry_at.isoformat()} (+{backoff_seconds:.0f}s backoff)"
                )
                return True
            else:
                # Max retries exceeded: final failure
                job.status = "failed"
                job.completed_at = datetime.utcnow()
                await self.db.commit()
                logger.error(f"[EXECUTOR] Job {job.id} failed after {job.max_retries} retries")
                return True

    async def enqueue(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        task_type: str = "simple",
        preferred_provider: Optional[str] = None,
        max_retries: int = 3,
        backoff_multiplier: float = 2.0,
        priority: int = 100,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Enqueue an inference request to the persistent queue.

        Args:
            prompt: User message / inference request
            system_prompt: System context
            task_type: Classification (simple, complex, teaching, code, vault)
            preferred_provider: Optional provider override
            max_retries: Maximum retry attempts
            backoff_multiplier: Exponential backoff multiplier
            priority: Priority level (0=highest, 255=lowest); default 100
            user_id: User who submitted request
            session_id: Chat session ID for correlation
            metadata: Custom JSON metadata

        Returns:
            job_id: UUID string for job tracking
        """
        # Import here to avoid circular imports
        from .._db_models import InferenceQueue
        import uuid

        job_id = str(uuid.uuid4())
        now = datetime.utcnow()

        job = InferenceQueue(
            id=job_id,
            status="queued",
            priority=priority,
            prompt=prompt,
            system_prompt=system_prompt,
            task_type=task_type,
            preferred_provider=preferred_provider,
            max_retries=max_retries,
            retry_count=0,
            backoff_multiplier=backoff_multiplier,
            last_attempt_at=None,
            next_retry_at=None,
            response=None,
            provider_used=None,
            error_message=None,
            execution_ms=None,
            cost_usd=0.0,
            user_id=user_id,
            session_id=session_id,
            metadata=json.dumps(metadata or {}),
            created_at=now,
            completed_at=None,
        )

        self.db.add(job)
        await self.db.commit()

        logger.info(
            f"[EXECUTOR] Enqueued job {job_id} (task_type={task_type}, "
            f"priority={priority}, user={user_id})"
        )
        return job_id

    async def get_job_status(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Get current status of a queued job.

        Returns:
            {
                "job_id": "...",
                "status": "queued|executing|success|failed|timeout",
                "response": "...",  # if success
                "error": "...",  # if failed
                "provider_used": "...",
                "latency_ms": 245.5,
                "cost_usd": 0.0125,
                "retry_count": 0,
                "next_retry_at": "2026-04-25T10:35:00Z",  # if scheduled
                "created_at": "2026-04-25T10:30:00Z",
                "completed_at": "2026-04-25T10:30:05Z",  # if complete
            }
        """
        # Import here to avoid circular imports
        from .._db_models import InferenceQueue

        stmt = select(InferenceQueue).where(InferenceQueue.id == job_id)
        result = await self.db.execute(stmt)
        job = result.scalars().first()

        if not job:
            return None

        return {
            "job_id": job.id,
            "status": job.status,
            "response": job.response,
            "error": job.error_message,
            "provider_used": job.provider_used,
            "latency_ms": job.execution_ms,
            "cost_usd": job.cost_usd,
            "retry_count": job.retry_count,
            "next_retry_at": job.next_retry_at.isoformat() if job.next_retry_at else None,
            "created_at": job.created_at.isoformat(),
            "completed_at": job.completed_at.isoformat() if job.completed_at else None,
            "task_type": job.task_type,
            "user_id": job.user_id,
            "session_id": job.session_id,
        }

    async def get_attempt_history(self, job_id: str) -> list[Dict[str, Any]]:
        """Get retry attempt history for a job.

        Returns list of attempts in chronological order, including:
            - attempt_number, provider, model
            - started_at, completed_at, latency_ms
            - success (1/0), error
            - cost_usd, prompt_tokens, completion_tokens
        """
        # Import here to avoid circular imports
        from .._db_models import InferenceQueueAttempt

        stmt = (
            select(InferenceQueueAttempt)
            .where(InferenceQueueAttempt.job_id == job_id)
            .order_by(InferenceQueueAttempt.attempt_number)
        )
        result = await self.db.execute(stmt)
        attempts = result.scalars().all()

        return [
            {
                "attempt_number": a.attempt_number,
                "provider": a.provider,
                "model": a.model,
                "started_at": a.started_at.isoformat(),
                "completed_at": a.completed_at.isoformat() if a.completed_at else None,
                "latency_ms": a.latency_ms,
                "success": bool(a.success),
                "error": a.error,
                "cost_usd": a.cost_usd,
                "prompt_tokens": a.prompt_tokens,
                "completion_tokens": a.completion_tokens,
            }
            for a in attempts
        ]

    async def _dequeue_next_job(self) -> Optional[Any]:
        """Internal: Dequeue the next job by priority and creation order.

        Returns InferenceQueue object or None if no queued jobs available.
        """
        # Import here to avoid circular imports
        from .._db_models import InferenceQueue

        stmt = (
            select(InferenceQueue)
            .where(InferenceQueue.status == "queued")
            .order_by(InferenceQueue.priority, InferenceQueue.created_at)
            .limit(1)
        )
        result = await self.db.execute(stmt)
        return result.scalars().first()

    async def _record_attempt(
        self,
        job_id: str,
        attempt_number: int,
        provider: str,
        model: Optional[str],
        success: bool,
        latency_ms: Optional[float],
        cost_usd: float,
        prompt_tokens: Optional[int],
        completion_tokens: Optional[int],
        error: Optional[str],
    ) -> None:
        """Internal: Record an attempt to the inference_queue_attempts table."""
        # Import here to avoid circular imports
        from .._db_models import InferenceQueueAttempt

        attempt = InferenceQueueAttempt(
            job_id=job_id,
            attempt_number=attempt_number,
            provider=provider,
            model=model,
            started_at=datetime.utcnow(),
            completed_at=datetime.utcnow(),
            latency_ms=latency_ms,
            success=1 if success else 0,
            error=error,
            cost_usd=cost_usd,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
        )

        self.db.add(attempt)
        await self.db.commit()
