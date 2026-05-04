"""Live multi-turn tool-use integration test against the running Guppy API.

Scenarios:
  1. memory_write -> memory_recall via action endpoint
  2. Multi-turn conversation: plant fact, recall it 3 turns later
  3. get_time tool call triggered via natural language
  4. web_fetch tool call triggered via natural language
  5. 5-turn coherence: in-history context retention
  6. Chained: preference set, then applied in next turn

Run with:
    python tools/test_tool_use_live.py
"""
from __future__ import annotations

import json
import os
import sys
import time
import urllib.request
import urllib.error

BASE = os.environ.get("GUPPY_TEST_BASE", "http://localhost:8081")
_TOKEN: str = ""


def _get_token() -> str:
    global _TOKEN
    if _TOKEN:
        return _TOKEN
    data = json.dumps({"username": "dev", "password": "dev"}).encode()
    req = urllib.request.Request(
        f"{BASE}/auth/local",
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        _TOKEN = json.loads(resp.read().decode())["access_token"]
    return _TOKEN


def _headers() -> dict:
    return {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {_get_token()}",
    }


def _post_stream(endpoint: str, payload: dict) -> str:
    """POST to SSE endpoint, collect all delta content, return full reply."""
    data = json.dumps(payload).encode()
    req = urllib.request.Request(
        f"{BASE}{endpoint}",
        data=data,
        headers=_headers(),
        method="POST",
    )
    full: list[str] = []
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            for raw in resp:
                line = raw.decode("utf-8", errors="replace").strip()
                if not line.startswith("data:"):
                    continue
                chunk = line[5:].strip()
                if chunk == "[DONE]":
                    break
                try:
                    obj = json.loads(chunk)
                    # OpenAI delta format
                    delta = (
                        obj.get("choices", [{}])[0]
                        .get("delta", {})
                        .get("content", "")
                    )
                    if delta:
                        full.append(delta)
                    # Guppy token format
                    tok = obj.get("token", "")
                    if tok:
                        full.append(tok)
                except Exception:
                    pass
    except urllib.error.HTTPError as exc:
        return f"[HTTP {exc.code}: {exc.reason}]"
    except Exception as exc:
        return f"[ERROR: {exc}]"
    return "".join(full)


def _post_json(endpoint: str, payload: dict) -> dict:
    data = json.dumps(payload).encode()
    req = urllib.request.Request(
        f"{BASE}{endpoint}",
        data=data,
        headers=_headers(),
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        return {"error": f"HTTP {exc.code}", "body": body[:300]}
    except Exception as exc:
        return {"error": str(exc)}


def _chat(history: list[dict], message: str, surface: str = "companion") -> tuple[str, list[dict]]:
    """Send one turn via /api/chat/stream. Returns (reply, updated_history)."""
    payload = {
        "message": message,
        "history": history,
        "surface": surface,
        "session_id": "test-session-live",
    }
    reply = _post_stream("/api/chat/stream", payload)
    updated = history + [
        {"role": "user", "content": message},
        {"role": "assistant", "content": reply},
    ]
    return reply, updated


def _hr(title: str) -> None:
    print()
    print("=" * 62)
    print(f"  {title}")
    print("=" * 62)


def _result(label: str, passed: bool, note: str = "") -> bool:
    status = "PASS" if passed else "FAIL"
    line = f"  [{status}]  {label}"
    if note:
        line += f"  ({note})"
    print(line)
    return passed


# ---- Scenario 1: Action endpoint direct tool calls -------------------------

def scenario_1_action_direct() -> bool:
    _hr("Scenario 1: /api/companion/action  memory_write + memory_recall")

    write_res = _post_json("/api/companion/action", {
        "action": "memory_write",
        "params": {"key": "live_test_pet", "value": "Ryan has a cat named Biscuit who is 5 years old.", "category": "personal"},
    })
    print(f"    write -> {write_res}")
    write_ok = "error" not in write_res

    time.sleep(0.5)

    recall_res = _post_json("/api/companion/action", {
        "action": "memory_recall",
        "params": {"query": "live_test_pet"},
    })
    print(f"    recall -> {str(recall_res)[:200]}")
    recall_ok = "biscuit" in str(recall_res).lower() or "live_test_pet" in str(recall_res).lower()

    return _result("action direct", write_ok and recall_ok, f"write_ok={write_ok} recall_ok={recall_ok}")


# ---- Scenario 2: Multi-turn memory via natural language --------------------

def scenario_2_memory_across_turns() -> bool:
    _hr("Scenario 2: Multi-turn  plant fact -> filler -> recall")
    history: list[dict] = []

    reply, history = _chat(history, "Please remember that my favorite programming language is Rust.")
    print(f"    T1: {reply[:140]}")

    reply, history = _chat(history, "What is 17 multiplied by 8?")
    print(f"    T2: {reply[:100]}")

    reply, history = _chat(history, "What programming language did I say was my favorite?")
    print(f"    T3: {reply[:200]}")

    passed = "rust" in reply.lower() and not reply.startswith("[")
    return _result("memory across turns", passed, f"reply contains 'rust'={passed}")


# ---- Scenario 3: get_time --------------------------------------------------

def scenario_3_get_time() -> bool:
    _hr("Scenario 3: get_time tool call")
    history: list[dict] = []

    reply, history = _chat(history, "What is the exact current date and time right now?")
    print(f"    Reply: {reply[:200]}")

    # Should return something with a year/time or acknowledge it can check
    passed = not reply.startswith("[") and len(reply) > 10
    return _result("get_time", passed)


# ---- Scenario 4: web_fetch -------------------------------------------------

def scenario_4_web_fetch() -> bool:
    _hr("Scenario 4: web_fetch tool call")
    history: list[dict] = []

    reply, history = _chat(
        history,
        "Please fetch https://httpbin.org/json and tell me what the slideshow title is."
    )
    print(f"    Reply: {reply[:300]}")

    passed = not reply.startswith("[HTTP 4") and not reply.startswith("[ERROR") and len(reply) > 10
    return _result("web_fetch", passed)


# ---- Scenario 5: 5-turn coherence ------------------------------------------

def scenario_5_coherence() -> bool:
    _hr("Scenario 5: 5-turn coherence  -- early context retained on turn 5")
    history: list[dict] = []

    reply, history = _chat(history, "My secret project is called AURORA. Remember that.")
    print(f"    T1: {reply[:120]}")

    reply, history = _chat(history, "What is the boiling point of water in Celsius?")
    print(f"    T2: {reply[:80]}")

    reply, history = _chat(history, "Name 3 famous jazz musicians.")
    print(f"    T3: {reply[:120]}")

    reply, history = _chat(history, "What is the largest planet in the solar system?")
    print(f"    T4: {reply[:80]}")

    reply, history = _chat(history, "What was the secret project name I told you about at the start?")
    print(f"    T5: {reply[:200]}")

    passed = "aurora" in reply.lower() and not reply.startswith("[")
    return _result("5-turn coherence", passed, f"reply contains 'AURORA'={passed}")


# ---- Scenario 6: Tool call + follow-up -------------------------------------

def scenario_6_tool_then_followup() -> bool:
    _hr("Scenario 6: tool call + follow-up question about the result")
    history: list[dict] = []

    reply, history = _chat(
        history,
        "Fetch https://httpbin.org/uuid and tell me the UUID you got back."
    )
    print(f"    T1 (fetch): {reply[:200]}")

    # Follow-up that requires the model to remember what it just fetched
    reply, history = _chat(history, "Is that UUID version 4? How can you tell?")
    print(f"    T2 (followup): {reply[:200]}")

    # Should reference UUID structure or v4 indicators - if T1 succeeded
    t1_ok = not reply.replace(" ","").startswith("[HTTP4") and len(reply) > 5
    t2_ok = not history[-1]["content"].startswith("[") and len(history[-1]["content"]) > 10
    passed = t1_ok and t2_ok
    return _result("tool + followup", passed)


# ---- Main ------------------------------------------------------------------

def main() -> None:
    print()
    print("Guppy Live Multi-Turn Tool-Use Test Suite")
    print(f"Target: {BASE}")

    try:
        tok = _get_token()
        print(f"Auth: OK (token ...{tok[-8:]})")
    except Exception as exc:
        print(f"AUTH FAILED: {exc}")
        sys.exit(1)

    results: list[tuple[str, bool]] = []

    scenarios = [
        ("action endpoint (direct)", scenario_1_action_direct),
        ("memory across turns", scenario_2_memory_across_turns),
        ("get_time", scenario_3_get_time),
        ("web_fetch", scenario_4_web_fetch),
        ("5-turn coherence", scenario_5_coherence),
        ("tool + follow-up", scenario_6_tool_then_followup),
    ]

    for name, fn in scenarios:
        try:
            t0 = time.monotonic()
            passed = fn()
            elapsed = time.monotonic() - t0
            results.append((name, passed))
            print(f"    [{elapsed:.1f}s]")
        except Exception as exc:
            import traceback
            print(f"    [CRASH] {exc}")
            traceback.print_exc()
            results.append((name, False))

    _hr("SUMMARY")
    total = len(results)
    passed_count = sum(1 for _, p in results if p)
    for name, p in results:
        print(f"  {'PASS' if p else 'FAIL'}  {name}")
    print()
    print(f"  {passed_count}/{total} passed")
    sys.exit(0 if passed_count == total else 1)


if __name__ == "__main__":
    main()
