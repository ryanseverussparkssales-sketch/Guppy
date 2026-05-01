from __future__ import annotations

from PySide6.QtWidgets import QLabel, QPushButton

from .. import tokens as T


def set_selected_runtime_role(owner, field_name: str, role_fields: list[tuple[str, str]]) -> None:
    owner._selected_runtime_role_field = field_name if field_name in owner._lemonade_role_inputs else "lemonade_fast_model"
    label = next((label for key, label in role_fields if key == owner._selected_runtime_role_field), "FAST")
    owner._runtime_library_target_lbl.setText(f"Assigning to {label}")
    refresh_runtime_library(owner)


def assign_runtime_model(owner, model_name: str) -> None:
    combo = owner._lemonade_role_inputs.get(owner._selected_runtime_role_field)
    if combo is None:
        return
    if combo.findText(model_name) < 0:
        combo.addItem(model_name)
    combo.setCurrentText(model_name)
    owner._set_runtime_status(
        f"Selected {model_name} for {owner._runtime_library_target_lbl.text().replace('Assigning to ', '').lower()} role",
        ok=True,
    )
    owner._refresh_runtime_summary()
    refresh_runtime_library(owner)


def refresh_runtime_library(owner) -> None:
    if not hasattr(owner, "_runtime_library_grid"):
        return
    while owner._runtime_library_grid.count():
        item = owner._runtime_library_grid.takeAt(0)
        if item is None:
            continue
        widget = item.widget()
        if widget is not None:
            widget.deleteLater()
    owner._runtime_library_buttons = []
    if owner._local_runtime_backend != "lemonade":
        owner._runtime_library_summary_lbl.setText("Switch to Lemonade to browse downloaded GGUF models here.")
        return
    query = owner._runtime_library_search.text().strip().lower()
    assigned: list[str] = []
    for combo in owner._lemonade_role_inputs.values():
        value = combo.currentText().strip()
        if value and value not in assigned:
            assigned.append(value)
    available = [name for name in owner._available_local_model_names() if not query or query in name.lower()]
    owner._runtime_library_summary_lbl.setText(
        ("Assigned now: " + ", ".join(assigned[:4]) if assigned else "Assigned now: none")
        + f" | Downloaded models: {len(owner._available_local_model_names())}"
        + (f" | Filtered: {len(available)}" if query else "")
        + " | Click a model to drop it into the selected role."
    )
    if not available:
        empty = QLabel("No downloaded models match this search yet.")
        empty.setStyleSheet(
            f"color: {T.DIM}; font-family: '{T.FF_MONO}'; font-size: {T.FS_TINY}pt; padding: 4px 0;"
        )
        owner._runtime_library_grid.addWidget(empty, 0, 0)
        return
    for index, model_name in enumerate(available):
        button = QPushButton(model_name)
        is_assigned = model_name in assigned
        accent = T.ACCENT_ORANGE if is_assigned else T.DIM
        button.setStyleSheet(
            f"QPushButton {{ background: {T.BG0}; color: {accent}; border: 1px solid {accent if is_assigned else T.BORDER_SOFT}; border-radius: 4px;"
            f" padding: 5px 8px; font-family: '{T.FF_MONO}'; font-size: {T.FS_TINY}pt; text-align: left; }}"
            f"QPushButton:hover {{ border-color: {T.ACCENT_ORANGE}; color: {T.ACCENT_ORANGE}; }}"
        )
        button.clicked.connect(lambda _=False, selected_model=model_name: owner._assign_runtime_model(selected_model))
        row = index // 3
        col = index % 3
        owner._runtime_library_grid.addWidget(button, row, col)
        owner._runtime_library_buttons.append(button)
