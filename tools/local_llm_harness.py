from __future__ import annotations

import argparse
from contextlib import contextmanager
import json
import time
import sys
import os
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
    get_runtime_backend_baseline,
    load_local_llm_manifest,
)
from src.guppy.memory.backend_adapter import get_memory_backend_id
from src.guppy.paths import RUNTIME_DIR
from tools.verify_ollama_runtime import parse_ollama_list, resolve_model_tag, run_cmd

DEFAULT_PROMPT_PACK = Path("config/local_llm/benchmark_prompts.json")
DEFAULT_MEMORY_SEED_PACK = Path("config/local_llm/benchmark_memory_seeds.json")
DEFAULT_OLLAMA_BASE_URL = "http://localhost:11434"
DEFAULT_LEMONADE_BASE_URL = "http://localhost:13305/api/v1"

LOCAL_GUPPY_SYSTEM = """You are Guppy, Ryan's local assistant.
Keep answers concise, grounded, and calm.
Do not claim actions or tool execution you did not actually perform.
If a relevant memory block is provided below, use it naturally without reciting it verbatim.
Prefer direct answers over narration about your own reasoning.
"""

TRACK_ROLE_MAP = {
    "daily_chat": "fast_assistant",
    "code_repo": "code_assistant",
    "tool_use": "general_reasoning",
    "memory_recall": "general_reasoning",
    "stability": "fast_assistant",
}


def build_record_id(record: dict[str, Any]) -> str:
    parts = [
        str(record.get("track") or "").strip(),
        str(record.get("prompt_index") or "").strip(),
        str(record.get("requested_tag") or "").strip(),
        str(record.get("prompt_style") or "").strip(),
        str(record.get("memory_backend") or "").strip(),
    ]
    return "::".join(parts)


def load_prompt_pack(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def load_memory_seed_pack(path: str | Path) -> list[dict[str, Any]]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if isinstance(payload, dict):
        entries = payload.get("entries") or payload.get("memories") or []
    elif isinstance(payload, list):
        entries = payload
    else:
        entries = []
    return [entry for entry in entries if isinstance(entry, dict)]


def select_track_model(track_id: str, manifest: dict[str, Any]) -> dict[str, Any]:
    role = TRACK_ROLE_MAP.get(track_id, "general_reasoning")
    for entry in get_baseline_model_entries(manifest):
        if str(entry.get("role") or "").strip() == role:
            return entry
    entries = get_baseline_model_entries(manifest)
    if not entries:
        raise RuntimeError("No baseline models found in manifest")
    return entries[0]


def build_override_model_entry(tag: str) -> dict[str, Any]:
    cleaned = str(tag or "").strip()
    return {
        "id": cleaned.replace(":", "-"),
        "tag": cleaned,
        "role": "challenger",
    }


def http_json_request(
    url: str,
    timeout_s: int,
    payload: dict[str, Any] | None = None,
    method: str = "POST",
) -> tuple[Any, float]:
    body = json.dumps(payload).encode("utf-8") if payload is not None else None
    req = urllib.request.Request(
        url,
        data=body,
        headers={"Content-Type": "application/json"},
        method=method,
    )
    started = time.perf_counter()
    with urllib.request.urlopen(req, timeout=timeout_s) as resp:
        raw = resp.read().decode("utf-8", errors="replace")
    duration_ms = round((time.perf_counter() - started) * 1000, 2)
    return json.loads(raw), duration_ms


def generate_once_ollama(
    model_tag: str,
    prompt: str,
    timeout_s: int,
    base_url: str = DEFAULT_OLLAMA_BASE_URL,
    keep_alive: str = "0s",
    think: bool | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "model": model_tag,
        "prompt": prompt,
        "stream": False,
        "keep_alive": keep_alive,
        "options": {"num_predict": 192},
    }
    if think is not None:
        payload["think"] = think
    url = f"{base_url.rstrip('/')}/api/generate"
    try:
        data, duration_ms = http_json_request(url, timeout_s=timeout_s, payload=payload)
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


def chat_once_ollama(
    model_tag: str,
    system_prompt: str,
    prompt: str,
    timeout_s: int,
    base_url: str = DEFAULT_OLLAMA_BASE_URL,
    keep_alive: str = "0s",
    think: bool | None = None,
) -> dict[str, Any]:
    url = f"{base_url.rstrip('/')}/api/chat"
    payload: dict[str, Any] = {
        "model": model_tag,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt},
        ],
        "stream": False,
        "keep_alive": keep_alive,
        "options": {"num_predict": 192},
    }
    if think is not None:
        payload["think"] = think
    try:
        data, duration_ms = http_json_request(url, timeout_s=timeout_s, payload=payload)
        message = data.get("message") or {}
        text = str(message.get("content") or "").strip()
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


