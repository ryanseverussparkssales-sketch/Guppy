from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from .. import tokens as T

_ROOT = Path(__file__).resolve().parent.parent.parent.parent
_CONFIG = _ROOT / "config" / "local_llm" / "models.json"
_BENCHMARK_LATEST = _ROOT / "runtime" / "local_llm_benchmarks" / "latest.json"
_BENCHMARK_HISTORY = _ROOT / "runtime" / "local_llm_benchmarks" / "history.jsonl"
_REVIEWS = _ROOT / "runtime" / "local_llm_benchmarks" / "reviews"
_CHALLENGERS = _ROOT / "runtime" / "runtime_challenger_snapshot.json"


def _read_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def _read_jsonl(path: Path, limit: int = 40) -> list[dict[str, Any]]:
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except Exception:
        return []
    rows: list[dict[str, Any]] = []
    for raw in lines[-limit:]:
        txt = raw.strip()
        if not txt:
            continue
        try:
            item = json.loads(txt)
        except Exception:
            continue
        if isinstance(item, dict):
            rows.append(item)
    return rows


def _slug_label(value: str) -> str:
    return str(value or "").replace("-", " ").replace("_", " ").strip().title() or "-"


class _MetricCard(QFrame):
    def __init__(self, title: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setStyleSheet(f"background-color: {T.BG0}; border: 1px solid {T.BORDER_SOFT}; border-radius: 4px;")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(4)

        badge = QLabel(title)
        badge.setStyleSheet(
            f"color: {T.ACCENT_TEAL}; font-family: '{T.FF_MONO}'; font-size: {T.FS_TINY}pt; letter-spacing: 2px; font-weight: bold;"
        )
        self._value = QLabel("-")
        self._value.setStyleSheet(
            f"color: {T.TEXT}; font-family: '{T.FF_HEAD}'; font-size: {T.FS_TITLE + 2}pt; font-weight: bold;"
        )
        self._detail = QLabel("")
        self._detail.setWordWrap(True)
        self._detail.setStyleSheet(
            f"color: {T.DIM}; font-family: '{T.FF_MONO}'; font-size: {T.FS_TINY}pt;"
        )
        layout.addWidget(badge)
        layout.addWidget(self._value)
        layout.addWidget(self._detail)

    def set_content(self, value: str, detail: str) -> None:
        self._value.setText(value)
        self._detail.setText(detail)


class LocalLLMView(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._cards: dict[str, _MetricCard] = {}
        self._details_visible = False
        self._summary_lbl: QLabel | None = None
        self._decision_lbl: QLabel | None = None
        self._details_btn: QPushButton | None = None
        self._manifest_lbl: QLabel | None = None
        self._benchmark_lbl: QLabel | None = None
        self._review_lbl: QLabel | None = None
        self._challenger_lbl: QLabel | None = None
        self._detail_frames: list[QFrame] = []
        self._footer_lbl: QLabel | None = None
        self._build_ui()
        if QApplication.instance() is not None:
            self.refresh()

    def _build_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        topbar = QFrame()
        topbar.setStyleSheet(f"background-color: {T.BG0}; border-bottom: 1px solid {T.BORDER};")
        top_layout = QHBoxLayout(topbar)
        top_layout.setContentsMargins(28, 0, 28, 0)
        title = QLabel("LOCAL LLM")
        title.setStyleSheet(
            f"color: {T.PRIMARY}; font-family: '{T.FF_HEAD}'; font-size: {T.FS_TITLE}pt; font-weight: bold; letter-spacing: 2px;"
        )
        self._summary_lbl = QLabel("Your current local AI setup at a glance.")
        self._summary_lbl.setStyleSheet(
            f"color: {T.DIM}; font-family: '{T.FF_MONO}'; font-size: {T.FS_TINY}pt; letter-spacing: 1px;"
        )
        self._details_btn = QPushButton("ADVANCED")
        self._details_btn.setFixedHeight(28)
        self._details_btn.setToolTip("Show benchmark history, review backlog, and experiment details")
        self._details_btn.setAccessibleName("Advanced local LLM details")
        self._details_btn.setAccessibleDescription("Shows benchmark and experiment details")
        self._details_btn.clicked.connect(self._toggle_details)
        refresh_btn = QPushButton("REFRESH")
        refresh_btn.setFixedHeight(28)
        refresh_btn.clicked.connect(self.refresh)
        top_layout.addWidget(title)
        top_layout.addStretch()
        top_layout.addWidget(self._summary_lbl)
        top_layout.addSpacing(16)
        top_layout.addWidget(self._details_btn)
        top_layout.addSpacing(8)
        top_layout.addWidget(refresh_btn)
        outer.addWidget(topbar)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        host = QWidget()
        layout = QVBoxLayout(host)
        layout.setContentsMargins(28, 22, 28, 28)
        layout.setSpacing(14)

        cards_row = QHBoxLayout()
        cards_row.setSpacing(12)
        for key, title_text in (
            ("runtime", "RUNTIME"),
            ("benchmarks", "CHECKS"),
            ("memory", "MEMORY"),
            ("reviews", "REVIEWS"),
            ("challengers", "TESTING"),
        ):
            card = _MetricCard(title_text)
            self._cards[key] = card
            cards_row.addWidget(card, stretch=1)
        layout.addLayout(cards_row)

        self._decision_lbl = QLabel("")
        self._decision_lbl.setWordWrap(True)
        self._decision_lbl.setStyleSheet(
            f"color: {T.TEXT}; font-family: '{T.FF_BODY}'; font-size: {T.FS_SMALL}pt; background-color: {T.BG0}; border: 1px solid {T.BORDER}; padding: 12px;"
        )
        layout.addWidget(self._decision_lbl)

        self._manifest_lbl = self._make_section(
            layout,
            "CURRENT SETUP",
            "What Guppy uses by default, what it uses for heavier work, and what stays off the everyday path.",
        )
        self._benchmark_lbl = self._make_section(
            layout,
            "RECENT TEST RESULTS",
            "Raw benchmark notes for comparison and review.",
            detail_only=True,
        )
        self._review_lbl = self._make_section(
            layout,
            "REVIEW BACKLOG",
            "Pending evaluation packets and scoring status.",
            detail_only=True,
        )
        self._challenger_lbl = self._make_section(
            layout,
            "EXPERIMENTS",
            "Runtime and memory options that are still in testing.",
            detail_only=True,
        )

        self._footer_lbl = QLabel(
            "Open MODELS to browse available models, or open RUNTIME to change backend settings. Show details for benchmarks, review backlog, and experimental notes."
        )
        self._footer_lbl.setWordWrap(True)
        self._footer_lbl.setStyleSheet(
            f"color: {T.DIM}; font-family: '{T.FF_MONO}'; font-size: {T.FS_TINY}pt; background-color: {T.BG0}; border: 1px solid {T.BORDER}; padding: 10px;"
        )
        layout.addWidget(self._footer_lbl)
        layout.addStretch(1)

        scroll.setWidget(host)
        outer.addWidget(scroll, stretch=1)
        self._sync_detail_visibility()

    def _make_section(self, root: QVBoxLayout, title: str, subtitle: str, *, detail_only: bool = False) -> QLabel:
        frame = QFrame()
        frame.setStyleSheet(f"background-color: {T.BG0}; border: 1px solid {T.BORDER};")
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(6)

        hdr = QLabel(title)
        hdr.setStyleSheet(
            f"color: {T.PRIMARY}; font-family: '{T.FF_MONO}'; font-size: {T.FS_TINY}pt; letter-spacing: 2px; font-weight: bold;"
        )
        desc = QLabel(subtitle)
        desc.setWordWrap(True)
        desc.setStyleSheet(f"color: {T.DIM}; font-family: '{T.FF_BODY}'; font-size: {T.FS_SMALL}pt;")
        body = QLabel("")
        body.setWordWrap(True)
        body.setTextInteractionFlags(body.textInteractionFlags() | body.textInteractionFlags())
        body.setStyleSheet(
            f"color: {T.TEXT}; font-family: '{T.FF_MONO}'; font-size: {T.FS_TINY}pt; line-height: 1.4;"
        )
        layout.addWidget(hdr)
        layout.addWidget(desc)
        layout.addWidget(body)
        root.addWidget(frame)
        if detail_only:
            self._detail_frames.append(frame)
        return body

    def _toggle_details(self) -> None:
        self._details_visible = not self._details_visible
        self._sync_detail_visibility()

    def _sync_detail_visibility(self) -> None:
        for frame in self._detail_frames:
            frame.setVisible(self._details_visible)
        if self._details_btn is not None:
            self._details_btn.setText("LESS ADVANCED" if self._details_visible else "ADVANCED")
            self._details_btn.setToolTip(
                "Hide benchmark history, review backlog, and experiment details"
                if self._details_visible
                else "Show benchmark history, review backlog, and experiment details"
            )
        if self._footer_lbl is not None:
            self._footer_lbl.setText(
                "Open MODELS to browse models, and open RUNTIME for backend settings. Details are open, so you are also seeing benchmarks and experimental notes."
                if self._details_visible
                else "Open MODELS to browse available models, or open RUNTIME to change backend settings. Show details for benchmarks, review backlog, and experimental notes."
            )

    def refresh(self) -> None:
        manifest = _read_json(_CONFIG)
        latest = _read_json(_BENCHMARK_LATEST)
        challenger = _read_json(_CHALLENGERS)
        history = _read_jsonl(_BENCHMARK_HISTORY)
        review_packets = sorted(_REVIEWS.glob("*.human_review_packet.json"))

        baseline_models = manifest.get("baseline_models", []) if isinstance(manifest.get("baseline_models"), list) else []
        runtime_cfg = manifest.get("runtime", {}) if isinstance(manifest.get("runtime"), dict) else {}
        memory_cfg = manifest.get("memory", {}) if isinstance(manifest.get("memory"), dict) else {}
        records = latest.get("records", []) if isinstance(latest.get("records"), list) else []

        success = int(latest.get("successful_cases", 0) or 0)
        total = int(latest.get("total_cases", 0) or 0)
        history_backends = sorted(
            {
                str(item.get("runtime_backend", "")).strip()
                for item in history
                if str(item.get("runtime_backend", "")).strip()
            }
        )
        review_ready = len(review_packets)
        latest_memory = str(latest.get("memory_backend", memory_cfg.get("baseline_backend", "semantic-sqlite")) or "semantic-sqlite").strip()
        latest_runtime = str(latest.get("runtime_backend", runtime_cfg.get("baseline_backend", "ollama")) or "ollama").strip()

        recommended = challenger.get("recommended_next", {}) if isinstance(challenger.get("recommended_next"), dict) else {}
        runtime_challengers = challenger.get("challengers", []) if isinstance(challenger.get("challengers"), list) else []

        self._cards["runtime"].set_content(
            latest_runtime.upper(),
            f"Baseline {str(runtime_cfg.get('baseline_backend', 'ollama')).upper()} | seen: {', '.join(history_backends) or 'none'}",
        )
        self._cards["benchmarks"].set_content(
            f"{success}/{total}",
            f"{len(records)} records in latest run | {len(history)} recent history entries",
        )
        self._cards["memory"].set_content(
            _slug_label(latest_memory),
            f"Baseline {_slug_label(str(memory_cfg.get('baseline_backend', 'semantic-sqlite')))}",
        )
        self._cards["reviews"].set_content(
            str(review_ready),
            "Human-review packets ready in runtime/local_llm_benchmarks/reviews",
        )
        self._cards["challengers"].set_content(
            str(len(runtime_challengers)),
            f"Next: {recommended.get('benchmark_first', '-')} / {recommended.get('integration_first', '-')}",
        )

        if self._summary_lbl is not None:
            self._summary_lbl.setText(
                f"Using qwen3:8b on Ollama | memory {_slug_label(latest_memory)} | latest check {success}/{total}"
            )

        daily_candidate = "-"
        daily_note = ""
        heavy_candidate = "-"
        rejected_models: list[str] = []
        for item in manifest.get("challenger_models", []) if isinstance(manifest.get("challenger_models"), list) else []:
            if not isinstance(item, dict):
                continue
            status = str(item.get("status", "") or "").strip().lower()
            model_id = str(item.get("id", "-") or "-").strip()
            notes = str(item.get("notes", "") or "").strip()
            if status == "promotion_candidate" and daily_candidate == "-":
                daily_candidate = model_id
                daily_note = notes
            elif status == "heavy_lane_candidate" and heavy_candidate == "-":
                heavy_candidate = model_id
            elif status == "daily_lane_rejected":
                rejected_models.append(model_id)

        if self._decision_lbl is not None:
            decision_parts = [
                f"{daily_candidate} is the everyday local model on {latest_runtime.upper()}."
                if daily_candidate != "-"
                else f"{latest_runtime.upper()} is still the main local runtime.",
                f"{heavy_candidate} stays available for slower, heavier requests." if heavy_candidate != "-" else "",
                f"Not recommended for everyday use: {', '.join(rejected_models)}." if rejected_models else "",
                daily_note if daily_note else "",
            ]
            self._decision_lbl.setText(" ".join(part for part in decision_parts if part))

        manifest_lines = [
            f"Default chat model: {daily_candidate} on {str(runtime_cfg.get('baseline_backend', 'ollama')).upper()}",
            f"Memory system: {_slug_label(str(memory_cfg.get('baseline_backend', 'semantic-sqlite')))}",
            f"Heavier fallback: {heavy_candidate}" if heavy_candidate != "-" else "Heavier fallback: none selected yet",
            f"Everyday-use rejects: {', '.join(rejected_models)}" if rejected_models else "Everyday-use rejects: none listed",
        ]
        if daily_note:
            manifest_lines.append(f"Why: {daily_note}")
        if self._details_visible:
            manifest_lines.append("")
            manifest_lines.append("Other baseline roles still wired:")
        for item in baseline_models:
            if not isinstance(item, dict):
                continue
            if self._details_visible:
                manifest_lines.append(
                    f"- {str(item.get('id', '-'))}: {str(item.get('role', '-'))} | {str(item.get('latency_class', '-'))} | {str(item.get('selection_reason', '')).strip()}"
                )
        if self._manifest_lbl is not None:
            self._manifest_lbl.setText("\n".join(manifest_lines) if manifest_lines else "No baseline fleet manifest found.")

        benchmark_lines = [
            f"- Timestamp: {str(latest.get('timestamp_utc', '-'))}",
            f"- Prompt file: {str(latest.get('prompt_file', '-'))}",
            f"- Successful cases: {success}/{total}",
        ]
        if records:
            durations = [float(record.get("duration_ms", 0.0) or 0.0) for record in records if float(record.get("duration_ms", 0.0) or 0.0) > 0]
            if durations:
                benchmark_lines.append(
                    f"- Duration band: {min(durations):.0f}ms to {max(durations):.0f}ms"
                )
            for record in records[:4]:
                benchmark_lines.append(
                    f"- {_slug_label(str(record.get('track', '-')))} -> {str(record.get('resolved_tag', record.get('requested_tag', '-')))}"
                )
        if self._benchmark_lbl is not None:
            self._benchmark_lbl.setText("\n".join(benchmark_lines))

        review_lines = [
            f"- Pending packets: {review_ready}",
            "- Review fields: review_score, notes, reviewer",
        ]
        for packet in review_packets[:5]:
            payload = _read_json(packet)
            records_payload = payload.get("records", []) if isinstance(payload.get("records"), list) else []
            model_hint = "-"
            if records_payload and isinstance(records_payload[0], dict):
                model_hint = str(records_payload[0].get("requested_tag", records_payload[0].get("resolved_tag", "-")))
            review_lines.append(f"- {packet.name}: {len(records_payload)} prompts | {model_hint}")
        if self._review_lbl is not None:
            self._review_lbl.setText("\n".join(review_lines))

        challenger_lines = [
            f"- Benchmark-first runtime: {str(recommended.get('benchmark_first', '-'))}",
            f"- Integration-first runtime: {str(recommended.get('integration_first', '-'))}",
            f"- Research track: {str(recommended.get('research_track', '-'))}",
            f"- Memory baseline: {_slug_label(str(memory_cfg.get('baseline_backend', 'semantic-sqlite')))}",
        ]
        for item in memory_cfg.get("backend_challengers", []) if isinstance(memory_cfg.get("backend_challengers"), list) else []:
            if not isinstance(item, dict):
                continue
            challenger_lines.append(
                f"- Memory challenger {str(item.get('id', '-'))}: {str(item.get('status', '-'))} | {str(item.get('notes', '')).strip()}"
            )
        for item in runtime_challengers[:3]:
            if not isinstance(item, dict):
                continue
            challenger_lines.append(
                f"- Runtime challenger {str(item.get('id', '-'))}: {str(item.get('host_fit', item.get('status', '-')))} | {str(item.get('notes', '')).strip()}"
            )
        if self._challenger_lbl is not None:
            self._challenger_lbl.setText("\n".join(challenger_lines))
