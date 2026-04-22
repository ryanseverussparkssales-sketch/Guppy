from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
API_DIR = ROOT / "src" / "guppy" / "api"
OUTPUT = API_DIR / "server_runtime_snapshot.py"
FRAGMENTS = (
    "_server_fragment_bootstrap.py",
    "_server_fragment_instances_telemetry.py",
    "_server_fragment_ops.py",
    "_server_fragment_local_runtime.py",
    "_server_fragment_runtime_status.py",
    "_server_fragment_runtime_calls.py",
    "_server_fragment_routes_core.py",
    "_server_fragment_routes_ops.py",
)


def build_server_runtime() -> str:
    sections: list[str] = [
        '"""Snapshot of the legacy fragment-stitched FastAPI server module.',
        "",
        "This file is for inspection only.",
        "The canonical server now lives in explicit imported modules under src/guppy/api/.",
        '"""',
        "",
    ]
    for fragment_name in FRAGMENTS:
        fragment_path = API_DIR / fragment_name
        sections.append(f"# === BEGIN {fragment_name} ===")
        sections.append(fragment_path.read_text(encoding="utf-8").rstrip())
        sections.append("")
        sections.append(f"# === END {fragment_name} ===")
        sections.append("")
    return "\n".join(sections)


def main() -> None:
    OUTPUT.write_text(build_server_runtime(), encoding="utf-8")
    print(f"wrote {OUTPUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
