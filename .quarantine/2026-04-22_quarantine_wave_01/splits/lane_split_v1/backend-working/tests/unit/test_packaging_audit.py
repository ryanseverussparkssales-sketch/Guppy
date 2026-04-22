from pathlib import Path

from src.guppy.launcher_application.packaging_audit import (
    all_packaging_assumptions_hold,
    all_packaging_paths_writable,
)


def test_packaging_write_targets_are_writable(tmp_path: Path) -> None:
    ok, statuses = all_packaging_paths_writable(tmp_path)

    assert ok is True
    assert [item.label for item in statuses] == [
        "runtime root",
        "runtime daily reports",
        "runtime stress reports",
        "workflow reports",
    ]
    assert all(item.writable for item in statuses)
    assert (tmp_path / "runtime").exists()
    assert (tmp_path / ".tmp" / "dev-workflow" / "reports").exists()


def test_packaging_assumptions_fail_when_dist_and_release_handoff_are_missing(tmp_path: Path) -> None:
    (tmp_path / "bin").mkdir()
    (tmp_path / "docs").mkdir()
    (tmp_path / "runtime").mkdir()
    (tmp_path / "guppy_launcher.py").write_text("print('launcher')\n", encoding="utf-8")
    (tmp_path / "bin" / "Guppy.spec").write_text("a = Analysis([])\n", encoding="utf-8")
    (tmp_path / "bin" / "build_executable.bat").write_text(
        "\n".join(
            (
                "@echo off",
                "py -m PyInstaller --noconfirm bin\\Guppy.spec --name \"Guppy\" --icon \"assets\\desktop\\guppy_launcher_icon.ico\" --add-data \"config\\local_llm;config\\local_llm\" --add-data \"runtime;runtime\" guppy_launcher.py",
            )
        ),
        encoding="utf-8",
    )
    (tmp_path / "bin" / "validate_build.bat").write_text(
        "\n".join(
            (
                "@echo off",
                "set BUILD_EXE=dist\\Guppy\\Guppy.exe",
                "if not exist \"%BUILD_EXE%\" set BUILD_EXE=dist\\Guppy.exe",
                "python tools\\validate_build_checks.py",
            )
        ),
        encoding="utf-8",
    )
    (tmp_path / "docs" / "PACKAGING.md").write_text(
        "\n".join(
            (
                "bin/build_executable.bat",
                "tools/ensure_desktop_launcher.ps1",
                "runtime/windows_release_receipt.json",
                "runtime/windows_release_summary.md",
                "runtime/beta_release_dry_run_report.json",
            )
        ),
        encoding="utf-8",
    )

    ok, statuses = all_packaging_assumptions_hold(tmp_path)

    assert ok is False
    status_by_label = {item.label: item for item in statuses}
    assert "no built dist/ artifact present yet" in status_by_label["dist artifact layout"].detail
    assert "release handoff artifacts are missing" in status_by_label["release handoff contract"].detail


def test_packaging_assumptions_validate_release_handoff_when_present(tmp_path: Path) -> None:
    (tmp_path / "bin").mkdir()
    (tmp_path / "docs").mkdir()
    runtime_dir = tmp_path / "runtime"
    runtime_dir.mkdir()
    dist_dir = tmp_path / "dist" / "Guppy"
    dist_dir.mkdir(parents=True)
    with (dist_dir / "Guppy.exe").open("wb") as handle:
        handle.truncate(51 * 1024 * 1024)
    (tmp_path / "guppy_launcher.py").write_text("print('launcher')\n", encoding="utf-8")
    (tmp_path / "bin" / "Guppy.spec").write_text("a = Analysis([])\n", encoding="utf-8")
    (tmp_path / "bin" / "build_executable.bat").write_text(
        "@echo off\npy -m PyInstaller --noconfirm bin\\Guppy.spec --name \"Guppy\" --icon \"assets\\desktop\\guppy_launcher_icon.ico\" --add-data \"config\\local_llm;config\\local_llm\" --add-data \"runtime;runtime\" guppy_launcher.py\n",
        encoding="utf-8",
    )
    (tmp_path / "bin" / "validate_build.bat").write_text(
        "@echo off\nset BUILD_EXE=dist\\Guppy\\Guppy.exe\nif not exist \"%BUILD_EXE%\" set BUILD_EXE=dist\\Guppy.exe\npython tools\\validate_build_checks.py\n",
        encoding="utf-8",
    )
    (tmp_path / "docs" / "PACKAGING.md").write_text(
        "\n".join(
            (
                "bin/build_executable.bat",
                "tools/ensure_desktop_launcher.ps1",
                "runtime/windows_release_receipt.json",
                "runtime/windows_release_summary.md",
                "runtime/beta_release_dry_run_report.json",
            )
        ),
        encoding="utf-8",
    )
    (runtime_dir / "windows_release_receipt.json").write_text(
        (
            "{"
            "\"release_stage\": \"package\","
            "\"action\": \"package_desktop\","
            "\"ok\": true,"
            "\"paths\": {"
            "\"receipt_path\": \"C:/repo/runtime/windows_release_receipt.json\","
            "\"summary_path\": \"C:/repo/runtime/windows_release_summary.md\""
            "},"
            "\"operator_guidance\": {"
            "\"docs_hint\": \"docs/PACKAGING.md\","
            "\"entry_point\": \"bin\\\\build_executable.bat --no-clean\""
            "},"
            "\"review_order\": []"
            "}"
        ),
        encoding="utf-8",
    )
    (runtime_dir / "windows_release_summary.md").write_text(
        "# Windows Release Summary\n\n- Doc: docs/PACKAGING.md\n",
        encoding="utf-8",
    )
    (runtime_dir / "beta_release_dry_run_report.json").write_text(
        "{\"ok\": true, \"checks\": []}\n",
        encoding="utf-8",
    )

    ok, statuses = all_packaging_assumptions_hold(tmp_path)

    assert ok is True
    status_by_label = {item.label: item for item in statuses}
    assert "validated handoff artifacts" in status_by_label["release handoff contract"].detail
    assert "found canonical onedir package output" in status_by_label["dist artifact layout"].detail


