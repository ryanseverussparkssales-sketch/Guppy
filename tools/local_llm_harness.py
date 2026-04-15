from __future__ import annotations

import argparse
import json
import time
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.guppy.local_llm.manifest import (
    DEFAULT_LOCAL_LLM_MANIFEST,
    get_baseline_model_entries,
    get_manifest_artifact_path,
    get_manifest_metadata,
    get_memory_backend_baseline,
    load_local_llm_manifest,
)
from tools.verify_ollama_runtime import parse_ollama_list, resolve_model_tag, run_cmd

DEFAULT_PROMPT_PACK = Path("config/local_llm/benchmark_prompts.json")

TRACK_ROLE_MAP = {
    "daily_chat": "fast_assistant",
    "code_repo": "code_assistant",
    "tool_use": "general_reasoning",
    "memory_recall": "general_reasoning",
    "stability": "fast_assistant",
}


def load_prompt_pack(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def select_track_model(track_id: str, manifest: dict[str, Any]) -> dict[str, Any]:
    role = TRACK_ROLE_MAP.get(track_id, "general_reasoning")
    for entry in get_baseline_model_entries(manifest):
        if str(entry.get("role") or "").strip() == role:
            return entry
    entries = get_baseline_model_entries(manifest)
    if not entries:
        raise RuntimeError("No baseline models found in manifest")
    return entries[0]


def generate_once(
    model_tag: str,
    prompt: str,
    timeout_s: int,
    keep_alive: str = "0s",
) -> dict[str, Any]:
    url = "http://localhost:11434/api/generate"
    body = json.dumps(
        {
            "model": model_tag,
            "prompt": prompt,
            "stream": False,
            "keep_alive": keep_alive,
            "options": {"num_predict": 192},
        }
    ).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        started = time.perf_counter()
        with urllib.request.urlopen(req, timeout=timeout_s) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
        duration_ms = round((time.perf_counter() - started) * 1000, 2)
        data = json.loads(raw)
        text = (data.get("response") or "").strip()
        success = bool(text)
        return {
            "success": success,
            "failure_mode": "none" if success else "empty",
            "response_preview": text.replace("\n", " ")[:240],
            "duration_ms": duration_ms,
            "first_token_ms": None,
        }
    except TimeoutError:
        return {
            "success": False,
            "failure_mode": "timeout",
            "response_preview": "",
            "duration_ms": timeout_s * 1000,
            "first_token_ms": None,
        }
    except urllib.error.URLError as exc:
        return {
            "success": False,
            "failure_mode": "runtime_error",
            "response_preview": str(exc.reason),
            "duration_ms": None,
            "first_token_ms": None,
        }
    except Exception as exc:
        return {
            "success": False,
            "failure_mode": "runtime_error",
            "response_preview": str(exc),
            "duration_ms": None,
            "first_token_ms": None,
        }


def ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def append_history(path: Path, payload: dict[str, Any]) -> None:
    ensure_parent(path)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload) + "\n")


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the Guppy Local LLM benchmark harness.")
    parser.add_argument(
        "--manifest-file",
        default=str(DEFAULT_LOCAL_LLM_MANIFEST),
        help="Pinned local-model manifest.",
    )
    parser.add_argument(
        "--prompt-file",
        default=str(DEFAULT_PROMPT_PACK),
        help="Prompt pack describing benchmark tracks.",
    )
    parser.add_argument(
        "--tracks",
        nargs="+",
        help="Optional subset of benchmark tracks to run.",
    )
    parser.add_argument(
        "--max-prompts-per-track",
        type=int,
        default=1,
        help="Maximum prompts to run per track for this harness pass.",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=90,
        help="Per-prompt timeout in seconds.",
    )
    parser.add_argument(
        "--memory-backend",
        default="",
        help="Override recorded memory backend id for the run.",
    )
    parser.add_argument(
        "--latest-file",
        default="",
        help="Override latest aggregate output path.",
    )
    parser.add_argument(
        "--history-file",
        default="",
        help="Override append-only history output path.",
    )
    args = parser.parse_args()

    manifest = load_local_llm_manifest(args.manifest_file)
    prompt_pack = load_prompt_pack(args.prompt_file)
    tracks = prompt_pack.get("tracks") or []
    selected = set(args.tracks or [])
    latest_path = Path(args.latest_file) if args.latest_file else get_manifest_artifact_path(
        manifest, "benchmark_latest", "runtime/local_llm_benchmarks/latest.json"
    )
    history_path = Path(args.history_file) if args.history_file else get_manifest_artifact_path(
        manifest, "benchmark_history", "runtime/local_llm_benchmarks/history.jsonl"
    )
    memory_backend = (
        (args.memory_backend or "").strip()
        or get_memory_backend_baseline(manifest)
    )

    installed_result = run_cmd(["ollama", "list"])
    if installed_result.returncode != 0:
        print(installed_result.stderr or "ollama list failed")
        return 2
    installed = parse_ollama_list(installed_result.stdout)

    ts = datetime.now(timezone.utc).isoformat()
    records: list[dict[str, Any]] = []
    for track in tracks:
        track_id = str(track.get("id") or "").strip()
        if not track_id:
            continue
        if selected and track_id not in selected:
            continue
        prompts = list(track.get("prompts") or [])[: max(1, args.max_prompts_per_track)]
        model_entry = select_track_model(track_id, manifest)
        requested_tag = str(model_entry.get("tag") or "").strip()
        resolved_tag = resolve_model_tag(requested_tag, installed)
        for idx, prompt in enumerate(prompts, start=1):
            if resolved_tag not in installed:
                result = {
                    "success": False,
                    "failure_mode": "runtime_error",
                    "response_preview": "model missing",
                    "duration_ms": None,
                    "first_token_ms": None,
                }
            else:
                result = generate_once(resolved_tag, str(prompt), args.timeout)
            records.append(
                {
                    "track": track_id,
                    "prompt_index": idx,
                    "prompt": str(prompt),
                    "requested_tag": requested_tag,
                    "resolved_tag": resolved_tag,
                    "model_id": model_entry.get("id"),
                    "role": model_entry.get("role"),
                    "memory_backend": memory_backend,
                    **result,
                }
            )

    successes = sum(1 for record in records if record.get("success"))
    payload = {
        "timestamp_utc": ts,
        "manifest_path": str(args.manifest_file),
        "manifest_metadata": get_manifest_metadata(manifest),
        "prompt_file": str(args.prompt_file),
        "memory_backend": memory_backend,
        "total_cases": len(records),
        "successful_cases": successes,
        "failed_cases": len(records) - successes,
        "records": records,
    }
    ensure_parent(latest_path)
    latest_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    append_history(
        history_path,
        {
            "timestamp_utc": ts,
            "total_cases": payload["total_cases"],
            "successful_cases": payload["successful_cases"],
            "failed_cases": payload["failed_cases"],
            "memory_backend": memory_backend,
            "prompt_file": str(args.prompt_file),
            "latest_file": str(latest_path),
        },
    )
    print(f"Latest benchmark written: {latest_path}")
    print(f"History appended: {history_path}")
    print(f"Cases: {payload['successful_cases']}/{payload['total_cases']} successful")
    return 0 if payload["failed_cases"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
