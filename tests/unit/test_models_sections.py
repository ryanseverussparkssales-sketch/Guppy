from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication

from ui.launcher.views.models_sections import build_models_loadout_section, build_models_runtime_section


@pytest.fixture(scope="module", autouse=True)
def _qapp() -> QApplication:
    return QApplication.instance() or QApplication([])


def test_build_models_loadout_section_creates_expected_inputs_and_actions() -> None:
    changes: list[tuple[str, str]] = []
    clicks: list[str] = []
    section = build_models_loadout_section(
        loadout_fields=[
            ("local_main_model", "MAIN"),
            ("local_sub_model_a", "SUB A"),
            ("local_sub_model_b", "SUB B"),
        ],
        on_loadout_changed=lambda field, value: changes.append((field, value)),
        on_apply_loadout=lambda: clicks.append("apply"),
        on_spawn_main=lambda: clicks.append("main"),
        on_spawn_subs=lambda: clicks.append("subs"),
        on_spawn_all=lambda: clicks.append("all"),
    )

    assert section.frame is not None
    assert set(section.inputs) == {"local_main_model", "local_sub_model_a", "local_sub_model_b"}

    section.inputs["local_main_model"].addItem("guppy")
    section.inputs["local_main_model"].setCurrentText("guppy")
    section.apply_button.click()
    section.spawn_main_button.click()
    section.spawn_subs_button.click()
    section.spawn_all_button.click()

    assert ("local_main_model", "guppy") in changes
    assert clicks == ["apply", "main", "subs", "all"]


def test_build_models_runtime_section_creates_backend_and_role_controls() -> None:
    backend_changes: list[str] = []
    role_changes: list[str] = []
    actions: list[str] = []
    section = build_models_runtime_section(
        lemonade_role_fields=[
            ("lemonade_fast_model", "FAST"),
            ("lemonade_complex_model", "COMPLEX"),
        ],
        default_lemonade_base_url="http://localhost:13305/api/v1",
        on_runtime_backend_changed=lambda text: backend_changes.append(text),
        on_save_runtime_settings=lambda: actions.append("save"),
        on_set_selected_runtime_role=lambda field: role_changes.append(field),
        on_refresh_runtime_library=lambda: actions.append("refresh_library"),
    )

    assert section.backend_combo.count() == 2
    assert set(section.lemonade_role_inputs) == {"lemonade_fast_model", "lemonade_complex_model"}

    section.backend_combo.setCurrentText("LEMONADE")
    section.save_button.click()
    section.runtime_library_search.setText("mixtral")
    section.lemonade_role_inputs["lemonade_fast_model"].addItem("mixtral")
    section.lemonade_role_inputs["lemonade_fast_model"].setCurrentText("mixtral")

    assert "LEMONADE" in backend_changes
    assert actions == ["save", "refresh_library"]
    assert "lemonade_fast_model" in role_changes
