#!/usr/bin/env python3
"""
Guppy Local LLM Benchmark Harness
===================================
Measures TTFT, tok/s, and quality pass rate across all llamacpp backends.

Usage:
    python tools/benchmark_local_llm.py
    python tools/benchmark_local_llm.py --model llamacpp-hermes3
    python tools/benchmark_local_llm.py --prompts config/local_llm/benchmark_prompts.json
    python tools/benchmark_local_llm.py --timeout 60 --output tools/benchmark_results/run.json
"""
from __future__ import annotations

import argparse
import datetime
import json
import os
import socket
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

# ---------------------------------------------------------------------------
# Optional deps — wrap so the script works even if not installed
# ---------------------------------------------------------------------------
try:
    import httpx as _httpx
    _HTTPX_AVAILABLE = True
except ImportError:
    _HTTPX_AVAILABLE = False

try:
    import tiktoken as _tiktoken
    _enc = _tiktoken.get_encoding("cl100k_base")
    def _count_tokens(text: str) -> int:
        return len(_enc.encode(text))
except Exception:
    def _count_tokens(text: str) -> int:  # type: ignore[misc]
        return max(1, len(text.split()))

# ---------------------------------------------------------------------------
# Model port registry — mirrors _LLAMACPP_CONFIG in routes_backends.py
# (copied here to avoid importing FastAPI deps)
# ---------------------------------------------------------------------------
_MODEL_PORTS: Dict[str, int] = {
    "llamacpp-dispatch":  8085,
    "llamacpp-hermes4":   8086,
    "llamacpp-hermes3":   8087,
    "llamacpp-pepe":      8082,
    "llamacpp-qwen3":     8083,
    "llamacpp-minicpm":   8084,
    "llamacpp-rocinante": 8088,
    "llamacpp-xlam":      8089,
    "llamacpp-chat":      8090,
    "llamacpp-phi4-mini": 8091,
}

# Labels for the ASCII table display
_MODEL_LABELS: Dict[str, str] = {
    "llamacpp-dispatch":  "Qwen2.5-3B Dispatch",
    "llamacpp-hermes4":   "Hermes 4 14B",
    "llamacpp-hermes3":   "Hermes 3 8B",
    "llamacpp-pepe":      "Assistant Pepe 8B",
    "llamacpp-qwen3":     "Qwen3 35B MoE",
    "llamacpp-minicpm":   "MiniCPM-o 4.5",
    "llamacpp-rocinante": "Rocinante X 12B",
    "llamacpp-xlam":      "xLAM-2-8B",
    "llamacpp-chat":      "Llama 3.3 70B (CPU)",
    "llamacpp-phi4-mini": "Phi-4-mini",
}

# ---------------------------------------------------------------------------
# Built-in fallback prompt set
# ---------------------------------------------------------------------------
_DEFAULT_PROMPTS: List[Dict[str, Any]] = [
    {
        "id": "greeting",
        "track": "daily_chat",
        "prompt": "Hello, how are you?",
        "max_tokens": 50,
    },
    {
        "id": "math",
        "track": "daily_chat",
        "prompt": "What is 17 × 23? Show your work.",
        "max_tokens": 100,
    },
    {
        "id": "reasoning",
        "track": "daily_chat",
        "prompt": "A farmer has 17 sheep. All but 9 run away. How many sheep does the farmer have?",
        "max_tokens": 80,
    },
    {
        "id": "code",
        "track": "code_repo",
        "prompt": "Write a Python function to check if a number is prime.",
        "max_tokens": 200,
    },
    {
        "id": "tool_call",
        "track": "tool_use",
        "prompt": "I need to know the weather in New York City.",
        "max_tokens": 150,
    },
    {
        "id": "long_context",
        "track": "stability",
        "prompt": (
            "Summarize the key principles of good software architecture "
            "in 5 bullet points."
        ),
        "max_tokens": 300,
    },
]

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _tcp_alive(port: int, timeout: float = 1.0) -> bool:
    """Quick TCP connect check — used as a fast pre-filter before HTTP liveness."""
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=timeout):
            return True
    except OSError:
        return False


def _http_alive(port: int, timeout: float = 2.0) -> bool:
    """Check liveness via the llamacpp /health endpoint (returns {"status": "ok"})."""
    if not _HTTPX_AVAILABLE:
        return _tcp_alive(port, timeout)
    try:
        r = _httpx.get(f"http://127.0.0.1:{port}/health", timeout=timeout)
        return r.status_code < 500
    except Exception:
        return False


