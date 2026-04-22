from __future__ import annotations

from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
)

from src.guppy.launcher_application.workflows import list_workflow_specs

from .. import tokens as T


def build_workflow_section(owner, layout, mono) -> None:
    owner._workflow_frame = QFrame()
    owner._workflow_frame.setStyleSheet(
        f"QFrame {{ background: {T.BG1}; border: 1px solid {T.BORDER}; }}"
    )
    workflow_layout = QVBoxLayout(owner._workflow_frame)
    workflow_layout.setContentsMargins(16, 16, 16, 16)
    workflow_layout.setSpacing(12)
    workflow_layout.addWidget(mono("WORKFLOW LOOPS", T.PRIMARY, T.FS_TINY, True))
    workflow_layout.addWidget(
        mono(
            "Launcher-first shortcuts for Morning, acceptance, midday, evening, and overnight operations.",
            T.DIM,
            T.FS_SMALL,
        )
    )

    workflow_row = QHBoxLayout()
    owner._workflow_cb = QComboBox()
    owner._workflow_cb.setStyleSheet(
        f"QComboBox {{ background: {T.BG0}; border: 1px solid {T.BORDER}; color: {T.TEXT};"
        f" font-family: '{T.FF_MONO}'; font-size: {T.FS_SMALL}pt; padding: 4px 8px; }}"
    )
    for recipe in list_workflow_specs(category="workflow_loop"):
        owner._workflow_cb.addItem(recipe.title, recipe.workflow_id)
    owner._workflow_cb.currentIndexChanged.connect(owner._sync_workflow_recipe)
    workflow_row.addWidget(owner._workflow_cb, stretch=1)

    owner._workflow_load_btn = QPushButton("LOAD FIRST CMD")
    owner._workflow_load_btn.setToolTip("Load the first command from the selected workflow into the embedded terminal.")
    owner._workflow_load_btn.clicked.connect(owner._load_workflow_recipe)
    owner._workflow_run_btn = QPushButton("RUN ALL")
    owner._workflow_run_btn.setToolTip("Queue the full selected workflow in the embedded terminal.")
    owner._workflow_run_btn.clicked.connect(owner._run_workflow_recipe)
    for button in (owner._workflow_load_btn, owner._workflow_run_btn):
        button.setStyleSheet(
            f"QPushButton {{ background: {T.BG0}; color: {T.DIM}; border: 1px solid {T.BORDER};"
            f" padding: 4px 10px; font-family: '{T.FF_MONO}'; font-size: {T.FS_TINY}pt; }}"
            f"QPushButton:hover {{ border-color: {T.PRIMARY}; color: {T.PRIMARY}; }}"
        )
        workflow_row.addWidget(button)
    workflow_layout.addLayout(workflow_row)

    owner._workflow_summary_lbl = mono("", T.DIM, T.FS_TINY)
    owner._workflow_summary_lbl.setWordWrap(True)
    workflow_layout.addWidget(owner._workflow_summary_lbl)
    owner._workflow_steps_lbl = mono("", T.PRIMARY_DIM, T.FS_TINY)
    owner._workflow_steps_lbl.setWordWrap(True)
    workflow_layout.addWidget(owner._workflow_steps_lbl)
    owner._workflow_next_step_lbl = mono("", T.DIM, T.FS_TINY)
    owner._workflow_next_step_lbl.setWordWrap(True)
    workflow_layout.addWidget(owner._workflow_next_step_lbl)
    owner._workflow_outcome_lbl = mono("Outcome: waiting for a workflow action.", T.DIM, T.FS_TINY)
    owner._workflow_outcome_lbl.setWordWrap(True)
    workflow_layout.addWidget(owner._workflow_outcome_lbl)
    owner._workflow_status_lbl = mono("Workflow shortcuts ready", T.DIM, T.FS_TINY)
    workflow_layout.addWidget(owner._workflow_status_lbl)
    owner._workflow_evidence_lbl = mono(
        "Evidence: pick a workflow to see command count, shell state, and next checks.",
        T.DIM,
        T.FS_TINY,
    )
    owner._workflow_evidence_lbl.setWordWrap(True)
    workflow_layout.addWidget(owner._workflow_evidence_lbl)
    layout.addWidget(owner._workflow_frame)
    owner._detail_frames.append(owner._workflow_frame)


