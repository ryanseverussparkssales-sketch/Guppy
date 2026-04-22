import argparse
import importlib.util
import json
import os
import platform
import re
import socket
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

_PENDING_STATUS_TOKENS = {"", "-", "—", "â€”", "Ã¢â‚¬â€"}
_STATUS_ORDER = ("PASS", "FAIL", "PREFILLED", "WAIVED", "PENDING", "OTHER")


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


def _normalize_status(value: str) -> str:
    token = str(value or "").strip()
    if token in _PENDING_STATUS_TOKENS:
        return "PENDING"

    upper = token.upper()
    for label in ("PASS", "FAIL", "PREFILLED", "WAIVED"):
        if upper.startswith(label):
            return label
    return "OTHER"


def _matrix_summary(path: Path) -> dict:
    text = path.read_text(encoding="utf-8") if path.exists() else ""
    scenario_rows = re.findall(r"^\|\s*([A-Z]+-[0-9]{2})\s*\|", text, flags=re.MULTILINE)
    status_counts = {label: 0 for label in _STATUS_ORDER}
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not re.match(r"^\|\s*[A-Z]+-[0-9]{2}\s*\|", line):
            continue
        cells = [cell.strip() for cell in line.strip("|").split("|")]
        if len(cells) < 5:
            continue
        status = _normalize_status(cells[-4])
        status_counts[status] = status_counts.get(status, 0) + 1
    return {
        "path": str(path).replace("\\", "/"),
        "exists": path.exists(),
        "scenario_count": len(scenario_rows),
        "pending_count": status_counts.get("PENDING", 0),
        "status_counts": status_counts,
    }


def _module_available(name: str) -> bool:
    try:
        return importlib.util.find_spec(name) is not None
    except Exception:
        return False


def _voice_runtime_capabilities() -> dict[str, object]:
    return {
        "edge_tts": _module_available("edge_tts"),
        "kokoro": _module_available("kokoro") or _module_available("kokoro_onnx"),
        "faster_whisper": _module_available("faster_whisper"),
        "sounddevice": _module_available("sounddevice"),
        "elevenlabs_api_key": bool(os.environ.get("ELEVENLABS_API_KEY", "").strip()),
        "tts_provider_env": (os.environ.get("GUPPY_TTS_PROVIDER", "").strip() or "auto"),
    }


def _voice_config_summary(voice_bindings: dict, persona_config: dict, app_settings: dict) -> dict[str, object]:
    defaults = voice_bindings.get("defaults", {}) if isinstance(voice_bindings, dict) else {}
    bindings = voice_bindings.get("bindings", {}) if isinstance(voice_bindings, dict) else {}
    by_persona = bindings.get("by_persona", {}) if isinstance(bindings, dict) else {}
    by_model = bindings.get("by_model", {}) if isinstance(bindings, dict) else {}
    assignments = persona_config.get("assignments", {}) if isinstance(persona_config, dict) else {}
    return {
        "default_engine": str(defaults.get("engine") or "unknown"),
        "default_voice_id": str(defaults.get("voice_id") or "unknown"),
        "default_persona_id": str(persona_config.get("default_persona_id") or "unknown"),
        "global_assignment": str(assignments.get("global") or "unknown"),
        "persona_binding_count": len(by_persona) if isinstance(by_persona, dict) else 0,
        "model_binding_count": len(by_model) if isinstance(by_model, dict) else 0,
        "voice_enabled": bool(app_settings.get("enable_voice", False)),
        "runtime_backend": str(app_settings.get("local_runtime_backend") or "unknown"),
    }


def _package_summary(receipt: dict) -> dict[str, object]:
    artifacts = receipt.get("artifacts", []) if isinstance(receipt, dict) else []
    first_artifact = artifacts[0] if isinstance(artifacts, list) and artifacts else {}
    artifact_path = "unknown"
    artifact_size = "unknown"
    if isinstance(first_artifact, dict):
        artifact_path = str(first_artifact.get("path") or "unknown")
        artifact_size = str(first_artifact.get("size") or "unknown")
    return {
        "timestamp": str(receipt.get("timestamp") or receipt.get("timestamp_utc") or "unknown"),
        "ok": bool(receipt.get("ok", False)),
        "stage": str(receipt.get("release_stage") or "unknown"),
        "summary": str(receipt.get("summary") or "unknown"),
        "artifact_path": artifact_path,
        "artifact_size": artifact_size,
    }