def test_packaging_assumptions_reject_non_packaging_release_receipt(tmp_path: Path) -> None:
    (tmp_path / "bin").mkdir()
    (tmp_path / "docs").mkdir()
    runtime_dir = tmp_path / "runtime"
    runtime_dir.mkdir()
    dist_dir = tmp_path / "dist"
    dist_dir.mkdir()
    with (dist_dir / "Guppy.exe").open("wb") as handle:
        handle.truncate(51 * 1024 * 1024)
    (tmp_path / "guppy_launcher.py").write_text("print('launcher')\n", encoding="utf-8")
    (tmp_path / "bin" / "Guppy.spec").write_text("a = Analysis([])\n", encoding="utf-8")
    (tmp_path / "bin" / "build_executable.bat").write_text(
        "@echo off\npy -m PyInstaller --noconfirm bin\\Guppy.spec --name \"Guppy\" --icon \"assets\\desktop\\guppy_launcher_icon.ico\" --add-data \"config\\local_llm;config\\local_llm\" --add-data \"runtime;runtime\" guppy_launcher.py\n",
        encoding="utf-8",
    )
    (tmp_path / "bin" / "validate_build.bat").write_text(
        "@echo off\nset BUILD_EXE=dist\\Guppy\\Guppy.exe\nif not exist \"%BUILD_EXE%\" set BUILD_EXE=dist\\Guppy.exe\npython tools\\validate_build_checks.py\n",
        encoding="utf-8",
    )
    (tmp_path / "docs" / "PACKAGING.md").write_text(
        "\n".join(
            (
                "bin/build_executable.bat",
                "tools/ensure_desktop_launcher.ps1",
                "runtime/windows_release_receipt.json",
                "runtime/windows_release_summary.md",
                "runtime/beta_release_dry_run_report.json",
            )
        ),
        encoding="utf-8",
    )
    (runtime_dir / "windows_release_receipt.json").write_text(
        (
            "{"
            "\"release_stage\": \"verification\","
            "\"action\": \"verify_runtime\","
            "\"ok\": true,"
            "\"paths\": {"
            "\"receipt_path\": \"C:/repo/runtime/windows_release_receipt.json\","
            "\"summary_path\": \"C:/repo/runtime/windows_release_summary.md\""
            "},"
            "\"operator_guidance\": {"
            "\"docs_hint\": \"docs/PACKAGING.md\","
            "\"entry_point\": \"bin\\\\build_executable.bat --no-clean\""
            "},"
            "\"review_order\": []"
            "}"
        ),
        encoding="utf-8",
    )
    (runtime_dir / "windows_release_summary.md").write_text(
        "# Windows Release Summary\n\n- Doc: docs/PACKAGING.md\n",
        encoding="utf-8",
    )
    (runtime_dir / "beta_release_dry_run_report.json").write_text(
        "{\"ok\": true, \"checks\": []}\n",
        encoding="utf-8",
    )

    ok, statuses = all_packaging_assumptions_hold(tmp_path)

    assert ok is False
    status_by_label = {item.label: item for item in statuses}
    assert "action must be package_desktop or release_dry_run" in status_by_label["release handoff contract"].detail
