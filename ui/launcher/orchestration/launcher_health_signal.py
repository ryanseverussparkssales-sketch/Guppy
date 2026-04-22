"""
launcher_health_signal.py

Extracted from: ui/launcher/launcher_window.py
Purpose: Harden polling and health signal mechanisms with reliability checks
Lane: TR54-D4

Responsibilities:
  - Health signal monitoring (recovery events, runtime status)
  - Polling reliability with timeout detection
  - Signal loss detection and recovery triggering
  - Health checkpoint validation
  - Status badge updates based on health

Health Signal Categories:
  1. HEALTHY - All systems operational, responsive
  2. DEGRADED - Systems operational but slow or partial
  3. UNHEALTHY - Systems non-responsive or failed
  4. RECOVERING - Recovery in progress

Polling Guarantees:
  - Poll rate: 250ms (configurable)
  - Max event drain: 12 events per tick
  - Timeout: 5000ms (non-responsive = unhealthy)
  - Recovery: Automatic restart of failed workers

Health Checkpoint Sequence:
  1. Poll recovery events (window visibility)
  2. Sync recovery outcome (classify, format)
  3. Update topbar model context
  4. Check runtime health
  5. Drain assistant events
  6. Drain deferred syslog
"""

import logging
import os
import time
from dataclasses import dataclass
from enum import Enum
from typing import Callable, Optional

logger = logging.getLogger("launcher.health")


