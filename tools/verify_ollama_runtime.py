import argparse
import json
import re
import subprocess
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

_NO_WIN: dict = (
    {"creationflags": subprocess.CREATE_NO_WINDOW}
    if sys.platform == "win32" else {}
)


DEFAULT_MODELS = ["guppy-fast", "vault-scraper", "merlin-code", "guppy", "merlin"]


@dataclass
class CmdResult:
    returncode: int
    stdout: str
    stderr: str


def run_cmd(args: list[str], timeout_s: int = 180) -> CmdResult:
    proc = subprocess.run(
        args,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout_s,
        **_NO_WIN,
    )
    return CmdResult(proc.returncode, (proc.stdout or "").strip(), (proc.stderr or "").strip())


def parse_ollama_list(output: str) -> set[str]:
    names: set[str] = set()
    for line in output.splitlines():
        line = line.strip()
        if not line or line.startswith("NAME"):
            continue
        parts = line.split()
        if parts:
            names.add(parts[0])
    return names


def extract_num_ctx(show_output: str) -> int | None:
    m = re.search(r"\bnum_ctx\s+(\d+)\b", show_output)
    if not m:
        return None
    return int(m.group(1))


def parse_ps_rows(ps_output: str) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for line in ps_output.splitlines():
        s = line.strip()
        if not s or s.startswith("NAME"):
            continue
        # Split on runs of 2+ spaces to preserve values like "4 minutes from now".
        cols = re.split(r"\s{2,}", s)
        if len(cols) >= 5:
            name = cols[0].strip()
            processor = cols[3].strip()
            context = cols[4].strip() if len(cols) >= 5 else ""
            until = cols[5].strip() if len(cols) >= 6 else ""
            rows.append(
                {
                    "name": name,
                    "processor": processor,
                    "context": context,
                    "until": until,
                }
            )
    return rows


def _console_safe(text: str) -> str:
    # Avoid UnicodeEncodeError on Windows consoles using legacy encodings.
    return text.encode("cp1252", errors="replace").decode("cp1252")


