from __future__ import annotations

from pathlib import Path


def _bat_path() -> Path:
    return Path(__file__).resolve().parents[2] / "bin" / "launch_automation_test.bat"


def test_launch_automation_bat_exists() -> None:
    assert _bat_path().exists()


def test_launch_automation_bat_has_fallback_chain() -> None:
    text = _bat_path().read_text(encoding="utf-8")
    assert ".venv\\Scripts\\pythonw.exe" in text
    assert ".venv\\Scripts\\python.exe" in text
    assert "pythonw" in text
    assert "python" in text


def test_launch_automation_bat_has_preflight_guard() -> None:
    text = _bat_path().read_text(encoding="utf-8")
    assert "launch.py" in text or "if not exist" in text.lower()


def test_launch_automation_bat_has_error_exit() -> None:
    text = _bat_path().read_text(encoding="utf-8")
    assert "exit /b 1" in text.lower()
