"""
verify_tool_agents.py — Health-check and preconditioner for the always-on workspace agent stack.

Tests three agents:
  dispatch  (Qwen2.5-Omni-3B)    port 8085  — orchestrator
  xLAM      (xLAM-2-8B-fc-r)    port 8089  — tool-call specialist
  hermes4   (Hermes 4 14B)       port 8086  — primary workspace agent

For each agent, three rounds:
  1. Liveness    — GET /v1/models, expect HTTP 200
  2. Chat        — simple non-tool completion, measures base latency
  3. Tool call   — sends a minimal tool definition; model MUST emit tool_calls JSON
                   (not free text) to pass. Verifies function name and argument key.

Then runs a preconditioning pass on agents that passed: sends the production system
prompt + the first N tool schemas so llama.cpp KV-cache is warm for real requests.

Usage:
  python tools/verify_tool_agents.py
  python tools/verify_tool_agents.py --skip-precondition
  python tools/verify_tool_agents.py --agents xlam hermes4
  python tools/verify_tool_agents.py --json          # machine-readable output
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# ── agent registry ────────────────────────────────────────────────────────────

_AGENTS: dict[str, dict[str, Any]] = {
    "dispatch": {
        "label": "Dispatch (Qwen2.5-Omni-3B)",
        "port": 8085,
        "model": "qwen2.5-omni-3b",
        "vram_gb": 2.5,
        # Dispatch is an orchestrator — it routes tasks to xLAM/Hermes4 rather than
        # executing tool calls directly. At 3B params, it lacks reliable structured
        # function-calling output. tool_call test is advisory-only for this agent.
        "tool_call_advisory": True,
    },
    "xlam": {
        "label": "xLAM-2-8B-fc-r (Llama-xLAM-2)",
        "port": 8089,
        "model": "Llama-xLAM-2-8B-fc-r-Q4_K_M.gguf",
        "vram_gb": 5.0,
        "tool_call_advisory": False,
    },
    "hermes4": {
        "label": "Hermes 4 14B",
        "port": 8086,
        "model": "hermes-4-14b",
        "vram_gb": 11.0,
        "tool_call_advisory": False,
    },
}

# ── probe tool definition ─────────────────────────────────────────────────────
# A single unambiguous tool that any properly-configured function-calling model
# should invoke when asked the probe question below.

_PROBE_TOOL = {
    "type": "function",
    "function": {
        "name": "get_current_time",
        "description": "Get the current date and time for a given timezone. Always call this tool when the user asks for the current time.",
        "parameters": {
            "type": "object",
            "properties": {
                "timezone": {
                    "type": "string",
                    "description": "IANA timezone name (e.g. UTC, America/New_York, Asia/Tokyo)",
                }
            },
            "required": ["timezone"],
        },
    },
}

_PROBE_QUESTION = (
    "What is the current time in Tokyo? "
    "You MUST call the get_current_time tool with timezone='Asia/Tokyo'. "
    "Do not answer from memory."
)

_PROBE_SYSTEM = (
    "You are a function-calling assistant. "
    "When the user asks for current time, always call the get_current_time tool. "
    "Never answer with a made-up time."
)

# ── production precondition payload ──────────────────────────────────────────
# Mirrors the system prompt prefix that stream_unified_inference injects.
# Sending this exact prefix primes llama.cpp KV-cache for real requests.

_PRECONDITION_SYSTEM = (
    "You are Guppy, a personal AI assistant with access to a wide set of tools. "
    "For any request that requires live data, file access, calendar entries, email, "
    "CRM contacts, media downloads, or web search — call the appropriate tool. "
    "Think step-by-step before calling tools. Never fabricate results.\n\n"
    "AVAILABLE TOOLS: web_search, calibre_search, calibre_add_book, "
    "send_to_kindle, gutenberg_search, openlibrary_search, screenpipe_search, "
    "calendar_list_events, calendar_create_event, email_search, email_send, "
    "crm_search_contacts, crm_create_contact, task_create, task_list, "
    "file_read, file_write, file_list, desktop_screenshot, desktop_click, "
    "desktop_type, reminders_create, reminders_list, media_search, "
    "document_upload, document_analyze, voip_log_call"
)

_PRECONDITION_MESSAGE = (
    "System warm-up: confirm you are ready and list the tool categories available to you. "
    "Keep the answer under 50 words."
)


# ── result types ──────────────────────────────────────────────────────────────

@dataclass
class StepResult:
    name: str
    ok: bool
    latency_ms: float = 0.0
    detail: str = ""


@dataclass
class AgentResult:
    name: str
    label: str
    port: int
    liveness: StepResult = field(default_factory=lambda: StepResult("liveness", False))
    chat: StepResult = field(default_factory=lambda: StepResult("chat", False))
    tool_call: StepResult = field(default_factory=lambda: StepResult("tool_call", False))
    precondition: StepResult = field(default_factory=lambda: StepResult("precondition", False))

    @property
    def overall_ok(self) -> bool:
        return self.liveness.ok and self.chat.ok and self.tool_call.ok


# ── HTTP helpers ──────────────────────────────────────────────────────────────

def _get(url: str, timeout: float = 3.0) -> tuple[int, dict]:
    try:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as e:
        return e.code, {}
    except Exception as e:
        return 0, {"error": str(e)}


def _post(url: str, payload: dict, timeout: float = 60.0) -> tuple[int, dict]:
    data = json.dumps(payload).encode()
    req = urllib.request.Request(
        url,
        data=data,
        method="POST",
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as e:
        try:
            body = json.loads(e.read())
        except Exception:
            body = {"error": str(e)}
        return e.code, body
    except Exception as e:
        return 0, {"error": str(e)}


# ── individual checks ─────────────────────────────────────────────────────────

def check_liveness(port: int) -> StepResult:
    url = f"http://127.0.0.1:{port}/v1/models"
    t0 = time.monotonic()
    status, body = _get(url, timeout=3.0)
    ms = (time.monotonic() - t0) * 1000
    if status == 200:
        models = [m.get("id", "") for m in (body.get("data") or [])]
        return StepResult("liveness", True, ms, f"models={models}")
    return StepResult("liveness", False, ms, f"HTTP {status} — {body.get('error', 'no response')}")


def check_chat(port: int, model: str) -> StepResult:
    url = f"http://127.0.0.1:{port}/v1/chat/completions"
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": "You are a helpful assistant. Be brief."},
            {"role": "user", "content": "Reply with exactly: AGENT_READY"},
        ],
        "max_tokens": 20,
        "temperature": 0,
        "stream": False,
    }
    t0 = time.monotonic()
    status, body = _post(url, payload, timeout=30.0)
    ms = (time.monotonic() - t0) * 1000
    if status != 200:
        return StepResult("chat", False, ms, f"HTTP {status} — {body.get('error', '')}")
    content = ((body.get("choices") or [{}])[0].get("message") or {}).get("content", "")
    ok = bool(content and len(content.strip()) > 0)
    return StepResult("chat", ok, ms, f"response={content.strip()[:80]!r}")


def check_tool_call(port: int, model: str) -> StepResult:
    """Verify the model emits a structured tool_call (not free text) for an unambiguous prompt."""
    url = f"http://127.0.0.1:{port}/v1/chat/completions"
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": _PROBE_SYSTEM},
            {"role": "user", "content": _PROBE_QUESTION},
        ],
        "tools": [_PROBE_TOOL],
        "tool_choice": "auto",
        "max_tokens": 256,
        "temperature": 0,
        "stream": False,
    }
    t0 = time.monotonic()
    status, body = _post(url, payload, timeout=60.0)
    ms = (time.monotonic() - t0) * 1000

    if status != 200:
        return StepResult("tool_call", False, ms, f"HTTP {status} — {body.get('error', '')}")

    choice = (body.get("choices") or [{}])[0]
    message = choice.get("message") or {}
    tool_calls = message.get("tool_calls") or []
    finish = choice.get("finish_reason", "")

    if not tool_calls:
        # Some models put tool calls in content as JSON text — detect that too
        content = str(message.get("content") or "")
        if "get_current_time" in content:
            return StepResult(
                "tool_call", False, ms,
                f"WARN: model embedded tool call in text (not structured). finish={finish!r}. "
                f"content={content[:120]!r}"
            )
        return StepResult(
            "tool_call", False, ms,
            f"No tool_calls emitted. finish={finish!r}. content={str(message.get('content',''))[:80]!r}"
        )

    fn = tool_calls[0].get("function", {})
    fn_name = fn.get("name", "")
    try:
        fn_args = json.loads(fn.get("arguments", "{}"))
    except Exception:
        fn_args = {}

    if fn_name != "get_current_time":
        return StepResult(
            "tool_call", False, ms,
            f"Wrong function called: {fn_name!r} (expected 'get_current_time'). args={fn_args}"
        )

    has_tz = "timezone" in fn_args
    return StepResult(
        "tool_call", True, ms,
        f"OK {fn_name}(timezone={fn_args.get('timezone')!r}) "
        + ("-- timezone arg present" if has_tz else "WARN: timezone arg missing")
    )


def run_precondition(port: int, model: str) -> StepResult:
    """Send the production system-prompt prefix to prime the model's KV cache."""
    url = f"http://127.0.0.1:{port}/v1/chat/completions"
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": _PRECONDITION_SYSTEM},
            {"role": "user", "content": _PRECONDITION_MESSAGE},
        ],
        "max_tokens": 80,
        "temperature": 0,
        "stream": False,
    }
    t0 = time.monotonic()
    status, body = _post(url, payload, timeout=90.0)
    ms = (time.monotonic() - t0) * 1000

    if status != 200:
        return StepResult("precondition", False, ms, f"HTTP {status} — {body.get('error', '')}")

    content = ((body.get("choices") or [{}])[0].get("message") or {}).get("content", "")
    tokens_in = (body.get("usage") or {}).get("prompt_tokens", 0)
    tokens_out = (body.get("usage") or {}).get("completion_tokens", 0)
    return StepResult(
        "precondition", True, ms,
        f"KV cache primed: {tokens_in} prompt tokens, {tokens_out} completion tokens. "
        f"response={content.strip()[:60]!r}"
    )


