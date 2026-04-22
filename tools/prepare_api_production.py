"""Prepare and validate API auth environment for production readiness.

Usage examples:
  # Report current status only
  python tools/prepare_api_production.py

  # Generate JWT secret if placeholder/missing and disable dev mode
  python tools/prepare_api_production.py --apply --set-strict

  # Keep dev mode enabled but still generate JWT secret
  python tools/prepare_api_production.py --apply
"""

from __future__ import annotations

import argparse
import secrets
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENV_PATH = ROOT / ".env"

_PLACEHOLDERS = {
    "",
    "your-secret-key-change-in-production",
    "your-turnstile-secret",
    "changeme",
    "replace-me",
}


def parse_env(path: Path) -> dict[str, str]:
    data: dict[str, str] = {}
    if not path.exists():
        return data
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        data[k.strip()] = v.strip().strip('"').strip("'")
    return data


def upsert_env(path: Path, updates: dict[str, str]) -> None:
    lines = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
    out: list[str] = []
    seen: set[str] = set()

    for raw in lines:
        if "=" not in raw or raw.lstrip().startswith("#"):
            out.append(raw)
            continue
        k, _ = raw.split("=", 1)
        key = k.strip()
        if key in updates:
            out.append(f"{key}={updates[key]}")
            seen.add(key)
        else:
            out.append(raw)

    for key, val in updates.items():
        if key not in seen:
            out.append(f"{key}={val}")

    path.write_text("\n".join(out) + "\n", encoding="utf-8")


def is_placeholder(val: str) -> bool:
    return (val or "").strip().lower() in _PLACEHOLDERS


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="Apply safe updates to .env")
    ap.add_argument(
        "--set-strict",
        action="store_true",
        help="Set GUPPY_DEV_MODE=0 (requires real TURNSTILE_SECRET for strict startup)",
    )
    args = ap.parse_args()

    env = parse_env(ENV_PATH)
    jwt_secret = env.get("GUPPY_JWT_SECRET", "")
    turnstile = env.get("TURNSTILE_SECRET", "")
    dev_mode = env.get("GUPPY_DEV_MODE", "0")

    jwt_ok = not is_placeholder(jwt_secret)
    turnstile_ok = not is_placeholder(turnstile)
    strict_ok = (dev_mode.strip().lower() in {"0", "false", "no", "off"}) and jwt_ok and turnstile_ok

    print("API auth env report")
    print(f"- .env exists: {ENV_PATH.exists()}")
    print(f"- GUPPY_DEV_MODE={dev_mode!r}")
    print(f"- GUPPY_JWT_SECRET configured: {jwt_ok}")
    print(f"- TURNSTILE_SECRET configured: {turnstile_ok}")
    print(f"- strict-startup ready: {strict_ok}")

    updates: dict[str, str] = {}
    if args.apply and not jwt_ok:
        updates["GUPPY_JWT_SECRET"] = secrets.token_urlsafe(48)
        print("- action: generated GUPPY_JWT_SECRET")

    if args.apply and args.set_strict:
        updates["GUPPY_DEV_MODE"] = "0"
        print("- action: set GUPPY_DEV_MODE=0")

    if updates:
        upsert_env(ENV_PATH, updates)
        print("- .env updated")
        if args.set_strict and not turnstile_ok:
            print("- warning: TURNSTILE_SECRET is still placeholder/missing; strict startup will fail")
            print("  set TURNSTILE_SECRET in .env before running guppy_api.py in strict mode")

    if not args.apply:
        print("- tip: run with --apply to auto-generate JWT secret")
        print("- tip: run with --apply --set-strict after TURNSTILE_SECRET is set")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
