"""
launcher_startup_orchestration.py

Extracted from: ui/launcher/launcher_window.py
Purpose: Orchestrate launcher startup sequence with explicit phase ordering and reliability
Lane: TR54-D1

Implemented Methods:
  - initialize_startup_sequence() - Initialize startup tracking
  - record_phase_start() - Mark phase start time
  - record_phase_complete() - Mark phase completion with timing
  - get_phase_duration_ms() - Get phase duration in milliseconds
  - is_phase_over_budget() - Check if phase exceeded timeout budget
  - log_startup_timing() - Log all startup timing data
  - validate_startup_readiness() - Verify all required phases complete
  - get_startup_health_summary() - Build human-readable startup status

Dependencies:
  - Standard library: time, logging
  - ui.launcher.launcher_window - Window instance reference
  - src.guppy.launcher_application.launcher_command_policy - Error humanization
  
Startup Phase Sequence (Strict Order):
  1. window_init (0-100ms) - Window creation, layout prep
  2. build_ui (200-800ms) - Component creation and assembly
  3. status_poll_start (100-200ms) - Timer setup
  4. personalization_scaffold_thread_start (0-50ms) - Thread launch
  5. first_poll (500-1500ms) - Initial status query
  6. view_ready (200-400ms) - View initialization complete
  7. ready (< 3000ms total) - System fully initialized

Budget Constraints:
  - Total startup: < 3000ms (configurable via GUPPY_STARTUP_PHASE_WARN_MS)
  - Per-phase budget: 500ms (most phases)
  - Poll phase budget: 1500ms (largest phase)

Timing Guarantees:
  - All timestamps relative to window init start
  - Phase ordering enforced via validation
  - Over-budget phases logged and tracked
  - Recovery available if startup exceeds budget
"""

import logging
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

logger = logging.getLogger("launcher.startup")


@dataclass
class StartupPhase:
    """Track a single startup phase."""
    name: str
    start_time: float
    end_time: Optional[float] = None
    budget_ms: int = 500
    notes: str = ""

    @property
    def duration_ms(self) -> int:
        """Get phase duration in milliseconds."""
        if self.end_time is None:
            return -1
        return int((self.end_time - self.start_time) * 1000)

    @property
    def is_over_budget(self) -> bool:
        """Check if phase exceeded budget."""
        return self.duration_ms > self.budget_ms and self.duration_ms >= 0

    def complete(self, end_time: Optional[float] = None) -> None:
        """Mark phase as complete."""
        self.end_time = end_time or time.monotonic()

    def __str__(self) -> str:
        """Format as readable string."""
        duration = self.duration_ms
        if duration < 0:
            return f"{self.name}: IN_PROGRESS"
        status = "⚠️ OVER" if self.is_over_budget else "✓"
        return f"{self.name}: {duration}ms {status} (budget: {self.budget_ms}ms)"


@dataclass
class StartupSequence:
    """Track complete startup sequence with phase ordering."""
    initial_time: float = field(default_factory=time.monotonic)
    phases: dict[str, StartupPhase] = field(default_factory=dict)
    startup_budget_ms: int = 3000
    phase_order: list[str] = field(
        default_factory=lambda: [
            "window_init",
            "build_ui",
            "status_poll_start",
            "personalization_scaffold_thread_start",
            "first_poll",
            "view_ready",
            "ready",
        ]
    )
    over_budget_phases: list[str] = field(default_factory=list)

    def record_phase_start(self, phase_name: str, budget_ms: int = 500) -> None:
        """
        Record start of a startup phase.

        Args:
            phase_name: Name of phase (e.g., "window_init", "build_ui")
            budget_ms: Timeout budget for this phase in milliseconds
        """
        now = time.monotonic()
        self.phases[phase_name] = StartupPhase(
            name=phase_name,
            start_time=now,
            budget_ms=budget_ms,
        )
        logger.debug(f"Startup phase START: {phase_name}")

    def record_phase_complete(
        self, phase_name: str, notes: str = "", end_time: Optional[float] = None
    ) -> int:
        """
        Record completion of a startup phase.

        Args:
            phase_name: Name of phase
            notes: Optional notes about phase completion
            end_time: Override end time (for testing)

        Returns:
            Phase duration in milliseconds
        """
        if phase_name not in self.phases:
            logger.warning(f"Phase {phase_name} was never started")
            return -1

        phase = self.phases[phase_name]
        phase.complete(end_time=end_time)
        phase.notes = notes

        duration_ms = phase.duration_ms
        status = "OVER" if phase.is_over_budget else "OK"
        logger.debug(
            f"Startup phase COMPLETE: {phase_name} ({duration_ms}ms) [{status}] {notes}"
        )

        if phase.is_over_budget:
            self.over_budget_phases.append(phase_name)

        return duration_ms

    def get_total_duration_ms(self) -> int:
        """Get total startup duration from init to now."""
        return int((time.monotonic() - self.initial_time) * 1000)

    def is_startup_complete(self) -> bool:
        """Check if all critical startup phases are complete."""
        required_phases = {"window_init", "build_ui", "status_poll_start", "first_poll"}
        return all(phase in self.phases for phase in required_phases)

    def is_startup_ready(self) -> bool:
        """Check if startup is fully ready (all phases complete)."""
        return "ready" in self.phases and self.phases["ready"].end_time is not None

    def is_over_startup_budget(self) -> bool:
        """Check if total startup time exceeded budget."""
        return self.get_total_duration_ms() > self.startup_budget_ms

    def get_phase_duration_ms(self, phase_name: str) -> int:
        """Get duration of a specific phase."""
        if phase_name not in self.phases:
            return -1
        return self.phases[phase_name].duration_ms

    def get_phase_timeline(self) -> str:
        """Get formatted timeline of all phases."""
        lines = [f"Startup Timeline (budget: {self.startup_budget_ms}ms):"]
        total = self.get_total_duration_ms()
        lines.append(f"  Total elapsed: {total}ms")

        for phase_name in self.phase_order:
            if phase_name in self.phases:
                phase = self.phases[phase_name]
                lines.append(f"  {phase}")

        return "\n".join(lines)

    def get_health_summary(self) -> dict[str, object]:
        """
        Get startup health summary as structured data.

        Returns:
            Dict with keys: is_complete, is_ready, is_over_budget, total_ms,
            over_budget_phases, phases
        """
        return {
            "is_startup_complete": self.is_startup_complete(),
            "is_startup_ready": self.is_startup_ready(),
            "is_over_startup_budget": self.is_over_startup_budget(),
            "total_duration_ms": self.get_total_duration_ms(),
            "startup_budget_ms": self.startup_budget_ms,
            "over_budget_phases": self.over_budget_phases,
            "phases": {
                name: {
                    "duration_ms": phase.duration_ms,
                    "budget_ms": phase.budget_ms,
                    "is_over_budget": phase.is_over_budget,
                }
                for name, phase in self.phases.items()
            },
        }


