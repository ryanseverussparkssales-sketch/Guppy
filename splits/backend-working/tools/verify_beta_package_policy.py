import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

DANGEROUS_TOOLS = {
    "execute_command",
    "write_file",
    "open_application",
    "mouse_move",
    "mouse_click",
    "keyboard_type",
    "keyboard_shortcut",
    "run_python",
    "send_email",
    "gmail_purge",
    "gmail_purge_label",
    "gmail_purge_sender",
    "gmail_purge_older_than",
    "gmail_empty_trash",
    "gmail_smart_cleanup",
    "crm_upsert_contact",
    "crm_create_opportunity",
    "voip_place_call",
}


def load_allowlist(path: Path) -> set[str]:
    if not path.exists():
        return set()
    names = set()
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        names.add(line)
    return names


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify remote beta tool restriction policy.")
    parser.add_argument(
        "--allowlist-file",
        default="config/beta_tool_allowlist.txt",
        help="Path to allowlist file relative to repo root.",
    )
    parser.add_argument(
        "--report",
        default="runtime/beta_policy_report.json",
        help="Output JSON report path.",
    )
    args = parser.parse_args()

    allowlist_path = (ROOT / args.allowlist_file).resolve()
    allowlist = load_allowlist(allowlist_path)

    policy_ok = True
    failures: list[str] = []

    if not allowlist:
        policy_ok = False
        failures.append("allowlist_missing_or_empty")

    dangerous_present = sorted(allowlist.intersection(DANGEROUS_TOOLS))
    if dangerous_present:
        policy_ok = False
        failures.append("dangerous_tools_present")

    try:
        import guppy_core

        runtime_policy = guppy_core.get_beta_policy_snapshot()
    except Exception as exc:
        runtime_policy = {"error": str(exc)}
        policy_ok = False
        failures.append("runtime_policy_load_failed")

    report = {
        "ok": policy_ok,
        "allowlist_file": str(allowlist_path),
        "allowlist_count": len(allowlist),
        "dangerous_tools_present": dangerous_present,
        "failures": failures,
        "runtime_policy": runtime_policy,
    }

    report_path = (ROOT / args.report).resolve()
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    print("=== Beta Policy Verifier ===")
    print(f"Allowlist file: {allowlist_path}")
    print(f"Allowlist entries: {len(allowlist)}")
    print(f"Dangerous present: {len(dangerous_present)}")
    print(f"Report: {report_path}")
    print("Result: PASS" if policy_ok else "Result: FAIL")

    return 0 if policy_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
