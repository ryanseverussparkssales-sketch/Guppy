#!/usr/bin/env python3
"""
smoke_api.py — Guppy Phase 3 API smoke test
============================================
Validates all API routes are reachable and responding correctly.

Usage:
    python tests/smoke_api.py
    python tests/smoke_api.py --base-url http://localhost:8080
    python tests/smoke_api.py --claude        # also test Claude endpoint (costs tokens)

Auth:
    Preferred: set GUPPY_JWT_SECRET in env — the script mints its own dev token locally.
    Fallback:  set GUPPY_DEV_MODE=1 on the server — /auth/verify accepts any token.
    Neither:   auth tests are skipped and the script reports what needs to be done.

Exit codes:
    0 — all non-skipped tests passed
    1 — one or more tests failed
"""

import argparse
import asyncio
import io
import json
import os
import socket
import struct
import sys
import time
import wave
from pathlib import Path

# ── Optional dependencies ──────────────────────────────────────────────────────

try:
    import httpx
    HTTPX_OK = True
except ImportError:
    HTTPX_OK = False

try:
    import websockets
    WS_OK = True
except ImportError:
    WS_OK = False

try:
    from jose import jwt as jose_jwt
    JOSE_OK = True
except ImportError:
    JOSE_OK = False

# ── Colour helpers ─────────────────────────────────────────────────────────────

_NO_COLOUR = os.environ.get("NO_COLOR") or not sys.stdout.isatty()

def _c(code: str, text: str) -> str:
    return text if _NO_COLOUR else f"\033[{code}m{text}\033[0m"

GREEN  = lambda t: _c("32", t)
RED    = lambda t: _c("31", t)
YELLOW = lambda t: _c("33", t)
DIM    = lambda t: _c("2",  t)
BOLD   = lambda t: _c("1",  t)

PASS = "PASS"
FAIL = "FAIL"
SKIP = "SKIP"

# ── Result tracking ────────────────────────────────────────────────────────────

_results: list[tuple[str, str, str, float]] = []  # (name, status, msg, ms)

def _record(name: str, status: str, msg: str = "", ms: float = 0.0) -> None:
    tag = {PASS: GREEN("[PASS]"), FAIL: RED("[FAIL]"), SKIP: YELLOW("[SKIP]")}[status]
    ms_str = DIM(f"{ms:6.0f}ms") if ms else DIM("      ")
    detail = f"  {DIM(msg)}" if msg else ""
    print(f"  {tag}  {name:<30} {ms_str}{detail}")
    _results.append((name, status, msg, ms))

def _summary() -> int:
    passed  = sum(1 for _, s, _, _ in _results if s == PASS)
    failed  = sum(1 for _, s, _, _ in _results if s == FAIL)
    skipped = sum(1 for _, s, _, _ in _results if s == SKIP)
    total   = passed + failed

    print()
    print("─" * 60)
    if failed == 0 and total > 0:
        print(BOLD(GREEN(f"  All {passed} tests passed")) + DIM(f"  ({skipped} skipped)"))
    else:
        print(BOLD(RED(f"  {failed}/{total} tests FAILED")) + DIM(f"  ({skipped} skipped)"))
    print()
    return 1 if failed else 0

# ── Helpers ────────────────────────────────────────────────────────────────────

def _silent_wav(duration_s: float = 0.5, sample_rate: int = 22050) -> bytes:
    """Generate a minimal silent WAV for voice endpoint testing."""
    buf = io.BytesIO()
    n_frames = int(sample_rate * duration_s)
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)       # 16-bit PCM
        w.setframerate(sample_rate)
        w.writeframes(b"\x00\x00" * n_frames)
    return buf.getvalue()


def _mint_token(secret: str, user: str = "smoke_test") -> str:
    """Mint a short-lived JWT locally using GUPPY_JWT_SECRET."""
    from datetime import datetime, timedelta, timezone
    payload = {
        "sub": user,
        "iat": datetime.now(timezone.utc),
        "exp": datetime.now(timezone.utc) + timedelta(hours=1),
    }
    return jose_jwt.encode(payload, secret, algorithm="HS256")


def _port_from_url(url: str) -> tuple[str, int]:
    """Parse host + port from a base URL."""
    url = url.rstrip("/")
    if "://" in url:
        url = url.split("://", 1)[1]
    host, _, rest = url.partition(":")
    port = int(rest) if rest else (443 if url.startswith("https") else 80)
    return host, port


# ── Core test runner ───────────────────────────────────────────────────────────