def _prefill_markdown(
    *,
    ts_utc: str,
    local_date: str,
    machine: dict,
    audio: dict,
    provider_snapshot: dict,
    ollama_snapshot: dict,
    voice_config: dict,
    voice_capabilities: dict,
    package_evidence: dict,
    voice_matrix: dict,
    runtime_matrix: dict,
) -> str:
    provider_ready = str(provider_snapshot.get("overall_state") or "unknown")
    if provider_ready == "unknown" and provider_snapshot:
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
        "## Voice Runtime Snapshot",
        "",
        "| Field | Value |",
        "|---|---|",
        f"| Voice Enabled | {voice_config.get('voice_enabled', False)} |",
        f"| Runtime Backend | {voice_config.get('runtime_backend', 'unknown')} |",
        f"| Default Voice Binding | {voice_config.get('default_engine', 'unknown')} / {voice_config.get('default_voice_id', 'unknown')} |",
        f"| Default Persona | {voice_config.get('default_persona_id', 'unknown')} |",
        f"| Global Persona Assignment | {voice_config.get('global_assignment', 'unknown')} |",
        f"| Persona Bindings | {voice_config.get('persona_binding_count', 0)} |",
        f"| Model Bindings | {voice_config.get('model_binding_count', 0)} |",
        "",
        "## Voice Capability Snapshot",
        "",
        "| Capability | Value |",
        "|---|---|",
        f"| edge_tts importable | {voice_capabilities.get('edge_tts', False)} |",
        f"| kokoro importable | {voice_capabilities.get('kokoro', False)} |",
        f"| faster_whisper importable | {voice_capabilities.get('faster_whisper', False)} |",
        f"| sounddevice importable | {voice_capabilities.get('sounddevice', False)} |",
        f"| ELEVENLABS_API_KEY present | {voice_capabilities.get('elevenlabs_api_key', False)} |",
        f"| GUPPY_TTS_PROVIDER | {voice_capabilities.get('tts_provider_env', 'auto')} |",
        "",
        "## Package Evidence Snapshot",
        "",
        "| Field | Value |",
        "|---|---|",
        f"| Receipt Timestamp | {package_evidence.get('timestamp', 'unknown')} |",
        f"| Packaging Result | {package_evidence.get('ok', False)} |",
        f"| Stage | {package_evidence.get('stage', 'unknown')} |",
        f"| Summary | {package_evidence.get('summary', 'unknown')} |",
        f"| Artifact | {package_evidence.get('artifact_path', 'unknown')} |",
        f"| Artifact Size | {package_evidence.get('artifact_size', 'unknown')} |",
        "",
        "## Matrix Coverage Summary",
        "",
        "| Matrix | Exists | Scenario Rows | Pass | Prefilled | Waived | Pending | Other |",
        "|---|---|---|---|---|---|---|---|",
        f"| Voice | {voice_matrix['exists']} | {voice_matrix['scenario_count']} | {voice_matrix['status_counts'].get('PASS', 0)} | {voice_matrix['status_counts'].get('PREFILLED', 0)} | {voice_matrix['status_counts'].get('WAIVED', 0)} | {voice_matrix['status_counts'].get('PENDING', 0)} | {voice_matrix['status_counts'].get('OTHER', 0)} |",
        f"| Runtime | {runtime_matrix['exists']} | {runtime_matrix['scenario_count']} | {runtime_matrix['status_counts'].get('PASS', 0)} | {runtime_matrix['status_counts'].get('PREFILLED', 0)} | {runtime_matrix['status_counts'].get('WAIVED', 0)} | {runtime_matrix['status_counts'].get('PENDING', 0)} | {runtime_matrix['status_counts'].get('OTHER', 0)} |",
        "",
        "## Suggested Matrix Header Prefill",
        "",
        "Use these values when filling non-pass/fail metadata fields in matrix headers.",
        "",
        f"- Tester: Automation prefill on {machine['hostname']}",
        f"- Date Range: {local_date} (local)",
        "- Blocking Issues: Keep manual unless an automation step failed above.",
        "",
        "## Manual Follow-Up Still Required",
        "",
        "- Execute real-device voice playback, interruption, preview, and hot-plug scenarios before any GO claim.",
        "- Re-run first-run voice setup on a fresh profile; current-machine evidence comes from an already-configured profile.",
        "- Execute Lemonade and packaged-runtime spot checks on machines that actually host those environments.",
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
        "--voice-bindings",
        default="runtime/voice_bindings.json",
        help="Voice bindings snapshot path.",
    )
    parser.add_argument(
        "--persona-config",
        default="runtime/persona_config.json",
        help="Persona config snapshot path.",
    )
    parser.add_argument(
        "--app-settings",
        default="runtime/app_settings.json",
        help="Application settings snapshot path.",
    )
    parser.add_argument(
        "--package-receipt",
        default="runtime/windows_release_receipt.json",
        help="Windows packaging receipt path.",
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
    voice_bindings = _safe_read_json(Path(args.voice_bindings))
    persona_config = _safe_read_json(Path(args.persona_config))
    app_settings = _safe_read_json(Path(args.app_settings))
    package_receipt = _safe_read_json(Path(args.package_receipt))

    machine = {
        "hostname": socket.gethostname(),
        "os": f"{platform.system()} {platform.release()}",
        "platform": platform.platform(),
        "python": platform.python_version(),
        "python_executable": os.path.abspath(sys.executable),
        "branch": _git_branch(),
    }
    audio = _audio_metadata()
    voice_config = _voice_config_summary(voice_bindings, persona_config, app_settings)
    voice_capabilities = _voice_runtime_capabilities()
    package_evidence = _package_summary(package_receipt)
    voice_matrix = _matrix_summary(voice_matrix_path)
    runtime_matrix = _matrix_summary(runtime_matrix_path)

    report = _prefill_markdown(
        ts_utc=ts_utc,
        local_date=datetime.now().astimezone().date().isoformat(),
        machine=machine,
        audio=audio,
        provider_snapshot=provider_snapshot,
        ollama_snapshot=ollama_snapshot,
        voice_config=voice_config,
        voice_capabilities=voice_capabilities,
        package_evidence=package_evidence,
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
