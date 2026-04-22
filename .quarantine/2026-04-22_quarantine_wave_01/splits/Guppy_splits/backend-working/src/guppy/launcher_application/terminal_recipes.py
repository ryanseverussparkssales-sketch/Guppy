"""Embedded terminal recipe tracking helpers for the launcher application layer."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import uuid4


TERMINAL_RECIPE_MARKER = "__GUPPY_RECIPE__|"


@dataclass(frozen=True, slots=True)
class TerminalRecipePlan:
    recipe_id: str
    label: str
    context: dict[str, object]
    rendered_commands: tuple[str, ...]

    @property
    def wrapped_commands(self) -> tuple[str, ...]:
        return self.rendered_commands


TrackedTerminalRecipe = TerminalRecipePlan


@dataclass(frozen=True, slots=True)
class TerminalRecipeMarkerResult:
    consumed: bool
    recipes: dict[str, dict[str, object]]
    status_text: str | None = None
    completed_payload: dict[str, object] | None = None

    @property
    def handled(self) -> bool:
        return self.consumed

    @property
    def payload(self) -> dict[str, object] | None:
        return self.completed_payload


def recipe_marker(*parts: object) -> str:
    cleaned = [str(part).replace("|", "/").strip() for part in parts]
    return TERMINAL_RECIPE_MARKER + "|".join(cleaned)


def build_tracked_terminal_recipe(
    commands: list[str],
    *,
    label: str,
    recipe_context: dict[str, object],
    recipe_id: str = "",
) -> TerminalRecipePlan:
    resolved_id = str(recipe_id or f"recipe-{uuid4().hex[:10]}").strip()
    cleaned = [str(item).strip() for item in commands if str(item).strip()]
    context = dict(recipe_context)
    context.update(
        {
            "id": resolved_id,
            "label": label,
            "commands": cleaned,
            "steps_total": len(cleaned),
            "steps_completed": 0,
            "step_results": [],
        }
    )
    wrapped: list[str] = [
        f'Write-Output "{recipe_marker("start", resolved_id, len(cleaned), label)}"',
        "$global:GuppyRecipeStop = 0",
    ]
    for idx, command in enumerate(cleaned, start=1):
        escaped = command.replace("'", "''")
        wrapped.append(
            "if ($global:GuppyRecipeStop -ne 0) "
            "{ "
            f'Write-Output "{recipe_marker("step", resolved_id, idx, "skipped")}"'
            " } else { "
            f"Invoke-Expression '{escaped}'; "
            "$code = if ($LASTEXITCODE -ne $null) { [int]$LASTEXITCODE } elseif ($?) { 0 } else { 1 }; "
            f'Write-Output "{recipe_marker("step", resolved_id, idx)}|$code"; '
            "if ($code -ne 0) { $global:GuppyRecipeStop = $code }"
            " }"
        )
    wrapped.append(f'Write-Output "{recipe_marker("end", resolved_id)}|$global:GuppyRecipeStop"')
    wrapped.append("Remove-Variable GuppyRecipeStop -Scope Global -ErrorAction SilentlyContinue")
    return TerminalRecipePlan(
        recipe_id=resolved_id,
        label=label,
        context=context,
        rendered_commands=tuple(wrapped),
    )


def build_tracked_recipe(
    commands: list[str],
    *,
    label: str,
    recipe_context: dict[str, object],
) -> TerminalRecipePlan:
    return build_tracked_terminal_recipe(commands, label=label, recipe_context=recipe_context)


def apply_terminal_recipe_marker(
    line: str,
    recipes: dict[str, dict[str, object]],
    *,
    shell_pid: int | None = None,
    shell_alive: bool = False,
) -> TerminalRecipeMarkerResult:
    updated_recipes = dict(recipes)
    if not str(line).startswith(TERMINAL_RECIPE_MARKER):
        return TerminalRecipeMarkerResult(consumed=False, recipes=updated_recipes)
    payload = str(line)[len(TERMINAL_RECIPE_MARKER):]
    parts = payload.split("|")
    if len(parts) < 2:
        return TerminalRecipeMarkerResult(consumed=True, recipes=updated_recipes)
    marker_type = str(parts[0]).strip().lower()
    recipe_id = str(parts[1]).strip()
    recipe = dict(updated_recipes.get(recipe_id, {}))
    if marker_type == "start":
        label = str(recipe.get("label", parts[3] if len(parts) > 3 else "recipe") or "recipe")
        steps_total = int(parts[2]) if len(parts) > 2 and str(parts[2]).isdigit() else int(recipe.get("steps_total", 0) or 0)
        recipe["steps_total"] = steps_total
        recipe["steps_completed"] = 0
        updated_recipes[recipe_id] = recipe
        return TerminalRecipeMarkerResult(
            consumed=True,
            recipes=updated_recipes,
            status_text=f"Shell running {label.lower()}",
        )
    if marker_type == "step":
        idx = int(parts[2]) if len(parts) > 2 and str(parts[2]).isdigit() else 0
        result = str(parts[3]).strip().lower() if len(parts) > 3 else ""
        code = (
            0
            if result == "skipped"
            else int(parts[4])
            if len(parts) > 4 and str(parts[4]).lstrip("-").isdigit()
            else int(parts[3])
            if len(parts) > 3 and str(parts[3]).lstrip("-").isdigit()
            else 0
        )
        step_results = recipe.get("step_results", [])
        if not isinstance(step_results, list):
            step_results = []
        command_list = recipe.get("commands", [])
        command_text = str(command_list[idx - 1]) if isinstance(command_list, list) and 0 < idx <= len(command_list) else ""
        step_results.append(
            {
                "index": idx,
                "exit_code": code,
                "ok": result != "skipped" and code == 0,
                "skipped": result == "skipped",
                "command": command_text,
            }
        )
        recipe["step_results"] = step_results
        recipe["steps_completed"] = len(step_results)
        updated_recipes[recipe_id] = recipe
        return TerminalRecipeMarkerResult(consumed=True, recipes=updated_recipes)
    if marker_type == "end":
        final_code = int(parts[2]) if len(parts) > 2 and str(parts[2]).lstrip("-").isdigit() else 0
        step_results = recipe.get("step_results", [])
        if not isinstance(step_results, list):
            step_results = []
        total = int(recipe.get("steps_total", len(step_results)) or len(step_results))
        completed = len([item for item in step_results if isinstance(item, dict) and not bool(item.get("skipped", False))])
        failed_steps = [
            item for item in step_results
            if isinstance(item, dict) and not bool(item.get("ok", False)) and not bool(item.get("skipped", False))
        ]
        ok = final_code == 0 and not failed_steps and completed == total
        label = str(recipe.get("label", "recipe") or "recipe")
        summary = (
            f"{label} completed {completed}/{total} step(s) successfully."
            if ok
            else f"{label} stopped after {completed}/{total} successful step(s)."
        )
        if failed_steps:
            failed = failed_steps[0]
            summary += f" Failed step {int(failed.get('index', 0) or 0)}: {str(failed.get('command', '') or '').strip()}"
        payload_out = {
            **recipe,
            "id": recipe_id,
            "ok": ok,
            "final_exit_code": final_code,
            "summary": summary,
            "steps_completed": completed,
            "steps_total": total,
            "failed_steps": failed_steps,
        }
        updated_recipes.pop(recipe_id, None)
        status_text = f"Shell ready [pid={shell_pid}]" if shell_alive and shell_pid is not None else "Shell idle"
        return TerminalRecipeMarkerResult(
            consumed=True,
            recipes=updated_recipes,
            status_text=status_text,
            completed_payload=payload_out,
        )
    return TerminalRecipeMarkerResult(consumed=True, recipes=updated_recipes)


def handle_recipe_marker(
    line: str,
    recipes: dict[str, dict[str, object]],
    *,
    shell_pid: int | None = None,
    shell_running: bool = False,
) -> TerminalRecipeMarkerResult:
    return apply_terminal_recipe_marker(
        line,
        recipes,
        shell_pid=shell_pid,
        shell_alive=shell_running,
    )
