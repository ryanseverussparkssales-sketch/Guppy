"""Compatibility wrapper for hub entrypoint."""
from __future__ import annotations

import sys

from src.guppy.apps.hub_app import main


if __name__ == "__main__":
    sys.exit(main())
