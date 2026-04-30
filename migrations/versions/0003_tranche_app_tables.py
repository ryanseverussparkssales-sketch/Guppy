"""tranche_app_tables - inventory Tranche A-H app tables

Revision ID: 0003
Revises: 0002
Create Date: 2026-04-30

Adds the SQLite tables currently implied by the Tranche A-H route skeletons.
The migration is intentionally idempotent because several route modules still
create their own tables during startup while consolidation continues.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: Union[str, Sequence[str], None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _table_names(bind) -> set[str]:
    return set(sa.inspect(bind).get_table_names())


def _column_names(bind, table_name: str) -> set[str]:
    return {row["name"] for row in sa.inspect(bind).get_columns(table_name)}


def _add_column_if_missing(bind, table_name: str, column_name: str, definition: str) -> None:
    if column_name not in _column_names(bind, table_name):
        op.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {definition}")


def _ensure_conversations_contract(bind) -> None:
    if "conversations" not in _table_names(bind):
        op.execute(
            """
            CREATE TABLE conversations (
                id            TEXT PRIMARY KEY,
                workspace_id  TEXT REFERENCES workspaces(id) ON DELETE CASCADE,
                title         TEXT NOT NULL DEFAULT 'New Conversation',
                session_title TEXT,
                model_backend TEXT,
                message_count INTEGER NOT NULL DEFAULT 0,
                created_at    TEXT NOT NULL DEFAULT (datetime('now')),
                updated_at    TEXT NOT NULL DEFAULT (datetime('now'))
            )
            """
        )
        return

    _add_column_if_missing(bind, "conversations", "session_title", "TEXT")
    _add_column_if_missing(bind, "conversations", "model_backend", "TEXT")
    _add_column_if_missing(bind, "conversations", "message_count", "INTEGER NOT NULL DEFAULT 0")


def upgrade() -> None:
    bind = op.get_bind()

    _ensure_conversations_contract(bind)

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS conversation_messages (
            id              TEXT PRIMARY KEY,
            conversation_id TEXT NOT NULL,
            role            TEXT NOT NULL,
            content         TEXT NOT NULL,
            image_url       TEXT,
            created_at      TEXT NOT NULL,
            FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE CASCADE
        )
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_conversation_messages_conversation "
        "ON conversation_messages(conversation_id, created_at)"
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS operator_settings (
            id                   INTEGER PRIMARY KEY DEFAULT 1,
            cloud_paid_enabled   INTEGER NOT NULL DEFAULT 1,
            cloud_free_enabled   INTEGER NOT NULL DEFAULT 0,
            conversation_partner TEXT NOT NULL DEFAULT 'conversation.default',
            updated_at           TEXT NOT NULL
        )
        """
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS surface_state (
            surface      TEXT PRIMARY KEY,
            status       TEXT NOT NULL DEFAULT 'idle',
            current_task TEXT,
            agent_count  INTEGER NOT NULL DEFAULT 0,
            last_context TEXT,
            updated_at   TEXT NOT NULL
        )
        """
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS surface_config (
            surface        TEXT PRIMARY KEY,
            backend        TEXT NOT NULL DEFAULT 'auto',
            model          TEXT NOT NULL DEFAULT 'auto',
            fallback_model TEXT,
            mode           TEXT NOT NULL DEFAULT 'auto',
            system_prompt  TEXT NOT NULL DEFAULT '',
            tool_policy    TEXT NOT NULL DEFAULT 'auto',
            updated_at     TEXT NOT NULL
        )
        """
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS surface_tasks (
            id          TEXT PRIMARY KEY,
            surface     TEXT NOT NULL,
            source      TEXT NOT NULL DEFAULT 'user',
            title       TEXT NOT NULL,
            description TEXT NOT NULL DEFAULT '',
            status      TEXT NOT NULL DEFAULT 'queued',
            result      TEXT,
            created_at  TEXT NOT NULL,
            updated_at  TEXT NOT NULL
        )
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_surface_tasks_surface_status "
        "ON surface_tasks(surface, status, created_at)"
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS workspace_tasks (
            id               TEXT PRIMARY KEY,
            task_description TEXT NOT NULL,
            source           TEXT NOT NULL DEFAULT 'workspace',
            state            TEXT NOT NULL DEFAULT 'queued',
            created_at       TEXT NOT NULL,
            started_at       TEXT,
            completed_at     TEXT,
            result           TEXT,
            error            TEXT
        )
        """
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS workspace_task_steps (
            id                    TEXT PRIMARY KEY,
            task_id               TEXT NOT NULL,
            step_number           INTEGER NOT NULL,
            tool_name             TEXT NOT NULL,
            tool_args             TEXT NOT NULL,
            result                TEXT,
            requires_confirmation INTEGER NOT NULL DEFAULT 0,
            confirmation_given    INTEGER NOT NULL DEFAULT 0,
            created_at            TEXT NOT NULL,
            completed_at          TEXT,
            FOREIGN KEY (task_id) REFERENCES workspace_tasks(id) ON DELETE CASCADE
        )
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_workspace_tasks_state_created "
        "ON workspace_tasks(state, created_at)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_workspace_task_steps_task_step "
        "ON workspace_task_steps(task_id, step_number)"
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS workspace_task_events (
            id         TEXT PRIMARY KEY,
            task_id    TEXT,
            event_type TEXT NOT NULL,
            payload    TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY (task_id) REFERENCES workspace_tasks(id) ON DELETE CASCADE
        )
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_workspace_task_events_task "
        "ON workspace_task_events(task_id, created_at)"
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS screen_windows (
            id           TEXT PRIMARY KEY,
            window_start TEXT NOT NULL,
            window_end   TEXT NOT NULL,
            apps         TEXT NOT NULL DEFAULT '[]',
            highlights   TEXT NOT NULL DEFAULT '[]',
            item_count   INTEGER NOT NULL DEFAULT 0,
            word_count   INTEGER NOT NULL DEFAULT 0,
            summary      TEXT NOT NULL DEFAULT '',
            created_at   TEXT NOT NULL
        )
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_screen_windows_start "
        "ON screen_windows(window_start DESC)"
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS library_items (
            id              TEXT PRIMARY KEY,
            type            TEXT NOT NULL DEFAULT 'artifact',
            title           TEXT NOT NULL,
            content         TEXT NOT NULL DEFAULT '',
            collection      TEXT,
            tags_json       TEXT NOT NULL DEFAULT '[]',
            is_favorite     INTEGER NOT NULL DEFAULT 0,
            file_path       TEXT,
            file_ext        TEXT,
            metadata_status TEXT NOT NULL DEFAULT 'pending',
            cover_url       TEXT,
            description     TEXT,
            isbn            TEXT,
            subjects_json   TEXT NOT NULL DEFAULT '[]',
            publish_year    INTEGER,
            created_at      TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at      TEXT NOT NULL DEFAULT (datetime('now'))
        )
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_library_items_collection "
        "ON library_items(collection, updated_at)"
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS library_metadata (
            cache_key     TEXT PRIMARY KEY,
            title         TEXT NOT NULL,
            author        TEXT,
            cover_url     TEXT,
            description   TEXT,
            subjects_json TEXT,
            publish_year  INTEGER,
            isbn          TEXT,
            payload_json  TEXT NOT NULL,
            fetched_at    TEXT NOT NULL
        )
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_library_metadata_fetched_at "
        "ON library_metadata(fetched_at)"
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS library_metadata")
    op.execute("DROP TABLE IF EXISTS library_items")
    op.execute("DROP TABLE IF EXISTS screen_windows")
    op.execute("DROP TABLE IF EXISTS workspace_task_events")
    op.execute("DROP TABLE IF EXISTS workspace_task_steps")
    op.execute("DROP TABLE IF EXISTS workspace_tasks")
    op.execute("DROP TABLE IF EXISTS surface_tasks")
    op.execute("DROP TABLE IF EXISTS surface_config")
    op.execute("DROP TABLE IF EXISTS surface_state")
    op.execute("DROP TABLE IF EXISTS operator_settings")
    op.execute("DROP TABLE IF EXISTS conversation_messages")
    # Added columns on conversations are intentionally left in place on SQLite.