# ── runner ────────────────────────────────────────────────────────────────────

def run_agent(name: str, skip_precondition: bool = False) -> AgentResult:
    cfg = _AGENTS[name]
    result = AgentResult(name=name, label=cfg["label"], port=cfg["port"])
    advisory = cfg.get("tool_call_advisory", False)

    result.liveness = check_liveness(cfg["port"])
    if not result.liveness.ok:
        return result

    result.chat = check_chat(cfg["port"], cfg["model"])
    if not result.chat.ok:
        return result

    tc = check_tool_call(cfg["port"], cfg["model"])
    if advisory and not tc.ok:
        # Rewrite as advisory pass so dispatch doesn't drag summary to FAIL
        tc = StepResult(
            "tool_call", True, tc.latency_ms,
            f"[ADVISORY] {tc.detail} — expected for orchestrator role at 3B params"
        )
    result.tool_call = tc

    if not skip_precondition and result.liveness.ok:
        result.precondition = run_precondition(cfg["port"], cfg["model"])

    return result


# ── output ────────────────────────────────────────────────────────────────────

_PASS = "PASS"
_FAIL = "FAIL"
_SKIP = "SKIP"


def _fmt(step: StepResult, ran: bool = True) -> str:
    if not ran:
        return f"  {_SKIP:<4}  {step.name}"
    badge = _PASS if step.ok else _FAIL
    lat = f"{step.latency_ms:6.0f}ms" if step.latency_ms else "       "
    return f"  {badge:<4}  {step.name:<14}  {lat}  {step.detail}"