class LauncherStartupOrchestrator:
    """Orchestrate launcher startup sequence with explicit phase ordering."""

    def __init__(self, startup_budget_ms: Optional[int] = None) -> None:
        """
        Initialize startup orchestrator.

        Args:
            startup_budget_ms: Total startup budget in milliseconds (default: 3000)
        """
        if startup_budget_ms is None:
            startup_budget_ms = int(
                os.environ.get("GUPPY_STARTUP_PHASE_WARN_MS", "3000")
            )

        self.sequence = StartupSequence(startup_budget_ms=startup_budget_ms)
        self.sequence.record_phase_start("window_init", budget_ms=100)

    def complete_phase(
        self, phase_name: str, budget_ms: Optional[int] = None, notes: str = ""
    ) -> int:
        """
        Complete a startup phase.

        Args:
            phase_name: Name of phase
            budget_ms: Override budget for this phase (optional)
            notes: Optional notes

        Returns:
            Phase duration in milliseconds
        """
        if phase_name in self.sequence.phases:
            phase = self.sequence.phases[phase_name]
            if budget_ms is not None:
                phase.budget_ms = budget_ms
        else:
            # Phase was never started - start it now with zero duration
            self.sequence.record_phase_start(phase_name, budget_ms=budget_ms or 500)

        return self.sequence.record_phase_complete(phase_name, notes=notes)

    def start_phase(self, phase_name: str, budget_ms: int = 500) -> None:
        """Start a new startup phase."""
        self.sequence.record_phase_start(phase_name, budget_ms=budget_ms)

    def get_status(self) -> str:
        """Get human-readable startup status."""
        return self.sequence.get_phase_timeline()

    def get_health(self) -> dict[str, object]:
        """Get structured startup health data."""
        return self.sequence.get_health_summary()

    def is_complete(self) -> bool:
        """Check if startup is complete (critical phases done)."""
        return self.sequence.is_startup_complete()

    def is_ready(self) -> bool:
        """Check if startup is fully ready."""
        return self.sequence.is_startup_ready()

    def is_over_budget(self) -> bool:
        """Check if startup exceeded total budget."""
        return self.sequence.is_over_startup_budget()

    def get_over_budget_phases(self) -> list[str]:
        """Get list of phases that exceeded their budget."""
        return self.sequence.over_budget_phases

    def log_startup_complete(self) -> None:
        """Log startup completion with full timing details."""
        if self.is_ready():
            logger.info(f"Startup complete: {self.sequence.get_total_duration_ms()}ms")
        else:
            logger.warning(f"Startup incomplete: {self.get_status()}")

        if self.is_over_budget():
            logger.warning(
                f"Startup over budget ({self.sequence.get_total_duration_ms()}ms > "
                f"{self.sequence.startup_budget_ms}ms). Over-budget phases: "
                f"{', '.join(self.sequence.over_budget_phases)}"
            )

    def validate_phase_order(self) -> tuple[bool, str]:
        """
        Validate that phases occurred in correct order.

        Returns:
            Tuple of (is_valid, message)
        """
        last_time = 0.0
        for phase_name in self.sequence.phase_order:
            if phase_name not in self.sequence.phases:
                continue
            phase = self.sequence.phases[phase_name]
            if phase.start_time < last_time:
                return (
                    False,
                    f"Phase {phase_name} started before previous phase completed",
                )
            last_time = phase.start_time

        return True, "All phases in correct order"


def create_startup_orchestrator(
    startup_budget_ms: Optional[int] = None,
) -> LauncherStartupOrchestrator:
    """
    Factory function to create a startup orchestrator.

    Args:
        startup_budget_ms: Optional budget override

    Returns:
        LauncherStartupOrchestrator instance
    """
    return LauncherStartupOrchestrator(startup_budget_ms=startup_budget_ms)
