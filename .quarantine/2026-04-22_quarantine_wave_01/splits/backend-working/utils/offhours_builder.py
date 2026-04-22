from __future__ import annotations

import hashlib
import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
RUNTIME = ROOT / "runtime"
QUEUE_PATH = RUNTIME / "offhours_task_queue.json"
RESULTS_PATH = RUNTIME / "offhours_task_results.jsonl"
METRICS_PATH = RUNTIME / "offhours_metrics.jsonl"
DRY_RUN_DIR = RUNTIME / "offhours_results" / "dry_run"
TEMPLATE_PATH = ROOT / "config" / "offhours_prompts" / "builder_task_templates.json"

_SAFE_ROOTS = {"docs", "tests"}
_SAFE_CONFIG_PREFIXES = {
    Path("config") / "generated",
    Path("config") / "offhours_prompts",
}
_SLUG_RE = re.compile(r"[^a-z0-9]+")
_ANSI_ESCAPE_RE = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~]|\][^\x07]*(?:\x07|\x1b\\))")
_CONTROL_CHAR_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")

_DEFAULT_TEMPLATE_PAYLOAD = {
    "version": 1,
    "templates": [
        {
            "id": "unit_test_stub",
            "title": "Generate unit test stub",
            "description": "Create a low-risk pytest module under tests/unit for a target module or behavior.",
            "target": "merlin-code",
            "task_type": "write",
            "requires_target": True,
            "target_hint": "Target module or behavior, e.g. src/guppy/api/server.py or instance capabilities",
            "default_target": "instance capabilities",
            "output_path_template": "tests/unit/test_builder_{target_slug}.py",
            "prompt_template": "You are preparing a low-risk pytest file for Guppy. Produce a complete Python file and return only one fenced code block. Target: {target_ref}. Output path: {output_path}. Constraints: stay self-contained, prefer smoke-safe assertions, avoid network calls, avoid destructive filesystem actions, and keep comments minimal.",
        },
        {
            "id": "smoke_test_stub",
            "title": "Generate smoke test stub",
            "description": "Create a low-risk smoke-style test scaffold under tests/smoke.",
            "target": "merlin-code",
            "task_type": "write",
            "requires_target": True,
            "target_hint": "Feature or UI path to smoke test",
            "default_target": "builder workflow",
            "output_path_template": "tests/smoke/test_builder_{target_slug}.py",
            "prompt_template": "Create a safe smoke test scaffold for Guppy. Target: {target_ref}. Output path: {output_path}. Return one fenced Python code block only. Constraints: no external network, no long sleeps, no destructive commands, and keep the test resilient when dependencies are absent.",
        },
        {
            "id": "docs_followup",
            "title": "Draft docs follow-up",
            "description": "Write a focused markdown follow-up note under docs/generated.",
            "target": "guppy-fast",
            "task_type": "write",
            "requires_target": True,
            "target_hint": "Topic or feature area",
            "default_target": "builder workflow",
            "output_path_template": "docs/generated/{target_slug}_followup.md",
            "prompt_template": "Draft a concise markdown follow-up note for Guppy about {target_ref}. Output path: {output_path}. Return one fenced markdown block only. Include summary, low-risk next actions, and validation notes.",
        },
        {
            "id": "config_example",
            "title": "Generate config example",
            "description": "Create a non-live example config file under config/generated.",
            "target": "merlin-code",
            "task_type": "write",
            "requires_target": True,
            "target_hint": "Config or policy topic",
            "default_target": "builder task policy",
            "output_path_template": "config/generated/{target_slug}.example.json",
            "prompt_template": "Create a safe example JSON config for Guppy about {target_ref}. Output path: {output_path}. Return one fenced json block only. Do not include secrets, absolute paths, or production credentials.",
        },
        {
            "id": "prompt_refresh",
            "title": "Draft prompt refresh",
            "description": "Create a new low-risk prompt draft under config/offhours_prompts.",
            "target": "guppy-fast",
            "task_type": "write",
            "requires_target": True,
            "target_hint": "Prompt purpose or workflow",
            "default_target": "low risk builder review",
            "output_path_template": "config/offhours_prompts/{target_slug}.md",
            "prompt_template": "Write a prompt draft for Guppy's low-risk automation about {target_ref}. Output path: {output_path}. Return one fenced markdown block only. Keep it explicit, bounded, and approval-first.",
        },
        {
            "id": "regression_checklist",
            "title": "Draft regression checklist",
            "description": "Create a focused regression checklist under docs/generated for a feature or release slice.",
            "target": "guppy-fast",
            "task_type": "write",
            "requires_target": True,
            "target_hint": "Feature area, release gate, or workflow to verify",
            "default_target": "launcher builder flow",
            "output_path_template": "docs/generated/{target_slug}_regression_checklist.md",
            "prompt_template": "Draft a concise regression checklist for Guppy covering {target_ref}. Output path: {output_path}. Return one fenced markdown block only. Include critical paths, edge checks, and validation commands without destructive actions.",
        },
        {
            "id": "ui_input_audit",
            "title": "Draft UI input audit",
            "description": "Create a launcher input/button audit note under docs/generated.",
            "target": "guppy-fast",
            "task_type": "write",
            "requires_target": True,
            "target_hint": "Launcher view, tab, or workflow to audit",
            "default_target": "unified launcher",
            "output_path_template": "docs/generated/{target_slug}_input_audit.md",
            "prompt_template": "Create a concise UI input and button audit for Guppy focused on {target_ref}. Output path: {output_path}. Return one fenced markdown block only. Separate live controls, disabled placeholders, and follow-up fixes.",
        },
        {
            "id": "fixture_example",
            "title": "Generate fixture example",
            "description": "Create a safe fixture/example payload under tests/fixtures for a bounded workflow.",
            "target": "merlin-code",
            "task_type": "write",
            "requires_target": True,
            "target_hint": "Workflow, API response, or UI state to model",
            "default_target": "launcher status snapshot",
            "output_path_template": "tests/fixtures/{target_slug}.json",
            "prompt_template": "Create a safe JSON fixture example for Guppy about {target_ref}. Output path: {output_path}. Return one fenced json block only. Use representative fake data, no secrets, and keep the schema easy to read.",
        },
        {
            "id": "schema_example",
            "title": "Generate schema example",
            "description": "Create a non-live schema example under config/generated.",
            "target": "merlin-code",
            "task_type": "write",
            "requires_target": True,
            "target_hint": "Workflow or config domain needing a sample schema",
            "default_target": "builder approval payload",
            "output_path_template": "config/generated/{target_slug}.schema.example.json",
            "prompt_template": "Create a safe example JSON schema-like document for Guppy about {target_ref}. Output path: {output_path}. Return one fenced json block only. Keep keys descriptive and avoid production-only fields.",
        },
    ],
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def append_jsonl(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=True) + "\n")


