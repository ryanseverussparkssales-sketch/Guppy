import argparse
import hashlib
import json
import platform
import shutil
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

SOURCE_ROOT = Path(__file__).resolve().parents[1]

DEFAULT_INCLUDE_PATHS = [
    "bin",
    "docs",
    "models",
    "tests",
    "tools",
    "ui",
    "utils",
    "web",
    "README.md",
    "ROADMAP.md",
    "DAILY_WORKFLOW.md",
    "requirements.txt",
    "pyproject.toml",
    "theme.json",
    "app_settings.json",
    "chroma_db",
    "runtime/ops_telemetry.sqlite3",
    "runtime/response_cache.sqlite3",
    "runtime/triage_regression_state.json",
    "runtime/nightly_triage_summary.md",
    "runtime/pilot_exit_report.json",
    "runtime/offhours_task_queue.json",
    "runtime/offhours_task_results.jsonl",
    "runtime/hub_patterns.jsonl",
    "runtime/router_scorecard.jsonl",
    "runtime/session_events.jsonl",
    "runtime/integration_events.jsonl",
    "runtime/reminder_events.jsonl",
    "runtime/agent_performance.jsonl",
    "runtime/daily_reports",
]

DEFAULT_GLOBS = ["*.py", "*.bat", "*.spec", "*.md"]

EXCLUDE_DIRS = {
    ".git",
    ".venv",
    ".pytest_cache",
    "__pycache__",
    "build",
    "dist",
    "node_modules",
}

EXCLUDE_SUFFIXES = {".pyc", ".pyo", ".tmp"}


@dataclass
class CopiedFile:
    rel_path: str
    size: int
    sha256: str


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _iter_files(path: Path) -> list[Path]:
    if path.is_file():
        return [path]

    files: list[Path] = []
    for candidate in path.rglob("*"):
        if not candidate.is_file():
            continue
        rel = candidate.relative_to(SOURCE_ROOT)
        if any(part in EXCLUDE_DIRS for part in rel.parts):
            continue
        if candidate.suffix.lower() in EXCLUDE_SUFFIXES:
            continue
        files.append(candidate)
    return files


def _collect_candidates() -> list[Path]:
    candidates: set[Path] = set()

    for rel_str in DEFAULT_INCLUDE_PATHS:
        rel = Path(rel_str)
        src = SOURCE_ROOT / rel
        if not src.exists():
            continue
        for item in _iter_files(src):
            candidates.add(item)

    for pattern in DEFAULT_GLOBS:
        for item in SOURCE_ROOT.glob(pattern):
            if item.is_file() and item.suffix.lower() not in EXCLUDE_SUFFIXES:
                candidates.add(item)

    return sorted(candidates)


def _copy_files(files: list[Path], snapshot_data_dir: Path, with_hash: bool) -> tuple[list[CopiedFile], int]:
    copied: list[CopiedFile] = []
    total_bytes = 0

    for src in files:
        rel = src.relative_to(SOURCE_ROOT)
        dst = snapshot_data_dir / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)

        size = src.stat().st_size
        total_bytes += size
        copied.append(
            CopiedFile(
                rel_path=rel.as_posix(),
                size=size,
                sha256=_sha256(src) if with_hash else "",
            )
        )

    return copied, total_bytes


def _prune_old_snapshots(snapshots_root: Path, retain: int) -> None:
    snapshots = sorted([p for p in snapshots_root.iterdir() if p.is_dir()])
    if len(snapshots) <= retain:
        return
    for old in snapshots[: len(snapshots) - retain]:
        shutil.rmtree(old, ignore_errors=True)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Create a portable Seed Vault backup snapshot for USB or NAS storage."
    )
    parser.add_argument(
        "--destination",
        required=True,
        help="Target root path for backups (USB path or NAS share).",
    )
    parser.add_argument(
        "--label",
        default="guppy_seed_vault",
        help="Backup container folder name under destination.",
    )
    parser.add_argument(
        "--retain",
        type=int,
        default=10,
        help="How many snapshots to keep.",
    )
    parser.add_argument(
        "--no-hash",
        action="store_true",
        help="Skip SHA-256 hashing to speed up backup.",
    )
    args = parser.parse_args()

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%SZ")

    destination_root = Path(args.destination).expanduser().resolve()
    vault_root = destination_root / args.label
    snapshots_root = vault_root / "snapshots"
    snapshot_root = snapshots_root / timestamp
    snapshot_data_dir = snapshot_root / "data"

    snapshot_data_dir.mkdir(parents=True, exist_ok=True)

    files = _collect_candidates()
    copied, total_bytes = _copy_files(files, snapshot_data_dir, with_hash=not args.no_hash)

    manifest = {
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "source_root": str(SOURCE_ROOT),
        "destination": str(snapshot_root),
        "host": platform.node(),
        "platform": platform.platform(),
        "file_count": len(copied),
        "total_bytes": total_bytes,
        "hashing_enabled": not args.no_hash,
        "files": [
            {"path": f.rel_path, "size": f.size, "sha256": f.sha256} for f in copied
        ],
    }

    manifest_path = snapshot_root / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    latest_path = vault_root / "latest.json"
    latest_path.write_text(
        json.dumps(
            {
                "latest_snapshot": str(snapshot_root),
                "created_utc": manifest["created_utc"],
                "file_count": manifest["file_count"],
                "total_bytes": manifest["total_bytes"],
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    _prune_old_snapshots(snapshots_root, max(1, args.retain))

    print("=== Seed Vault Backup ===")
    print(f"Source: {SOURCE_ROOT}")
    print(f"Snapshot: {snapshot_root}")
    print(f"Files copied: {len(copied)}")
    print(f"Total bytes: {total_bytes}")
    print(f"Manifest: {manifest_path}")
    print("Result: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
