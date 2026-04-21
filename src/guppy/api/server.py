"""Compatibility shim for the explicit FastAPI server module."""

from __future__ import annotations

import importlib as _importlib
import runpy as _runpy
import sys as _sys

_SERVER_MODULE = "src.guppy.api.server_runtime"

if __name__ == "__main__":
    _runpy.run_module(_SERVER_MODULE, run_name="__main__", alter_sys=True)
else:
    _sys.modules[__name__] = _importlib.import_module(_SERVER_MODULE)
