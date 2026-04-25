"""Compatibility wrapper for the fishbowl companion entrypoint."""
from __future__ import annotations

import sys

from src.guppy.apps.fishbowl_app import main

__all__ = ["main"]


if __name__ == "__main__":
    sys.exit(main())