def _passes_quality(text: str) -> bool:
    """Return True if the response looks like a valid (non-error) answer."""
    stripped = text.strip()
    if len(stripped) <= 5:
        return False
    if stripped.startswith('{"error"') or stripped.startswith("{'error'"):
        return False
    if stripped.lower().startswith('"error"') or stripped.lower() == '"error"':
        return False
    return True


def _infer_failure_mode(text: str, timed_out: bool, http_error: Optional[str]) -> str:
    if timed_out:
        return "timeout"
    if http_error:
        return "runtime_error"
    stripped = text.strip()
    if not stripped or len(stripped) <= 5:
        return "empty"
    if stripped.startswith('{"error"'):
        return "runtime_error"
    return "none"


# ---------------------------------------------------------------------------
# Core benchmark logic
# ---------------------------------------------------------------------------

def _run_prompt_streaming(
    port: int,
    model_key: str,
    prompt_text: str,
    max_tokens: int,
    timeout: float,
) -> Dict[str, Any]:
    """
    Send a single chat-completion request (streaming) and measure:
      - ttft_s   : time to first token (seconds)
      - total_s  : total wall-clock duration (seconds)
      - tokens   : total tokens generated (estimated)
      - tok_s    : tokens per second
      - text     : full concatenated response text
      - passed   : quality check result
      - failure  : failure mode string
      - error    : error detail if any
    """
    if not _HTTPX_AVAILABLE:
        return {
            "ttft_s": None,
            "total_s": None,
            "tokens": 0,
            "tok_s": None,
            "text": "",
            "passed": False,
            "failure": "runtime_error",
            "error": "httpx not installed — run: pip install httpx",
        }

    url = f"http://127.0.0.1:{port}/v1/chat/completions"
    payload = {
        "model": model_key,
        "messages": [{"role": "user", "content": prompt_text}],
        "max_tokens": max_tokens,
        "stream": True,
        "temperature": 0.7,
    }

    text_chunks: List[str] = []
    ttft_s: Optional[float] = None
    timed_out = False
    http_error: Optional[str] = None

    t0 = time.monotonic()
    try:
        with _httpx.stream(
            "POST",
            url,
            json=payload,
            timeout=timeout,
            headers={"Accept": "text/event-stream"},
        ) as response:
            if response.status_code >= 400:
                http_error = f"HTTP {response.status_code}"
                return {
                    "ttft_s": None,
                    "total_s": time.monotonic() - t0,
                    "tokens": 0,
                    "tok_s": None,
                    "text": "",
                    "passed": False,
                    "failure": "runtime_error",
                    "error": http_error,
                }

            for raw_line in response.iter_lines():
                line = raw_line.strip()
                if not line:
                    continue
                if line.startswith("data:"):
                    data_str = line[5:].strip()
                    if data_str == "[DONE]":
                        break
                    # Record time-to-first-token on the first real data chunk
                    if ttft_s is None:
                        ttft_s = time.monotonic() - t0
                    try:
                        chunk = json.loads(data_str)
                        delta = chunk.get("choices", [{}])[0].get("delta", {})
                        content = delta.get("content", "")
                        if content:
                            text_chunks.append(content)
                    except (json.JSONDecodeError, IndexError, KeyError):
                        # Some backends emit non-JSON lines — skip gracefully
                        pass

    except _httpx.TimeoutException:
        timed_out = True
    except _httpx.ConnectError:
        http_error = "connection refused"
    except Exception as exc:
        http_error = str(exc)

    total_s = time.monotonic() - t0
    full_text = "".join(text_chunks)
    token_count = _count_tokens(full_text) if full_text else 0
    tok_s = (token_count / total_s) if (total_s > 0 and token_count > 0) else None
    passed = _passes_quality(full_text) and not timed_out and not http_error
    failure = _infer_failure_mode(full_text, timed_out, http_error)
    error_detail = None
    if timed_out:
        error_detail = "timeout"
    elif http_error:
        error_detail = http_error

    return {
        "ttft_s": round(ttft_s, 3) if ttft_s is not None else None,
        "total_s": round(total_s, 3),
        "tokens": token_count,
        "tok_s": round(tok_s, 1) if tok_s is not None else None,
        "text": full_text[:500],  # truncate stored text to keep JSON manageable
        "passed": passed,
        "failure": failure,
        "error": error_detail,
    }


