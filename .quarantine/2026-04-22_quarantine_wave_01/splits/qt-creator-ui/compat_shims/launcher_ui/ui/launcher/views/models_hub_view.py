from __future__ import annotations

from typing import Callable

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from .. import tokens as T


_OUTER_MARGIN_X = 28
_OUTER_MARGIN_TOP = 22
_OUTER_MARGIN_BOTTOM = 26
_OUTER_SPACING = 14
_TAB_MIN_HEIGHT = 36
_CARD_RADIUS = 16


def _mono(text: str, color: str = T.DIM, size: int = T.FS_SMALL, bold: bool = False) -> QLabel:
    label = QLabel(text)
    label.setWordWrap(True)
    label.setStyleSheet(
        f"color: {color}; font-family: '{T.FF_MONO}'; font-size: {size}pt; letter-spacing: 1px;"
        + (" font-weight: bold;" if bold else "")
    )
    return label


def _tab_button_style(active: bool) -> str:
    if active:
        return (
            f"QPushButton {{ background: {T.INK}; color: {T.BG}; border: 1px solid {T.INK}; "
            f"border-radius: 12px; padding: 8px 12px; font-family: '{T.FF_MONO}'; font-size: {T.FS_TINY}pt; }}"
        )
    return (
        f"QPushButton {{ background: {T.BG0}; color: {T.DIM}; border: 1px solid {T.BORDER}; "
        f"border-radius: 12px; padding: 8px 12px; font-family: '{T.FF_MONO}'; font-size: {T.FS_TINY}pt; }}"
        f"QPushButton:hover {{ color: {T.PRIMARY}; border-color: {T.PRIMARY}; }}"
    )