def sanitize_builder_output(text: str) -> str:
    if not text:
        return ""
    cleaned = text.replace("\r\n", "\n").replace("\r", "\n")
    cleaned = _ANSI_ESCAPE_RE.sub("", cleaned)
    cleaned = _CONTROL_CHAR_RE.sub("", cleaned)
    return "\n".join(line.rstrip() for line in cleaned.split("\n")).strip()


def sanitize_builder_file_text(text: str) -> str:
    cleaned = sanitize_builder_output(text)
    if cleaned and not cleaned.endswith("\n"):
        cleaned += "\n"
    return cleaned


def _read_json(path: Path, fallback: dict[str, Any]) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            return data
    except Exception:
        pass
    return json.loads(json.dumps(fallback))


def ensure_builder_template_file(path: Path = TEMPLATE_PATH) -> None:
    if path.exists():
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(_DEFAULT_TEMPLATE_PAYLOAD, indent=2) + "\n", encoding="utf-8")


def _merge_template_payload(payload: dict[str, Any]) -> dict[str, Any]:
    templates = payload.get("templates", []) if isinstance(payload, dict) else []
    merged_templates: list[dict[str, Any]] = []
    seen_ids: set[str] = set()

    if isinstance(templates, list):
        for item in templates:
            if not isinstance(item, dict):
                continue
            template_id = str(item.get("id", "")).strip()
            if not template_id or template_id in seen_ids:
                continue
            merged_templates.append(json.loads(json.dumps(item)))
            seen_ids.add(template_id)

    for item in _DEFAULT_TEMPLATE_PAYLOAD["templates"]:
        template_id = str(item.get("id", "")).strip()
        if template_id and template_id not in seen_ids:
            merged_templates.append(json.loads(json.dumps(item)))
            seen_ids.add(template_id)

    version = max(
        int(payload.get("version", 1) or 1) if isinstance(payload, dict) else 1,
        int(_DEFAULT_TEMPLATE_PAYLOAD.get("version", 1) or 1),
    )
    return {"version": version, "templates": merged_templates}


