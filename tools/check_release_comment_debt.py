"""Fail release guard if newly added comment debt markers appear in release-facing files."""
from __future__ import annotations

import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
# Build the pattern without embedding the marker words literally so this file
# cannot trigger its own scan when it appears in a diff.
_WORDS = "|".join(["T" + "ODO", "F" + "IXME", "H" + "ACK"])
MARKER_RE = re.compile(rf"\b({_WORDS})\b", re.IGNORECASE)
# Always skip the checker file itself to avoid self-referential false positives.
SELF_PATH = Path(__file__).resolve().relative_to(ROOT).as_posix()
RELEASE_PATH_PREFIXES = (
    "tools/",
    "src/guppy/",
    "ui/",
    "docs/",
    "documentation/",
    "bin/",
)
RELEASE_PATH_FILES = {
    "README.md",
    "CONTRIBUTING.md",
    "ROADMAP.md",
    "guppy_api.py",
    "guppy_hub.py",
    "guppy_launcher.py",
}


def _run_git(args: list[str]) -> str:
    return subprocess.check_output(["git", *args], cwd=ROOT, text=True, stderr=subprocess.DEVNULL)


def _is_release_facing(rel_posix: str) -> bool:
    if rel_posix == SELF_PATH:
        return False
    return rel_posix in RELEASE_PATH_FILES or any(
        rel_posix.startswith(prefix) for prefix in RELEASE_PATH_PREFIXES
    )


def _changed_files_from_last_commit() -> set[str]:
    try:
        raw = _run_git(["diff", "--name-only", "--diff-filter=AM", "HEAD~1", "HEAD"])
    except Exception:
        return set()

    changed: set[str] = set()
    for line in raw.splitlines():
        rel = line.strip()
        if rel and (ROOT / rel).exists() and _is_release_facing(rel.replace("\\", "/")):
            changed.add(rel)
    return changed


def _changed_files_from_worktree() -> set[str]:
    try:
        raw = _run_git(["status", "--porcelain"])
    except Exception:
        return set()

    changed: set[str] = set()
    for line in raw.splitlines():
        if len(line) < 4:
            continue
        rel = line[3:].strip()
        if rel.endswith("/"):
            continue
        rel_posix = rel.replace("\\", "/")
        if rel and (ROOT / rel).exists() and _is_release_facing(rel_posix):
            changed.add(rel)
    return changed


def _has_local_changes(path: str) -> bool:
    try:
        raw = _run_git(["status", "--porcelain", "--", path])
    except Exception:
        return False
    return bool(raw.strip())


def _added_lines_for_path(path: str, commit_range: bool) -> list[str]:
    if commit_range:
        diff_args = ["diff", "--unified=0", "HEAD~1", "HEAD", "--", path]
        try:
            raw = _run_git(diff_args)
        except Exception:
            return []
        return _parse_added_lines(raw)

    lines: list[str] = []
    # Include unstaged and staged local additions.
    for args in (["diff", "--unified=0", "--", path], ["diff", "--cached", "--unified=0", "--", path]):
        try:
            raw = _run_git(args)
        except Exception:
            continue
        lines.extend(_parse_added_lines(raw))

    if lines:
        return lines

    # For untracked files, scan full text as all content is newly introduced.
    file_path = ROOT / path
    if file_path.exists():
        try:
            return file_path.read_text(encoding="utf-8", errors="replace").splitlines()
        except Exception:
            return []
    return []


def _parse_added_lines(diff_text: str) -> list[str]:
    out: list[str] = []
    for line in diff_text.splitlines():
        if not line.startswith("+"):
            continue
        if line.startswith("+++"):
            continue
        out.append(line[1:])
    return out


def _find_markers_in_lines(path: str, lines: list[str]) -> list[str]:
    findings: list[str] = []
    for idx, line in enumerate(lines, start=1):
        marker_match = MARKER_RE.search(line)
        if marker_match is None:
            continue
        findings.append(f"{path}:added-line-{idx}: contains {marker_match.group(1).upper()}")
    return findings


def main() -> int:
    changed_from_commit = _changed_files_from_last_commit()
    changed_from_worktree = _changed_files_from_worktree()
    changed = changed_from_commit or changed_from_worktree

    if not changed:
        print("release comment-debt check passed (no changed release-facing files)")
        return 0

    findings: list[str] = []
    for path in sorted(changed):
        use_commit_range = path in changed_from_commit and not _has_local_changes(path)
        added_lines = _added_lines_for_path(path, commit_range=use_commit_range)
        findings.extend(_find_markers_in_lines(path, added_lines))

    if findings:
        print("release comment-debt check failed:")
        for finding in findings:
            print(f" - {finding}")
        print("Remove debt markers or replace with tracked issue references.")
        return 1

    print("release comment-debt check passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
