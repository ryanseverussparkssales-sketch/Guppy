"""Compatibility wrapper for Guppy legacy surface entrypoint."""
from __future__ import annotations

from src.guppy.apps.guppy_surface_app import main


if __name__ == "__main__":
    raise SystemExit(main())
