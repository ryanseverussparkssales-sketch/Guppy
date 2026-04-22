"""Compatibility shim - canonical implementation in compat_shims.launcher_ui.launcher_app."""
from __future__ import annotations

import importlib as _il
import runpy as _rp
import sys as _sys


if __name__ == "__main__":
    _rp.run_module("compat_shims.launcher_ui.launcher_app", run_name="__main__", alter_sys=True)
else:
    _sys.modules[__name__] = _il.import_module("compat_shims.launcher_ui.launcher_app")
