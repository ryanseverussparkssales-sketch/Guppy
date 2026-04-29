"""verify_voice_runtime.py

Real-machine validation for voice engine readiness.
Run this before a release or after changes to TTS dependencies.

Usage:
    python tools/verify_voice_runtime.py            # check all engines
    python tools/verify_voice_runtime.py --engine EDGE TTS
    python tools/verify_voice_runtime.py --quiet    # exit 0/1, no table

Exit codes:
    0  all checked engines are ready
    1  one or more checked engines are unavailable
    2  tool usage error
"""
from __future__ import annotations

import argparse
import os
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.guppy.launcher_application.voice_catalog_support import (
    build_engine_capabilities,
    engine_is_available,
)
from compat_shims.launcher_ui.ui.launcher.views.voices_view import ENGINES

PASS = "READY"
FAIL = "UNAVAILABLE"
SKIP = "SKIPPED"

_COL = {"READY": "\033[32m", "UNAVAILABLE": "\033[31m", "SKIPPED": "\033[33m", "RESET": "\033[0m"}


@dataclass
class EngineResult:
    engine: str
    status: str
    reason: str


def _colour(status: str, text: str) -> str:
    if not sys.stdout.isatty():
        return text
    return f"{_COL.get(status, '')}{text}{_COL['RESET']}"


def check_engines(target: str | None = None) -> list[EngineResult]:
    engines_to_check = {k: v for k, v in ENGINES.items() if target is None or k == target}
    caps = build_engine_capabilities(engines_to_check)
    results: list[EngineResult] = []
    for engine in engines_to_check:
        ok, reason = engine_is_available(caps, engine)
        results.append(EngineResult(engine=engine, status=PASS if ok else FAIL, reason=reason))
    return results


def check_guppy_voice_import() -> tuple[bool, str]:
    try:
        from src.guppy.voice import voice as _v  # noqa: F401
        _ = _v.get_voice_config()
        return True, "Stack C voice facade import OK"
    except Exception as exc:
        return False, f"Voice facade unavailable: {exc}"


def print_table(results: list[EngineResult], gv_ok: bool, gv_reason: str) -> None:
    width = max(len(r.engine) for r in results) + 2
    print(f"\n{'ENGINE':<{width}}  {'STATUS':<12}  REASON")
    print("-" * (width + 35))
    for r in results:
        status_str = _colour(r.status, f"{r.status:<12}")
        print(f"{r.engine:<{width}}  {status_str}  {r.reason}")
    gv_status = PASS if gv_ok else FAIL
    gv_str = _colour(gv_status, f"{gv_status:<12}")
    print(f"{'GuppyVoice backend':<{width}}  {gv_str}  {gv_reason}")
    print()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate voice engine readiness on this machine.")
    parser.add_argument("--engine", help="Check a single engine by name (e.g. 'EDGE TTS')")
    parser.add_argument("--quiet", action="store_true", help="No table output; exit code only")
    args = parser.parse_args(argv)

    target = args.engine or None
    if target and target not in ENGINES:
        print(f"Unknown engine '{target}'. Known engines: {', '.join(ENGINES)}", file=sys.stderr)
        return 2

    results = check_engines(target)
    gv_ok, gv_reason = check_guppy_voice_import()

    if not args.quiet:
        elevenlabs_key = os.environ.get("ELEVENLABS_API_KEY", "")
        if any(r.engine == "ELEVENLABS" for r in results) and not elevenlabs_key:
            print("Note: ELEVENLABS_API_KEY not set — ElevenLabs will show UNAVAILABLE.")
        print_table(results, gv_ok, gv_reason)

    failed = [r for r in results if r.status == FAIL]
    if not gv_ok:
        failed.append(EngineResult("GuppyVoice backend", FAIL, gv_reason))

    if not args.quiet:
        if failed:
            print(f"{len(failed)} engine(s) unavailable: {', '.join(f.engine for f in failed)}")
            print("Run 'pip install edge-tts sounddevice soundfile' for Edge TTS.")
            print("Run 'pip install kokoro kokoro-onnx' for Kokoro (or check Kokoro docs).")
            print("Install pyttsx3 for Windows SAPI. Set ELEVENLABS_API_KEY for ElevenLabs.")
        else:
            ready = [r.engine for r in results if r.status == PASS]
            print(f"All {len(ready)} checked engine(s) ready: {', '.join(ready)}")

    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
