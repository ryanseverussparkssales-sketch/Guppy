"""Seam wrapper for off-hours builder task operations.

Exposes the minimal builder-task API needed by the launcher shell so that
launcher_window.py no longer imports utils.offhours_builder directly.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

try:
    from utils.offhours_builder import (
        QUEUE_PATH as _QUEUE_PATH,
        RESULTS_PATH as _RESULTS_PATH,
        METRICS_PATH as _METRICS_PATH,
        approve_builder_task as _approve_builder_task,
        build_builder_report as _build_builder_report,
        enqueue_builder_task as _enqueue_builder_task,
        render_builder_task as _render_builder_task,
    )

    _BACKEND = True
except Exception:
    _BACKEND = False

    _ROOT = Path(__file__).resolve().parents[3]
    _RUNTIME = _ROOT / "runtime"
    _QUEUE_PATH = _RUNTIME / "offhours_task_queue.json"
    _RESULTS_PATH = _RUNTIME / "offhours_task_results.jsonl"
    _METRICS_PATH = _RUNTIME / "offhours_metrics.jsonl"

    def _build_builder_report(**_kwargs: Any) -> dict[str, Any]:  # type: ignore[misc]
        return {}

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


QUEUE_PATH: Path = _QUEUE_PATH
RESULTS_PATH: Path = _RESULTS_PATH
METRICS_PATH: Path = _METRICS_PATH


def build_builder_report(
    *,
    queue_path: Path | None = None,
    results_path: Path | None = None,
    metrics_path: Path | None = None,
) -> dict[str, Any]:
    return _build_builder_report(
        queue_path=queue_path if queue_path is not None else QUEUE_PATH,
        results_path=results_path if results_path is not None else RESULTS_PATH,
        metrics_path=metrics_path if metrics_path is not None else METRICS_PATH,
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


def builder_backend_available() -> bool:
    return _BACKEND
