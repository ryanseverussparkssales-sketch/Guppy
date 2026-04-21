"""Pure presenter helpers for Home workspace framing and starter copy."""

from __future__ import annotations

from dataclasses import dataclass

from .instance_manager_presenter import workspace_default_purpose, workspace_recent_context
from .tool_action_registry import get_tool_starters as _get_tool_starters_from_registry


@dataclass(frozen=True, slots=True)
class HomeWorkspaceCopy:
    role_label: str
    purpose: str
    entry_hint: str
    first_run_recipe: str
    starter_summary: str
    onboarding_title: str
    onboarding_subtitle: str
    onboarding_recipe: str
    primary_starter_label: str
    input_placeholder: str


@dataclass(frozen=True, slots=True)
class HomeStarterTemplate:
    starter_id: str
    title: str
    mode: str
    prompt: str


@dataclass(frozen=True, slots=True)
class HomeWorkspaceState:
    role_label: str
    purpose: str
    entry_hint: str
    starter_summary: str
    onboarding_title: str
    onboarding_subtitle: str
    onboarding_recipe: str
    primary_starter_label: str
    input_placeholder: str
    workspace_summary: str
    welcome_message: str


@dataclass(frozen=True, slots=True)
class HomeStarterState:
    starter_id: str
    label: str
    mode: str
    prompt: str
    background_event: str
    starter_summary: str
    status: str


def _workspace_key(workspace_type: str) -> str:
    return (workspace_type or "user_instance").strip().lower() or "user_instance"


def home_workspace_role_label(workspace_type: str) -> str:
    key = _workspace_key(workspace_type)
    return {
        "user_instance": "Daily assistant workspace",
        "builder_instance": "Builder collaborator workspace",
        "read_only_instance": "Read-only reference workspace",
        "admin_instance": "Operations workspace",
    }.get(key, key.replace("_", " ").strip().capitalize() or "Workspace")


def build_home_workspace_copy(workspace_type: str, *, description: str = "") -> HomeWorkspaceCopy:
    key = _workspace_key(workspace_type)
    purpose = (description or workspace_default_purpose(key)).strip()
    mapping = {
        "user_instance": HomeWorkspaceCopy(
            role_label=home_workspace_role_label(key),
            purpose=purpose,
            entry_hint="type one short request and press Send.",
            first_run_recipe="Ask one clear question first, then use MORNING BRIEF if you want a draft.",
            starter_summary="Optional starter: MORNING BRIEF. Or just ask for the next thing you want to move forward.",
            onboarding_title="Start here",
            onboarding_subtitle="Use the composer for the next thing you want to move forward. Starters are optional. One clear ask is enough.",
            onboarding_recipe="Next step: ask one clear question and press Send.",
            primary_starter_label="MORNING BRIEF",
            input_placeholder="Ask for the next thing you want to move forward...",
        ),
        "builder_instance": HomeWorkspaceCopy(
            role_label=home_workspace_role_label(key),
            purpose=purpose,
            entry_hint="start with PLAN NEXT PASS if you want a draft first.",
            first_run_recipe="Ask for the next pass or bug hunt first, then load PLAN NEXT PASS if you want a draft.",
            starter_summary="Optional starter: PLAN NEXT PASS. Or just ask for the next pass you want help with.",
            onboarding_title="Builder workspace ready",
            onboarding_subtitle="Use the composer for the next pass you want help with. Starters are optional. One pass at a time is enough.",
            onboarding_recipe="Next step: ask for the next pass or load PLAN NEXT PASS.",
            primary_starter_label="PLAN NEXT PASS",
            input_placeholder="Ask for the next pass, review, or patch you need...",
        ),
        "read_only_instance": HomeWorkspaceCopy(
            role_label=home_workspace_role_label(key),
            purpose=purpose,
            entry_hint="start with SOURCE RESEARCH if you want evidence first.",
            first_run_recipe="Ask one evidence question first, then load SOURCE RESEARCH if you want a starter brief.",
            starter_summary="Optional starter: SOURCE RESEARCH. Or just ask one evidence question.",
            onboarding_title="Reference workspace ready",
            onboarding_subtitle="Use the composer for one evidence question or source check. Starters are optional. One clear question is enough.",
            onboarding_recipe="Next step: ask for evidence first or load SOURCE RESEARCH.",
            primary_starter_label="SOURCE RESEARCH",
            input_placeholder="Ask one evidence or source-check question...",
        ),
        "admin_instance": HomeWorkspaceCopy(
            role_label=home_workspace_role_label(key),
            purpose=purpose,
            entry_hint="start with OPS CHECK if you want a quick read first.",
            first_run_recipe="Ask for a short status check first, then load OPS CHECK if you want a quick read.",
            starter_summary="Optional starter: OPS CHECK. Or just ask for the safest next step.",
            onboarding_title="Operations workspace ready",
            onboarding_subtitle="Keep the first ask small and clear. Starters are optional. One safe step is enough.",
            onboarding_recipe="Next step: ask for a short status check or load OPS CHECK.",
            primary_starter_label="OPS CHECK",
            input_placeholder="Ask for a short status check or the safest next step...",
        ),
    }
    return mapping.get(key, mapping["user_instance"])


