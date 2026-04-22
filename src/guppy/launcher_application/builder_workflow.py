"""Seam wrapper for off-hours builder task operations.

Exposes the minimal builder-task API needed by the launcher shell so that
launcher_window.py no longer imports utils.offhours_builder directly.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

try:
    import utils.offhours_builder as _builder_backend

    from utils.offhours_builder import (
        QUEUE_PATH as _QUEUE_PATH,
        RESULTS_PATH as _RESULTS_PATH,
        METRICS_PATH as _METRICS_PATH,
        approve_builder_task as _approve_builder_task,
        build_builder_report as _build_builder_report,
        enqueue_builder_task as _enqueue_builder_task,
        load_builder_templates as _load_builder_templates,
        render_builder_task as _render_builder_task,
    )

    _BACKEND = True
except Exception:
    _BACKEND = False
    _builder_backend = None  # type: ignore[assignment]

    _ROOT = Path(__file__).resolve().parents[3]
    _RUNTIME = _ROOT / "runtime"
    _QUEUE_PATH = _RUNTIME / "offhours_task_queue.json"
    _RESULTS_PATH = _RUNTIME / "offhours_task_results.jsonl"
    _METRICS_PATH = _RUNTIME / "offhours_metrics.jsonl"

    def _build_builder_report(**_kwargs: Any) -> dict[str, Any]:  # type: ignore[misc]
        return {
            "generated_utc": "",
            "queue_counts": {
                "pending": 0,
                "running": 0,
                "awaiting_approval": 0,
                "done": 0,
                "failed": 0,
            },
            "pending_approvals": [],
            "recent_results": [],
            "recent_metrics": [],
            "recent_activity": [],
            "stress_validation": {},
        }

    def _enqueue_builder_task(_task: dict[str, Any]) -> None:  # type: ignore[misc]
        pass

    def _render_builder_task(  # type: ignore[misc]
        _template_id: str,
        *,
        target_ref: str = "",
        requested_by_instance: str = "",
    ) -> dict[str, Any]:
        return {"id": "unavailable", "title": "unavailable", "output_file_path": ""}

    def _approve_builder_task(_task_id: str, **_kwargs: Any) -> dict[str, Any]:  # type: ignore[misc]
        return {}

    def _load_builder_templates() -> list[dict[str, Any]]:  # type: ignore[misc]
        return []


QUEUE_PATH: Path = _QUEUE_PATH
RESULTS_PATH: Path = _RESULTS_PATH
METRICS_PATH: Path = _METRICS_PATH


def queue_path() -> Path:
    if _BACKEND and _builder_backend is not None:
        return Path(getattr(_builder_backend, "QUEUE_PATH", QUEUE_PATH))
    return QUEUE_PATH


def results_path() -> Path:
    if _BACKEND and _builder_backend is not None:
        return Path(getattr(_builder_backend, "RESULTS_PATH", RESULTS_PATH))
    return RESULTS_PATH


def metrics_path() -> Path:
    if _BACKEND and _builder_backend is not None:
        return Path(getattr(_builder_backend, "METRICS_PATH", METRICS_PATH))
    return METRICS_PATH


def build_builder_report(
    *,
    queue_path: Path | None = None,
    results_path: Path | None = None,
    metrics_path: Path | None = None,
) -> dict[str, Any]:
    return _build_builder_report(
        queue_path=queue_path if queue_path is not None else globals()["queue_path"](),
        results_path=results_path if results_path is not None else globals()["results_path"](),
        metrics_path=metrics_path if metrics_path is not None else globals()["metrics_path"](),
    )


def enqueue_builder_task(task: dict[str, Any]) -> None:
    _enqueue_builder_task(task)


def render_builder_task(
    template_id: str,
    *,
    target_ref: str = "",
    requested_by_instance: str = "",
) -> dict[str, Any]:
    return _render_builder_task(
        template_id,
        target_ref=target_ref,
        requested_by_instance=requested_by_instance,
    )


def approve_builder_task(task_id: str, **kwargs: Any) -> dict[str, Any]:
    return _approve_builder_task(task_id, **kwargs)


def load_builder_templates() -> list[dict[str, Any]]:
    templates = _load_builder_templates()
    return templates if isinstance(templates, list) else []


def builder_backend_available() -> bool:
    return _BACKEND
