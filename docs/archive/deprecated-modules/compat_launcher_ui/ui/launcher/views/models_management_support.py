from __future__ import annotations

import os
import time
from typing import Any

from src.guppy.experience_config import (
    apply_runtime_settings_to_env as apply_settings_to_env,
    ensure_personalization_scaffold,
    load_provider_registry,
    save_provider_registry,
    save_runtime_settings as save_app_settings,
    validate_provider_registry,
)
from src.guppy.inference.router import resolve_ui_route
from src.guppy.launcher_application.models_presenter import (
    build_models_active_identity_text,
    build_models_loadout_help_text,
    build_models_route_preview_hint_text,
    build_models_route_preview_text,
    build_models_route_summary_text,
    friendly_models_route_target,
)
from src.guppy.launcher_application.models_route_support import (
    latest_runtime_latency,
    parse_fallback_chain,
    route_targets_from_registry,
)

from .. import tokens as T


def sync_runtime_mapping_options(owner) -> None:
    names = owner._available_local_model_names()
    for _field_name, combo in owner._lemonade_role_inputs.items():
        owner._set_combo_items_preserve_text(combo, names, combo.currentText().strip())
    refresh_loadout_inputs(owner)
    refresh_mix_route_inputs(owner)
    owner._refresh_runtime_summary()
    owner._refresh_runtime_library()


def available_route_targets(owner) -> list[str]:
    local_targets = [f"local/{name}" for name in owner._available_local_model_names() if name]
    return sorted(set(owner._route_options + local_targets))


def refresh_mix_route_inputs(owner) -> None:
    options = available_route_targets(owner)
    for _field_name, combo in owner._mix_route_inputs.items():
        current = combo.currentText().strip()
        owner._set_combo_items_preserve_text(combo, options, current)


def load_mix_from_routes(owner) -> None:
    if not owner._mix_route_inputs:
        return
    owner._mix_route_inputs["mix_main_route"].setCurrentText(owner._complex_route_cb.currentText().strip())
    owner._mix_route_inputs["mix_sub_route_a"].setCurrentText(owner._simple_route_cb.currentText().strip())
    owner._mix_route_inputs["mix_sub_route_b"].setCurrentText(owner._teaching_route_cb.currentText().strip())


def set_mix_status(owner, text: str, ok: bool) -> None:
    color = T.STATUS_SUCCESS if ok else T.STATUS_ERROR
    owner._mix_status_lbl.setText(text)
    owner._mix_status_lbl.setStyleSheet(
        f"color: {color}; font-family: '{T.FF_MONO}'; font-size: {T.FS_TINY}pt;"
    )


def apply_mixed_loadout(owner, *, provider_backend_available: bool) -> None:
    if not provider_backend_available:
        set_mix_status(owner, "Provider backend unavailable", ok=False)
        return
    main = owner._mix_route_inputs["mix_main_route"].currentText().strip()
    sub_a = owner._mix_route_inputs["mix_sub_route_a"].currentText().strip()
    sub_b = owner._mix_route_inputs["mix_sub_route_b"].currentText().strip()
    if not main or not sub_a or not sub_b:
        set_mix_status(owner, "Mix requires a main route plus spawned routes A and B", ok=False)
        return
    valid_targets = set(available_route_targets(owner))
    for target in (main, sub_a, sub_b):
        if target not in valid_targets:
            set_mix_status(owner, f"Invalid target: {target}", ok=False)
            return
    try:
        registry = load_provider_registry()
        if not isinstance(registry, dict):
            set_mix_status(owner, "Provider registry is invalid", ok=False)
            return
        routes = registry.setdefault("routes", {})
        if not isinstance(routes, dict):
            routes = {}
            registry["routes"] = routes
        routes["complex"] = main
        routes["simple"] = sub_a
        routes["teaching"] = sub_b
        fallback_chain = [main, sub_a, sub_b]
        preferred_local = preferred_local_route_target(owner)
        if preferred_local:
            fallback_chain.append(preferred_local)
        routes["fallback_chain"] = list(dict.fromkeys(fallback_chain))
        errors = validate_provider_registry(registry)
        if errors:
            set_mix_status(owner, f"Registry invalid: {errors[0]}", ok=False)
            return
        save_provider_registry(registry)
        owner._provider_registry = registry
        owner._route_options = route_targets_from_registry(registry)
        for cb in [owner._simple_route_cb, owner._complex_route_cb, owner._teaching_route_cb]:
            current = cb.currentText().strip()
            cb.clear()
            cb.addItems(owner._route_options)
            set_combo_to_text(cb, current)
        set_combo_to_text(owner._simple_route_cb, sub_a)
        set_combo_to_text(owner._complex_route_cb, main)
        set_combo_to_text(owner._teaching_route_cb, sub_b)
        owner._fallback_chain_input.setText(", ".join(routes["fallback_chain"]))
        os.environ["GUPPY_MAIN_ROUTE"] = main
        os.environ["GUPPY_SUB_ROUTE_A"] = sub_a
        os.environ["GUPPY_SUB_ROUTE_B"] = sub_b
        refresh_mix_route_inputs(owner)
        refresh_route_summary(owner, runtime_dir=owner._runtime_dir, heartbeat_fresh_seconds=owner._heartbeat_fresh_seconds)
        refresh_route_preview(owner, runtime_dir=owner._runtime_dir, heartbeat_fresh_seconds=owner._heartbeat_fresh_seconds)
        set_mix_status(owner, "Mixed loadout applied", ok=True)
    except Exception as exc:
        set_mix_status(owner, f"Mix save failed: {exc}", ok=False)


