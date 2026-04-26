"""Guppy Launcher Platform — unified service lifecycle management.

Provides:
  - ProcessRegistry  — start/stop/restart/reset/status for all Guppy services
  - HealthMonitor    — async HTTP health probes for each service
  - Standalone server (port 8082) with embedded web UI
  - /api/launcher/* routes mountable on the main API (port 8081)

Entry point:
  python launch_platform.py          # standalone launcher UI at :8082
  python -m src.guppy.launcher_platform
"""
from .process_registry import ProcessRegistry
from .health_monitor import check_service, check_all

_registry: ProcessRegistry | None = None


def get_registry() -> ProcessRegistry:
    """Return the module-level singleton process registry."""
    global _registry
    if _registry is None:
        _registry = ProcessRegistry()
    return _registry
