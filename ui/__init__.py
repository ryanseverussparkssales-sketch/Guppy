"""Compatibility UI package exposing the live launcher-era UI modules."""
from __future__ import annotations

from pathlib import Path
from pkgutil import extend_path

__path__ = extend_path(__path__, __name__)

_COMPAT_ROOT = Path(__file__).resolve().parents[1] / "compat_shims" / "launcher_ui" / "ui"
if _COMPAT_ROOT.exists():
    compat_path = str(_COMPAT_ROOT)
    if compat_path not in __path__:
        __path__.append(compat_path)