def _run_model_benchmark(
    model_key: str,
    port: int,
    prompts: List[Dict[str, Any]],
    timeout: float,
    verbose: bool = False,
) -> Dict[str, Any]:
    """Benchmark a single model against all prompts. Returns structured result dict."""
    is_alive = _http_alive(port, timeout=min(timeout, 3.0))

    results: List[Dict[str, Any]] = []
    for p in prompts:
        prompt_id   = p.get("id", "unknown")
        prompt_text = p.get("prompt", "")
        max_tokens  = p.get("max_tokens", 150)
        track       = p.get("track", "unknown")

        if not is_alive:
            results.append({
                "prompt_id":  prompt_id,
                "track":      track,
                "ttft_s":     None,
                "total_s":    None,
                "tokens":     0,
                "tok_s":      None,
                "passed":     False,
                "failure":    "runtime_error",
                "error":      "model offline",
            })
            continue

        if verbose:
            print(f"    [{model_key}] prompt={prompt_id!r} ...", end="", flush=True)

        r = _run_prompt_streaming(port, model_key, prompt_text, max_tokens, timeout)

        result_entry = {
            "prompt_id": prompt_id,
            "track":     track,
            "ttft_s":    r["ttft_s"],
            "total_s":   r["total_s"],
            "tokens":    r["tokens"],
            "tok_s":     r["tok_s"],
            "passed":    r["passed"],
            "failure":   r["failure"],
            "error":     r.get("error"),
        }
        results.append(result_entry)

        if verbose:
            status = "PASS" if r["passed"] else f"FAIL({r['failure']})"
            ttft_str = f"{r['ttft_s']:.2f}s" if r["ttft_s"] is not None else "—"
            toks_str = f"{r['tok_s']:.1f}" if r["tok_s"] is not None else "—"
            print(f" {status}  ttft={ttft_str}  tok/s={toks_str}")

    # Aggregate stats
    online_results = [r for r in results if r["error"] != "model offline"]
    passed_count = sum(1 for r in results if r["passed"])
    total_count  = len(results)

    ttfts   = [r["ttft_s"] for r in online_results if r["ttft_s"] is not None]
    tok_ss  = [r["tok_s"]  for r in online_results if r["tok_s"]  is not None]

    avg_ttft  = (sum(ttfts)  / len(ttfts))  if ttfts  else None
    avg_tok_s = (sum(tok_ss) / len(tok_ss)) if tok_ss else None

    return {
        "model_key":   model_key,
        "port":        port,
        "label":       _MODEL_LABELS.get(model_key, model_key),
        "online":      is_alive,
        "total":       total_count,
        "passed":      passed_count,
        "avg_ttft_s":  round(avg_ttft,  3) if avg_ttft  is not None else None,
        "avg_tok_s":   round(avg_tok_s, 1) if avg_tok_s is not None else None,
        "results":     results,
    }


# ---------------------------------------------------------------------------
# ASCII table rendering
# ---------------------------------------------------------------------------

def _render_table(
    model_results: List[Dict[str, Any]],
    run_ts: str,
    total_prompts: int,
) -> str:
    lines: List[str] = []

    header = f"Guppy Local LLM Benchmark — {run_ts}"
    sep_double = "═" * 79
    sep_single = "─" * 79
    col_header = (
        f"{'Model':<22} {'Port':<6} {'Status':<9} "
        f"{'Prompts':<9} {'Avg TTFT':<10} {'Avg tok/s':<11} {'Pass%'}"
    )

    lines.append(header)
    lines.append(sep_double)
    lines.append(col_header)
    lines.append(sep_single)

    for mr in model_results:
        status = "ONLINE" if mr["online"] else "OFFLINE"
        if mr["online"]:
            prompts_str = f"{mr['passed']}/{mr['total']}"
            ttft_str    = f"{mr['avg_ttft_s']:.2f}s" if mr["avg_ttft_s"] is not None else "—"
            toks_str    = f"{mr['avg_tok_s']:.1f}"   if mr["avg_tok_s"]  is not None else "—"
            pct         = int(round(mr["passed"] / mr["total"] * 100)) if mr["total"] else 0
            pass_str    = f"{pct}%"
        else:
            prompts_str = "—"
            ttft_str    = "—"
            toks_str    = "—"
            pass_str    = "—"

        row = (
            f"{mr['model_key']:<22} {mr['port']:<6} {status:<9} "
            f"{prompts_str:<9} {ttft_str:<10} {toks_str:<11} {pass_str}"
        )
        lines.append(row)

    lines.append(sep_double)

    # Summary footer
    online_count = sum(1 for mr in model_results if mr["online"])
    total_count  = len(model_results)
    all_passed   = sum(mr["passed"] for mr in model_results)
    all_total    = sum(mr["total"]  for mr in model_results)
    lines.append(
        f"  {online_count}/{total_count} backends online · "
        f"{all_passed}/{all_total} prompts passed · "
        f"{total_prompts} prompt(s) per model"
    )

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# JSON output
# ---------------------------------------------------------------------------