def _http_ping(tag: str, prompt: str, timeout_s: int) -> dict:
    """
    Ping a model via the Ollama HTTP API (POST /api/generate).
    Avoids the 30-60s cold-start overhead of `ollama run` subprocess.
    Uses keep_alive=0 so the model unloads immediately after the ping.
    """
    url = "http://localhost:11434/api/generate"
    body = json.dumps({
        "model": tag,
        "prompt": prompt,
        "stream": False,
        "keep_alive": "0s",
        "options": {"num_predict": 16},   # very short reply — just confirm the model responds
    }).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout_s) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
        data = json.loads(raw)
        response_text = (data.get("response") or "").strip()
        ok = bool(response_text)
        sample = response_text.replace("\n", " ")[:120]
        return {"ok": ok, "reason": "ok" if ok else "empty response", "sample": sample}
    except TimeoutError:
        return {"ok": False, "reason": f"timeout after {timeout_s}s", "sample": ""}
    except urllib.error.URLError as e:
        return {"ok": False, "reason": f"connection error: {e.reason}", "sample": ""}
    except Exception as e:
        return {"ok": False, "reason": str(e), "sample": ""}


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Verify Ollama model/runtime readiness for Guppy personas."
    )
    parser.add_argument(
        "--models",
        nargs="+",
        default=DEFAULT_MODELS,
        help="Model names (without :latest) to verify.",
    )
    parser.add_argument(
        "--prompt",
        default="status ping",
        help="Short prompt used for per-model readiness pings.",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=180,
        help="Per-command timeout in seconds (ollama list/show/ps).",
    )
    parser.add_argument(
        "--ping-timeout",
        type=int,
        default=60,
        help="Per-model HTTP ping timeout in seconds (default 60). "
             "Uses Ollama REST API — much faster than CLI run.",
    )
    parser.add_argument(
        "--skip-ping",
        action="store_true",
        help="Skip model response pings entirely.",
    )
    parser.add_argument(
        "--snapshot-file",
        default="runtime/model_runtime_snapshot.json",
        help="Where to write JSON verification snapshot.",
    )
    args = parser.parse_args()

    ts = datetime.now(timezone.utc).isoformat()
    wanted_tags = list(dict.fromkeys(m if ":" in m else f"{m}:latest" for m in args.models))

    print("=== Guppy Ollama Runtime Verifier ===")
    print(f"Timestamp (UTC): {ts}")
    print(f"Models: {', '.join(wanted_tags)}")
    print()

    version = run_cmd(["ollama", "--version"], timeout_s=args.timeout)
    if version.returncode != 0:
        print("FAIL: Ollama is not reachable from PATH.")
        if version.stderr:
            print(version.stderr)
        return 2
    print(f"OK: {version.stdout or 'ollama detected'}")

    listed = run_cmd(["ollama", "list"], timeout_s=args.timeout)
    if listed.returncode != 0:
        print("FAIL: Could not list Ollama models.")
        if listed.stderr:
            print(listed.stderr)
        return 2

    installed = parse_ollama_list(listed.stdout)
    missing = [m for m in wanted_tags if m not in installed]

    print("\n[1] Installed model check")
    for tag in wanted_tags:
        print(f"- {'OK' if tag in installed else 'MISSING'} {tag}")

    print("\n[2] Runtime parameter check (num_ctx)")
    model_ctx: dict[str, int | None] = {}
    for tag in wanted_tags:
        show = run_cmd(["ollama", "show", tag], timeout_s=args.timeout)
        num_ctx = extract_num_ctx(show.stdout) if show.returncode == 0 else None
        model_ctx[tag] = num_ctx
        if show.returncode == 0:
            print(f"- {tag}: num_ctx={num_ctx if num_ctx is not None else 'unknown'}")
        else:
            print(f"- {tag}: show failed ({show.stderr or 'no error text'})")

    ping_results: dict[str, dict[str, str | bool]] = {}
    if not args.skip_ping:
        print(f"\n[3] Per-model HTTP ping (timeout={args.ping_timeout}s each)")
        print("    Using Ollama REST API — no subprocess load overhead.")
        for tag in wanted_tags:
            if tag in missing:
                ping_results[tag] = {"ok": False, "reason": "model missing", "sample": ""}
                print(f"- SKIP {tag}: model missing")
                continue
            result = _http_ping(tag, args.prompt, args.ping_timeout)
            ping_results[tag] = result
            ok = result["ok"]
            sample = _console_safe(str(result.get("sample", "")))
            print(f"- {'OK  ' if ok else 'FAIL'} {tag}: {sample}")
    else:
        print("\n[3] Per-model response ping (skipped)")

    ps = run_cmd(["ollama", "ps"], timeout_s=args.timeout)
    print("\n[4] Active residency and GPU split (ollama ps)")
    if ps.returncode == 0:
        print(ps.stdout or "(no active models)")
    else:
        print(f"FAIL: {ps.stderr or 'unable to query ollama ps'}")

    ps_rows = parse_ps_rows(ps.stdout) if ps.returncode == 0 else []

    snapshot = {
        "timestamp_utc": ts,
        "requested_models": wanted_tags,
        "installed_models": sorted(installed),
        "missing_models": missing,
        "model_num_ctx": model_ctx,
        "ping_results": ping_results,
        "ps_rows": ps_rows,
        "ps_raw": ps.stdout,
    }

    out_path = Path(args.snapshot_file)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(snapshot, indent=2), encoding="utf-8")
    print(f"\nSnapshot written: {out_path}")

    any_ping_fail = any(not item.get("ok", False) for item in ping_results.values())
    ok = not missing and not any_ping_fail and version.returncode == 0 and listed.returncode == 0
    print("\nOverall:", "READY" if ok else "NOT READY")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())