def ensure_queue_file(path: Path = QUEUE_PATH) -> None:
    if path.exists():
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"version": 1, "tasks": []}, indent=2) + "\n", encoding="utf-8")


def load_builder_templates(path: Path = TEMPLATE_PATH) -> list[dict[str, Any]]:
    ensure_builder_template_file(path)
    payload = _read_json(path, _DEFAULT_TEMPLATE_PAYLOAD)
    merged_payload = _merge_template_payload(payload)
    if merged_payload != payload:
        path.write_text(json.dumps(merged_payload, indent=2) + "\n", encoding="utf-8")
    templates = merged_payload.get("templates", [])
    return [item for item in templates if isinstance(item, dict) and str(item.get("id", "")).strip()]


def _slugify(raw: str) -> str:
    normalized = _SLUG_RE.sub("-", (raw or "").strip().lower()).strip("-")
    return normalized[:48] or "builder-task"


def is_safe_builder_output(rel_path: str) -> bool:
    candidate = Path(str(rel_path or "").replace("\\", "/"))
    if candidate.is_absolute() or not candidate.parts:
        return False
    head = candidate.parts[0]
    if head in _SAFE_ROOTS:
        return True
    return any(candidate == prefix or prefix in candidate.parents for prefix in _SAFE_CONFIG_PREFIXES)


def resolve_safe_builder_output(rel_path: str) -> Path | None:
    candidate = Path(str(rel_path or "").replace("\\", "/"))
    if not is_safe_builder_output(str(candidate)):
        return None
    resolved = (ROOT / candidate).resolve()
    try:
        if resolved.is_relative_to(ROOT.resolve()):
            return resolved
    except Exception:
        return None
    return None


def render_builder_task(
    template_id: str,
    *,
    target_ref: str = "",
    requested_by_instance: str = "guppy-primary",
    queue_path: Path = QUEUE_PATH,
) -> dict[str, Any]:
    template = next((item for item in load_builder_templates() if item["id"] == template_id), None)
    if template is None:
        raise ValueError(f"unknown builder template: {template_id}")
    chosen_target = (target_ref or str(template.get("default_target", "")).strip()).strip()
    target_slug = _slugify(chosen_target or template_id)
    output_path = str(template.get("output_path_template", "")).format(target_slug=target_slug)
    if not resolve_safe_builder_output(output_path):
        raise ValueError(f"unsafe output path for template {template_id}: {output_path}")
    ensure_queue_file(queue_path)
    task_id = f"builder_{template_id}_{int(time.time())}_{target_slug}"
    prompt = str(template.get("prompt_template", "")).format(
        target_ref=chosen_target,
        target_slug=target_slug,
        output_path=output_path,
    )
    return {
        "id": task_id,
        "title": str(template.get("title", template_id)),
        "template_id": template_id,
        "target": str(template.get("target", "merlin-code")),
        "task_type": str(template.get("task_type", "write")),
        "prompt": prompt,
        "status": "pending",
        "priority": 2,
        "created_utc": utc_now(),
        "updated_utc": utc_now(),
        "retry_count": 0,
        "max_retries": 2,
        "dry_run": True,
        "requested_by_instance": requested_by_instance,
        "target_ref": chosen_target,
        "output_file_path": output_path,
    }