def home_workspace_starter_templates(workspace_type: str) -> tuple[HomeStarterTemplate, ...]:
    key = _workspace_key(workspace_type)
    mapping = {
        "user_instance": (
            HomeStarterTemplate(
                "morning_brief",
                "MORNING BRIEF",
                "auto",
                "Give me a morning brief for this workspace: priorities, blockers, and the best first move.",
            ),
            HomeStarterTemplate(
                "focused_research",
                "FOCUSED RESEARCH",
                "claude",
                "Research this topic for the active workspace and return a concise brief with recommendations: ",
            ),
            HomeStarterTemplate(
                "file_triage",
                "FILE TRIAGE",
                "local",
                "Help me triage files for this workspace. Start by asking which folder or files I want reviewed.",
            ),
            HomeStarterTemplate(
                "builder_review",
                "BUILDER REVIEW",
                "code",
                "Review the current builder work for this workspace with bugs, regressions, and missing tests first.",
            ),
        ),
        "builder_instance": (
            HomeStarterTemplate(
                "morning_brief",
                "PLAN NEXT PASS",
                "code",
                "Plan the next builder pass for this workspace: goals, review targets, and the safest high-value next move.",
            ),
            HomeStarterTemplate(
                "focused_research",
                "DESIGN RESEARCH",
                "claude",
                "Research this implementation question for the builder workspace and return tradeoffs, risks, and a recommended plan: ",
            ),
            HomeStarterTemplate(
                "file_triage",
                "PATCH TRIAGE",
                "local",
                "Help me triage changed files for this builder workspace. Start by asking which files or modules need review.",
            ),
            HomeStarterTemplate(
                "builder_review",
                "BUILDER REVIEW",
                "code",
                "Review the current builder work for this workspace with bugs, regressions, and missing tests first.",
            ),
        ),
        "read_only_instance": (
            HomeStarterTemplate(
                "morning_brief",
                "REFERENCE SNAPSHOT",
                "auto",
                "Summarize the key reference context for this workspace: what matters now, what changed, and what to inspect next.",
            ),
            HomeStarterTemplate(
                "focused_research",
                "SOURCE RESEARCH",
                "claude",
                "Research this topic for the reference workspace and return a concise evidence-first brief: ",
            ),
            HomeStarterTemplate(
                "file_triage",
                "SOURCE TRIAGE",
                "local",
                "Help me inspect files for this read-only workspace. Start by asking which folder or files I want compared or reviewed.",
            ),
            HomeStarterTemplate(
                "builder_review",
                "REFERENCE REVIEW",
                "code",
                "Review this source or diff for the reference workspace and call out risks, gaps, and evidence without proposing writes first.",
            ),
        ),
        "admin_instance": (
            HomeStarterTemplate(
                "morning_brief",
                "OPS CHECK",
                "auto",
                "Give me an operations check for this workspace: current health, likely blockers, and the safest first operator step.",
            ),
            HomeStarterTemplate(
                "focused_research",
                "INCIDENT RESEARCH",
                "claude",
                "Research this operational issue for the active workspace and return a concise diagnosis brief with likely follow-ups: ",
            ),
            HomeStarterTemplate(
                "file_triage",
                "EVIDENCE TRIAGE",
                "local",
                "Help me triage logs or artifacts for this operations workspace. Start by asking which files or folders need inspection.",
            ),
            HomeStarterTemplate(
                "builder_review",
                "RECOVERY REVIEW",
                "code",
                "Review the current recovery or servicing work for this workspace with failure points, regressions, and missing validation first.",
            ),
        ),
    }
    return mapping.get(key, mapping["user_instance"])


