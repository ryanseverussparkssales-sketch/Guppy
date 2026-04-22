import argparse
import json
import os
import platform
import re
import socket
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


def _safe_read_json(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _git_branch() -> str:
    try:
        proc = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=10,
            check=False,
        )
    except Exception:
        return "unknown"
    if proc.returncode != 0:
        return "unknown"
    return (proc.stdout or "").strip() or "unknown"


def _audio_metadata() -> dict:
    payload: dict[str, object] = {
        "available": False,
        "device_count": 0,
        "default_input_index": None,
        "default_output_index": None,
        "default_input_name": "unknown",
        "default_output_name": "unknown",
        "error": "sounddevice unavailable",
    }
    try:
        import sounddevice as sd

        devices = sd.query_devices()
        defaults = sd.default.device
        input_index = defaults[0] if isinstance(defaults, (list, tuple)) and len(defaults) > 0 else None
        output_index = defaults[1] if isinstance(defaults, (list, tuple)) and len(defaults) > 1 else None

        def _name_for(index: int | None) -> str:
            if index is None:
                return "unknown"
            if index < 0:
                return "system-default"
            if not isinstance(devices, (list, tuple)):
                return "unknown"
            if index >= len(devices):
                return "unknown"
            row = devices[index]
            if isinstance(row, dict):
                return str(row.get("name") or "unknown")
            return "unknown"

        payload.update(
            {
                "available": True,
                "device_count": len(devices) if isinstance(devices, (list, tuple)) else 0,
                "default_input_index": input_index,
                "default_output_index": output_index,
                "default_input_name": _name_for(input_index),
                "default_output_name": _name_for(output_index),
                "error": "",
            }
        )
    except Exception as e:
        payload["error"] = str(e)
    return payload


def _matrix_summary(path: Path) -> dict:
    text = path.read_text(encoding="utf-8") if path.exists() else ""
    scenario_rows = re.findall(r"^\|\s*([A-Z]+-[0-9]{2})\s*\|", text, flags=re.MULTILINE)
    pending_tokens = {"-", "—", "â€”"}
    pending_count = 0
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not re.match(r"^\|\s*[A-Z]+-[0-9]{2}\s*\|", line):
            continue
        cells = [cell.strip() for cell in line.strip("|").split("|")]
        if len(cells) < 6:
            continue
        if all(cell in pending_tokens for cell in cells[-4:]):
            pending_count += 1
    return {
        "path": str(path).replace("\\", "/"),
        "exists": path.exists(),
        "scenario_count": len(scenario_rows),
        "pending_count": pending_count,
    }