class _ModelOpsTab(QWidget):
    def __init__(
        self,
        heading: str,
        action_label: str,
        description: str,
        *,
        on_execute: Callable[[str], None],
        on_refresh_status: Callable[[], str],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._on_execute = on_execute
        self._on_refresh_status = on_refresh_status

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(_OUTER_SPACING)

        hero = QFrame()
        hero.setStyleSheet(f"QFrame {{ background: {T.BG1}; border: 1px solid {T.BORDER}; border-radius: {_CARD_RADIUS}px; }}")
        hero_layout = QVBoxLayout(hero)
        hero_layout.setContentsMargins(18, 14, 18, 14)
        hero_layout.setSpacing(8)
        hero_layout.addWidget(_mono(heading, T.PRIMARY, T.FS_TINY, True))
        hero_layout.addWidget(_mono(description, T.TEXT, T.FS_SMALL))
        hero_layout.addWidget(
            _mono(
                "Install/uninstall actions run through Ollama. Use Model Sourcing for LM Studio, harness, or Lemonade lanes.",
                T.DIM,
                T.FS_TINY,
            )
        )
        layout.addWidget(hero)

        action_frame = QFrame()
        action_frame.setStyleSheet(f"QFrame {{ background: {T.BG0}; border: 1px solid {T.BORDER}; border-radius: {_CARD_RADIUS}px; }}")
        action_frame.setMinimumHeight(188)
        action_layout = QVBoxLayout(action_frame)
        action_layout.setContentsMargins(18, 14, 18, 14)
        action_layout.setSpacing(10)
        action_layout.addWidget(_mono("MODEL NAME", T.TEXT, T.FS_TINY, True))
        self._model_input = QLineEdit()
        self._model_input.setMinimumHeight(38)
        self._model_input.setPlaceholderText("Example: qwen3:8b")
        self._model_input.setToolTip("Type the Ollama model name exactly as it should be installed or removed.")
        action_layout.addWidget(self._model_input)

        button_row = QHBoxLayout()
        button_row.setSpacing(10)
        self._run_btn = QPushButton(action_label)
        self._run_btn.setMinimumHeight(38)
        self._run_btn.setToolTip(description)
        self._run_btn.clicked.connect(self._run)
        self._refresh_btn = QPushButton("REFRESH STATUS")
        self._refresh_btn.setMinimumHeight(38)
        self._refresh_btn.setToolTip("Refresh the live status text from the runtime controls.")
        self._refresh_btn.clicked.connect(self._sync_status)
        button_row.addWidget(self._run_btn)
        button_row.addWidget(self._refresh_btn)
        button_row.addStretch(1)
        action_layout.addLayout(button_row)

        self._status_lbl = _mono("Ready.", T.DIM, T.FS_SMALL)
        self._status_lbl.setToolTip("Latest model operation status.")
        action_layout.addWidget(self._status_lbl)
        layout.addWidget(action_frame)
        layout.addStretch(1)

    def _run(self) -> None:
        model_name = self._model_input.text().strip()
        if not model_name:
            self._status_lbl.setText("Enter a model name first.")
            return
        self._on_execute(model_name)
        self._status_lbl.setText(f"Started task for {model_name}.")
        self._sync_status()

    def _sync_status(self) -> None:
        text = self._on_refresh_status().strip()
        if text:
            self._status_lbl.setText(text)


class _ModelSourcingTab(QWidget):
    def __init__(
        self,
        *,
        on_save: Callable[[str, str], None],
        on_refresh: Callable[[str], None],
        on_state: Callable[[], tuple[str, str, str]],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._on_save = on_save
        self._on_refresh = on_refresh
        self._on_state = on_state

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(_OUTER_SPACING)

        summary = QFrame()
        summary.setStyleSheet(f"QFrame {{ background: {T.BG1}; border: 1px solid {T.BORDER}; border-radius: {_CARD_RADIUS}px; }}")
        summary_layout = QVBoxLayout(summary)
        summary_layout.setContentsMargins(18, 14, 18, 14)
        summary_layout.setSpacing(8)
        summary_layout.addWidget(_mono("MODEL SOURCING", T.PRIMARY, T.FS_TINY, True))
        summary_layout.addWidget(
            _mono(
                "Pick the local model lane and endpoint for this workspace.",
                T.TEXT,
                T.FS_SMALL,
            )
        )
        self._summary_lbl = _mono("", T.DIM, T.FS_SMALL)
        summary_layout.addWidget(self._summary_lbl)
        layout.addWidget(summary)

        source_frame = QFrame()
        source_frame.setStyleSheet(f"QFrame {{ background: {T.BG0}; border: 1px solid {T.BORDER}; border-radius: {_CARD_RADIUS}px; }}")
        source_frame.setMinimumHeight(226)
        source_layout = QVBoxLayout(source_frame)
        source_layout.setContentsMargins(18, 14, 18, 14)
        source_layout.setSpacing(10)
        source_layout.addWidget(_mono("LOCAL MODEL SOURCE", T.TEXT, T.FS_TINY, True))
        self._backend_combo = QComboBox()
        self._backend_combo.addItems(["OLLAMA", "LM STUDIO", "LOCAL HARNESS", "LEMONADE"])
        self._backend_combo.setMinimumHeight(38)
        self._backend_combo.setToolTip("Select the local runtime lane Guppy should use for local model discovery.")
        self._backend_combo.currentTextChanged.connect(self._sync_endpoint_placeholder)
        source_layout.addWidget(self._backend_combo)

        source_layout.addWidget(_mono("ENDPOINT", T.TEXT, T.FS_TINY, True))
        self._endpoint_input = QLineEdit()
        self._endpoint_input.setMinimumHeight(38)
        self._endpoint_input.setToolTip("Endpoint Guppy should call for the selected local runtime lane.")
        source_layout.addWidget(self._endpoint_input)

        button_row = QHBoxLayout()
        button_row.setSpacing(10)
        save_btn = QPushButton("SAVE SOURCE")
        save_btn.setMinimumHeight(38)
        save_btn.setToolTip("Save the selected local model source and endpoint.")
        save_btn.clicked.connect(self._save)
        refresh_btn = QPushButton("REFRESH MODELS")
        refresh_btn.setMinimumHeight(38)
        refresh_btn.setToolTip("Reload the available local models using the selected source.")
        refresh_btn.clicked.connect(self._refresh)
        button_row.addWidget(save_btn)
        button_row.addWidget(refresh_btn)
        button_row.addStretch(1)
        source_layout.addLayout(button_row)

        self._status_lbl = _mono("", T.DIM, T.FS_SMALL)
        source_layout.addWidget(self._status_lbl)
        layout.addWidget(source_frame)
        layout.addStretch(1)

        self.sync_from_models()

    def _sync_endpoint_placeholder(self) -> None:
        placeholders = {
            "OLLAMA": "http://127.0.0.1:11434",
            "LM STUDIO": "http://127.0.0.1:1234/v1",
            "LOCAL HARNESS": "http://127.0.0.1:8001",
            "LEMONADE": "http://localhost:13305/api/v1",
        }
        backend = self._backend_combo.currentText().strip().upper()
        self._endpoint_input.setPlaceholderText(placeholders.get(backend, "http://127.0.0.1:11434"))

    def sync_from_models(self) -> None:
        backend, endpoint, summary = self._on_state()
        options = {
            "ollama": "OLLAMA",
            "lmstudio": "LM STUDIO",
            "local_harness": "LOCAL HARNESS",
            "lemonade": "LEMONADE",
        }
        self._backend_combo.blockSignals(True)
        self._backend_combo.setCurrentText(options.get(backend, "OLLAMA"))
        self._backend_combo.blockSignals(False)
        self._sync_endpoint_placeholder()
        self._endpoint_input.setText(endpoint)
        self._summary_lbl.setText(summary)
        self._status_lbl.setText(f"Current source: {options.get(backend, 'OLLAMA')}")

    def _save(self) -> None:
        backend = self._backend_combo.currentText().strip().lower().replace(" ", "_")
        endpoint = self._endpoint_input.text().strip()
        self._on_save(backend, endpoint)
        self._status_lbl.setText(f"Saved {self._backend_combo.currentText().strip()} source.")
        self.sync_from_models()

    def _refresh(self) -> None:
        backend = self._backend_combo.currentText().strip().lower().replace(" ", "_")
        self._on_refresh(backend)
        self._status_lbl.setText(f"Refreshing models from {self._backend_combo.currentText().strip()}.")
        self.sync_from_models()


class ModelsHubView(QWidget):
    model_selected = Signal(str)
    runtime_settings_saved = Signal(dict)
    bindings_changed = Signal(dict)

    def __init__(
        self,
        models_view: QWidget,
        local_llm_panel: QWidget,
        voice_panel: QWidget,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._models_view = models_view
        self._local_llm_panel = local_llm_panel
        self._voice_panel = voice_panel
        self._tab_buttons: dict[str, QPushButton] = {}
        self._content_layout: QVBoxLayout | None = None
        self._content_title: QLabel | None = None
        self._content_note: QLabel | None = None
        self._active_tab = "status"
        self._install_page: _ModelOpsTab | None = None
        self._uninstall_page: _ModelOpsTab | None = None
        self._sourcing_page: _ModelSourcingTab | None = None
        set_mode = getattr(self._models_view, "_set_page_mode", None)
        if callable(set_mode):
            set_mode("hub")
        self._wire_child_signals()
        self._build_ui()

    def _wire_child_signals(self) -> None:
        model_selected = getattr(self._models_view, "model_selected", None)
        if model_selected is not None:
            model_selected.connect(self.model_selected.emit)
        runtime_settings_saved = getattr(self._models_view, "runtime_settings_saved", None)
        if runtime_settings_saved is not None:
            runtime_settings_saved.connect(self.runtime_settings_saved.emit)
        bindings_changed = getattr(self._voice_panel, "bindings_changed", None)
        if bindings_changed is not None:
            bindings_changed.connect(self.bindings_changed.emit)

    def _build_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(_OUTER_MARGIN_X, _OUTER_MARGIN_TOP, _OUTER_MARGIN_X, _OUTER_MARGIN_BOTTOM)
        outer.setSpacing(_OUTER_SPACING)

        title = QLabel("Models")
        title.setStyleSheet(
            f"color: {T.TEXT}; font-family: '{T.FF_HEAD}'; font-size: 28pt; font-weight: 900; letter-spacing: -1px;"
        )
        outer.addWidget(title)

        purpose = QLabel("MODELS - Pick the model, pick the local runtime, and manage voice in one place.")
        purpose.setObjectName("hub-purpose")
        purpose.setWordWrap(True)
        purpose.setStyleSheet(
            f"color: {T.DIM}; font-family: '{T.FF_MONO}'; font-size: {T.FS_TINY}pt; letter-spacing: 1px;"
        )
        purpose.setToolTip("This hub owns model choice, local model source, and voice routing. Keys and accounts stay in Settings.")
        outer.addWidget(purpose)
        outer.addWidget(
            _mono(
                "Use tabs to focus one job at a time. Keys and accounts stay in Settings.",
                T.DIM,
                T.FS_SMALL,
            )
        )

        tabs_row = QHBoxLayout()
        tabs_row.setSpacing(8)
        for key, label, tooltip in [
            ("status", "Local LLMs Status", "Benchmark and local model readiness status."),
            ("swapping", "Model Swapping", "Choose the active model and the spawned model loadout."),
            ("install", "Model Installation", "Install an Ollama model from a focused tab."),
            ("uninstall", "Model Uninstallation", "Remove an Ollama model from a focused tab."),
            ("sourcing", "Model Sourcing", "Choose Ollama, LM Studio, the local harness, or Lemonade."),
            ("voice", "Voice", "Manage text-to-speech and speech-to-text routing."),
        ]:
            button = QPushButton(label.upper())
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.setMinimumHeight(_TAB_MIN_HEIGHT)
            button.setToolTip(tooltip)
            button.clicked.connect(lambda _=False, target=key: self._set_active_tab(target))
            self._tab_buttons[key] = button
            tabs_row.addWidget(button)
        tabs_row.addStretch(1)
        outer.addLayout(tabs_row)

        content_frame = QFrame()
        content_frame.setStyleSheet(f"QFrame {{ background: {T.BG1}; border: 1px solid {T.BORDER}; border-radius: {_CARD_RADIUS + 2}px; }}")
        content_frame.setMinimumHeight(520)
        content_layout = QVBoxLayout(content_frame)
        content_layout.setContentsMargins(22, 18, 22, 20)
        content_layout.setSpacing(10)
        self._content_title = QLabel("")
        self._content_title.setStyleSheet(
            f"color: {T.TEXT}; font-family: '{T.FF_HEAD}'; font-size: {T.FS_TITLE + 1}pt; font-weight: 800;"
        )
        self._content_note = _mono("", T.DIM, T.FS_SMALL)
        content_layout.addWidget(self._content_title)
        content_layout.addWidget(self._content_note)
        self._content_layout = content_layout
        outer.addWidget(content_frame, stretch=1)

        self._install_page = _ModelOpsTab(
            "MODEL INSTALLATION",
            "INSTALL MODEL",
            "Install a named Ollama model without dropping into the full runtime controls.",
            on_execute=lambda model: self._run_model_operation("pull", model),
            on_refresh_status=self._model_operation_status,
        )
        self._uninstall_page = _ModelOpsTab(
            "MODEL UNINSTALLATION",
            "UNINSTALL MODEL",
            "Remove a named Ollama model from this machine without hunting through a long form.",
            on_execute=lambda model: self._run_model_operation("rm", model),
            on_refresh_status=self._model_operation_status,
        )
        self._sourcing_page = _ModelSourcingTab(
            on_save=self._save_model_source,
            on_refresh=self._refresh_model_source,
            on_state=self._model_source_state,
        )
        self._set_active_tab("status")

    def _clear_content(self) -> None:
        if self._content_layout is None:
            return
        while self._content_layout.count() > 2:
            item = self._content_layout.takeAt(2)
            widget = item.widget()
            if widget is not None:
                widget.setParent(None)

    def _set_active_tab(self, tab: str) -> None:
        self._active_tab = tab
        for key, button in self._tab_buttons.items():
            button.setStyleSheet(_tab_button_style(key == tab))

        configs = {
            "status": (
                "Local LLMs Status",
                "See what is installed, what has been benchmarked, and what is still experimental.",
                self._local_llm_panel,
            ),
            "swapping": (
                "Model Swapping",
                "Choose the main model, the two spawned secondary models, and the current session model.",
                self._models_view,
            ),
            "install": (
                "Model Installation",
                "Use a focused install panel instead of digging through a tall mixed-purpose screen.",
                self._install_page,
            ),
            "uninstall": (
                "Model Uninstallation",
                "Remove local Ollama models from a clean dedicated panel.",
                self._uninstall_page,
            ),
            "sourcing": (
                "Model Sourcing",
                "Point Guppy at Ollama, LM Studio, the local harness, or Lemonade and save the endpoint cleanly.",
                self._sourcing_page,
            ),
            "voice": (
                "Voice",
                "Keep voice routing under Models so the chosen model and the chosen voice path stay together.",
                self._voice_panel,
            ),
        }
        title, note, widget = configs.get(tab, configs["status"])
        if self._content_title is not None:
            self._content_title.setText(title)
        if self._content_note is not None:
            self._content_note.setText(note)

        if tab == "swapping":
            set_mode = getattr(self._models_view, "_set_page_mode", None)
            if callable(set_mode):
                set_mode("hub")
        if tab == "sourcing" and self._sourcing_page is not None:
            self._sourcing_page.sync_from_models()
        if tab in {"install", "uninstall"}:
            set_mode = getattr(self._models_view, "_set_page_mode", None)
            if callable(set_mode):
                set_mode("runtime")

        self._clear_content()
        if self._content_layout is not None and widget is not None:
            self._content_layout.addWidget(widget, stretch=1)

    def _run_model_operation(self, operation: str, model_name: str) -> None:
        model_input = getattr(self._models_view, "_ops_model_input", None)
        if isinstance(model_input, QLineEdit):
            model_input.setText(model_name)
        runner = getattr(self._models_view, "_run_ollama_model_op", None)
        if callable(runner):
            runner(operation)

    def _model_operation_status(self) -> str:
        status_label = getattr(self._models_view, "_ops_status_lbl", None)
        text_getter = getattr(status_label, "text", None)
        return str(text_getter() or "").strip() if callable(text_getter) else ""

    def _model_source_state(self) -> tuple[str, str, str]:
        backend = str(getattr(self._models_view, "_local_runtime_backend", "ollama"))
        endpoint_resolver = getattr(self._models_view, "_runtime_endpoint_for_backend", None)
        endpoint = endpoint_resolver(backend) if callable(endpoint_resolver) else ""
        summary_label = getattr(self._models_view, "_runtime_summary_lbl", None)
        summary_getter = getattr(summary_label, "text", None)
        summary = str(summary_getter() or "").strip() if callable(summary_getter) else ""
        return backend, endpoint, summary

    def _save_model_source(self, backend: str, endpoint: str) -> None:
        normalized = str(backend or "").strip().lower()
        normalizer = getattr(self._models_view, "_normalize_runtime_backend", None)
        if callable(normalizer):
            normalized = normalizer(normalized)
        backend_combo = getattr(self._models_view, "_runtime_backend_cb", None)
        if isinstance(backend_combo, QComboBox):
            display = {
                "ollama": "OLLAMA",
                "lmstudio": "LM STUDIO",
                "local_harness": "LOCAL HARNESS",
                "lemonade": "LEMONADE",
            }.get(normalized, "OLLAMA")
            backend_combo.setCurrentText(display)
        input_box = getattr(self._models_view, "_lemonade_base_url_input", None)
        if isinstance(input_box, QLineEdit):
            input_box.setText(endpoint)
        endpoint_store = getattr(self._models_view, "_store_runtime_endpoint_for_backend", None)
        if callable(endpoint_store):
            endpoint_store(normalized, endpoint)
        setattr(self._models_view, "_local_runtime_backend", normalized)
        update_controls = getattr(self._models_view, "_update_runtime_controls", None)
        if callable(update_controls):
            update_controls()
        saver = getattr(self._models_view, "_save_runtime_settings", None)
        if callable(saver):
            saver()

    def _refresh_model_source(self, backend: str) -> None:
        self._save_model_source(backend, self._model_source_state()[1])
        refresher = getattr(self._models_view, "_refresh", None)
        if callable(refresher):
            refresher()

    def set_status_snapshot(self, payload: dict) -> None:
        setter = getattr(self._models_view, "set_status_snapshot", None)
        if callable(setter):
            setter(payload)
        if self._sourcing_page is not None:
            self._sourcing_page.sync_from_models()

    def refresh_voice_assignments(self) -> None:
        load_options = getattr(self._voice_panel, "_load_assignment_options", None)
        if callable(load_options):
            load_options()
        refresh_bindings = getattr(self._voice_panel, "_refresh_bindings_summary", None)
        if callable(refresh_bindings):
            refresh_bindings()
        refresh_evidence = getattr(self._voice_panel, "_refresh_voice_evidence", None)
        if callable(refresh_evidence):
            refresh_evidence()