def refresh_loadout_inputs(owner) -> None:
    names = owner._available_local_model_names()
    for field_name, combo in owner._loadout_inputs.items():
        current = owner._model_loadout.get(field_name, combo.currentText().strip())
        owner._set_combo_items_preserve_text(combo, names, current)


def on_loadout_changed(owner, field_name: str, value: str) -> None:
    owner._model_loadout[field_name] = str(value or "").strip()
    refresh_loadout_help(owner)


def refresh_loadout_help(owner) -> None:
    owner._loadout_help_lbl.setText(
        build_models_loadout_help_text(
            main_model=owner._model_loadout.get("local_main_model", ""),
            sub_a_model=owner._model_loadout.get("local_sub_model_a", ""),
            sub_b_model=owner._model_loadout.get("local_sub_model_b", ""),
        )
    )


def loadout_payload(owner, loadout_fields: list[tuple[str, str]]) -> dict[str, str]:
    payload: dict[str, str] = {}
    for field_name, _label in loadout_fields:
        combo = owner._loadout_inputs.get(field_name)
        value = combo.currentText().strip() if combo is not None else owner._model_loadout.get(field_name, "")
        payload[field_name] = value
    return payload


def apply_model_loadout(owner, *, runtime_settings_backend_available: bool, loadout_fields: list[tuple[str, str]]) -> None:
    payload = loadout_payload(owner, loadout_fields)
    main_model = payload.get("local_main_model", "")
    sub_a = payload.get("local_sub_model_a", "")
    sub_b = payload.get("local_sub_model_b", "")
    if not main_model or not sub_a or not sub_b:
        set_loadout_status(owner, "Loadout requires a main model plus spawned models A and B", ok=False)
        return
    owner._model_loadout.update(payload)
    os.environ["GUPPY_MAIN_MODEL"] = main_model
    os.environ["GUPPY_SUB_MODEL_A"] = sub_a
    os.environ["GUPPY_SUB_MODEL_B"] = sub_b
    os.environ["GUPPY_LOCAL_COMPLEX_MODEL"] = main_model
    os.environ["GUPPY_LOCAL_FAST_MODEL"] = sub_a
    os.environ["GUPPY_LOCAL_CODE_MODEL"] = sub_b
    os.environ["OLLAMA_MODEL"] = main_model
    os.environ["OLLAMA_FAST_MODEL"] = sub_a
    os.environ["OLLAMA_CODE_MODEL"] = sub_b
    owner._active_model = main_model
    owner._active_lbl.setText(build_models_active_identity_text(main_model))
    for card in owner._local_cards:
        card.mark_active(card._model_name == main_model)
    owner._rebuild_local_sections()
    owner._apply_library_filter()
    owner.model_selected.emit(main_model)

    if runtime_settings_backend_available:
        merged_payload = dict(owner._runtime_settings_payload())
        merged_payload.update(payload)
        try:
            save_app_settings(merged_payload)
            apply_settings_to_env(merged_payload)
        except Exception as exc:
            set_loadout_status(owner, f"Loadout save failed: {exc}", ok=False)
            return

    owner._refresh_library_summary()
    refresh_loadout_help(owner)
    set_loadout_status(owner, "Loadout applied: main model plus two spawned models ready", ok=True)


def set_loadout_status(owner, text: str, ok: bool) -> None:
    color = T.STATUS_SUCCESS if ok else T.STATUS_ERROR
    owner._loadout_status_lbl.setText(text)
    owner._loadout_status_lbl.setStyleSheet(
        f"color: {color}; font-family: '{T.FF_MONO}'; font-size: {T.FS_TINY}pt;"
    )


