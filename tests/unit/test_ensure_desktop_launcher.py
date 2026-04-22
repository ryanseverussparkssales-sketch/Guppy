from __future__ import annotations

import subprocess
from pathlib import Path


def _run_shortcut_script(repo_root: Path, desktop_root: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            "powershell",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(repo_root / "tools" / "ensure_desktop_launcher.ps1"),
            "-DesktopRoot",
            str(desktop_root),
        ],
        cwd=repo_root,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=30,
        check=False,
    )


def test_ensure_desktop_launcher_creates_batch_and_shortcut(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[2]

    proc = _run_shortcut_script(repo_root, tmp_path)

    assert proc.returncode == 0, proc.stderr or proc.stdout
    batch_path = tmp_path / "Applications" / "Guppy Launcher.bat"
    shortcut_path = tmp_path / "Guppy Launcher.lnk"
    assert batch_path.exists()
    assert shortcut_path.exists()

    batch_text = batch_path.read_text(encoding="utf-8")
    assert r'set "REPO_LAUNCHER=%REPO_ROOT%\bin\Guppy.bat"' in batch_text
    assert r'set "PACKAGED_ONEDIR=%REPO_ROOT%\dist\Guppy\Guppy.exe"' in batch_text


def test_ensure_desktop_launcher_prefers_packaged_executable_when_present(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[2]
    packaged_exe = repo_root / "dist" / "Guppy" / "Guppy.exe"
    created_packaged_dir = False
    if not packaged_exe.parent.exists():
        packaged_exe.parent.mkdir(parents=True, exist_ok=True)
        created_packaged_dir = True
    packaged_exe.write_text("packaged launcher stub", encoding="utf-8")

    try:
        proc = _run_shortcut_script(repo_root, tmp_path)

        assert proc.returncode == 0, proc.stderr or proc.stdout
        assert f"Shortcut target: {packaged_exe}" in proc.stdout
    finally:
        packaged_exe.unlink(missing_ok=True)
        if created_packaged_dir:
            packaged_exe.parent.rmdir()
            packaged_exe.parent.parent.rmdir()
