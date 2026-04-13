"""Compatibility shim for legacy root module path.

Canonical implementation lives in the package entrypoint at guppy_core/__init__.py.
Keep this file thin so there is only one real implementation surface.
"""
from __future__ import annotations

from importlib import import_module as _import_module

_pkg = _import_module("guppy_core")

# Re-export public package symbols for legacy direct-path consumers.
if hasattr(_pkg, "__all__"):
    __all__ = list(getattr(_pkg, "__all__"))
else:
    __all__ = [name for name in dir(_pkg) if not name.startswith("_")]

globals().update({name: getattr(_pkg, name) for name in __all__})