def enqueue_builder_task(task: dict[str, Any], queue_path: Path = QUEUE_PATH, metrics_path: Path = METRICS_PATH) -> dict[str, Any]:
    ensure_queue_file(queue_path)
    queue = _read_json(queue_path, {"version": 1, "tasks": []})
    queue.setdefault("tasks", []).append(task)
    queue_path.write_text(json.dumps(queue, indent=2) + "\n", encoding="utf-8")
    append_jsonl(
        metrics_path,
        {
            "ts": utc_now(),
            "event": "builder_task_enqueued",
            "task_id": task.get("id"),
            "template_id": task.get("template_id"),
            "target": task.get("target"),
            "task_type": task.get("task_type"),
            "requested_by_instance": task.get("requested_by_instance"),
        },
    )
    return task


def staged_file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    digest.update(path.read_bytes())
    return digest.hexdigest()


def approve_builder_task(
    task_id: str,
    *,
    queue_path: Path = QUEUE_PATH,
    results_path: Path = RESULTS_PATH,
    metrics_path: Path = METRICS_PATH,
    approved_by: str = "human",
) -> dict[str, Any]:
    ensure_queue_file(queue_path)
    queue = _read_json(queue_path, {"version": 1, "tasks": []})
    tasks = queue.get("tasks", [])
    task = next((item for item in tasks if str(item.get("id", "")) == task_id), None)
    if task is None:
        raise ValueError(f"unknown task id: {task_id}")
    if str(task.get("status", "")) != "awaiting_approval":
        raise ValueError(f"task {task_id} is not awaiting approval")
    approval = task.get("pending_approval") if isinstance(task.get("pending_approval"), dict) else {}
    staged_file = Path(str(approval.get("staged_file", "")))
    output_rel = str(approval.get("workspace_file", task.get("output_file_path", "")))
    safe_output = resolve_safe_builder_output(output_rel)
    if safe_output is None:
        raise ValueError(f"unsafe builder output path: {output_rel}")
    staged_resolved = staged_file.resolve()
    if not staged_resolved.exists() or not staged_resolved.is_relative_to(DRY_RUN_DIR.resolve()):
        raise ValueError(f"invalid staged file: {staged_file}")
    content = sanitize_builder_file_text(staged_resolved.read_text(encoding="utf-8", errors="replace"))
    safe_output.parent.mkdir(parents=True, exist_ok=True)
    safe_output.write_text(content, encoding="utf-8")
    task["status"] = "done"
    task["approved_utc"] = utc_now()
    task["approved_by"] = approved_by
    task["updated_utc"] = utc_now()
    task["approved_output_file"] = str(safe_output.relative_to(ROOT))
    task.pop("pending_approval", None)
    queue_path.write_text(json.dumps(queue, indent=2) + "\n", encoding="utf-8")
    result_payload = {
        "ts": utc_now(),
        "event": "offhours_task_approved",
        "task_id": task.get("id"),
        "title": task.get("title"),
        "template_id": task.get("template_id"),
        "approved_by": approved_by,
        "output_file": str(safe_output),
        "sha256": staged_file_sha256(staged_resolved),
    }
    append_jsonl(results_path, result_payload)
    append_jsonl(metrics_path, result_payload)
    return result_payload


def build_builder_report(
    *,
    queue_path: Path = QUEUE_PATH,
    results_path: Path = RESULTS_PATH,
    metrics_path: Path = METRICS_PATH,
) -> dict[str, Any]:
    ensure_queue_file(queue_path)
    queue = _read_json(queue_path, {"version": 1, "tasks": []})
    counts: dict[str, int] = {}
    for task in queue.get("tasks", []):
        status = str(task.get("status", "unknown"))
        counts[status] = counts.get(status, 0) + 1

    def _tail(path: Path, limit: int = 20) -> list[dict[str, Any]]:
        if not path.exists():
            return []
        items: list[dict[str, Any]] = []
        for line in path.read_text(encoding="utf-8", errors="ignore").splitlines()[-limit:]:
            try:
                payload = json.loads(line)
            except Exception:
                continue
            if isinstance(payload, dict):
                items.append(payload)
        return items

    return {
        "generated_utc": utc_now(),
        "queue_counts": counts,
        "recent_results": _tail(results_path),
        "recent_metrics": _tail(metrics_path),
    }
