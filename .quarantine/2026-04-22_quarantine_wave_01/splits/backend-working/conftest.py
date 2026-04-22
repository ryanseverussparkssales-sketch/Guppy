from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PySide6.QtWidgets import QApplication
except Exception:  # pragma: no cover - PySide6 is optional in some environments
    QApplication = None  # type: ignore[assignment]


def pytest_configure(config) -> None:  # pragma: no cover - test bootstrap
    del config
    if QApplication is None:
        return
    QApplication.instance() or QApplication([])