def build_home_workspace_summary(
    instance_name: str,
    *,
    workspace_type: str,
    description: str,
    mode: str,
    persona: str,
    voice: str,
    last_message: str,
) -> str:
    copy = build_home_workspace_copy(workspace_type, description=description)
    mode_label = (mode or "auto").strip().upper() or "AUTO"
    persona_label = (persona or "guppy").strip().upper() or "GUPPY"
    voice_label = (voice or "default").strip().upper() or "DEFAULT"
    recent_text = workspace_recent_context({"last_message": last_message})
    return (
        f"Active workspace: {copy.role_label}. {copy.purpose} "
        f"Saved context: {mode_label} mode | {persona_label} persona | {voice_label} voice. "
        f"Next move: {copy.first_run_recipe} {recent_text}"
    )


def build_home_welcome_message(workspace_type: str, *, description: str = "") -> str:
    copy = build_home_workspace_copy(workspace_type, description=description)
    return (
        f"{copy.onboarding_title}. {copy.onboarding_subtitle} "
        f"{copy.onboarding_recipe} Optional starter: {copy.primary_starter_label}."
    )


def build_home_workspace_state(
    instance_name: str,
    *,
    workspace_type: str,
    description: str,
    mode: str,
    persona: str,
    voice: str,
    last_message: str,
) -> HomeWorkspaceState:
    copy = build_home_workspace_copy(workspace_type, description=description)
    workspace_name = (instance_name or "guppy-primary").strip() or "guppy-primary"
    return HomeWorkspaceState(
        role_label=copy.role_label,
        purpose=copy.purpose,
        entry_hint=f"Start here in {workspace_name}: {copy.entry_hint}",
        starter_summary=copy.starter_summary,
        onboarding_title=copy.onboarding_title,
        onboarding_subtitle=copy.onboarding_subtitle,
        onboarding_recipe=copy.onboarding_recipe,
        primary_starter_label=copy.primary_starter_label,
        input_placeholder=copy.input_placeholder,
        workspace_summary=build_home_workspace_summary(
            workspace_name,
            workspace_type=workspace_type,
            description=copy.purpose,
            mode=mode,
            persona=persona,
            voice=voice,
            last_message=last_message,
        ),
        welcome_message=build_home_welcome_message(workspace_type, description=copy.purpose),
    )


def get_tool_starters() -> list[dict[str, str]]:
    """Return starter entries for all registered tools.

    Each entry is a dict with: tool_key, label, command_hint,
    home_starter_prompt, category. Delegates to the shared tool action
    registry so wording stays consistent across all surfaces.
    """
    return _get_tool_starters_from_registry()


def build_home_starter_state(workspace_type: str, starter_id: str) -> HomeStarterState:
    for item in home_workspace_starter_templates(workspace_type):
        if item.starter_id != starter_id:
            continue
        label = item.title.strip() or "STARTER"
        return HomeStarterState(
            starter_id=item.starter_id,
            label=label,
            mode=item.mode,
            prompt=item.prompt,
            background_event=f"Starter loaded: {label}. Edit the draft if needed, then press send.",
            starter_summary=f"{label} is ready in the composer. Edit it if needed, then send.",
            status="STARTER READY",
        )
    return HomeStarterState(
        starter_id=starter_id,
        label="STARTER",
        mode="auto",
        prompt="",
        background_event="Starter loaded: STARTER. Edit the draft if needed, then press send.",
        starter_summary="STARTER is ready in the composer. Edit it if needed, then send.",
        status="STARTER READY",
    )