def _prefill_markdown(
    *,
    ts_utc: str,
    machine: dict,
    audio: dict,
    provider_snapshot: dict,
    ollama_snapshot: dict,
    voice_matrix: dict,
    runtime_matrix: dict,
) -> str:
    provider_ready = "unknown"
    if provider_snapshot:
        libs = provider_snapshot.get("libraries", {})
        smoke_results = provider_snapshot.get("smoke_results", {})
        libs_ready = isinstance(libs, dict) and all(str(v) != "not-installed" for v in libs.values())
        smoke_ready = isinstance(smoke_results, dict) and all(bool(v.get("ok", False)) for v in smoke_results.values())
        provider_ready = "READY" if (libs_ready and smoke_ready) else "NOT_READY"

    ollama_ready = "unknown"
    if ollama_snapshot:
        missing = ollama_snapshot.get("missing_models", [])
        ping = ollama_snapshot.get("ping_results", {})
        ping_ok = isinstance(ping, dict) and all(bool(v.get("ok", False)) for v in ping.values())
        ollama_ready = "READY" if (not missing and ping_ok) else "NOT_READY"

    lines = [
        "# Voice + Runtime Matrix Prefill Report",
        "",
        f"Generated (UTC): {ts_utc}",
        "",
        "## Automation Scope",
        "",
        "- This report only pre-fills machine/runtime context and does not mark manual pass/fail rows as complete.",
        "- Real-device execution and operator judgment are still required for matrix sign-off.",
        "",
        "## Machine Metadata",
        "",
        "| Field | Value |",
        "|---|---|",
        f"| Hostname | {machine['hostname']} |",
        f"| OS | {machine['os']} |",
        f"| Platform | {machine['platform']} |",
        f"| Python | {machine['python']} |",
        f"| Python Executable | {machine['python_executable']} |",
        f"| Git Branch | {machine['branch']} |",
        "",
        "## Audio Device Snapshot",
        "",
        "| Field | Value |",
        "|---|---|",
        f"| sounddevice Available | {audio.get('available', False)} |",
        f"| Device Count | {audio.get('device_count', 0)} |",
        f"| Default Input | {audio.get('default_input_name', 'unknown')} (index={audio.get('default_input_index')}) |",
        f"| Default Output | {audio.get('default_output_name', 'unknown')} (index={audio.get('default_output_index')}) |",
        f"| Error | {audio.get('error', '') or 'none'} |",
        "",
        "## Runtime Snapshot Status",
        "",
        "| Source | Status | Path |",
        "|---|---|---|",
        f"| Provider Runtime Snapshot | {provider_ready} | runtime/provider_runtime_snapshot.json |",
        f"| Ollama Runtime Snapshot | {ollama_ready} | runtime/model_runtime_snapshot.json |",
        "",
        "## Matrix Coverage Summary",
        "",
        "| Matrix | Exists | Scenario Rows | Pending Rows |",
        "|---|---|---|---|",
        f"| Voice | {voice_matrix['exists']} | {voice_matrix['scenario_count']} | {voice_matrix['pending_count']} |",
        f"| Runtime | {runtime_matrix['exists']} | {runtime_matrix['scenario_count']} | {runtime_matrix['pending_count']} |",
        "",
        "## Suggested Matrix Header Prefill",
        "",
        "Use these values when filling non-pass/fail metadata fields in matrix headers.",
        "",
        f"- Tester: Automation prefill on {machine['hostname']}",
        f"- Date Range: {ts_utc[:10]}",
        "- Blocking Issues: Keep manual unless an automation step failed above.",
        "",
        "## Manual Follow-Up Still Required",
        "",
        "- Execute all real-device voice playback, interruption, and hot-plug scenarios in the voice matrix.",
        "- Execute machine-specific runtime/provider checks on environments that actually hold provider keys and target models.",
        "",
    ]
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate a machine/runtime prefill report for voice and runtime validation matrices."
    )
    parser.add_argument(
        "--voice-matrix",
        default="docs/generated/VOICE_VALIDATION_MATRIX.md",
        help="Voice matrix markdown path.",
    )
    parser.add_argument(
        "--runtime-matrix",
        default="docs/generated/RUNTIME_VALIDATION_MATRIX.md",
        help="Runtime matrix markdown path.",
    )
    parser.add_argument(
        "--provider-snapshot",
        default="runtime/provider_runtime_snapshot.json",
        help="Provider runtime snapshot path.",
    )
    parser.add_argument(
        "--ollama-snapshot",
        default="runtime/model_runtime_snapshot.json",
        help="Ollama runtime snapshot path.",
    )
    parser.add_argument(
        "--report",
        default="docs/generated/VOICE_RUNTIME_VALIDATION_PREFILL.md",
        help="Output markdown report path.",
    )
    args = parser.parse_args()

    ts_utc = datetime.now(timezone.utc).isoformat()
    voice_matrix_path = Path(args.voice_matrix)
    runtime_matrix_path = Path(args.runtime_matrix)
    provider_snapshot = _safe_read_json(Path(args.provider_snapshot))
    ollama_snapshot = _safe_read_json(Path(args.ollama_snapshot))

    machine = {
        "hostname": socket.gethostname(),
        "os": f"{platform.system()} {platform.release()}",
        "platform": platform.platform(),
        "python": platform.python_version(),
        "python_executable": os.path.abspath(sys.executable),
        "branch": _git_branch(),
    }
    audio = _audio_metadata()
    voice_matrix = _matrix_summary(voice_matrix_path)
    runtime_matrix = _matrix_summary(runtime_matrix_path)

    report = _prefill_markdown(
        ts_utc=ts_utc,
        machine=machine,
        audio=audio,
        provider_snapshot=provider_snapshot,
        ollama_snapshot=ollama_snapshot,
        voice_matrix=voice_matrix,
        runtime_matrix=runtime_matrix,
    )

    out_path = Path(args.report)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(report + "\n", encoding="utf-8")

    print("=== Voice/Runtime Matrix Prefill Generator ===")
    print(f"Generated (UTC): {ts_utc}")
    print(f"Report: {out_path}")
    print(f"Voice matrix scenarios: {voice_matrix['scenario_count']} pending: {voice_matrix['pending_count']}")
    print(f"Runtime matrix scenarios: {runtime_matrix['scenario_count']} pending: {runtime_matrix['pending_count']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
