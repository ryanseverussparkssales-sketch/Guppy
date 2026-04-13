import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path


def _pkg_version(name: str) -> str:
    try:
        import importlib.metadata as md

        return md.version(name)
    except Exception:
        return "not-installed"


def _check_openai_compatible(base_url: str, api_key: str, label: str) -> tuple[bool, str]:
    try:
        from openai import OpenAI

        client = OpenAI(api_key=api_key, base_url=base_url)
        models = client.models.list()
        count = len(getattr(models, "data", []) or [])
        return True, f"{label} models listed: {count}"
    except Exception as e:
        return False, f"{label} check failed: {e}"


def _check_gemini(api_key: str) -> tuple[bool, str]:
    try:
        import google.generativeai as genai

        genai.configure(api_key=api_key)
        models = list(genai.list_models())
        return True, f"Gemini models listed: {len(models)}"
    except Exception as e:
        return False, f"Gemini check failed: {e}"


def _check_mistral(api_key: str) -> tuple[bool, str]:
    try:
        from mistralai import Mistral

        client = Mistral(api_key=api_key)
        models = client.models.list()
        data = getattr(models, "data", []) or []
        return True, f"Mistral models listed: {len(data)}"
    except Exception as e:
        return False, f"Mistral check failed: {e}"


def _check_anthropic(api_key: str) -> tuple[bool, str]:
    try:
        import anthropic

        client = anthropic.Anthropic(api_key=api_key)
        # Cheap metadata check that does not generate model output.
        models = client.models.list(limit=5)
        data = getattr(models, "data", []) or []
        return True, f"Anthropic models listed: {len(data)}"
    except Exception as e:
        return False, f"Anthropic check failed: {e}"


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify external LLM provider key/runtime readiness.")
    parser.add_argument("--smoke", action="store_true", help="Run lightweight provider API checks.")
    parser.add_argument(
        "--snapshot-file",
        default="runtime/provider_runtime_snapshot.json",
        help="Path for JSON snapshot output.",
    )
    args = parser.parse_args()

    ts = datetime.now(timezone.utc).isoformat()
    keys = {
        "ANTHROPIC_API_KEY": bool(os.environ.get("ANTHROPIC_API_KEY", "").strip()),
        "OPENROUTER_API_KEY": bool(os.environ.get("OPENROUTER_API_KEY", "").strip()),
        "GROQ_API_KEY": bool(os.environ.get("GROQ_API_KEY", "").strip()),
        "GEMINI_API_KEY": bool(os.environ.get("GEMINI_API_KEY", "").strip()),
        "MISTRAL_API_KEY": bool(os.environ.get("MISTRAL_API_KEY", "").strip()),
    }

    libs = {
        "anthropic": _pkg_version("anthropic"),
        "openai": _pkg_version("openai"),
        "google-generativeai": _pkg_version("google-generativeai"),
        "mistralai": _pkg_version("mistralai"),
    }

    print("=== Guppy Provider Runtime Verifier ===")
    print(f"Timestamp (UTC): {ts}")
    print("\n[1] API key presence")
    for k, present in keys.items():
        print(f"- {'OK' if present else 'MISSING'} {k}")

    print("\n[2] Library availability")
    for k, v in libs.items():
        print(f"- {k}: {v}")

    smoke_results: dict[str, dict[str, str | bool]] = {}
    if args.smoke:
        print("\n[3] Lightweight API smoke checks")
        if keys["ANTHROPIC_API_KEY"]:
            ok, msg = _check_anthropic(os.environ["ANTHROPIC_API_KEY"])
            smoke_results["anthropic"] = {"ok": ok, "message": msg}
            print(f"- {'OK' if ok else 'FAIL'} {msg}")
        if keys["OPENROUTER_API_KEY"]:
            ok, msg = _check_openai_compatible(
                "https://openrouter.ai/api/v1", os.environ["OPENROUTER_API_KEY"], "OpenRouter"
            )
            smoke_results["openrouter"] = {"ok": ok, "message": msg}
            print(f"- {'OK' if ok else 'FAIL'} {msg}")
        if keys["GROQ_API_KEY"]:
            ok, msg = _check_openai_compatible(
                "https://api.groq.com/openai/v1", os.environ["GROQ_API_KEY"], "Groq"
            )
            smoke_results["groq"] = {"ok": ok, "message": msg}
            print(f"- {'OK' if ok else 'FAIL'} {msg}")
        if keys["GEMINI_API_KEY"]:
            ok, msg = _check_gemini(os.environ["GEMINI_API_KEY"])
            smoke_results["gemini"] = {"ok": ok, "message": msg}
            print(f"- {'OK' if ok else 'FAIL'} {msg}")
        if keys["MISTRAL_API_KEY"]:
            ok, msg = _check_mistral(os.environ["MISTRAL_API_KEY"])
            smoke_results["mistral"] = {"ok": ok, "message": msg}
            print(f"- {'OK' if ok else 'FAIL'} {msg}")
    else:
        print("\n[3] Lightweight API smoke checks (skipped)")

    out = {
        "timestamp_utc": ts,
        "key_presence": keys,
        "libraries": libs,
        "smoke_results": smoke_results,
    }

    out_path = Path(args.snapshot_file)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(f"\nSnapshot written: {out_path}")

    missing_keys = [k for k, v in keys.items() if not v]
    smoke_failed = any(not v.get("ok", False) for v in smoke_results.values())
    # READY means runtime tooling is intact; key completeness is advisory.
    ready = all(v != "not-installed" for v in libs.values()) and not smoke_failed
    print("Overall:", "READY" if ready else "NOT READY")
    if missing_keys:
        print("Missing keys (optional, provider-specific): " + ", ".join(missing_keys))

    return 0 if ready else 1


if __name__ == "__main__":
    raise SystemExit(main())
