import argparse
import json
import os
import re
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

RUNTIME = Path("runtime")
QUEUE_PATH = RUNTIME / "offhours_task_queue.json"
RESULTS_PATH = RUNTIME / "offhours_task_results.jsonl"
STATE_PATH = RUNTIME / "offhours_task_worker_state.json"
RESULT_DIR = RUNTIME / "offhours_results"

IDLE_STATES = {"idle", "ready", "waiting", ""}
ACTIVE_STATES = {"thinking", "speaking", "listening", "busy", "running"}

ANSI_ESCAPE_RE = re.compile(r"\x1B\[[0-?]*[ -/]*[@-~]")

MODEL_MAP = {
    "guppy-fast": "guppy-fast:latest",
    "vault-scraper": "vault-scraper:latest",
    "merlin-code": "merlin-code:latest",
    "guppy": "guppy:latest",
    "merlin": "merlin:latest",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def parse_utc(ts: str) -> datetime | None:
    try:
        return datetime.fromisoformat(ts)
    except Exception:
        return None


def clean_control_text(text: str) -> str:
    if not text:
        return ""
    stripped = ANSI_ESCAPE_RE.sub("", text)
    # Keep newline/tab and ASCII printable characters; drop spinner glyphs and control chars.
    cleaned = "".join(ch for ch in stripped if ch in "\n\r\t" or 32 <= ord(ch) <= 126)
    return cleaned.strip()


def _read_json(path: Path, fallback: dict[str, Any]) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            return data
    except Exception:
        pass
    return json.loads(json.dumps(fallback))


def _write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def ensure_queue_file(path: Path) -> None:
    if path.exists():
        return
    _write_json(
        path,
        {
            "version": 1,
            "tasks": [],
        },
    )


def append_jsonl(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(payload, ensure_ascii=True) + "\n")


def load_queue(path: Path) -> dict[str, Any]:
    ensure_queue_file(path)
    return _read_json(path, {"version": 1, "tasks": []})


def save_queue(path: Path, queue: dict[str, Any]) -> None:
    _write_json(path, queue)


def seed_defaults(path: Path) -> None:
    queue = load_queue(path)
    tasks = queue.get("tasks", [])
    if tasks:
        return
    now = utc_now()
    queue["tasks"] = [
        {
            "id": "task_gf_daily_summary",
            "title": "Summarize recent runtime signals",
            "target": "guppy-fast",
            "prompt": "Read recent runtime events and produce a concise summary with top 5 action items.",
            "status": "pending",
            "priority": 2,
            "created_utc": now,
            "retry_count": 0,
            "max_retries": 2,
        },
        {
            "id": "task_vault_dedup",
            "title": "Extract metadata and dedup hints",
            "target": "vault-scraper",
            "prompt": "Given pending media notes, produce normalized metadata records and duplicate candidates.",
            "status": "pending",
            "priority": 3,
            "created_utc": now,
            "retry_count": 0,
            "max_retries": 2,
        },
        {
            "id": "task_code_review_batch",
            "title": "Generate overnight code review notes",
            "target": "merlin-code",
            "prompt": "Generate a concise batch code review checklist and likely failure points for changed files.",
            "status": "pending",
            "priority": 1,
            "created_utc": now,
            "retry_count": 0,
            "max_retries": 2,
        },
    ]
    save_queue(path, queue)


def add_task(path: Path, title: str, target: str, prompt: str, priority: int) -> dict[str, Any]:
    queue = load_queue(path)
    task_id = f"task_{int(time.time())}_{abs(hash((title, target))) % 10000}"
    task = {
        "id": task_id,
        "title": title,
        "target": target,
        "prompt": prompt,
        "status": "pending",
        "priority": int(priority),
        "created_utc": utc_now(),
        "retry_count": 0,
        "max_retries": 2,
    }
    queue.setdefault("tasks", []).append(task)
    save_queue(path, queue)
    return task


def list_tasks(path: Path) -> list[dict[str, Any]]:
    queue = load_queue(path)
    return list(queue.get("tasks", []))


def read_activity_state(agent_id: str) -> str:
    p = RUNTIME / f"{agent_id}.activity"
    if not p.exists():
        return ""
    try:
        return p.read_text(encoding="utf-8", errors="ignore").strip().lower()
    except Exception:
        return ""


def is_recent_user_activity(idle_seconds: int) -> bool:
    path = RUNTIME / "launcher_events.jsonl"
    if not path.exists():
        return False
    now = time.time()
    if now - path.stat().st_mtime > idle_seconds:
        return False
    try:
        lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
    except Exception:
        return True
    for line in reversed(lines[-50:]):
        try:
            obj = json.loads(line)
        except Exception:
            continue
        evt = str(obj.get("event", "")).strip().lower()
        if evt == "command_submitted":
            return True
    return False


def agents_are_idle(idle_seconds: int) -> tuple[bool, dict[str, str]]:
    states = {
        "guppy": read_activity_state("guppy"),
        "merlin": read_activity_state("merlin"),
        "council": read_activity_state("council"),
    }
    if is_recent_user_activity(idle_seconds):
        return False, states

    for state in states.values():
        if state in ACTIVE_STATES:
            return False, states
        if state and state not in IDLE_STATES:
            return False, states
    return True, states


def pick_next_task(queue: dict[str, Any]) -> dict[str, Any] | None:
    tasks = [t for t in queue.get("tasks", []) if str(t.get("status", "")) == "pending"]
    if not tasks:
        return None
    tasks.sort(key=lambda t: (int(t.get("priority", 999)), str(t.get("created_utc", ""))))
    return tasks[0]


def recover_stale_running_tasks(queue: dict[str, Any], stale_running_seconds: int) -> int:
    now = datetime.now(timezone.utc)
    changed = 0
    for task in queue.get("tasks", []):
        if str(task.get("status", "")) != "running":
            continue
        last_run = parse_utc(str(task.get("last_run_utc", "")))
        if last_run is None:
            task["status"] = "pending"
            task["updated_utc"] = utc_now()
            changed += 1
            continue
        age_s = (now - last_run).total_seconds()
        if age_s >= stale_running_seconds:
            task["status"] = "pending"
            task["updated_utc"] = utc_now()
            changed += 1
    return changed


def run_local_model(model_tag: str, prompt: str, timeout_s: int) -> tuple[bool, str, str]:
    try:
        res = subprocess.run(
            ["ollama", "run", model_tag, prompt],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout_s,
        )
        out = (res.stdout or "").strip()
        err = (res.stderr or "").strip()
        ok = res.returncode == 0 and bool(out)
        return ok, out, err
    except Exception as e:
        return False, "", str(e)


def run_haiku(prompt: str) -> tuple[bool, str, str]:
    api_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if not api_key:
        return False, "", "ANTHROPIC_API_KEY is not set"
    try:
        import anthropic

        model = os.environ.get("ANTHROPIC_HAIKU_MODEL", "claude-haiku-4-5-20251001")
        client = anthropic.Anthropic(api_key=api_key)
        resp = client.messages.create(
            model=model,
            max_tokens=900,
            temperature=0.2,
            messages=[{"role": "user", "content": prompt}],
        )
        text = (resp.content[0].text if resp.content else "").strip()
        return bool(text), text, ""
    except Exception as e:
        return False, "", str(e)


def execute_task(task: dict[str, Any], timeout_s: int) -> tuple[bool, str, str]:
    target = str(task.get("target", "")).strip().lower()
    prompt = str(task.get("prompt", "")).strip()
    if not prompt:
        return False, "", "task prompt is empty"

    if target == "haiku":
        return run_haiku(prompt)

    model_tag = MODEL_MAP.get(target)
    if not model_tag:
        return False, "", f"unsupported target: {target}"
    return run_local_model(model_tag, prompt, timeout_s)


def write_task_output(task: dict[str, Any], ok: bool, output: str, error: str) -> str:
    RESULT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    task_id = str(task.get("id", "task"))
    out_path = RESULT_DIR / f"{task_id}_{stamp}.md"
    lines = [
        f"# Off-hours Task Result: {task.get('title', task_id)}",
        "",
        f"- task_id: {task_id}",
        f"- target: {task.get('target', '')}",
        f"- status: {'SUCCESS' if ok else 'FAILED'}",
        f"- timestamp_utc: {utc_now()}",
        "",
        "## Prompt",
        str(task.get("prompt", "")),
        "",
        "## Output",
        output or "(no output)",
    ]
    if error:
        lines.extend(["", "## Error", error])
    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return str(out_path)


def process_one_task(queue_path: Path, results_path: Path, timeout_s: int) -> bool:
    queue = load_queue(queue_path)
    task = pick_next_task(queue)
    if task is None:
        return False

    task["status"] = "running"
    task["last_run_utc"] = utc_now()
    save_queue(queue_path, queue)

    ok, output, error = execute_task(task, timeout_s)
    error = clean_control_text(error)
    output_file = write_task_output(task, ok, output, error)

    task["output_file"] = output_file
    task["updated_utc"] = utc_now()

    if ok:
        task["status"] = "done"
    else:
        retry_count = int(task.get("retry_count", 0)) + 1
        max_retries = int(task.get("max_retries", 2))
        task["retry_count"] = retry_count
        task["status"] = "pending" if retry_count <= max_retries else "failed"

    save_queue(queue_path, queue)

    append_jsonl(
        results_path,
        {
            "ts": utc_now(),
            "event": "offhours_task_complete",
            "task_id": task.get("id"),
            "title": task.get("title"),
            "target": task.get("target"),
            "ok": ok,
            "status": task.get("status"),
            "retry_count": task.get("retry_count", 0),
            "output_file": output_file,
            "error": error,
        },
    )
    return True


def write_state(state_path: Path, payload: dict[str, Any]) -> None:
    _write_json(state_path, payload)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run queued off-hours tasks only when agents are idle."
    )
    parser.add_argument("--queue", default=str(QUEUE_PATH))
    parser.add_argument("--results", default=str(RESULTS_PATH))
    parser.add_argument("--state", default=str(STATE_PATH))
    parser.add_argument("--poll-seconds", type=int, default=60)
    parser.add_argument("--idle-seconds", type=int, default=180)
    parser.add_argument("--task-timeout", type=int, default=240)
    parser.add_argument("--stale-running-seconds", type=int, default=900)
    parser.add_argument("--max-tasks-per-run", type=int, default=20)
    parser.add_argument("--once", action="store_true", help="Run one check cycle and exit")
    parser.add_argument("--seed-defaults", action="store_true", help="Seed queue with starter tasks")
    parser.add_argument("--add-title", default="")
    parser.add_argument("--add-target", default="")
    parser.add_argument("--add-prompt", default="")
    parser.add_argument("--add-priority", type=int, default=5)
    parser.add_argument("--list", action="store_true", help="List queue and exit")
    args = parser.parse_args()

    queue_path = Path(args.queue)
    results_path = Path(args.results)
    state_path = Path(args.state)

    ensure_queue_file(queue_path)

    if args.seed_defaults:
        seed_defaults(queue_path)

    if args.add_title and args.add_target and args.add_prompt:
        task = add_task(queue_path, args.add_title, args.add_target, args.add_prompt, args.add_priority)
        print(f"Added task: {task['id']} -> {task['target']}")
        return 0

    if args.list:
        tasks = list_tasks(queue_path)
        print(json.dumps({"count": len(tasks), "tasks": tasks}, indent=2))
        return 0

    processed = 0
    while True:
        queue = load_queue(queue_path)
        reset_count = recover_stale_running_tasks(queue, int(args.stale_running_seconds))
        if reset_count:
            save_queue(queue_path, queue)

        idle, states = agents_are_idle(int(args.idle_seconds))
        state_payload = {
            "ts": utc_now(),
            "idle": idle,
            "activity_states": states,
            "processed_this_run": processed,
            "stale_running_reset": reset_count,
        }
        write_state(state_path, state_payload)

        if idle and processed < int(args.max_tasks_per_run):
            did = process_one_task(queue_path, results_path, timeout_s=int(args.task_timeout))
            if did:
                processed += 1

        if args.once:
            break

        time.sleep(max(10, int(args.poll_seconds)))

    print(
        json.dumps(
            {
                "ts": utc_now(),
                "processed": processed,
                "queue": str(queue_path),
                "results": str(results_path),
                "state": str(state_path),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
