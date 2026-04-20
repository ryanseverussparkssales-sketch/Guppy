from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path


@dataclass(frozen=True, slots=True)
class PackagingPathStatus:
    label: str
    path: Path
    writable: bool
    error: str = ""


@dataclass(frozen=True, slots=True)
class PackagingAssumptionStatus:
    label: str
    ok: bool
    detail: str


def packaging_write_targets(repo_root: Path) -> tuple[PackagingPathStatus, ...]:
    root = Path(repo_root)
    targets = (
        ("runtime root", root / "runtime"),
        ("runtime daily reports", root / "runtime" / "daily_reports"),
        ("runtime stress reports", root / "runtime" / "stress_reports"),
        ("workflow reports", root / ".tmp" / "dev-workflow" / "reports"),
    )
    statuses: list[PackagingPathStatus] = []
    for label, path in targets:
        statuses.append(_check_writable_directory(label, path))
    return tuple(statuses)


def all_packaging_paths_writable(repo_root: Path) -> tuple[bool, tuple[PackagingPathStatus, ...]]:
    statuses = packaging_write_targets(repo_root)
    return all(item.writable for item in statuses), statuses


def packaging_assumption_checks(repo_root: Path) -> tuple[PackagingAssumptionStatus, ...]:
    root = Path(repo_root)
    return (
        _check_required_file(root, "launcher entrypoint", root / "guppy_launcher.py"),
        _check_required_file(root, "package builder", root / "bin" / "build_executable.bat"),
        _check_required_file(root, "package validator", root / "bin" / "validate_build.bat"),
        _check_required_file(root, "PyInstaller spec", root / "bin" / "Guppy.spec"),
        _check_required_file(root, "packaging guide", root / "docs" / "PACKAGING.md"),
        _check_build_script_contract(root),
        _check_validate_script_contract(root),
        _check_packaging_doc_contract(root),
        _check_release_handoff_contract(root),
        _check_dist_layout_contract(root),
    )


def all_packaging_assumptions_hold(repo_root: Path) -> tuple[bool, tuple[PackagingAssumptionStatus, ...]]:
    statuses = packaging_assumption_checks(repo_root)
    return all(item.ok for item in statuses), statuses


def _check_writable_directory(label: str, path: Path) -> PackagingPathStatus:
    try:
        path.mkdir(parents=True, exist_ok=True)
        probe = path / "._guppy_packaging_write_test.tmp"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
        return PackagingPathStatus(label=label, path=path, writable=True)
    except Exception as exc:
        return PackagingPathStatus(label=label, path=path, writable=False, error=str(exc))


def _check_required_file(repo_root: Path, label: str, path: Path) -> PackagingAssumptionStatus:
    exists = path.exists()
    detail = str(_display_path(repo_root, path)) if exists else f"missing: {_display_path(repo_root, path)}"
    return PackagingAssumptionStatus(label=label, ok=exists, detail=detail)


def _check_build_script_contract(repo_root: Path) -> PackagingAssumptionStatus:
    path = repo_root / "bin" / "build_executable.bat"
    if not path.exists():
        return PackagingAssumptionStatus("build script contract", False, f"missing: {_display_path(repo_root, path)}")
    text = path.read_text(encoding="utf-8", errors="replace")
    required_tokens = (
        "guppy_launcher.py",
        "bin\\Guppy.spec",
        "--name \"Guppy\"",
        "--add-data \"runtime;runtime\"",
    )
    missing = [token for token in required_tokens if token not in text]
    if missing:
        return PackagingAssumptionStatus(
            "build script contract",
            False,
            f"missing tokens in {_display_path(repo_root, path)}: {', '.join(missing)}",
        )
    return PackagingAssumptionStatus(
        "build script contract",
        True,
        f"{_display_path(repo_root, path)} references canonical launcher/spec/runtime packaging inputs",
    )


def _check_validate_script_contract(repo_root: Path) -> PackagingAssumptionStatus:
    path = repo_root / "bin" / "validate_build.bat"
    if not path.exists():
        return PackagingAssumptionStatus("build validator contract", False, f"missing: {_display_path(repo_root, path)}")
    text = path.read_text(encoding="utf-8", errors="replace")
    required_tokens = (
        "dist\\Guppy\\Guppy.exe",
        "dist\\Guppy.exe",
        "tools\\validate_build_checks.py",
    )
    missing = [token for token in required_tokens if token not in text]
    if missing:
        return PackagingAssumptionStatus(
            "build validator contract",
            False,
            f"missing tokens in {_display_path(repo_root, path)}: {', '.join(missing)}",
        )
    return PackagingAssumptionStatus(
        "build validator contract",
        True,
        f"{_display_path(repo_root, path)} checks canonical dist outputs and delegates to validate_build_checks.py",
    )


def _check_packaging_doc_contract(repo_root: Path) -> PackagingAssumptionStatus:
    path = repo_root / "docs" / "PACKAGING.md"
    if not path.exists():
        return PackagingAssumptionStatus("packaging doc contract", False, f"missing: {_display_path(repo_root, path)}")
    text = path.read_text(encoding="utf-8", errors="replace")
    required_tokens = (
        "bin/build_executable.bat",
        "runtime/windows_release_receipt.json",
        "runtime/windows_release_summary.md",
        "runtime/beta_release_dry_run_report.json",
    )
    missing = [token for token in required_tokens if token not in text]
    if missing:
        return PackagingAssumptionStatus(
            "packaging doc contract",
            False,
            f"missing tokens in {_display_path(repo_root, path)}: {', '.join(missing)}",
        )
    return PackagingAssumptionStatus(
        "packaging doc contract",
        True,
        f"{_display_path(repo_root, path)} documents canonical build and release-handoff artifacts",
    )


