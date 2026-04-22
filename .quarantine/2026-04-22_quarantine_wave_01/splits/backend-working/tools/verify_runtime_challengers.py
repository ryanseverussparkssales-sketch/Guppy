from __future__ import annotations

import argparse
import json
import platform
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.guppy.local_llm import DEFAULT_LOCAL_LLM_MANIFEST
from src.guppy.local_llm.runtime_challengers import HostRuntimeFacts, load_manifest_runtime_probe


def _read_windows_gpu_names() -> list[str]:
    if sys.platform != "win32":
        return []
    try:
        import subprocess

        cmd = [
            "powershell",
            "-NoProfile",
            "-Command",
            "Get-CimInstance Win32_VideoController | Select-Object -ExpandProperty Name",
        ]
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=20,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        if proc.returncode != 0:
            return []
        return [line.strip() for line in (proc.stdout or "").splitlines() if line.strip()]
    except Exception:
        return []


def _read_windows_memory_bytes() -> int | None:
    if sys.platform != "win32":
        return None
    try:
        import subprocess

        cmd = [
            "powershell",
            "-NoProfile",
            "-Command",
            "(Get-CimInstance Win32_ComputerSystem).TotalPhysicalMemory",
        ]
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=20,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        if proc.returncode != 0:
            return None
        raw = (proc.stdout or "").strip()
        return int(raw) if raw.isdigit() else None
    except Exception:
        return None


def main() -> int:
    parser = argparse.ArgumentParser(description="Probe local runtime challengers for the current host.")
    parser.add_argument(
        "--manifest-file",
        default=str(DEFAULT_LOCAL_LLM_MANIFEST),
        help="Local LLM manifest file to inspect.",
    )
    parser.add_argument(
        "--snapshot-file",
        default="runtime/runtime_challenger_snapshot.json",
        help="Where to write the challenger runtime snapshot.",
    )
    args = parser.parse_args()

    host = HostRuntimeFacts(
        platform_system=platform.system(),
        gpu_names=tuple(_read_windows_gpu_names()),
        total_memory_bytes=_read_windows_memory_bytes(),
    )
    payload = load_manifest_runtime_probe(args.manifest_file, host=host)
    payload["timestamp_utc"] = datetime.now(timezone.utc).isoformat()
    payload["manifest_path"] = str(Path(args.manifest_file))

    snapshot_path = Path(args.snapshot_file)
    snapshot_path.parent.mkdir(parents=True, exist_ok=True)
    snapshot_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    print("=== Guppy Runtime Challenger Probe ===")
    print(f"Host: {payload['host']['platform_system']}")
    if payload["host"]["gpu_names"]:
        print(f"GPU(s): {', '.join(payload['host']['gpu_names'])}")
    benchmark_first = payload["recommended_next"]["benchmark_first"] or "none"
    integration_first = payload["recommended_next"]["integration_first"] or "none"
    research_track = payload["recommended_next"]["research_track"] or "none"
    print(f"Benchmark-first challenger: {benchmark_first}")
    print(f"Integration-first challenger: {integration_first}")
    print(f"Research track: {research_track}")
    print(f"Snapshot written: {snapshot_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
