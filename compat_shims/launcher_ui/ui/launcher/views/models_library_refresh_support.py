from __future__ import annotations

import os
from typing import Any

from src.guppy.launcher_application.models_presenter import build_models_active_identity_text

from .models_runtime_support import normalize_runtime_backend
from .models_runtime_workers import LocalRuntimeFetchThread
from .models_sections import _ModelCard


def refresh_local_runtime_library(owner: Any) -> None:
    owner._refresh_btn.setEnabled(False)
    owner._refresh_btn.setText("FETCHING...")
    owner._store_runtime_endpoint_for_backend(
        owner._local_runtime_backend,
        owner._lemonade_base_url_input.text().strip(),
    )
    owner._fetch_thread = LocalRuntimeFetchThread(
        owner._local_runtime_backend,
        owner._runtime_endpoint_for_backend(owner._local_runtime_backend),
        owner,
    )
    owner._fetch_thread.finished.connect(owner._on_local_result)
    owner._fetch_thread.start()


def _empty_library_hint(backend: str) -> str:
    if backend == "lemonade":
        return "Pull a Lemonade GGUF model and click REFRESH."
    if backend == "lmstudio":
        return "Turn on the LM Studio local server and click REFRESH."
    if backend == "local_harness":
        return "Start the local harness and click REFRESH."
    return "Start Ollama and click REFRESH."


def on_local_runtime_result(owner: Any, payload: dict[str, Any]) -> None:
    owner._refresh_btn.setEnabled(True)
    owner._refresh_btn.setText("REFRESH")
    backend = normalize_runtime_backend(str(payload.get("backend", owner._local_runtime_backend)))
    models = payload.get("models", [])
    error = str(payload.get("error", "") or "").strip()
    for card in owner._local_cards:
        section = getattr(card, "_library_section", "installed")
        section_layout = owner._local_section_layouts.get(section)
        if section_layout is not None:
            section_layout.removeWidget(card)
        card.deleteLater()
    owner._local_cards.clear()
    for key in owner._local_section_cards:
        owner._local_section_cards[key] = []
    if owner._local_placeholder:
        owner._local_placeholder.setVisible(False)
    if not isinstance(models, list) or not models:
        owner._local_placeholder.setText("No local models found.\n" + _empty_library_hint(backend))
        owner._local_placeholder.setVisible(True)
        for section in owner._local_sections.values():
            section.setVisible(False)
        owner._set_runtime_status(
            f"{backend.upper()} library unavailable: {error}" if error else f"{backend.upper()} library is empty",
            ok=not bool(error),
        )
        owner._sync_runtime_mapping_options()
        owner._apply_library_filter()
        return
    for item in models:
        if not isinstance(item, dict):
            continue
        card = _ModelCard(
            str(item.get("name", "unknown")),
            str(item.get("display", item.get("name", "unknown"))),
            "LOCAL",
            str(item.get("context", "-") or "-"),
            str(item.get("note", "") or ""),
            int(item.get("size", 0) or 0),
        )
        card.mark_active(card._model_name == owner._active_model)
        card.set_active.connect(owner._on_model_selected)
        owner._local_cards.append(card)
    owner._local_placeholder.setVisible(False)
    owner._rebuild_local_sections()
    owner._sync_runtime_mapping_options()
    owner._set_runtime_status(f"{backend.upper()} library refreshed", ok=True)
    owner._apply_library_filter()


def on_model_selected(owner: Any, name: str) -> None:
    owner._active_model = name
    owner._active_lbl.setText(build_models_active_identity_text(name))
    os.environ["GUPPY_LOCAL_MODEL"] = name
    for card in owner._local_cards:
        card.mark_active(card._model_name == name)
    owner._rebuild_local_sections()
    owner._apply_library_filter()
    owner.model_selected.emit(name)
    owner._refresh_library_summary()
