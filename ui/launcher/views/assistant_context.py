from __future__ import annotations

from src.guppy.launcher_application.library_presenter import build_library_surface_state

from .. import tokens as T


def _context_origin_label(item: dict[str, str]) -> str:
    origin = str(item.get("origin", "") or "").strip().lower()
    source_label = str(item.get("source_label", "") or "").strip()
    if origin == "assistant_reply":
        return "saved reply note"
    if origin == "assistant_reply_artifact":
        return "saved output"
    if source_label:
        return source_label.lower()
    return "Library source"


def format_active_context_summary(items: list[dict[str, str]], *, used_for_latest_reply: bool = False) -> str:
    if not items:
        return "No Library sources attached yet. Open Library and use USE IN CHAT to ground the next reply."
    primary = items[0]
    primary_title = str(primary.get("title", "") or "").strip() or "current source"
    primary_label = _context_origin_label(primary)
    attached_titles = [
        str(item.get("title", "") or "").strip()
        for item in items[1:3]
        if str(item.get("title", "") or "").strip()
    ]
    prefix = "Current sources were used for the latest reply." if used_for_latest_reply else f"Current sources: {len(items)} attached and ready."
    summary = f"{prefix} Primary source: {primary_title} ({primary_label})."
    if attached_titles:
        summary += f" Also attached: {', '.join(attached_titles)}."
    return summary


def build_grounding_cue(item: dict[str, str]) -> tuple[str, str]:
    title = str(item.get("title", "") or "").strip() or "current source"
    origin = str(item.get("origin", "") or "").strip().lower()
    if origin == "assistant_reply":
        return (
            "CURRENT SOURCE · SAVED REPLY NOTE",
            f"Current turn is grounded in saved reply note: {title}",
        )
    if origin == "assistant_reply_artifact":
        return (
            "CURRENT SOURCE · SAVED OUTPUT",
            f"Current turn is grounded in saved output: {title}",
        )
    return (
        f"CURRENT SOURCE · {title[:28].upper()}",
        f"Current turn is grounded in Library source: {title}",
    )


def build_composer_guidance(
    base_placeholder: str,
    base_summary: str,
    items: list[dict[str, str]],
) -> tuple[str, str]:
    if not items:
        return base_placeholder, base_summary
    primary = items[0]
    primary_title = str(primary.get("title", "") or "").strip()
    other_titles = [
        str(item.get("title", "") or "").strip()
        for item in items[1:3]
        if str(item.get("title", "") or "").strip()
    ]
    origin = str(primary.get("origin", "") or "").strip().lower()
    if origin == "assistant_reply" and primary_title:
        placeholder = f"Build on saved reply note {primary_title}."
        summary = f"{base_summary} Current source: saved reply note {primary_title}."
    elif origin == "assistant_reply_artifact" and primary_title:
        placeholder = f"Use saved output {primary_title} for the next step."
        summary = f"{base_summary} Current source: saved output {primary_title}."
    elif origin == "library_note" and primary_title:
        placeholder = f"Continue from pinned note {primary_title}."
        summary = f"{base_summary} Current source: pinned note {primary_title}."
    elif origin == "library_media" and primary_title:
        media_label = str(primary.get("source_label", "") or "local media").lower()
        placeholder = f"Use {primary_title} as {media_label} context for the next step."
        summary = f"{base_summary} Current source: {media_label} {primary_title}."
    elif primary_title:
        placeholder = f"Ask the next thing using {primary_title} as source context."
        summary = f"{base_summary} Current source: {primary_title}."
    else:
        placeholder = "Ask the next thing using the attached Library context."
        summary = f"{base_summary} Current source is attached from Library."
    if other_titles:
        summary += f" Also attached: {', '.join(other_titles)}."
    return placeholder, summary


def sync_context_bar_visibility(owner) -> None:
    if not getattr(owner, "_home_operator_details_enabled", True):
        owner._context_details_visible = False
        owner._context_details_btn.setVisible(False)
        owner._context_details_host.setVisible(False)
        owner._context_bar.setVisible(False)
        return
    primary_visible = any(
        not widget.isHidden()
        for widget in (
            owner._background_event,
            owner._workspace_summary,
        )
    )
    details_available = any(
        not widget.isHidden()
        for widget in (
            owner._runtime_facts,
            owner._route_facts,
            owner._recovery_summary,
        )
    )
    owner._context_details_btn.setVisible(primary_visible and details_available)
    owner._context_details_host.setVisible(primary_visible and details_available and owner._context_details_visible)
    owner._context_details_btn.setText("HIDE DETAILS" if not owner._context_details_host.isHidden() else "DETAILS")
    owner._context_bar.setVisible(primary_visible or not owner._context_details_host.isHidden())


def toggle_context_details(owner) -> None:
    owner._context_details_visible = not owner._context_details_visible
    sync_context_bar_visibility(owner)


def refresh_resource_context(owner) -> None:
    state = build_library_surface_state(
        owner._workspace_name,
        workspace_type=owner._workspace_type,
        description=owner._workspace_purpose,
        mode=owner.selected_mode(),
        last_message=owner._conversation_history[-1]["content"] if owner._conversation_history else "",
        include_root_file_cards=False,
    )
    owner.set_resource_context(
        files=state.files_summary,
        study=state.study_summary,
        coding=state.coding_summary,
    )


