"""Background scheduler for inference queue retry management and processing.

Runs as a background task that:
    - Periodically checks for jobs ready to retry (next_retry_at <= now)
    - Transitions timed-out jobs back to queued status if retries available
    - Coordinates with QueueExecutor for job processing
    - Logs metrics and monitors queue health

Designed for both long-running daemon and periodic batch processing modes.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy import select, update, and_
from sqlalchemy.ext.asyncio import AsyncSession

from .queue_executor import QueueExecutor
from .provider_registry import ProviderRegistry, get_provider_registry

logger = logging.getLogger(__name__)


class QueueScheduler:
    """Background scheduler for inference queue retry management.

    Monitors the inference_queue table and:
    1. Processes jobs with status='queued' via QueueExecutor
    2. Reschedules 'timeout' jobs for retry if retries available
    3. Cleans up stuck/abandoned jobs
    4. Reports queue health metrics

    Usage:
        scheduler = QueueScheduler(db_session, registry)
        # Run as daemon
        await scheduler.start()

        # Or run once per batch
        metrics = await scheduler.process_ready_jobs(limit=10)
    """

    def __init__(
        self,
        db_session: AsyncSession,
        registry: Optional[ProviderRegistry] = None,
        poll_interval_seconds: float = 5.0,
    ):
        """Initialize queue scheduler.

        Args:
            db_session: SQLAlchemy async session for database operations
            registry: ProviderRegistry instance; defaults to global singleton
            poll_interval_seconds: Time between retry checks (default 5s)
        """
        self.db = db_session
        self.registry = registry or get_provider_registry()
        self.poll_interval_seconds = poll_interval_seconds
        self.executor = QueueExecutor(db_session, registry)
        self._running = False

    async def start(self) -> None:
        """Start the scheduler as a long-running background task.

        Continuously monitors queue and processes jobs until stopped.
        Safe to call multiple times (idempotent).
        """
        if self._running:
            logger.warning("[SCHEDULER] Already running, ignoring start() call")
            return

        self._running = True
        logger.info(
            f"[SCHEDULER] Started (poll_interval={self.poll_interval_seconds}s)"
        )

        try:
            while self._running:
                try:
                    # Process one job
                    processed = await self.executor.process_next_job()

                    if not processed:
                        # No job available, sleep before next poll
                        await asyncio.sleep(self.poll_interval_seconds)
                    # If job was processed, loop immediately for next one

                except Exception as e:
                    logger.error(f"[SCHEDULER] Error during processing: {e}", exc_info=True)
                    await asyncio.sleep(self.poll_interval_seconds)

        except asyncio.CancelledError:
            logger.info("[SCHEDULER] Cancelled (graceful shutdown)")
            self._running = False
        except Exception as e:
            logger.error(f"[SCHEDULER] Fatal error: {e}", exc_info=True)
            self._running = False

    async def stop(self) -> None:
        """Stop the scheduler gracefully.

        Sets flag to exit main loop; scheduler finishes current job before stopping.
        """
        logger.info("[SCHEDULER] Stop requested")
        self._running = False

    async def process_ready_jobs(self, limit: int = 10) -> dict:
        """Process one batch of ready jobs (non-blocking mode).

        Called by periodic background task (e.g., every 30 seconds) to process
        queued jobs in bulk without long-running daemon.

        Args:
            limit: Maximum jobs to process in this batch

        Returns:
            {
                "processed": 5,
                "succeeded": 3,
                "failed": 2,
                "queued_remaining": 12,
                "executing": 1,
            }
        """
        logger.info(f"[SCHEDULER] Processing batch (limit={limit})")

        processed = 0
        succeeded = 0
        failed = 0

        for _ in range(limit):
            try:
                job_processed = await self.executor.process_next_job()
                if not job_processed:
                    break  # No more jobs available

                processed += 1

                # Fetch job status to determine outcome
                # (would need to track this in executor for better efficiency)

            except Exception as e:
                logger.error(f"[SCHEDULER] Error processing job: {e}")
                failed += 1

        # Get queue health metrics
        metrics = await self.get_queue_metrics()

        return {
            "processed": processed,
            "queued_remaining": metrics["queued_count"],
            "executing": metrics["executing_count"],
            "succeeded_total": metrics["success_count"],
            "failed_total": metrics["failed_count"],
            "average_latency_ms": metrics["avg_latency_ms"],
        }

    async def reschedule_timeout_jobs(self) -> int:
        """Transition timed-out jobs back to queued for retry.

        Finds jobs with status='timeout' and retry_count < max_retries,
        calculates next_retry_at with exponential backoff, and returns to queue.

        Returns:
            Number of jobs rescheduled
        """
        # Import here to avoid circular imports
        from .._db_models import InferenceQueue

        stmt = select(InferenceQueue).where(
            and_(
                InferenceQueue.status == "timeout",
                InferenceQueue.retry_count < InferenceQueue.max_retries,
            )
        )
        result = await self.db.execute(stmt)
        timeout_jobs = result.scalars().all()

        rescheduled = 0

        for job in timeout_jobs:
            job.retry_count += 1
            backoff_seconds = 2 ** job.retry_count * job.backoff_multiplier
            job.next_retry_at = datetime.utcnow() + timedelta(seconds=backoff_seconds)
            job.status = "queued"

            logger.info(
                f"[SCHEDULER] Rescheduled timeout job {job.id} "
                f"(retry #{job.retry_count}, backoff={backoff_seconds}s)"
            )
            rescheduled += 1

        if rescheduled > 0:
            await self.db.commit()

        return rescheduled

    async def get_queue_metrics(self) -> dict:
        """Get queue health metrics.

        Returns:
            {
                "total_jobs": 42,
                "queued_count": 5,
                "executing_count": 1,
                "success_count": 30,
                "failed_count": 3,
                "timeout_count": 2,
                "avg_latency_ms": 245.5,
                "total_cost_usd": 0.125,
                "oldest_queued_age_seconds": 300,
            }
        """
        # Import here to avoid circular imports
        from .._db_models import InferenceQueue

        # Total counts by status
        for status in ["queued", "executing", "success", "failed", "timeout"]:
            stmt = select(InferenceQueue).where(InferenceQueue.status == status)
            result = await self.db.execute(stmt)
            count = len(result.scalars().all())

            if status == "queued":
                queued_count = count
            elif status == "executing":
                executing_count = count
            elif status == "success":
                success_count = count
            elif status == "failed":
                failed_count = count
            elif status == "timeout":
                timeout_count = count

        # Average latency (success only)
        stmt = select(InferenceQueue).where(InferenceQueue.status == "success")
        result = await self.db.execute(stmt)
        success_jobs = result.scalars().all()

        avg_latency = (
            sum(j.execution_ms for j in success_jobs if j.execution_ms) / len(success_jobs)
            if success_jobs
            else 0.0
        )

        # Total cost
        stmt = select(InferenceQueue)
        result = await self.db.execute(stmt)
        all_jobs = result.scalars().all()
        total_cost = sum(j.cost_usd or 0.0 for j in all_jobs)

        # Oldest queued job age
        stmt = select(InferenceQueue).where(InferenceQueue.status == "queued")
        result = await self.db.execute(stmt)
        queued_jobs = result.scalars().all()

        if queued_jobs:
            oldest = min(j.created_at for j in queued_jobs)
            oldest_age = (datetime.utcnow() - oldest).total_seconds()
        else:
            oldest_age = 0

        return {
            "total_jobs": len(all_jobs),
            "queued_count": queued_count,
            "executing_count": executing_count,
            "success_count": success_count,
            "failed_count": failed_count,
            "timeout_count": timeout_count,
            "avg_latency_ms": avg_latency,
            "total_cost_usd": total_cost,
            "oldest_queued_age_seconds": oldest_age,
        }

    async def cleanup_stuck_jobs(self, max_age_seconds: int = 3600) -> int:
        """Clean up abandoned jobs (executing but no recent updates).

        Finds jobs with status='executing' and last_attempt_at older than max_age_seconds,
        marks them as 'timeout', and attempts retry.

        Args:
            max_age_seconds: Jobs older than this are considered stuck (default 1 hour)

        Returns:
            Number of jobs cleaned up
        """
        # Import here to avoid circular imports
        from .._db_models import InferenceQueue

        cutoff_time = datetime.utcnow() - timedelta(seconds=max_age_seconds)

        stmt = select(InferenceQueue).where(
            and_(
                InferenceQueue.status == "executing",
                InferenceQueue.last_attempt_at <= cutoff_time,
            )
        )
        result = await self.db.execute(stmt)
        stuck_jobs = result.scalars().all()

        cleaned_up = 0

        for job in stuck_jobs:
            logger.warning(
                f"[SCHEDULER] Detected stuck job {job.id} "
                f"(last_attempt_at={job.last_attempt_at})"
            )

            job.status = "timeout"
            job.error_message = f"Job execution timeout (no update for {max_age_seconds}s)"

            # Attempt to reschedule if retries available
            if job.retry_count < job.max_retries:
                job.retry_count += 1
                backoff_seconds = 2 ** job.retry_count * job.backoff_multiplier
                job.next_retry_at = datetime.utcnow() + timedelta(seconds=backoff_seconds)
                job.status = "queued"
                logger.info(
                    f"[SCHEDULER] Rescheduled stuck job {job.id} "
                    f"(retry #{job.retry_count}, backoff={backoff_seconds}s)"
                )
            else:
                logger.error(
                    f"[SCHEDULER] Stuck job {job.id} exceeded max retries, marking failed"
                )
                job.status = "failed"
                job.completed_at = datetime.utcnow()

            cleaned_up += 1

        if cleaned_up > 0:
            await self.db.commit()

        return cleaned_up


class QueueSchedulerDaemon:
    """Convenience wrapper for running scheduler as a managed daemon task.

    Creates and manages a background asyncio task that runs the scheduler
    in a long-lived event loop.

    Usage:
        daemon = QueueSchedulerDaemon(db_session)
        task = asyncio.create_task(daemon.run())
        # Later: await daemon.stop()
    """

    def __init__(self, db_session: AsyncSession, poll_interval_seconds: float = 5.0):
        """Initialize daemon.

        Args:
            db_session: SQLAlchemy async session
            poll_interval_seconds: Poll interval for retry checks
        """
        self.scheduler = QueueScheduler(db_session, poll_interval_seconds=poll_interval_seconds)
        self.task: Optional[asyncio.Task] = None

    async def run(self) -> None:
        """Run the scheduler daemon.

        Blocks until stop() is called. Safe to use with asyncio.create_task().
        """
        await self.scheduler.start()

    async def stop(self, timeout_seconds: float = 5.0) -> None:
        """Stop the daemon gracefully.

        Args:
            timeout_seconds: Wait this long for scheduler to stop
        """
        await self.scheduler.stop()

        if self.task:
            try:
                await asyncio.wait_for(self.task, timeout=timeout_seconds)
            except asyncio.TimeoutError:
                logger.warning("[DAEMON] Scheduler did not stop within timeout, cancelling")
                self.task.cancel()
                try:
                    await self.task
                except asyncio.CancelledError:
                    pass
