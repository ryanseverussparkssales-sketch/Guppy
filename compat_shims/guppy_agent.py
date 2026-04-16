"""Compatibility shim — canonical implementation in src.guppy.cli.agent."""
from __future__ import annotations
import importlib as _il, runpy as _rp, sys as _sys

if __name__ == "__main__":
    _rp.run_module("src.guppy.cli.agent", run_name="__main__", alter_sys=True)
else:
    _sys.modules[__name__] = _il.import_module("src.guppy.cli.agent")