def spawn_loadout_models(owner, *, include_main: bool, include_subs: bool, loadout_fields: list[tuple[str, str]]) -> None:
    if owner._local_runtime_backend != "ollama":
        set_loadout_status(owner, "Spawn controls are available for Ollama loadouts", ok=False)
        return
    payload = loadout_payload(owner, loadout_fields)
    targets: list[str] = []
    if include_main:
        main_model = payload.get("local_main_model", "")
        if main_model:
            targets.append(main_model)
    if include_subs:
        for key in ("local_sub_model_a", "local_sub_model_b"):
            model = payload.get(key, "")
            if model:
                targets.append(model)
    deduped = list(dict.fromkeys(targets))
    if not deduped:
        set_loadout_status(owner, "No models selected to spawn", ok=False)
        return
    if owner._loadout_spawn_thread is not None and owner._loadout_spawn_thread.isRunning():
        set_loadout_status(owner, "Spawn already running", ok=False)
        return
    set_loadout_status(owner, "Spawning selected models...", ok=True)
    owner._loadout_spawn_thread = owner._model_warm_spawn_thread_factory(deduped, owner)
    owner._loadout_spawn_thread.finished.connect(owner._on_spawn_finished)
    owner._loadout_spawn_thread.start()


def on_spawn_finished(owner, payload: dict[str, Any]) -> None:
    warmed = [str(item).strip() for item in payload.get("warmed", []) if str(item).strip()]
    failed = [str(item).strip() for item in payload.get("failed", []) if str(item).strip()]
    if failed:
        if warmed:
            set_loadout_status(
                owner,
                f"Spawn partial: warmed {', '.join(warmed)}; failed {', '.join(failed)}",
                ok=False,
            )
        else:
            set_loadout_status(owner, f"Spawn failed: {', '.join(failed)}", ok=False)
        return
    set_loadout_status(owner, f"Spawned: {', '.join(warmed)}", ok=True)


def set_route_status(owner, text: str, ok: bool = True) -> None:
    color = T.GREEN if ok else T.ERROR
    owner._route_status_lbl.setText(text)
    owner._route_status_lbl.setStyleSheet(
        f"color: {color}; font-family: '{T.FF_MONO}'; font-size: {T.FS_TINY}pt; letter-spacing: 1px;"
    )


def load_route_config(owner, *, provider_backend_available: bool, runtime_dir, heartbeat_fresh_seconds: float) -> None:
    if not provider_backend_available:
        owner._apply_routes_btn.setEnabled(False)
        set_route_status(owner, "Provider backend unavailable", ok=False)
        return
    try:
        ensure_personalization_scaffold()
        registry = load_provider_registry()
        owner._provider_registry = registry if isinstance(registry, dict) else {}
        owner._route_options = route_targets_from_registry(owner._provider_registry)
        for cb in [owner._simple_route_cb, owner._complex_route_cb, owner._teaching_route_cb]:
            cb.clear()
            cb.addItems(owner._route_options)
        routes = owner._provider_registry.get("routes", {}) if isinstance(owner._provider_registry, dict) else {}
        if isinstance(routes, dict):
            set_combo_to_text(owner._simple_route_cb, str(routes.get("simple", "")))
            set_combo_to_text(owner._complex_route_cb, str(routes.get("complex", "")))
            set_combo_to_text(owner._teaching_route_cb, str(routes.get("teaching", "")))
            fallback = routes.get("fallback_chain", [])
            if isinstance(fallback, list):
                owner._fallback_chain_input.setText(", ".join(str(item).strip() for item in fallback if str(item).strip()))
        refresh_mix_route_inputs(owner)
        load_mix_from_routes(owner)
        refresh_route_summary(owner, runtime_dir=runtime_dir, heartbeat_fresh_seconds=heartbeat_fresh_seconds)
        refresh_route_preview(owner, runtime_dir=runtime_dir, heartbeat_fresh_seconds=heartbeat_fresh_seconds)
        set_route_status(owner, "Route strategy loaded", ok=True)
    except Exception as exc:
        set_route_status(owner, f"Route load failed: {exc}", ok=False)


def preferred_local_route_target(owner) -> str:
    preferred = (
        owner._model_loadout.get("local_main_model", "")
        or owner._active_model
        or (owner._local_cards[0]._model_name if owner._local_cards else "")
    ).strip()
    return f"local/{preferred}" if preferred else ""


def set_combo_to_text(combo, target: str) -> None:
    idx = combo.findText(target)
    if idx >= 0:
        combo.setCurrentIndex(idx)


