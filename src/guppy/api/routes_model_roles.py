"""Model role registry API + operator settings.

GET  /api/model-roles                          — full registry + current assignments
PUT  /api/model-roles/conversation-partner     — change active conversation partner

GET  /api/control/operator-settings            — current operator settings
PUT  /api/control/operator-settings            — update operator settings
"""
from __future__ import annotations

import logging
import sqlite3
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from src.guppy.api.server_context import ServerContext
from src.guppy.model_roles import (
    CONVERSATION_PARTNER_ROLES,
    get_registry_info,
)
from src.guppy.paths import USER_DATA_DIR

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# DB helpers — operator_settings table lives in guppy_main.db (surface DB path)
# ---------------------------------------------------------------------------

_DB_PATH: str = ""

_OPERATOR_SCHEMA = """
CREATE TABLE IF NOT EXISTS operator_settings (
    id                   INTEGER PRIMARY KEY DEFAULT 1,
    cloud_paid_enabled   INTEGER NOT NULL DEFAULT 1,
    cloud_free_enabled   INTEGER NOT NULL DEFAULT 0,
    conversation_partner TEXT    NOT NULL DEFAULT 'conversation.default',
    updated_at           TEXT    NOT NULL
);
"""


def _db() -> sqlite3.Connection:
    path = _DB_PATH or str(USER_DATA_DIR / "guppy_main.db")
    conn = sqlite3.connect(path, check_same_thread=False, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _ensure_schema() -> None:
    with _db() as conn:
        conn.executescript(_OPERATOR_SCHEMA)
        # Seed single row (id=1) if absent
        conn.execute(
            """INSERT OR IGNORE INTO operator_settings
               (id, cloud_paid_enabled, cloud_free_enabled, conversation_partner, updated_at)
               VALUES (1, 1, 0, 'conversation.default', ?)""",
            (_now(),),
        )
        conn.commit()


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------


class ConversationPartnerRequest(BaseModel):
    role: str


class OperatorSettingsRequest(BaseModel):
    cloud_paid_enabled: bool | None = None
    cloud_free_enabled: bool | None = None
    conversation_partner: str | None = None


# ---------------------------------------------------------------------------
# Router factory
# ---------------------------------------------------------------------------


def build_model_roles_router(ctx: ServerContext) -> APIRouter:
    global _DB_PATH
    from src.guppy.api.routes_surface import _DB_PATH as _surface_db_path
    if _surface_db_path:
        _DB_PATH = _surface_db_path
    else:
        _DB_PATH = str(USER_DATA_DIR / "guppy_main.db")

    _ensure_schema()

    router = APIRouter(prefix="/api/model-roles", tags=["model-roles"])

    @router.get("")
    async def get_model_roles():
        """Return the full model role registry with current assignments."""
        info = get_registry_info()
        # Add current operator settings
        try:
            with _db() as conn:
                row = conn.execute(
                    "SELECT cloud_paid_enabled, cloud_free_enabled, conversation_partner FROM operator_settings WHERE id=1"
                ).fetchone()
                if row:
                    info["operator_settings"] = {
                        "cloud_paid_enabled": bool(row["cloud_paid_enabled"]),
                        "cloud_free_enabled": bool(row["cloud_free_enabled"]),
                        "conversation_partner": row["conversation_partner"],
                    }
        except Exception as exc:
            logger.warning("Could not read operator_settings: %s", exc)
            info["operator_settings"] = {
                "cloud_paid_enabled": True,
                "cloud_free_enabled": False,
                "conversation_partner": "conversation.default",
            }
        return info

    @router.put("/conversation-partner")
    async def set_conversation_partner(req: ConversationPartnerRequest):
        """Change the active conversation partner role.

        Body: {"role": "conversation.partner.writing"}
        Validates against CONVERSATION_PARTNER_ROLES.
        """
        if req.role not in CONVERSATION_PARTNER_ROLES:
            raise HTTPException(
                status_code=422,
                detail=(
                    f"Invalid conversation partner role: {req.role!r}. "
                    f"Valid roles: {CONVERSATION_PARTNER_ROLES}"
                ),
            )
        try:
            with _db() as conn:
                conn.execute(
                    """UPDATE operator_settings
                       SET conversation_partner=?, updated_at=?
                       WHERE id=1""",
                    (req.role, _now()),
                )
                if conn.execute("SELECT changes()").fetchone()[0] == 0:
                    # Row was not present — insert it
                    conn.execute(
                        """INSERT INTO operator_settings
                           (id, cloud_paid_enabled, cloud_free_enabled, conversation_partner, updated_at)
                           VALUES (1, 1, 0, ?, ?)""",
                        (req.role, _now()),
                    )
                conn.commit()
        except Exception as exc:
            logger.error("Failed to update conversation_partner: %s", exc)
            raise HTTPException(status_code=500, detail=str(exc))

        return {"ok": True, "conversation_partner": req.role}

    # -----------------------------------------------------------------------
    # /api/control/operator-settings
    # -----------------------------------------------------------------------

    control_router = APIRouter(prefix="/api/control", tags=["control"])

    @control_router.get("/operator-settings")
    async def get_operator_settings():
        """Return current operator settings."""
        try:
            with _db() as conn:
                row = conn.execute(
                    "SELECT cloud_paid_enabled, cloud_free_enabled, conversation_partner FROM operator_settings WHERE id=1"
                ).fetchone()
                if row:
                    return {
                        "cloud_paid_enabled": bool(row["cloud_paid_enabled"]),
                        "cloud_free_enabled": bool(row["cloud_free_enabled"]),
                        "conversation_partner": row["conversation_partner"],
                    }
        except Exception as exc:
            logger.warning("Could not read operator_settings: %s", exc)
        return {
            "cloud_paid_enabled": True,
            "cloud_free_enabled": False,
            "conversation_partner": "conversation.default",
        }

    @control_router.put("/operator-settings")
    async def update_operator_settings(req: OperatorSettingsRequest):
        """Update operator settings (partial update — only supplied fields change)."""
        if req.conversation_partner is not None and req.conversation_partner not in CONVERSATION_PARTNER_ROLES:
            raise HTTPException(
                status_code=422,
                detail=(
                    f"Invalid conversation partner role: {req.conversation_partner!r}. "
                    f"Valid roles: {CONVERSATION_PARTNER_ROLES}"
                ),
            )
        try:
            with _db() as conn:
                # Build partial SET clause for only supplied fields
                updates: list[tuple[str, object]] = []
                if req.cloud_paid_enabled is not None:
                    updates.append(("cloud_paid_enabled", int(req.cloud_paid_enabled)))
                if req.cloud_free_enabled is not None:
                    updates.append(("cloud_free_enabled", int(req.cloud_free_enabled)))
                if req.conversation_partner is not None:
                    updates.append(("conversation_partner", req.conversation_partner))
                if not updates:
                    raise HTTPException(status_code=422, detail="No fields to update.")
                set_clause = ", ".join(f"{col}=?" for col, _ in updates)
                values = [v for _, v in updates] + [_now(), 1]
                conn.execute(
                    f"UPDATE operator_settings SET {set_clause}, updated_at=? WHERE id=?",  # noqa: S608
                    values,
                )
                if conn.execute("SELECT changes()").fetchone()[0] == 0:
                    conn.execute(
                        """INSERT INTO operator_settings
                           (id, cloud_paid_enabled, cloud_free_enabled, conversation_partner, updated_at)
                           VALUES (1, 1, 0, 'conversation.default', ?)""",
                        (_now(),),
                    )
                conn.commit()
        except HTTPException:
            raise
        except Exception as exc:
            logger.error("Failed to update operator_settings: %s", exc)
            raise HTTPException(status_code=500, detail=str(exc))

        # Return updated settings
        return await get_operator_settings()

    return router, control_router