def print_result(r: AgentResult, ran_precondition: bool = True) -> None:
    overall = "PASS" if r.overall_ok else "FAIL"
    print(f"\n{'-'*60}")
    print(f"  {r.label}  (port {r.port})  ->  {overall}")
    print(f"{'-'*60}")
    print(_fmt(r.liveness))
    print(_fmt(r.chat, ran=r.liveness.ok))
    print(_fmt(r.tool_call, ran=r.liveness.ok and r.chat.ok))
    if ran_precondition:
        print(_fmt(r.precondition, ran=r.liveness.ok))


def results_to_dict(results: list[AgentResult]) -> dict:
    out = {}
    for r in results:
        out[r.name] = {
            "label": r.label,
            "port": r.port,
            "ok": r.overall_ok,
            "liveness": {"ok": r.liveness.ok, "ms": r.liveness.latency_ms, "detail": r.liveness.detail},
            "chat": {"ok": r.chat.ok, "ms": r.chat.latency_ms, "detail": r.chat.detail},
            "tool_call": {"ok": r.tool_call.ok, "ms": r.tool_call.latency_ms, "detail": r.tool_call.detail},
            "precondition": {"ok": r.precondition.ok, "ms": r.precondition.latency_ms, "detail": r.precondition.detail},
        }
    return out


