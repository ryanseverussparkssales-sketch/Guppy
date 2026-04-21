from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication

from ui.launcher.views.models_sections import build_models_loadout_section, build_models_route_section, build_models_runtime_section


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
            ("lemonade_fast_model", "DAILY SLOT"),
            ("lemonade_complex_model", "HEAVY SLOT"),
        ],
        default_lemonade_base_url="http://localhost:13305/api/v1",
        on_runtime_backend_changed=lambda text: backend_changes.append(text),
        on_save_runtime_settings=lambda: actions.append("save"),
        on_set_selected_runtime_role=lambda field: role_changes.append(field),
        on_refresh_runtime_library=lambda: actions.append("refresh_library"),
    )

    assert section.backend_combo.count() >= 2  # OLLAMA, LEMONADE + any additional backends
    assert set(section.lemonade_role_inputs) == {"lemonade_fast_model", "lemonade_complex_model"}

    section.backend_combo.setCurrentText("LEMONADE")
    section.save_button.click()
    section.runtime_library_search.setText("mixtral")
    section.lemonade_role_inputs["lemonade_fast_model"].addItem("mixtral")
    section.lemonade_role_inputs["lemonade_fast_model"].setCurrentText("mixtral")

    assert "LEMONADE" in backend_changes
    assert actions == ["save", "refresh_library"]
    assert "lemonade_fast_model" in role_changes


def test_build_models_route_section_creates_route_and_ops_controls() -> None:
    callbacks: list[str] = []
    section = build_models_route_section(
        mix_route_fields=[
            ("mix_main_route", "MAIN ROUTE"),
            ("mix_sub_route_a", "SPAWNED ROUTE A"),
        ],
        route_modes=["AUTO", "CLAUDE"],
        on_route_changed=lambda: callbacks.append("route_changed"),
        on_apply_routes=lambda: callbacks.append("apply_routes"),
        on_apply_mix=lambda: callbacks.append("apply_mix"),
        on_toggle_ops=lambda: callbacks.append("toggle_ops"),
        on_download=lambda: callbacks.append("download"),
        on_uninstall=lambda: callbacks.append("uninstall"),
        on_check_health=lambda: callbacks.append("check_health"),
        on_route_mode_changed=lambda _text: callbacks.append("route_mode"),
        on_route_input_changed=lambda _text: callbacks.append("route_input"),
    )

    section.simple_route_combo.addItem("local/qwen2.5:7b")
    section.simple_route_combo.setCurrentText("local/qwen2.5:7b")
    section.route_mode_combo.setCurrentText("CLAUDE")
    section.route_input.setText("Write a summary")
    section.apply_routes_button.click()
    section.apply_mix_button.click()
    section.ops_toggle_button.click()
    section.ops_download_button.click()
    section.ops_uninstall_button.click()
    section.ops_health_button.click()

    assert set(section.mix_route_inputs) == {"mix_main_route", "mix_sub_route_a"}
    assert section.route_preview_label is not None
    assert callbacks.count("route_changed") >= 1
    assert callbacks.count("route_mode") >= 1
    assert callbacks.count("route_input") >= 1
    assert callbacks[-6:] == ["apply_routes", "apply_mix", "toggle_ops", "download", "uninstall", "check_health"]
