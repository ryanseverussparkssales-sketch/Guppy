"""Compatibility wrapper for Merlin legacy surface entrypoint."""
from __future__ import annotations

from src.guppy.apps.merlin_surface_app import main


if __name__ == "__main__":
    raise SystemExit(main())
