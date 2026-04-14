"""Compatibility wrapper for Council legacy surface entrypoint."""
from __future__ import annotations

from src.guppy.apps.council_surface_app import main


if __name__ == "__main__":
    raise SystemExit(main())
