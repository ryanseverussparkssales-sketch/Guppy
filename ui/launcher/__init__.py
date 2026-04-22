"""Compatibility launcher package exposing the live launcher UI modules."""
from __future__ import annotations

from pathlib import Path
from pkgutil import extend_path

__path__ = extend_path(__path__, __name__)

_COMPAT_ROOT = Path(__file__).resolve().parents[2] / "compat_shims" / "launcher_ui" / "ui" / "launcher"
if _COMPAT_ROOT.exists():
    compat_path = str(_COMPAT_ROOT)
    if compat_path not in __path__:
        __path__.append(compat_path)

__all__ = ["LauncherWindow"]


def __getattr__(name: str):
    if name == "LauncherWindow":
        from .launcher_window import LauncherWindow

        return LauncherWindow
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