class HealthStatus(Enum):
    """Health status enumeration."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    RECOVERING = "recovering"
    UNKNOWN = "unknown"

    def to_severity(self) -> str:
        """Convert health status to severity level."""
        return {
            HealthStatus.HEALTHY: "success",
            HealthStatus.DEGRADED: "warning",
            HealthStatus.UNHEALTHY: "error",
            HealthStatus.RECOVERING: "info",
            HealthStatus.UNKNOWN: "warning",
        }[self]


@dataclass
class HealthCheckpoint:
    """Single health checkpoint result."""
    name: str
    status: HealthStatus
    timestamp: float
    message: str = ""
    duration_ms: int = 0

    def is_healthy(self) -> bool:
        """Check if checkpoint is healthy."""
        return self.status in (HealthStatus.HEALTHY, HealthStatus.DEGRADED)

    def __str__(self) -> str:
        """Format checkpoint as string."""
        emoji = {
            HealthStatus.HEALTHY: "✓",
            HealthStatus.DEGRADED: "⚠",
            HealthStatus.UNHEALTHY: "✗",
            HealthStatus.RECOVERING: "↻",
            HealthStatus.UNKNOWN: "?",
        }[self.status]
        return f"{emoji} {self.name}: {self.status.value} ({self.duration_ms}ms)"


@dataclass
class HealthSignal:
    """Complete health signal from a poll tick."""
    timestamp: float
    overall_status: HealthStatus
    checkpoints: list[HealthCheckpoint]
    recovery_events_drained: int = 0
    assistant_events_drained: int = 0
    syslog_lines_drained: int = 0
    notes: str = ""

    def is_healthy(self) -> bool:
        """Check if overall health is healthy."""
        return self.overall_status in (HealthStatus.HEALTHY, HealthStatus.DEGRADED)

    def is_unhealthy(self) -> bool:
        """Check if health indicates failure."""
        return self.overall_status == HealthStatus.UNHEALTHY

    def is_recovering(self) -> bool:
        """Check if recovery is in progress."""
        return self.overall_status == HealthStatus.RECOVERING

    def get_summary(self) -> str:
        """Get human-readable health summary."""
        lines = [
            f"Health Status: {self.overall_status.value.upper()}",
            f"Checkpoints ({len(self.checkpoints)}):",
        ]
        for cp in self.checkpoints:
            lines.append(f"  {cp}")
        lines.append(f"Events drained: recovery={self.recovery_events_drained}, "
                    f"assistant={self.assistant_events_drained}, syslog={self.syslog_lines_drained}")
        if self.notes:
            lines.append(f"Notes: {self.notes}")
        return "\n".join(lines)


class HealthSignalMonitor:
    """Monitor and manage health signals from polling."""

    # Configuration
    DEFAULT_POLL_INTERVAL_MS = 250
    DEFAULT_POLL_TIMEOUT_MS = 5000
    DEFAULT_MAX_RECOVERY_EVENTS_PER_TICK = 12
    DEFAULT_MAX_ASSISTANT_EVENTS_PER_TICK = 12
    DEFAULT_MAX_SYSLOG_PER_TICK = 24

    def __init__(
        self,
        poll_interval_ms: Optional[int] = None,
        poll_timeout_ms: Optional[int] = None,
        max_recovery_events: Optional[int] = None,
        max_assistant_events: Optional[int] = None,
        max_syslog_lines: Optional[int] = None,
    ) -> None:
        """
        Initialize health signal monitor.

        Args:
            poll_interval_ms: Polling interval in milliseconds
            poll_timeout_ms: Timeout for unresponsive polls
            max_recovery_events: Max recovery events to drain per tick
            max_assistant_events: Max assistant events to drain per tick
            max_syslog_lines: Max syslog lines to drain per tick
        """
        self.poll_interval_ms = poll_interval_ms or self.DEFAULT_POLL_INTERVAL_MS
        self.poll_timeout_ms = poll_timeout_ms or self.DEFAULT_POLL_TIMEOUT_MS
        self.max_recovery_events = max_recovery_events or self.DEFAULT_MAX_RECOVERY_EVENTS_PER_TICK
        self.max_assistant_events = max_assistant_events or self.DEFAULT_MAX_ASSISTANT_EVENTS_PER_TICK
        self.max_syslog_lines = max_syslog_lines or self.DEFAULT_MAX_SYSLOG_PER_TICK

        self.last_poll_time: float = 0.0
        self.last_healthy_time: float = 0.0
        self.poll_fail_count: int = 0
        self.last_health_signal: Optional[HealthSignal] = None
        self.health_history: list[HealthSignal] = []
        self.recovery_triggered_at: Optional[float] = None

    def record_poll_start(self) -> float:
        """Record start of a poll tick. Returns timestamp."""
        return time.monotonic()

    def record_checkpoint(
        self, name: str, status: HealthStatus, start_time: float, message: str = ""
    ) -> HealthCheckpoint:
        """
        Record a health checkpoint result.

        Args:
            name: Checkpoint name (e.g., "recovery_events", "runtime_health")
            status: Health status
            start_time: Checkpoint start time (for duration calculation)
            message: Optional status message

        Returns:
            HealthCheckpoint instance
        """
        duration_ms = int((time.monotonic() - start_time) * 1000)
        checkpoint = HealthCheckpoint(
            name=name,
            status=status,
            timestamp=time.monotonic(),
            message=message,
            duration_ms=duration_ms,
        )
        logger.debug(f"Health checkpoint: {checkpoint}")
        return checkpoint

    def finalize_poll(
        self,
        checkpoints: list[HealthCheckpoint],
        recovery_events_drained: int = 0,
        assistant_events_drained: int = 0,
        syslog_lines_drained: int = 0,
        notes: str = "",
    ) -> HealthSignal:
        """
        Finalize a poll tick and compute overall health.

        Args:
            checkpoints: List of health checkpoints from this poll
            recovery_events_drained: Number of recovery events processed
            assistant_events_drained: Number of assistant events processed
            syslog_lines_drained: Number of syslog lines processed
            notes: Optional poll notes

        Returns:
            HealthSignal instance
        """
        # Determine overall status from checkpoints
        if not checkpoints:
            overall_status = HealthStatus.UNKNOWN
        elif any(cp.status == HealthStatus.UNHEALTHY for cp in checkpoints):
            overall_status = HealthStatus.UNHEALTHY
        elif any(cp.status == HealthStatus.RECOVERING for cp in checkpoints):
            overall_status = HealthStatus.RECOVERING
        elif any(cp.status == HealthStatus.DEGRADED for cp in checkpoints):
            overall_status = HealthStatus.DEGRADED
        else:
            overall_status = HealthStatus.HEALTHY

        signal = HealthSignal(
            timestamp=time.monotonic(),
            overall_status=overall_status,
            checkpoints=checkpoints,
            recovery_events_drained=recovery_events_drained,
            assistant_events_drained=assistant_events_drained,
            syslog_lines_drained=syslog_lines_drained,
            notes=notes,
        )

        # Track history and update state
        self.last_health_signal = signal
        self.health_history.append(signal)
        if len(self.health_history) > 100:  # Keep last 100 signals
            self.health_history = self.health_history[-100:]

        # Update health tracking
        if signal.is_healthy():
            self.last_healthy_time = time.monotonic()
            self.poll_fail_count = 0
        else:
            self.poll_fail_count += 1

        # Log summary
        if signal.is_unhealthy():
            logger.warning(f"Health degraded: {signal.overall_status.value}")
        elif signal.is_recovering():
            logger.info("Health signal: RECOVERING")
        elif signal.is_healthy() and len(self.health_history) > 1:
            prev = self.health_history[-2]
            if prev.is_unhealthy():
                logger.info("Health signal: RECOVERED to HEALTHY")

        return signal

    def should_trigger_recovery(self) -> bool:
        """
        Determine if recovery should be triggered.

        Returns:
            True if health is critically degraded and recovery needed
        """
        if self.last_health_signal is None:
            return False

        # Recovery triggered if: unhealthy for multiple ticks, or timeout exceeded
        time_since_healthy = time.monotonic() - self.last_healthy_time
        consecutive_failures = self.poll_fail_count
        is_timeout = time_since_healthy > self.poll_timeout_ms / 1000.0

        should_recover = (
            (self.last_health_signal.is_unhealthy() and consecutive_failures >= 3)
            or is_timeout
        )

        return should_recover

    def trigger_recovery(self, recovery_reason: str = "") -> None:
        """
        Trigger recovery sequence.

        Args:
            recovery_reason: Reason for triggering recovery
        """
        self.recovery_triggered_at = time.monotonic()
        logger.warning(f"Recovery triggered: {recovery_reason}")

    def is_recovering(self) -> bool:
        """Check if recovery is currently in progress."""
        if self.recovery_triggered_at is None:
            return False
        # Recovery timeout: 10 seconds
        recovery_elapsed = time.monotonic() - self.recovery_triggered_at
        return recovery_elapsed < 10.0

    def get_status_summary(self) -> dict[str, object]:
        """
        Get structured health status summary.

        Returns:
            Dict with: status, is_healthy, last_signal, poll_fail_count,
            recovery_triggered, time_since_healthy_ms
        """
        time_since_healthy = (time.monotonic() - self.last_healthy_time) * 1000
        return {
            "overall_status": self.last_health_signal.overall_status.value
            if self.last_health_signal else "unknown",
            "is_healthy": self.last_health_signal.is_healthy()
            if self.last_health_signal else False,
            "is_unhealthy": self.last_health_signal.is_unhealthy()
            if self.last_health_signal else False,
            "poll_fail_count": self.poll_fail_count,
            "recovery_triggered": self.recovery_triggered_at is not None,
            "is_recovering": self.is_recovering(),
            "time_since_healthy_ms": int(time_since_healthy),
            "last_signal_timestamp": self.last_health_signal.timestamp
            if self.last_health_signal else None,
        }

    def get_health_history_summary(self, limit: int = 10) -> list[str]:
        """
        Get recent health history as strings.

        Args:
            limit: Number of recent signals to return

        Returns:
            List of formatted health signal summaries
        """
        recent = self.health_history[-limit:]
        return [
            f"{s.timestamp:.1f}: {s.overall_status.value} "
            f"(recovery={s.recovery_events_drained}, "
            f"assistant={s.assistant_events_drained})"
            for s in recent
        ]


def create_health_monitor(
    poll_interval_ms: Optional[int] = None,
) -> HealthSignalMonitor:
    """
    Factory function to create a health signal monitor.

    Args:
        poll_interval_ms: Optional poll interval override

    Returns:
        HealthSignalMonitor instance
    """
    return HealthSignalMonitor(poll_interval_ms=poll_interval_ms)
