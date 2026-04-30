"""
Authoritative model role registry.

No surface, route, or UI passes a raw backend key as a routing string.
All model selection goes through this module.
"""

from __future__ import annotations

import logging
import sqlite3

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

MODEL_ROLES: dict[str, str] = {
    "conversation.default":           "llamacpp-hermes3",
    "conversation.partner.writing":   "llamacpp-rocinante",
    "conversation.partner.study":     "llamacpp-pepe",
    "conversation.partner.vision":    "llamacpp-minicpm",
    "workspace.controller":           "llamacpp-dispatch",
    "workspace.worker.primary":       "llamacpp-hermes4",
    "workspace.worker.escalation":    "llamacpp-chat",
    "workspace.tool_specialist":      "llamacpp-xlam",
}

# Roles that should be kept warm at all times
ALWAYS_ON_ROLES: set[str] = {
    "workspace.controller",
    "workspace.worker.primary",
    "conversation.default",
}

# Roles valid for operator conversation-partner selection
CONVERSATION_PARTNER_ROLES: list[str] = [
    "conversation.default",
    "conversation.partner.writing",
    "conversation.partner.study",
    "conversation.partner.vision",
]

# Friendly display labels for each role
ROLE_LABELS: dict[str, dict[str, str]] = {
    "conversation.default": {
        "label": "Hermes 3",
        "description": "Default fast conversation partner",
        "model": "Hermes 3 8B Lorablated",
        "port": "8087",
    },
    "conversation.partner.writing": {
        "label": "Rocinante",
        "description": "Creative writing and roleplay",
        "model": "Rocinante X 12B",
        "port": "8088",
    },
    "conversation.partner.study": {
        "label": "Pepe",
        "description": "Study mode, casual and direct",
        "model": "Assistant Pepe 8B",
        "port": "8082",
    },
    "conversation.partner.vision": {
        "label": "MiniCPM Vision",
        "description": "Vision + speech, private multimodal",
        "model": "MiniCPM-o 4.5 Omni",
        "port": "8084",
    },
    "workspace.controller": {
        "label": "Dispatch",
        "description": "Workspace task orchestrator",
        "model": "Qwen2.5-3B-Instruct",
        "port": "8085",
    },
    "workspace.worker.primary": {
        "label": "Hermes 4",
        "description": "Primary workspace worker with tools",
        "model": "Hermes 4 14B",
        "port": "8086",
    },
    "workspace.worker.escalation": {
        "label": "Llama 70B",
        "description": "Escalation to 70B CPU flagship",
        "model": "Llama 3.3 70B Instruct",
        "port": "8090",
    },
    "workspace.tool_specialist": {
        "label": "xLAM",
        "description": "Tool-call specialist (on-demand)",
        "model": "xLAM-2-8B-fc-r",
        "port": "8089",
    },
}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def resolve_role(role: str) -> str:
    """Return the backend key for a role.

    Raises ValueError for unknown roles.
    """
    try:
        return MODEL_ROLES[role]
    except KeyError:
        raise ValueError(f"Unknown model role: {role!r}. Valid roles: {sorted(MODEL_ROLES)}")


def get_active_conversation_partner() -> str:
    """Return the backend key for the currently active conversation partner.

    Reads operator_settings from the DB. Falls back to conversation.default
    if the DB is unavailable or no partner is set.
    """
    try:
        from src.guppy.paths import MAIN_DB_PATH, ensure_user_data_dir

        ensure_user_data_dir()
        with sqlite3.connect(str(MAIN_DB_PATH), timeout=10) as conn:
            row = conn.execute(
                "SELECT conversation_partner FROM operator_settings LIMIT 1"
            ).fetchone()
            if row and row[0]:
                role = row[0]
                return resolve_role(role)
    except Exception as exc:
        logger.debug("Could not read operator_settings: %s — using default", exc)

    return MODEL_ROLES["conversation.default"]


def get_registry_info() -> dict:
    """Return the full registry with current assignments for the API."""
    active_partner_role = _get_active_partner_role()
    roles_out = {}
    for role, backend in MODEL_ROLES.items():
        info = ROLE_LABELS.get(role, {})
        roles_out[role] = {
            "backend": backend,
            "label": info.get("label", role),
            "description": info.get("description", ""),
            "model": info.get("model", ""),
            "port": info.get("port", ""),
            "always_on": role in ALWAYS_ON_ROLES,
            "conversation_partner_eligible": role in CONVERSATION_PARTNER_ROLES,
            "active_partner": role == active_partner_role,
        }
    return {
        "roles": roles_out,
        "always_on": sorted(ALWAYS_ON_ROLES),
        "conversation_partner_roles": CONVERSATION_PARTNER_ROLES,
        "active_conversation_partner_role": active_partner_role,
        "active_conversation_partner_backend": MODEL_ROLES.get(active_partner_role, ""),
    }


def _get_active_partner_role() -> str:
    """Return the currently active conversation partner role key."""
    try:
        from src.guppy.paths import MAIN_DB_PATH, ensure_user_data_dir

        ensure_user_data_dir()
        with sqlite3.connect(str(MAIN_DB_PATH), timeout=10) as conn:
            row = conn.execute(
                "SELECT conversation_partner FROM operator_settings LIMIT 1"
            ).fetchone()
            if row and row[0] and row[0] in CONVERSATION_PARTNER_ROLES:
                return row[0]
    except Exception:
        pass
    return "conversation.default"
