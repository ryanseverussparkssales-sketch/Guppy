"""
bin/vllm_chat.py — Terminal chat against the local vLLM server.

Usage:
    python bin/vllm_chat.py [--url URL] [--model MODEL] [--system SYSTEM_PROMPT]

Defaults to http://127.0.0.1:8000 / model "guppy".
Ctrl+C or type 'exit' / 'quit' to leave.
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.request

# Ollama (already running, GPU-accelerated via HIP) is the default.
# Switch to vLLM if/when the Docker container is running:
#   python bin/vllm_chat.py --url http://127.0.0.1:8000
_DEFAULT_URL = "http://127.0.0.1:11434"
_DEFAULT_MODEL = "guppy"
_SYSTEM = (
    "You are Guppy, a capable local AI assistant running on Ryan's machine. "
    "Be concise and direct."
)


def _post(base: str, path: str, payload: dict, timeout: float = 120.0) -> dict:
    data = json.dumps(payload).encode()
    req = urllib.request.Request(
        f"{base.rstrip('/')}{path}",
        data=data,
        headers={"Content-Type": "application/json", "Accept": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read())


def _stream(base: str, messages: list[dict], model: str) -> str:
    payload = {
        "model": model,
        "messages": messages,
        "stream": True,
        "max_tokens": 2048,
        "temperature": 0.7,
    }
    data = json.dumps(payload).encode()
    req = urllib.request.Request(
        f"{base.rstrip('/')}/v1/chat/completions",
        data=data,
        headers={"Content-Type": "application/json", "Accept": "text/event-stream"},
        method="POST",
    )
    full = ""
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
                delta = obj.get("choices", [{}])[0].get("delta", {}).get("content") or ""
                if delta:
                    print(delta, end="", flush=True)
                    full += delta
            except Exception:
                pass
    print()
    return full


def _check_health(base: str) -> bool:
    # Ollama uses GET / and returns 200; vLLM uses GET /health
    for path in ("/health", "/"):
        try:
            req = urllib.request.Request(
                f"{base.rstrip('/')}{path}",
                headers={"Accept": "application/json"},
                method="GET",
            )
            with urllib.request.urlopen(req, timeout=3) as r:
                if r.status == 200:
                    return True
        except Exception:
            pass
    return False


def main() -> None:
    parser = argparse.ArgumentParser(description="Terminal chat with vLLM")
    parser.add_argument("--url", default=_DEFAULT_URL)
    parser.add_argument("--model", default=_DEFAULT_MODEL)
    parser.add_argument("--system", default=_SYSTEM)
    args = parser.parse_args()

    base: str = args.url
    model: str = args.model

    print(f"Connecting to vLLM at {base}...")
    if not _check_health(base):
        print(f"ERROR: vLLM not reachable at {base}/health")
        print("Start it with:  docker compose -f docker/docker-compose.vllm.yml up -d")
        sys.exit(1)

    print(f"Connected. Model: {model}  (type 'exit' to quit)\n")

    messages: list[dict] = [{"role": "system", "content": args.system}]

    while True:
        try:
            user = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nBye.")
            break

        if not user:
            continue
        if user.lower() in {"exit", "quit", "q"}:
            print("Bye.")
            break

        messages.append({"role": "user", "content": user})
        print("Guppy: ", end="", flush=True)
        try:
            reply = _stream(base, messages, model)
        except Exception as exc:
            print(f"\n[ERROR] {exc}")
            messages.pop()
            continue

        if reply:
            messages.append({"role": "assistant", "content": reply})


if __name__ == "__main__":
    main()