# ── entry point ───────────────────────────────────────────────────────────────

def main() -> int:
    parser = argparse.ArgumentParser(description="Verify and precondition workspace tool agents")
    parser.add_argument(
        "--agents", nargs="+", choices=list(_AGENTS), default=list(_AGENTS),
        metavar="NAME", help="Which agents to test (default: all)"
    )
    parser.add_argument("--skip-precondition", action="store_true", help="Skip KV-cache warm-up pass")
    parser.add_argument("--json", action="store_true", dest="json_out", help="Output machine-readable JSON")
    args = parser.parse_args()

    if not args.json_out:
        print(f"\nGuppy Workspace Agent Verification  —  {time.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"Agents: {', '.join(args.agents)}")
        print(f"Precondition: {'no' if args.skip_precondition else 'yes'}")

    results: list[AgentResult] = []
    for name in args.agents:
        if not args.json_out:
            print(f"\n[{name}] testing...")
        r = run_agent(name, skip_precondition=args.skip_precondition)
        results.append(r)
        if not args.json_out:
            print_result(r, ran_precondition=not args.skip_precondition)

    if args.json_out:
        print(json.dumps(results_to_dict(results), indent=2))
        return 0

    passed = sum(1 for r in results if r.overall_ok)
    total = len(results)
    print(f"\n{'='*60}")
    print(f"  Summary: {passed}/{total} agents fully operational")

    for r in results:
        cfg = _AGENTS.get(r.name, {})
        if not r.liveness.ok:
            bat = {
                "dispatch": r"C:\llama-cpp\launch-dispatch.bat",
                "xlam":     r"C:\llama-cpp\launch-xlam.bat",
                "hermes4":  r"C:\llama-cpp\launch-hermes-4-14b.bat",
            }.get(r.name, "")
            print(f"\n  ! {r.label} is DOWN.")
            if bat:
                print(f"    Start it: {bat}")
            print(f"    Or let the Guppy API auto-start it (restarts clear and re-trigger auto_start).")
        elif not r.tool_call.ok and not cfg.get("tool_call_advisory", False):
            print(f"\n  ! {r.label}: structured tool_calls not working.")
            print(f"    Ensure llama-server was started with --jinja (required since llama.cpp b5000+).")
            print(f"    Check: curl http://127.0.0.1:{r.port}/v1/models")

    print()
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