def refresh_route_summary(owner, *, runtime_dir, heartbeat_fresh_seconds: float) -> None:
    fallback = parse_fallback_chain(owner._fallback_chain_input.text())
    health = route_health_summary(owner, runtime_dir=runtime_dir, heartbeat_fresh_seconds=heartbeat_fresh_seconds)
    summary, evidence = build_models_route_summary_text(
        simple_target=friendly_models_route_target(owner._simple_route_cb.currentText()),
        complex_target=friendly_models_route_target(owner._complex_route_cb.currentText()),
        teaching_target=friendly_models_route_target(owner._teaching_route_cb.currentText()),
        fallback_targets=[friendly_models_route_target(item) for item in fallback],
        health_summary=health,
    )
    owner._route_summary_lbl.setText(summary)
    owner._route_evidence_lbl.setText(evidence)


def route_health_summary(owner, *, runtime_dir, heartbeat_fresh_seconds: float) -> str:
    api_key = bool((os.environ.get("ANTHROPIC_API_KEY", "") or "").strip())
    local_count = max(0, len(owner._local_cards))
    latency = latest_runtime_latency(runtime_dir)
    heartbeat_path = runtime_dir / "guppy.heartbeat"
    heartbeat = False
    if heartbeat_path.exists():
        try:
            heartbeat = (time.time() - heartbeat_path.stat().st_mtime) < heartbeat_fresh_seconds
        except OSError:
            heartbeat = False
    parts = [
        f"Cloud path {'configured' if api_key else 'needs API key'}",
        f"Local runtime {owner._local_runtime_backend.upper()} {'heartbeat seen' if heartbeat else 'heartbeat missing'}",
        f"{local_count} local model{'s' if local_count != 1 else ''} visible" if local_count else "local library not loaded yet",
    ]
    if latency:
        parts.append(f"launcher-wide last reply {latency}")
    return " | ".join(parts)


def refresh_route_preview(owner, *, runtime_dir, heartbeat_fresh_seconds: float) -> None:
    sample = owner._route_input.text().strip()
    if not sample:
        owner._route_preview_lbl.setText(build_models_route_preview_hint_text())
        return
    try:
        decision = resolve_ui_route(
            user_text=sample,
            mode=owner._route_mode_cb.currentText().strip().lower(),
            api_key_available=bool((os.environ.get("ANTHROPIC_API_KEY", "") or "").strip()),
        )
        owner._route_preview_lbl.setText(
            build_models_route_preview_text(
                decision,
                health_summary=route_health_summary(
                    owner,
                    runtime_dir=runtime_dir,
                    heartbeat_fresh_seconds=heartbeat_fresh_seconds,
                ),
            )
        )
    except Exception as exc:
        owner._route_preview_lbl.setText(f"Route preview failed: {exc}")


def apply_routes(owner, *, provider_backend_available: bool, runtime_dir, heartbeat_fresh_seconds: float) -> None:
    if not provider_backend_available:
        set_route_status(owner, "Provider backend unavailable", ok=False)
        return
    try:
        registry = load_provider_registry()
        if not isinstance(registry, dict):
            set_route_status(owner, "Provider registry is invalid", ok=False)
            return
        valid_targets = set(route_targets_from_registry(registry))
        simple = owner._simple_route_cb.currentText().strip()
        complex_route = owner._complex_route_cb.currentText().strip()
        teaching = owner._teaching_route_cb.currentText().strip()
        for label, value in [("simple", simple), ("complex", complex_route), ("teaching", teaching)]:
            if value not in valid_targets:
                set_route_status(owner, f"Invalid {label} target: {value}", ok=False)
                return
        fallback = parse_fallback_chain(owner._fallback_chain_input.text())
        invalid_fallback = [item for item in fallback if item not in valid_targets]
        if invalid_fallback:
            set_route_status(owner, f"Invalid fallback target: {invalid_fallback[0]}", ok=False)
            return
        routes = registry.setdefault("routes", {})
        registry["routes"] = routes if isinstance(routes, dict) else {}
        registry["routes"]["simple"] = simple
        registry["routes"]["complex"] = complex_route
        registry["routes"]["teaching"] = teaching
        registry["routes"]["fallback_chain"] = fallback
        errors = validate_provider_registry(registry)
        if errors:
            set_route_status(owner, f"Provider registry invalid: {errors[0]}", ok=False)
            return
        save_provider_registry(registry)
        owner._provider_registry = registry
        refresh_route_summary(owner, runtime_dir=runtime_dir, heartbeat_fresh_seconds=heartbeat_fresh_seconds)
        refresh_route_preview(owner, runtime_dir=runtime_dir, heartbeat_fresh_seconds=heartbeat_fresh_seconds)
        set_route_status(owner, "Route strategy saved", ok=True)
    except Exception as exc:
        set_route_status(owner, f"Apply routes failed: {exc}", ok=False)
