"""Compatibility loader for the split FastAPI server module."""

from __future__ import annotations

from pathlib import Path


def _exec_fragment(filename: str) -> None:
    fragment_path = Path(__file__).with_name(filename)
    source = fragment_path.read_text(encoding="utf-8")
    exec(compile(source, str(fragment_path), "exec"), globals(), globals())


for _fragment_name in (
    "_server_fragment_bootstrap.py",
    "_server_fragment_instances_telemetry.py",
    "_server_fragment_ops.py",
    "_server_fragment_local_runtime.py",
    "_server_fragment_runtime_status.py",
    "_server_fragment_runtime_calls.py",
    "_server_fragment_routes_core.py",
    "_server_fragment_routes_ops.py",
):
    _exec_fragment(_fragment_name)


del _exec_fragment
del _fragment_name