async def run(base_url: str, test_claude: bool) -> int:
    ws_url = base_url.replace("http://", "ws://").replace("https://", "wss://") + "/ws"

    print()
    print(BOLD("Guppy API Smoke Test"))
    print(f"  Target : {base_url}")
    print(f"  Claude : {'enabled' if test_claude else 'skipped (pass --claude to enable)'}")
    print("─" * 60)

    # ── 1. Port reachable ──────────────────────────────────────────────────────
    host, port = _port_from_url(base_url)
    t0 = time.perf_counter()
    try:
        with socket.create_connection((host, port), timeout=2.0):
            pass
        _record("port_reachable", PASS, f"{host}:{port}", (time.perf_counter() - t0) * 1000)
    except OSError as e:
        _record("port_reachable", FAIL, str(e))
        print()
        print(RED("  Server not running.") + "  Start it with:  " + BOLD("bin\\launch_api.bat"))
        return _summary()

    if not HTTPX_OK:
        print(RED("\n  httpx not installed.") + "  Run: pip install httpx")
        return 1

    async with httpx.AsyncClient(base_url=base_url, timeout=10.0) as client:

        # ── 2. Root (no auth) ──────────────────────────────────────────────────
        t0 = time.perf_counter()
        try:
            r = await client.get("/")
            ms = (time.perf_counter() - t0) * 1000
            if r.status_code == 200:
                _record("GET /", PASS, r.json().get("status", ""), ms)
            else:
                _record("GET /", FAIL, f"HTTP {r.status_code}", ms)
        except Exception as e:
            _record("GET /", FAIL, str(e))

        # ── 3. Auth ────────────────────────────────────────────────────────────
        token: str | None = None
        secret = os.environ.get("GUPPY_JWT_SECRET", "").strip()
        _dev_secrets = {"", "dev-secret-key-change-in-production"}

        if JOSE_OK and secret and secret not in _dev_secrets:
            # Mint locally — most reliable, no Turnstile dependency
            t0 = time.perf_counter()
            try:
                token = _mint_token(secret)
                _record("auth_local_mint", PASS,
                        "JWT minted from GUPPY_JWT_SECRET",
                        (time.perf_counter() - t0) * 1000)
            except Exception as e:
                _record("auth_local_mint", FAIL, str(e))
        else:
            # Fall back to /auth/verify — only works if GUPPY_DEV_MODE=1 on server
            t0 = time.perf_counter()
            try:
                r = await client.post("/auth/verify", json={"token": "smoke-test"})
                ms = (time.perf_counter() - t0) * 1000
                if r.status_code == 200:
                    token = r.json().get("access_token")
                    _record("POST /auth/verify", PASS, "dev mode token issued", ms)
                else:
                    _record("POST /auth/verify", FAIL,
                            f"HTTP {r.status_code} — set GUPPY_DEV_MODE=1 or GUPPY_JWT_SECRET", ms)
            except Exception as e:
                _record("POST /auth/verify", FAIL, str(e))

        if not token:
            print()
            print(YELLOW("  Auth unavailable — remaining tests skipped."))
            print("  Fix: set " + BOLD("GUPPY_JWT_SECRET") + " in env, or start server with "
                  + BOLD("GUPPY_DEV_MODE=1"))
            for name in ("GET /status", "POST /chat (ollama)", "POST /chat (claude)", "WS /ws", "POST /chat/voice"):
                _record(name, SKIP, "no token")
            return _summary()

        hdrs = {"Authorization": f"Bearer {token}"}

        # ── 4. /status ─────────────────────────────────────────────────────────
        t0 = time.perf_counter()
        try:
            r = await client.get("/status", headers=hdrs)
            ms = (time.perf_counter() - t0) * 1000
            if r.status_code == 200:
                body = r.json()
                info = (
                    f"tts={body.get('voice_tts_backend', '?')}  "
                    f"stt={body.get('voice_stt_backend', '?')}  "
                    f"daemon={body.get('daemon_available', '?')}"
                )
                _record("GET /status", PASS, info, ms)
            else:
                _record("GET /status", FAIL, f"HTTP {r.status_code}", ms)
        except Exception as e:
            _record("GET /status", FAIL, str(e))

        # ── 5. /chat via Ollama ────────────────────────────────────────────────
        t0 = time.perf_counter()
        try:
            r = await client.post(
                "/chat",
                json={"message": "reply with the single word: pong", "use_claude": False},
                headers=hdrs,
                timeout=60.0,
            )
            ms = (time.perf_counter() - t0) * 1000
            if r.status_code == 200:
                preview = (r.json().get("response") or "")[:50].replace("\n", " ")
                _record("POST /chat (ollama)", PASS, f'"{preview}"', ms)
            elif r.status_code == 503:
                _record("POST /chat (ollama)", SKIP, "Ollama unavailable (503)", ms)
            else:
                _record("POST /chat (ollama)", FAIL, f"HTTP {r.status_code}: {r.text[:80]}", ms)
        except Exception as e:
            _record("POST /chat (ollama)", FAIL, str(e))

        # ── 6. /chat via Claude (opt-in) ───────────────────────────────────────
        if not test_claude:
            _record("POST /chat (claude)", SKIP, "pass --claude to enable")
        else:
            t0 = time.perf_counter()
            try:
                r = await client.post(
                    "/chat",
                    json={"message": "reply with the single word: pong", "use_claude": True},
                    headers=hdrs,
                    timeout=60.0,
                )
                ms = (time.perf_counter() - t0) * 1000
                if r.status_code == 200:
                    preview = (r.json().get("response") or "")[:50].replace("\n", " ")
                    _record("POST /chat (claude)", PASS, f'"{preview}"', ms)
                elif r.status_code == 503:
                    _record("POST /chat (claude)", SKIP, "Claude unavailable (503)", ms)
                else:
                    _record("POST /chat (claude)", FAIL, f"HTTP {r.status_code}: {r.text[:80]}", ms)
            except Exception as e:
                _record("POST /chat (claude)", FAIL, str(e))

        # ── 7. WebSocket ───────────────────────────────────────────────────────
        if not WS_OK:
            _record("WS /ws", SKIP, "websockets package not installed")
        else:
            t0 = time.perf_counter()
            try:
                async with websockets.connect(ws_url, open_timeout=5) as ws:
                    # Auth handshake
                    await ws.send(json.dumps({"token": token}))
                    auth_resp = json.loads(await asyncio.wait_for(ws.recv(), timeout=5))
                    if auth_resp.get("status") != "authenticated":
                        raise RuntimeError(f"Auth rejected: {auth_resp}")

                    # Send a message
                    await ws.send(json.dumps({
                        "message": "reply with one word: pong",
                        "use_claude": False,
                    }))

                    # Collect until "done" or first chunk
                    got_response = False
                    deadline = time.perf_counter() + 60
                    while time.perf_counter() < deadline:
                        try:
                            raw = await asyncio.wait_for(ws.recv(), timeout=5)
                            frame = json.loads(raw)
                            if frame.get("done"):
                                got_response = True
                                break
                            if frame.get("chunk") or frame.get("response"):
                                got_response = True
                                break
                            if frame.get("error"):
                                raise RuntimeError(frame["error"])
                        except asyncio.TimeoutError:
                            break

                ms = (time.perf_counter() - t0) * 1000
                if got_response:
                    _record("WS /ws", PASS, "auth + stream exchange OK", ms)
                else:
                    _record("WS /ws", FAIL, "no chunk/done received within timeout", ms)
            except Exception as e:
                _record("WS /ws", FAIL, str(e), (time.perf_counter() - t0) * 1000)

        # ── 8. /chat/voice ─────────────────────────────────────────────────────
        t0 = time.perf_counter()
        try:
            wav_bytes = _silent_wav()
            r = await client.post(
                "/chat/voice",
                files={"file": ("smoke_test.wav", wav_bytes, "audio/wav")},
                params={"use_claude": "false"},
                headers=hdrs,
                timeout=60.0,
            )
            ms = (time.perf_counter() - t0) * 1000
            if r.status_code == 200:
                body = r.json()
                transcript = (body.get("transcription") or "")[:40]
                _record("POST /chat/voice", PASS, f'transcription="{transcript}"', ms)
            elif r.status_code in (400, 422):
                # Could not transcribe silent audio — route is working, audio was just empty
                _record("POST /chat/voice", PASS,
                        f"HTTP {r.status_code} — route OK, silent audio not transcribable", ms)
            elif r.status_code == 503:
                _record("POST /chat/voice", SKIP, "voice backend unavailable (503)", ms)
            else:
                _record("POST /chat/voice", FAIL, f"HTTP {r.status_code}: {r.text[:80]}", ms)
        except Exception as e:
            _record("POST /chat/voice", FAIL, str(e))

    return _summary()


# ── Entry point ────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="Guppy API smoke test")
    parser.add_argument(
        "--base-url",
        default=os.environ.get("GUPPY_API_URL", "http://localhost:8080"),
        help="Base URL of the API server (default: http://localhost:8080)",
    )
    parser.add_argument(
        "--claude",
        action="store_true",
        help="Also test the Claude endpoint (uses API credits)",
    )
    args = parser.parse_args()

    exit_code = asyncio.run(run(args.base_url, args.claude))
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
