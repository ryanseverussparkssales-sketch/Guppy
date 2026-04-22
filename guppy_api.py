"""Compatibility shim - canonical implementation in src.guppy.api.server."""
from __future__ import annotations

import importlib as _il
import runpy as _rp
import sys as _sys


if __name__ == "__main__":
    _rp.run_module("src.guppy.api.server", run_name="__main__", alter_sys=True)
else:
    _sys.modules[__name__] = _il.import_module("src.guppy.api.server")
