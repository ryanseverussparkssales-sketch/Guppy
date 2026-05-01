import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.guppy.local_llm.manifest import DEFAULT_LOCAL_LLM_MANIFEST
from src.guppy.local_llm.runtime_challengers import HostRuntimeFacts, load_manifest_runtime_probe

_NO_WIN: dict = (
    {"creationflags": subprocess.CREATE_NO_WINDOW}
    if sys.platform == "win32"
    else {}
)


def _detect_windows_gpu_names() -> tuple[str, ...]:
    if sys.platform != "win32":
        return tuple()
    try:
        proc = subprocess.run(
            ["wmic", "path", "win32_VideoController", "get", "name"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=10,
            **_NO_WIN,
        )
    except Exception:
        return tuple()

    if proc.returncode != 0:
        return tuple()

    names: list[str] = []
    for line in proc.stdout.splitlines():
        value = line.strip()
        if not value or value.lower() == "name":
            continue
        names.append(value)
    return tuple(dict.fromkeys(names))


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Probe local runtime challenger availability and host-fit guidance."
    )
    parser.add_argument(
        "--manifest-file",
        default=str(DEFAULT_LOCAL_LLM_MANIFEST),
        help="Local LLM manifest file containing runtime_challengers.",
    )
    parser.add_argument(
        "--snapshot-file",
        default="runtime/runtime_challenger_snapshot.json",
        help="Where to write JSON challenger snapshot.",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Exit non-zero when no benchmark-first recommendation is available.",
    )
    args = parser.parse_args()

    host = HostRuntimeFacts(
        platform_system=sys.platform,
        gpu_names=_detect_windows_gpu_names(),
    )

    payload = load_manifest_runtime_probe(args.manifest_file, host=host)
    payload["timestamp_utc"] = datetime.now(timezone.utc).isoformat()
    payload["manifest_path"] = str(args.manifest_file)

    out_path = Path(args.snapshot_file)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    recommended = payload.get("recommended_next") or {}
    benchmark_first = str(recommended.get("benchmark_first") or "")
    integration_first = str(recommended.get("integration_first") or "")
    research_track = str(recommended.get("research_track") or "")

    print("=== Guppy Runtime Challenger Probe ===")
    print(f"Manifest: {args.manifest_file}")
    print(f"Host platform: {host.platform_system}")
    print(f"Host GPUs: {', '.join(host.gpu_names) if host.gpu_names else '(none detected)'}")
    print()
    print("Recommended next:")
    print(f"- benchmark_first: {benchmark_first or '(none)'}")
    print(f"- integration_first: {integration_first or '(none)'}")
    print(f"- research_track: {research_track or '(none)'}")
    print()
    print(f"Snapshot written: {out_path}")

    if args.strict and not benchmark_first:
        print("Overall: NOT READY (no benchmark-first challenger)")
        return 1

    print("Overall: READY")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