def _check_release_handoff_contract(repo_root: Path) -> PackagingAssumptionStatus:
    runtime_root = repo_root / "runtime"
    receipt_path = runtime_root / "windows_release_receipt.json"
    summary_path = runtime_root / "windows_release_summary.md"
    dry_run_path = runtime_root / "beta_release_dry_run_report.json"
    present = [path for path in (receipt_path, summary_path, dry_run_path) if path.exists()]
    if not present:
        return PackagingAssumptionStatus(
            "release handoff contract",
            True,
            "release handoff receipts not present yet; packaging audit will validate them when generated",
        )
    if receipt_path.exists() != summary_path.exists():
        return PackagingAssumptionStatus(
            "release handoff contract",
            False,
            "windows release handoff is incomplete: receipt and summary must appear together",
        )
    errors: list[str] = []
    if receipt_path.exists():
        try:
            payload = json.loads(receipt_path.read_text(encoding="utf-8"))
        except Exception as exc:
            errors.append(f"invalid JSON in {_display_path(repo_root, receipt_path)}: {exc}")
        else:
            errors.extend(_validate_receipt_payload(payload))
    if summary_path.exists():
        summary_text = summary_path.read_text(encoding="utf-8", errors="replace")
        if "# Windows Release Summary" not in summary_text:
            errors.append(f"{_display_path(repo_root, summary_path)} is missing the release summary heading")
        if "docs/PACKAGING.md" not in summary_text:
            errors.append(f"{_display_path(repo_root, summary_path)} is missing the packaging doc handoff hint")
    if dry_run_path.exists():
        try:
            payload = json.loads(dry_run_path.read_text(encoding="utf-8"))
        except Exception as exc:
            errors.append(f"invalid JSON in {_display_path(repo_root, dry_run_path)}: {exc}")
        else:
            if "ok" not in payload or "checks" not in payload:
                errors.append(f"{_display_path(repo_root, dry_run_path)} is missing expected dry-run keys")
    if errors:
        return PackagingAssumptionStatus("release handoff contract", False, " | ".join(errors))
    available = [
        _display_path(repo_root, path)
        for path in (receipt_path, summary_path, dry_run_path)
        if path.exists()
    ]
    return PackagingAssumptionStatus(
        "release handoff contract",
        True,
        f"validated handoff artifacts: {', '.join(str(item) for item in available)}",
    )


def _check_dist_layout_contract(repo_root: Path) -> PackagingAssumptionStatus:
    one_dir = repo_root / "dist" / "Guppy" / "Guppy.exe"
    one_file = repo_root / "dist" / "Guppy.exe"
    dist_root = repo_root / "dist"
    if one_dir.exists():
        return PackagingAssumptionStatus(
            "dist artifact layout",
            True,
            f"found canonical onedir package output at {_display_path(repo_root, one_dir)}",
        )
    if one_file.exists():
        return PackagingAssumptionStatus(
            "dist artifact layout",
            True,
            f"found canonical onefile package output at {_display_path(repo_root, one_file)}",
        )
    if dist_root.exists():
        return PackagingAssumptionStatus(
            "dist artifact layout",
            False,
            "dist/ exists but neither dist/Guppy/Guppy.exe nor dist/Guppy.exe is present",
        )
    return PackagingAssumptionStatus(
        "dist artifact layout",
        True,
        "no built dist/ artifact present yet; canonical output paths remain dist/Guppy/Guppy.exe or dist/Guppy.exe",
    )


def _validate_receipt_payload(payload: object) -> list[str]:
    if not isinstance(payload, dict):
        return ["windows release receipt must be a JSON object"]
    errors: list[str] = []
    for key in ("action", "ok", "paths", "operator_guidance"):
        if key not in payload:
            errors.append(f"windows release receipt missing '{key}'")
    paths = payload.get("paths")
    if isinstance(paths, dict):
        receipt_path = str(paths.get("receipt_path", ""))
        summary_path = str(paths.get("summary_path", ""))
        if not receipt_path.endswith("windows_release_receipt.json"):
            errors.append("windows release receipt paths.receipt_path must end with windows_release_receipt.json")
        if not summary_path.endswith("windows_release_summary.md"):
            errors.append("windows release receipt paths.summary_path must end with windows_release_summary.md")
    operator_guidance = payload.get("operator_guidance")
    if isinstance(operator_guidance, dict):
        docs_hint = str(operator_guidance.get("docs_hint", ""))
        entry_point = str(operator_guidance.get("entry_point", ""))
        if docs_hint and docs_hint != "docs/PACKAGING.md":
            errors.append("windows release receipt operator_guidance.docs_hint must point to docs/PACKAGING.md when present")
        if not entry_point:
            errors.append("windows release receipt operator_guidance.entry_point is missing")
    return errors


def _display_path(repo_root: Path, path: Path) -> Path:
    try:
        return path.relative_to(repo_root)
    except ValueError:
        return path
