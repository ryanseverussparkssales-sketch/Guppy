"""
guppy_core/beta_policy.py
Beta-restricted-mode allowlist: which tools may run in restricted/pilot builds.
"""
from __future__ import annotations

import os
from pathlib import Path

_BETA_DEFAULT_ALLOWLIST: set[str] = {
    "read_file", "list_directory", "search_web", "fetch_url", "get_news",
    "remember", "recall", "semantic_remember", "semantic_recall",
    "add_task", "get_tasks", "complete_task", "save_contact", "get_contacts",
    "morning_brief", "get_reminders", "calendar_events",
    "gmail_scan_inbox", "gmail_list_accounts",
    "spotify_current", "youtube_search", "github",
    "get_foundation_readiness", "get_revenue_dashboard",
    "get_pipeline_items", "list_external_integrations",
    "notify", "clipboard_read", "get_active_window",
}


def _env_flag(name: str, default: str = "0") -> bool:
    return (os.environ.get(name, default) or "").strip().lower() in {"1", "true", "yes", "on"}


def _load_beta_tool_allowlist() -> set[str]:
    raw_env = (os.environ.get("GUPPY_BETA_TOOL_ALLOWLIST", "") or "").strip()
    if raw_env:
        return {x.strip() for x in raw_env.split(",") if x.strip()}

    default_file = Path(__file__).parent.parent / "config" / "beta_tool_allowlist.txt"
    file_path = Path(os.environ.get("GUPPY_BETA_ALLOWLIST_FILE", str(default_file))).expanduser()
    if file_path.exists():
        try:
            names = {
                line.strip()
                for line in file_path.read_text(encoding="utf-8", errors="ignore").splitlines()
                if line.strip() and not line.strip().startswith("#")
            }
            if names:
                return names
        except Exception:
            pass
    return set(_BETA_DEFAULT_ALLOWLIST)


BETA_RESTRICTED_MODE: bool = _env_flag("GUPPY_BETA_RESTRICTED_MODE", "0")
BETA_TOOL_ALLOWLIST: set[str] = _load_beta_tool_allowlist()


def get_beta_policy_snapshot() -> dict:
    return {
        "restricted_mode": BETA_RESTRICTED_MODE,
        "allowlist": sorted(BETA_TOOL_ALLOWLIST),
        "allowlist_size": len(BETA_TOOL_ALLOWLIST),
    }