def _build_json_output(
    model_results: List[Dict[str, Any]],
    run_ts: str,
    prompts: List[Dict[str, Any]],
) -> Dict[str, Any]:
    return {
        "schema_version": 1,
        "run_at": run_ts,
        "prompt_count": len(prompts),
        "models": model_results,
        "summary": {
            "online": sum(1 for mr in model_results if mr["online"]),
            "total":  len(model_results),
            "passed": sum(mr["passed"] for mr in model_results),
            "all_prompts_attempted": sum(mr["total"] for mr in model_results),
        },
    }


# ---------------------------------------------------------------------------
# Prompt loading
# ---------------------------------------------------------------------------

def _load_prompts(prompts_file: Optional[str]) -> List[Dict[str, Any]]:
    """Load prompts from a JSON file, or return the built-in default set."""
    if prompts_file is None:
        # Check the canonical repo location first
        repo_default = (
            Path(__file__).resolve().parent.parent
            / "config" / "local_llm" / "benchmark_prompts.json"
        )
        if repo_default.exists():
            prompts_file = str(repo_default)
        else:
            return _DEFAULT_PROMPTS

    path = Path(prompts_file)
    if not path.exists():
        print(f"[warn] Prompts file not found: {prompts_file} — using built-in defaults")
        return _DEFAULT_PROMPTS

    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
    except Exception as exc:
        print(f"[warn] Could not parse {prompts_file}: {exc} — using built-in defaults")
        return _DEFAULT_PROMPTS

    # Support two formats:
    #   1. Array of {id, prompt, max_tokens}  (simple flat list)
    #   2. {tracks: [{id, prompts: [str, ...]}]}  (the repo's benchmark_prompts.json format)
    if isinstance(data, list):
        return data

    if isinstance(data, dict) and "tracks" in data:
        flat: List[Dict[str, Any]] = []
        for track in data["tracks"]:
            track_id = track.get("id", "unknown")
            for i, prompt_text in enumerate(track.get("prompts", [])):
                flat.append({
                    "id":         f"{track_id}_{i+1}",
                    "track":      track_id,
                    "prompt":     prompt_text,
                    "max_tokens": 300,
                })
        return flat if flat else _DEFAULT_PROMPTS

    return _DEFAULT_PROMPTS


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Guppy Local LLM Benchmark Harness",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--model",
        metavar="KEY",
        help=(
            "Benchmark only this backend key (e.g. llamacpp-hermes3). "
            "Default: all registered backends."
        ),
    )
    parser.add_argument(
        "--prompts",
        metavar="FILE",
        help=(
            "Path to a JSON prompt file. "
            "Defaults to config/local_llm/benchmark_prompts.json (or built-in set)."
        ),
    )
    parser.add_argument(
        "--output",
        metavar="FILE",
        help="Write JSON results to this path.",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=30.0,
        metavar="SECONDS",
        help="Per-prompt timeout in seconds (default: 30).",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Print per-prompt progress while running.",
    )
    parser.add_argument(
        "--save-default",
        action="store_true",
        help=(
            "Auto-save results to tools/benchmark_results/YYYY-MM-DD_HH-MM.json "
            "even if --output is not specified."
        ),
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()

    if not _HTTPX_AVAILABLE:
        print("[error] httpx is required: pip install httpx", file=sys.stderr)
        # Don't exit — allow the rest of the code to produce an OFFLINE table

    # ── determine which models to benchmark ────────────────────────────────
    if args.model:
        if args.model not in _MODEL_PORTS:
            print(
                f"[error] Unknown model key: {args.model!r}\n"
                f"Known keys: {', '.join(sorted(_MODEL_PORTS.keys()))}",
                file=sys.stderr,
            )
            return 1
        model_keys = [args.model]
    else:
        # Consistent ordering: always-on stack first, then rest alphabetically
        always_on_order = [
            "llamacpp-hermes3",
            "llamacpp-hermes4",
            "llamacpp-dispatch",
            "llamacpp-phi4-mini",
        ]
        rest = sorted(k for k in _MODEL_PORTS if k not in always_on_order)
        model_keys = always_on_order + rest

    # ── load prompts ────────────────────────────────────────────────────────
    prompts = _load_prompts(args.prompts)
    if not prompts:
        print("[error] No prompts loaded.", file=sys.stderr)
        return 1

    run_ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"\nGuppy Local LLM Benchmark — {run_ts}")
    print(f"  Models : {len(model_keys)}")
    print(f"  Prompts: {len(prompts)}")
    print(f"  Timeout: {args.timeout}s per prompt\n")

    # ── run benchmarks ──────────────────────────────────────────────────────
    model_results: List[Dict[str, Any]] = []
    for key in model_keys:
        port = _MODEL_PORTS[key]
        label = _MODEL_LABELS.get(key, key)
        print(f"  Probing {key} (port {port}) ...", flush=True)
        mr = _run_model_benchmark(
            model_key=key,
            port=port,
            prompts=prompts,
            timeout=args.timeout,
            verbose=args.verbose,
        )
        model_results.append(mr)

        status = "ONLINE" if mr["online"] else "OFFLINE"
        if mr["online"]:
            ttft_str = f"{mr['avg_ttft_s']:.2f}s" if mr["avg_ttft_s"] is not None else "—"
            toks_str = f"{mr['avg_tok_s']:.1f}"   if mr["avg_tok_s"]  is not None else "—"
            pct = int(round(mr["passed"] / mr["total"] * 100)) if mr["total"] else 0
            print(
                f"    → {status}  {mr['passed']}/{mr['total']} passed  "
                f"ttft={ttft_str}  tok/s={toks_str}  pass={pct}%"
            )
        else:
            print(f"    → {status}")

    # ── render table ─────────────────────────────────────────────────────────
    print()
    table = _render_table(model_results, run_ts, len(prompts))
    print(table)
    print()

    # ── JSON output ──────────────────────────────────────────────────────────
    json_data = _build_json_output(model_results, run_ts, prompts)

    output_path: Optional[str] = args.output

    if output_path is None and args.save_default:
        ts_file = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M")
        out_dir = Path(__file__).resolve().parent / "benchmark_results"
        out_dir.mkdir(parents=True, exist_ok=True)
        output_path = str(out_dir / f"{ts_file}.json")

    if output_path:
        try:
            out_p = Path(output_path)
            out_p.parent.mkdir(parents=True, exist_ok=True)
            with open(out_p, "w", encoding="utf-8") as fh:
                json.dump(json_data, fh, indent=2)
            print(f"Results written to: {out_p}")
        except Exception as exc:
            print(f"[warn] Could not write results to {output_path}: {exc}", file=sys.stderr)

    # Also append to the canonical history file (spec: runtime/local_llm_benchmarks/)
    history_dir = Path(__file__).resolve().parent.parent / "runtime" / "local_llm_benchmarks"
    history_path = history_dir / "history.jsonl"
    try:
        history_dir.mkdir(parents=True, exist_ok=True)
        with open(history_path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps({
                "run_at": json_data["run_at"],
                "summary": json_data["summary"],
                "prompt_count": json_data["prompt_count"],
            }) + "\n")
        # Overwrite latest.json
        latest_path = history_dir / "latest.json"
        with open(latest_path, "w", encoding="utf-8") as fh:
            json.dump(json_data, fh, indent=2)
    except Exception as exc:
        # Never crash just because we couldn't write history
        print(f"[warn] Could not update benchmark history: {exc}", file=sys.stderr)

    # Return exit code 0 even when all models are offline (offline is valid output)
    return 0


if __name__ == "__main__":
    sys.exit(main())
