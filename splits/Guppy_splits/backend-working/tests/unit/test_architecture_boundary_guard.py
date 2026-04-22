from __future__ import annotations

from tools import check_architecture_boundaries as boundary_guard


def test_forbidden_import_map_covers_ui_and_utils_layers() -> None:
    assert "ui/" in boundary_guard.FORBIDDEN_IMPORT_MAP
    assert "utils/" in boundary_guard.FORBIDDEN_IMPORT_MAP

    ui_rule_ids = {entry[0] for entry in boundary_guard.FORBIDDEN_IMPORT_MAP["ui/"]}
    utils_rule_ids = {entry[0] for entry in boundary_guard.FORBIDDEN_IMPORT_MAP["utils/"]}

    assert {
        "ui-runtime-api-import",
        "ui-governance-import",
        "ui-experience-config-import",
    }.issubset(ui_rule_ids)
    assert "utils-to-ui" in utils_rule_ids


def test_find_boundary_hits_flags_forbidden_ui_and_utils_imports() -> None:
    ui_lines = [
        "from src.guppy.api import server",
        "from utils.runtime_profile import load_runtime_profile",
        "from utils.connector_manager import connector_inventory",
    ]
    ui_violations, ui_waived = boundary_guard.find_boundary_hits("ui/panel.py", ui_lines, scope="delta")
    assert ui_waived == []
    assert len(ui_violations) == 3

    utils_lines = [
        "from ui.launcher.launcher_window import LauncherWindow",
    ]
    utils_violations, utils_waived = boundary_guard.find_boundary_hits(
        "utils/bridge.py", utils_lines, scope="delta"
    )
    assert utils_waived == []
    assert len(utils_violations) == 1


def test_find_boundary_hits_respects_launcher_app_exclusion() -> None:
    lines = ["from ui.launcher.launcher_window import LauncherWindow"]
    violations, _waived = boundary_guard.find_boundary_hits(
        "src/guppy/apps/launcher_app.py",
        lines,
        scope="delta",
    )
    assert violations == []