def build_operator_logs_section(owner, layout, mono) -> None:
    owner._operator_logs_frame = QFrame()
    owner._operator_logs_frame.setObjectName("syslog_term")
    owner._operator_logs_frame.setStyleSheet(
        f"QFrame#syslog_term {{ background-color: {T.BG0}; border: 1px solid {T.BORDER}; }}"
    )
    term_layout = QVBoxLayout(owner._operator_logs_frame)
    term_layout.setContentsMargins(16, 16, 16, 16)
    term_layout.setSpacing(10)

    term_hdr = QHBoxLayout()
    term_hdr.addWidget(mono("OPERATOR LOGS", T.DIM, T.FS_TINY))
    term_hdr.addStretch()
    owner._filter_cb = QComboBox()
    owner._filter_cb.addItems(["ALL", "WARN", "ERROR"])
    owner._filter_cb.setStyleSheet(
        f"QComboBox {{ background: {T.BG1}; border: 1px solid {T.BORDER}; color: {T.TEXT};"
        f" font-family: '{T.FF_MONO}'; font-size: {T.FS_TINY}pt; padding: 2px 6px; }}"
    )
    owner._filter_cb.currentTextChanged.connect(owner._set_log_filter)
    term_hdr.addWidget(owner._filter_cb)
    term_layout.addLayout(term_hdr)

    owner._syslog = QPlainTextEdit()
    owner._syslog.setReadOnly(True)
    owner._syslog.setMinimumHeight(200)
    owner._syslog.setStyleSheet(
        f"QPlainTextEdit {{ background: {T.BG0}; border: 1px solid {T.BORDER}; color: {T.TEXT};"
        f" font-family: '{T.FF_MONO}'; font-size: {T.FS_TINY}pt; }}"
    )
    term_layout.addWidget(owner._syslog)
    layout.addWidget(owner._operator_logs_frame)
    owner._detail_frames.append(owner._operator_logs_frame)


def build_terminal_section(owner, layout, mono) -> None:
    owner._terminal_frame = QFrame()
    owner._terminal_frame.setObjectName("embedded_terminal")
    owner._terminal_frame.setStyleSheet(
        f"QFrame#embedded_terminal {{ background-color: {T.BG0}; border: 1px solid {T.BORDER}; }}"
    )
    terminal_layout = QVBoxLayout(owner._terminal_frame)
    terminal_layout.setContentsMargins(16, 14, 16, 14)
    terminal_layout.setSpacing(12)

    terminal_hdr = QHBoxLayout()
    terminal_hdr.addWidget(mono("EMBEDDED TERMINAL", T.DIM, T.FS_TINY))
    terminal_hdr.addStretch()
    owner._terminal_status_lbl = mono("Shell idle", T.DIM, T.FS_TINY)
    terminal_hdr.addWidget(owner._terminal_status_lbl)
    terminal_layout.addLayout(terminal_hdr)

    owner._terminal_output = QPlainTextEdit()
    owner._terminal_output.setReadOnly(True)
    owner._terminal_output.setMinimumHeight(200)
    owner._terminal_output.setStyleSheet(
        f"QPlainTextEdit {{ background: {T.BG0}; border: 1px solid {T.BORDER}; color: {T.TEXT};"
        f" font-family: '{T.FF_MONO}'; font-size: {T.FS_TINY}pt; }}"
    )
    terminal_layout.addWidget(owner._terminal_output)

    terminal_input_row = QHBoxLayout()
    owner._terminal_input = QLineEdit()
    owner._terminal_input.setPlaceholderText("Enter a PowerShell command to run inside the launcher terminal")
    owner._terminal_input.returnPressed.connect(owner._submit_terminal_command)
    owner._terminal_input.setStyleSheet(
        f"QLineEdit {{ background: {T.BG1}; border: 1px solid {T.BORDER}; color: {T.TEXT};"
        f" font-family: '{T.FF_MONO}'; font-size: {T.FS_TINY}pt; padding: 4px 8px; }}"
    )
    terminal_input_row.addWidget(owner._terminal_input, stretch=1)

    owner._terminal_run_btn = QPushButton("RUN")
    owner._terminal_run_btn.setToolTip("Run the current PowerShell command in the embedded terminal.")
    owner._terminal_run_btn.clicked.connect(owner._submit_terminal_command)
    owner._terminal_clear_btn = QPushButton("CLEAR")
    owner._terminal_clear_btn.setToolTip("Clear the terminal output pane.")
    owner._terminal_clear_btn.clicked.connect(owner._terminal_output.clear)
    owner._terminal_stop_btn = QPushButton("STOP")
    owner._terminal_stop_btn.setToolTip("Stop the currently running terminal command.")
    owner._terminal_stop_btn.clicked.connect(owner._stop_terminal_process)
    for button in (owner._terminal_run_btn, owner._terminal_clear_btn, owner._terminal_stop_btn):
        button.setStyleSheet(
            f"QPushButton {{ background: {T.BG1}; color: {T.DIM}; border: 1px solid {T.BORDER};"
            f" padding: 4px 10px; font-family: '{T.FF_MONO}'; font-size: {T.FS_TINY}pt; }}"
            f"QPushButton:hover {{ border-color: {T.PRIMARY}; color: {T.PRIMARY}; }}"
        )
        terminal_input_row.addWidget(button)
    terminal_layout.addLayout(terminal_input_row)
    layout.addWidget(owner._terminal_frame)
    owner._detail_frames.append(owner._terminal_frame)
