"""Compatibility shim — canonical implementation in src.guppy.voice.voice."""
from __future__ import annotations
import importlib as _il, sys as _sys

_sys.modules[__name__] = _il.import_module("src.guppy.voice.voice")