def chat_once_lemonade(
    model_tag: str,
    system_prompt: str,
    prompt: str,
    timeout_s: int,
    base_url: str = DEFAULT_LEMONADE_BASE_URL,
) -> dict[str, Any]:
    messages: list[dict[str, Any]] = []
    if system_prompt.strip():
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})
    payload = {
        "model": model_tag,
        "messages": messages,
        "stream": False,
        "max_completion_tokens": 192,
        "temperature": 0.2,
    }
    url = f"{base_url.rstrip('/')}/chat/completions"
    try:
        data, duration_ms = http_json_request(url, timeout_s=timeout_s, payload=payload)
        choices = data.get("choices") or []
        first_choice = choices[0] if choices else {}
        message = first_choice.get("message") or {}
        text = str(message.get("content") or "").strip()
        reasoning_text = str(message.get("reasoning_content") or "").strip()
        success = bool(text)
        preview_source = text or (f"[reasoning_only] {reasoning_text}" if reasoning_text else "")
        return {
            "success": success,
            "failure_mode": "none" if success else "empty",
            "response_preview": preview_source.replace("\n", " ")[:240],
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


def fetch_lemonade_downloaded_models(
    timeout_s: int,
    base_url: str = DEFAULT_LEMONADE_BASE_URL,
) -> set[str]:
    url = f"{base_url.rstrip('/')}/models"
    data, _ = http_json_request(url, timeout_s=timeout_s, payload=None, method="GET")
    models = data.get("data") or []
    names: set[str] = set()
    for entry in models:
        if not isinstance(entry, dict):
            continue
        model_id = str(entry.get("id") or "").strip()
        if model_id:
            names.add(model_id)
    return names


def run_prompt_once(
    model_tag: str,
    prompt: str,
    timeout_s: int,
    runtime_backend: str,
    prompt_style: str,
    memory_backend: str,
    runtime_base_url: str,
    memory_context: str = "",
    think: bool | None = None,
) -> dict[str, Any]:
    previous_backend = os.environ.get("GUPPY_SEMANTIC_BACKEND")
    try:
        if memory_backend:
            os.environ["GUPPY_SEMANTIC_BACKEND"] = memory_backend
        if prompt_style == "guppy":
            from guppy_core.system_prompt import get_startup_system

            system_prompt = get_startup_system(
                session_id="local-llm-harness",
                query_context=prompt,
            )
            if runtime_backend == "lemonade":
                return chat_once_lemonade(model_tag, system_prompt, prompt, timeout_s, base_url=runtime_base_url)
            return chat_once_ollama(model_tag, system_prompt, prompt, timeout_s, base_url=runtime_base_url, think=think)
        if prompt_style == "guppy_local":
            system_prompt = LOCAL_GUPPY_SYSTEM
            if memory_context:
                system_prompt += "\n\n" + memory_context
            if runtime_backend == "lemonade":
                return chat_once_lemonade(model_tag, system_prompt, prompt, timeout_s, base_url=runtime_base_url)
            return chat_once_ollama(model_tag, system_prompt, prompt, timeout_s, base_url=runtime_base_url, think=think)
        if runtime_backend == "lemonade":
            return chat_once_lemonade(model_tag, "", prompt, timeout_s, base_url=runtime_base_url)
        return generate_once_ollama(model_tag, prompt, timeout_s, base_url=runtime_base_url, think=think)
    finally:
        if previous_backend is None:
            os.environ.pop("GUPPY_SEMANTIC_BACKEND", None)
        else:
            os.environ["GUPPY_SEMANTIC_BACKEND"] = previous_backend


def reset_harness_prompt_caches() -> None:
    try:
        import guppy_core.system_prompt as system_prompt

        system_prompt._startup_context_cache.clear()
        system_prompt._semantic_context_cache.clear()
        system_prompt._window_context_cache = (0.0, "")
    except Exception:
        return


def get_semantic_context_preview(query: str, n: int = 4) -> str:
    try:
        from src.guppy.memory.semantic import build_semantic_prompt_context

        context = build_semantic_prompt_context(query, n=n)
    except Exception as exc:
        return f"Error: semantic context preview failed. {exc}"
    if not context:
        return ""
    cleaned = " ".join(str(context).split())
    return cleaned[:480]


@contextmanager
def activate_memory_backend(
    memory_backend: str,
    run_root: Path | None = None,
    seed_entries: list[dict[str, Any]] | None = None,
):
    backend_id = get_memory_backend_id(memory_backend)
    previous_backend = os.environ.get("GUPPY_SEMANTIC_BACKEND")
    previous_palace_path = os.environ.get("GUPPY_MEMPALACE_PATH")

    import src.guppy.memory.semantic as semantic

    previous_db_path = semantic.DB_PATH
    previous_chroma_path = semantic.CHROMA_PATH

    try:
        os.environ["GUPPY_SEMANTIC_BACKEND"] = backend_id
        if run_root is not None:
            backend_root = run_root / backend_id
            semantic.DB_PATH = backend_root / "semantic_sqlite" / "guppy_memory.db"
            semantic.CHROMA_PATH = backend_root / "chroma"
            semantic.DB_PATH.parent.mkdir(parents=True, exist_ok=True)
            semantic.CHROMA_PATH.mkdir(parents=True, exist_ok=True)
            if backend_id == "mempalace-adapter":
                palace_path = backend_root / "palace"
                os.environ["GUPPY_MEMPALACE_PATH"] = str(palace_path.resolve())
            else:
                os.environ.pop("GUPPY_MEMPALACE_PATH", None)

        reset_harness_prompt_caches()
        seed_errors: list[str] = []
        for entry in seed_entries or []:
            result = semantic.remember_semantic(
                str(entry.get("key") or "").strip(),
                str(entry.get("value") or "").strip(),
                str(entry.get("category") or "general").strip() or "general",
            )
            if str(result).startswith("Error:"):
                seed_errors.append(str(result))
        if seed_errors:
            joined = " | ".join(seed_errors[:3])
            raise RuntimeError(f"Failed to seed memory backend {backend_id}: {joined}")
        reset_harness_prompt_caches()
        yield backend_id
    finally:
        semantic.DB_PATH = previous_db_path
        semantic.CHROMA_PATH = previous_chroma_path
        if previous_backend is None:
            os.environ.pop("GUPPY_SEMANTIC_BACKEND", None)
        else:
            os.environ["GUPPY_SEMANTIC_BACKEND"] = previous_backend
        if previous_palace_path is None:
            os.environ.pop("GUPPY_MEMPALACE_PATH", None)
        else:
            os.environ["GUPPY_MEMPALACE_PATH"] = previous_palace_path
        reset_harness_prompt_caches()


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
        "--prompt-style",
        default="raw",
        choices=("raw", "guppy", "guppy_local"),
        help="Run raw local generation, the broad Guppy startup scaffold, or a local-lane Guppy scaffold that relies on semantic memory instead of startup briefing.",
    )
    parser.add_argument(
        "--all-tracks-model-tag",
        default="",
        help="Run every track against a single challenger model tag.",
    )
    parser.add_argument(
        "--think",
        default="false",
        choices=("auto", "true", "false"),
        help="Thinking mode for models that support it. Default is false so direct-answer comparisons stay comparable.",
    )
    parser.add_argument(
        "--memory-backend",
        default="",
        help="Override recorded memory backend id for the run.",
    )
    parser.add_argument(
        "--compare-memory-backends",
        nargs="+",
        help="Run the same benchmark pass against multiple memory backends and record all records in one artifact.",
    )
    parser.add_argument(
        "--memory-seed-file",
        default="",
        help="Optional seed pack for isolated memory-backend comparisons.",
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
    parser.add_argument(
        "--runtime-backend-override",
        default="",
        choices=("", "ollama", "lemonade"),
        help="Override the runtime backend recorded and used for the run.",
    )
    parser.add_argument(
        "--runtime-base-url",
        default="",
        help="Optional runtime base URL. Defaults depend on the selected backend.",
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
    memory_backends = (
        [get_memory_backend_id(value) for value in args.compare_memory_backends]
        if args.compare_memory_backends
        else [get_memory_backend_id(memory_backend)]
    )
    deduped_memory_backends: list[str] = []
    for backend in memory_backends:
        if backend not in deduped_memory_backends:
            deduped_memory_backends.append(backend)
    memory_backends = deduped_memory_backends
    runtime_backend = (args.runtime_backend_override or "").strip() or get_runtime_backend_baseline(manifest)
    runtime_base_url = (
        (args.runtime_base_url or "").strip()
        or (DEFAULT_LEMONADE_BASE_URL if runtime_backend == "lemonade" else DEFAULT_OLLAMA_BASE_URL)
    )
    prompt_style = str(args.prompt_style or "raw").strip().lower()
    override_entry = build_override_model_entry(args.all_tracks_model_tag) if args.all_tracks_model_tag else None
    think_mode = str(args.think or "false").strip().lower()
    think_flag = None if think_mode == "auto" else think_mode == "true"
    memory_seed_entries = (
        load_memory_seed_pack(args.memory_seed_file)
        if (args.memory_seed_file or "").strip()
        else []
    )
    use_isolated_memory_root = bool(memory_seed_entries or len(memory_backends) > 1)
    memory_run_root = (
        RUNTIME_DIR
        / "local_memory"
        / "benchmark_runs"
        / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        if use_isolated_memory_root
        else None
    )

    if runtime_backend == "lemonade":
        try:
            installed = fetch_lemonade_downloaded_models(args.timeout, base_url=runtime_base_url)
        except Exception as exc:
            print(str(exc) or "lemonade models query failed")
            return 2
    else:
        installed_result = run_cmd(["ollama", "list"])
        if installed_result.returncode != 0:
            print(installed_result.stderr or "ollama list failed")
            return 2
        installed = parse_ollama_list(installed_result.stdout)

    ts = datetime.now(timezone.utc).isoformat()
    records: list[dict[str, Any]] = []
    for active_memory_backend in memory_backends:
        with activate_memory_backend(
            active_memory_backend,
            run_root=memory_run_root,
            seed_entries=memory_seed_entries,
        ):
            for track in tracks:
                track_id = str(track.get("id") or "").strip()
                if not track_id:
                    continue
                if selected and track_id not in selected:
                    continue
                prompts = list(track.get("prompts") or [])[: max(1, args.max_prompts_per_track)]
                model_entry = override_entry or select_track_model(track_id, manifest)
                requested_tag = str(model_entry.get("tag") or "").strip()
                resolved_tag = (
                    requested_tag
                    if runtime_backend == "lemonade"
                    else resolve_model_tag(requested_tag, installed)
                )
                for idx, prompt in enumerate(prompts, start=1):
                    semantic_context_preview = (
                        get_semantic_context_preview(str(prompt))
                        if prompt_style in {"guppy", "guppy_local"}
                        else ""
                    )
                    if resolved_tag not in installed:
                        result = {
                            "success": False,
                            "failure_mode": "runtime_error",
                            "response_preview": "model missing",
                            "duration_ms": None,
                            "first_token_ms": None,
                        }
                    else:
                        result = run_prompt_once(
                            resolved_tag,
                            str(prompt),
                            args.timeout,
                            runtime_backend=runtime_backend,
                            prompt_style=prompt_style,
                            memory_backend=active_memory_backend,
                            runtime_base_url=runtime_base_url,
                            memory_context=semantic_context_preview,
                            think=think_flag,
                        )
                    record = {
                        "track": track_id,
                        "prompt_index": idx,
                        "prompt": str(prompt),
                        "requested_tag": requested_tag,
                        "resolved_tag": resolved_tag,
                        "route": f"{runtime_backend}:{resolved_tag}",
                        "model_id": model_entry.get("id"),
                        "role": model_entry.get("role"),
                        "prompt_style": prompt_style,
                        "think_mode": think_mode,
                        "memory_backend": active_memory_backend,
                        "memory_context_preview": semantic_context_preview,
                        "review_score": None,
                        "notes": "",
                    }
                    record["record_id"] = build_record_id(record)
                    record.update(result)
                    records.append(record)

    successes = sum(1 for record in records if record.get("success"))
    payload = {
        "timestamp_utc": ts,
        "manifest_path": str(args.manifest_file),
        "manifest_metadata": get_manifest_metadata(manifest),
        "prompt_file": str(args.prompt_file),
        "runtime_backend": runtime_backend,
        "runtime_base_url": runtime_base_url,
        "prompt_style": prompt_style,
        "think_mode": think_mode,
        "memory_backend": memory_backends[0] if len(memory_backends) == 1 else None,
        "memory_backends": memory_backends,
        "memory_seed_file": str(args.memory_seed_file or ""),
        "memory_seed_count": len(memory_seed_entries),
        "comparison_mode": len(memory_backends) > 1,
        "memory_run_root": str(memory_run_root) if memory_run_root is not None else "",
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
            "runtime_backend": runtime_backend,
            "runtime_base_url": runtime_base_url,
            "prompt_style": prompt_style,
            "think_mode": think_mode,
            "memory_backend": memory_backends[0] if len(memory_backends) == 1 else None,
            "memory_backends": memory_backends,
            "memory_seed_file": str(args.memory_seed_file or ""),
            "memory_seed_count": len(memory_seed_entries),
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
