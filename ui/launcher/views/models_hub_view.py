from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QLabel,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from .. import tokens as T


def _mono(text: str, color: str = T.DIM, size: int = T.FS_SMALL, bold: bool = False) -> QLabel:
    label = QLabel(text)
    label.setWordWrap(True)
    label.setStyleSheet(
        f"color: {color}; font-family: '{T.FF_MONO}'; font-size: {size}pt; letter-spacing: 1px;"
        + (" font-weight: bold;" if bold else "")
    )
    return label


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
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")

        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(24, 20, 24, 24)
        layout.setSpacing(16)

        title = QLabel("Models Hub")
        title.setStyleSheet(
            f"color: {T.TEXT}; font-family: '{T.FF_HEAD}'; font-size: 28pt; font-weight: 900; letter-spacing: -1px;"
        )
        layout.addWidget(title)
        purpose = QLabel("MODELS — Choose your AI model, configure local LLMs, and manage voice settings.")
        purpose.setObjectName("hub-purpose")
        purpose.setWordWrap(True)
        purpose.setStyleSheet(
            f"color: {T.DIM}; font-family: '{T.FF_MONO}'; font-size: {T.FS_TINY}pt; letter-spacing: 1px;"
        )
        layout.addWidget(purpose)
        layout.addWidget(
            _mono(
                "Unified model ownership: local model library, main/sub loadouts, runtime routing, local LLM evidence, and voice flows now live here. "
                "Provider accounts and API-key storage remain unified in Settings.",
                T.DIM,
                T.FS_SMALL,
            )
        )

        overview = QFrame()
        overview.setStyleSheet(f"QFrame {{ background: {T.BG1}; border: 1px solid {T.BORDER}; }}")
        overview_layout = QVBoxLayout(overview)
        overview_layout.setContentsMargins(16, 14, 16, 14)
        overview_layout.setSpacing(10)
        overview_layout.addWidget(_mono("SECTION OWNERSHIP", T.PRIMARY, T.FS_TINY, True))
        overview_layout.addWidget(
            _mono(
                "Models owns selection, runtime readiness, sub-agent loadouts, local evidence, and voice routing. Settings still owns account management and secret storage.",
                T.DIM,
                T.FS_SMALL,
            )
        )

        grid = QGridLayout()
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(10)
        items = [
            (
                "Model Library",
                "Choose the session model, keep one stable main model, and pin two spawnable sub models.",
            ),
            (
                "Runtime",
                "Ollama remains the stable default lane. Lemonade is opt-in, LM Studio is discovery-only, and Hugging Face local stays on the planned adapter lane until it is stable.",
            ),
            (
                "Local LLM Evidence",
                "Benchmark receipts, challenger posture, and policy notes stay attached to the model surface instead of Home.",
            ),
            (
                "Voice Stack",
                "Voice flows now sit under Models: Edge, Kokoro, Windows SAPI, and ElevenLabs are live TTS paths; local Whisper STT is already live; Deepgram remains explicitly planned.",
            ),
        ]
        for index, (heading, detail) in enumerate(items):
            card = QFrame()
            card.setStyleSheet(f"QFrame {{ background: {T.BG0}; border: 1px solid {T.BORDER}; }}")
            card_layout = QVBoxLayout(card)
            card_layout.setContentsMargins(12, 12, 12, 12)
            card_layout.setSpacing(8)
            card_layout.addWidget(_mono(heading.upper(), T.TEXT, T.FS_TINY, True))
            card_layout.addWidget(_mono(detail, T.DIM, T.FS_SMALL))
            grid.addWidget(card, index // 2, index % 2)
        overview_layout.addLayout(grid)
        layout.addWidget(overview)

        models_frame = QFrame()
        models_frame.setStyleSheet(f"QFrame {{ background: {T.BG1}; border: 1px solid {T.BORDER}; }}")
        models_layout = QVBoxLayout(models_frame)
        models_layout.setContentsMargins(16, 14, 16, 14)
        models_layout.setSpacing(10)
        models_layout.addWidget(_mono("MODELS + RUNTIME", T.PRIMARY, T.FS_TINY, True))
        models_layout.addWidget(
            _mono(
                "This section owns the live model library, route mix, local-runtime mapping, and main/sub-agent loadout controls.",
                T.DIM,
                T.FS_SMALL,
            )
        )
        models_layout.addWidget(self._models_view)
        layout.addWidget(models_frame)

        local_frame = QFrame()
        local_frame.setStyleSheet(f"QFrame {{ background: {T.BG1}; border: 1px solid {T.BORDER}; }}")
        local_layout = QVBoxLayout(local_frame)
        local_layout.setContentsMargins(16, 14, 16, 14)
        local_layout.setSpacing(10)
        local_layout.addWidget(_mono("LOCAL LLM EVIDENCE", T.PRIMARY, T.FS_TINY, True))
        local_layout.addWidget(
            _mono(
                "Local evidence stays in Models so benchmark outcomes and promotion decisions stay next to the loadout they affect.",
                T.DIM,
                T.FS_SMALL,
            )
        )
        local_layout.addWidget(self._local_llm_panel)
        layout.addWidget(local_frame)

        voice_frame = QFrame()
        voice_frame.setStyleSheet(f"QFrame {{ background: {T.BG1}; border: 1px solid {T.BORDER}; }}")
        voice_layout = QVBoxLayout(voice_frame)
        voice_layout.setContentsMargins(16, 14, 16, 14)
        voice_layout.setSpacing(10)
        voice_layout.addWidget(_mono("VOICE STACK", T.PRIMARY, T.FS_TINY, True))
        voice_layout.addWidget(
            _mono(
                "Integrated now: Edge TTS, Kokoro, Windows SAPI, ElevenLabs, and local Whisper STT. "
                "Planned next: Deepgram voice services once they can share the same stable assignment and readiness contract.",
                T.DIM,
                T.FS_SMALL,
            )
        )
        voice_layout.addWidget(self._voice_panel)
        layout.addWidget(voice_frame)
        layout.addStretch(1)

        scroll.setWidget(content)
        outer.addWidget(scroll)

    def set_status_snapshot(self, payload: dict) -> None:
        setter = getattr(self._models_view, "set_status_snapshot", None)
        if callable(setter):
            setter(payload)

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
