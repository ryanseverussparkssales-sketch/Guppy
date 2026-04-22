"""Compatibility wrapper for launcher entrypoint."""
from __future__ import annotations

from src.guppy.apps.launcher_app import main

__all__ = ["main"]


if __name__ == "__main__":
    raise SystemExit(main())