def set_route_preview(
    owner,
    *,
    task_type: str = "unknown",
    route: str = "pending",
    model: str = "",
    backup_model: str = "",
    reason: str = "",
    evidence: str = "",
) -> None:
    reason_text = (reason or "").strip()
    evidence_text = (evidence or "").strip()
    route_bits: list[str] = []
    if str(task_type or "").strip():
        route_bits.append(f"{str(task_type).strip().capitalize()} task")
    if str(route or "").strip():
        route_bits.append(f"via {str(route).strip().upper()}")
    if model:
        route_bits.append(f"using {str(model).strip().upper()}")
    if backup_model:
        route_bits.append(f"backup {str(backup_model).strip().upper()}")
    summary = ", ".join(route_bits) if route_bits else "waiting for your next message"
    details: list[str] = []
    if reason_text:
        details.append(f"Why: {reason_text}")
    if evidence_text:
        details.append(f"Evidence: {evidence_text}")
    owner._route_facts.setText(f"Next reply: {summary}." + (f" {' '.join(details)}" if details else ""))
    owner._route_facts.setVisible(getattr(owner, "_home_operator_details_enabled", True))
    sync_context_bar_visibility(owner)


def set_background_status(owner, text: str, healthy: bool = True) -> None:
    msg = (text or "ready").strip() or "ready"
    color = T.GREEN if healthy else T.ERROR
    background = "rgba(90,196,122,0.08)" if healthy else "rgba(226,92,92,0.08)"
    border = "rgba(90,196,122,0.24)" if healthy else "rgba(226,92,92,0.24)"
    owner._background_chip.setText(msg.upper())
    owner._background_chip.setStyleSheet(
        f"color: {color}; background-color: {background}; border: 1px solid {border};"
        f"border-radius: 10px; font-family: '{T.FF_MONO}'; font-size: {T.FS_TINY}pt; letter-spacing: 1px; padding: 4px 8px;"
    )


def set_background_event(owner, text: str) -> None:
    msg = (text or "workspace ready").strip() or "workspace ready"
    owner._background_event.setText(f"Latest activity: {msg}")
    owner._background_event.setVisible(getattr(owner, "_home_operator_details_enabled", True))
    sync_context_bar_visibility(owner)


def set_runtime_facts(
    owner,
    *,
    profile: str = "standard",
    model: str = "guppy",
    voice: str = "edge",
    latency: str = "-",
    last_query: str = "-",
) -> None:
    query = (last_query or "-").strip() or "-"
    query = query[:96] + "..." if len(query) > 96 else query
    details = [
        f"{str(profile).capitalize()} profile",
        f"{str(model).upper()} model",
        f"{str(voice).strip() or 'edge'} voice",
    ]
    if str(latency).strip() and str(latency).strip() not in {"-", "—"}:
        details.append(f"{latency} ms latency")
    if query not in {"-", "—"}:
        details.append(f"last request: {query}")
    owner._runtime_facts.setText("Ready now: " + ", ".join(details) + ".")
    owner._runtime_facts.setVisible(getattr(owner, "_home_operator_details_enabled", True))
    sync_context_bar_visibility(owner)


def set_recovery_summary(owner, text: str, healthy: bool = True) -> None:
    summary = (text or "stable").strip() or "stable"
    color = T.GREEN if healthy else T.ERROR
    prefix = "System health" if healthy else "Needs attention"
    owner._recovery_summary.setText(f"{prefix}: {summary}")
    show_operator_details = getattr(owner, "_home_operator_details_enabled", True)
    owner._recovery_summary.setVisible(show_operator_details)
    if not healthy and show_operator_details:
        owner._context_details_visible = True
    owner._entry_hint.setStyleSheet(
        f"color: {T.PRIMARY if healthy else T.ERROR}; font-family: '{T.FF_MONO}';"
        f"font-size: {T.FS_TINY}pt; letter-spacing: 1px;"
    )
    owner._recovery_summary.setStyleSheet(
        f"color: {color}; font-family: '{T.FF_MONO}';"
        f"font-size: {T.FS_TINY}pt; letter-spacing: 1px;"
    )
    sync_context_bar_visibility(owner)



def active_context_titles(items: list[dict[str, str]], limit: int = 2) -> list[str]:
    return [
        str(item.get("title", "") or "").strip()
        for item in items[:max(0, limit)]
        if str(item.get("title", "") or "").strip()
    ]


def context_aware_starter_title(items: list[dict[str, str]], starter_id: str, title: str) -> str:
    if not items or starter_id == "morning_brief":
        return title
    return f"{title} +" if not title.endswith(" +") else title


def context_aware_starter_prompt(items: list[dict[str, str]], prompt: str) -> str:
    titles = active_context_titles(items)
    if not titles:
        return prompt
    return f"{prompt.rstrip()} Use attached Library context first when relevant: {', '.join(titles)}."


def normalize_context_items(items: list[dict]) -> list[dict[str, str]]:
    return [
        {
            "title": str(item.get("title", "") or "").strip(),
            "kind": str(item.get("kind", "file") or "file").strip().upper(),
            "detail": str(item.get("detail", "") or "").strip(),
            "origin": str(item.get("origin", "") or "").strip().lower(),
            "source_label": str(item.get("source_label", "") or "").strip(),
        }
        for item in items[:3]
        if isinstance(item, dict) and str(item.get("title", "") or "").strip()
    ]
