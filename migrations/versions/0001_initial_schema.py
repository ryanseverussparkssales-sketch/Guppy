"""initial_schema — baseline tables for guppy_main.db

Revision ID: 0001
Revises:
Create Date: 2026-04-24

Captures the existing schema so future migrations can build on it.
Tables currently managed by their own .db files (tools.db, chat_history.db,
etc.) are consolidated here. Each route module's CREATE TABLE IF NOT EXISTS
remains for backward compatibility during the transition period.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '0001'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS tools (
            id          TEXT PRIMARY KEY,
            name        TEXT NOT NULL,
            description TEXT NOT NULL,
            category    TEXT NOT NULL,
            type        TEXT NOT NULL DEFAULT 'builtin',
            parameters  TEXT NOT NULL DEFAULT '{}',
            is_enabled  INTEGER NOT NULL DEFAULT 1
        )
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS workspaces (
            id          TEXT PRIMARY KEY,
            name        TEXT NOT NULL,
            description TEXT,
            created_at  TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at  TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS conversations (
            id              TEXT PRIMARY KEY,
            workspace_id    TEXT NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
            title           TEXT NOT NULL DEFAULT 'New Conversation',
            created_at      TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at      TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id              TEXT PRIMARY KEY,
            conversation_id TEXT NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
            role            TEXT NOT NULL CHECK(role IN ('user','assistant','system')),
            content         TEXT NOT NULL,
            created_at      TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS settings (
            key         TEXT PRIMARY KEY,
            value       TEXT NOT NULL,
            updated_at  TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """)

    # Indexes for common query patterns
    op.execute("CREATE INDEX IF NOT EXISTS idx_conversations_workspace ON conversations(workspace_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_messages_conversation ON messages(conversation_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_messages_created ON messages(created_at)")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_messages_created")
    op.execute("DROP INDEX IF EXISTS idx_messages_conversation")
    op.execute("DROP INDEX IF EXISTS idx_conversations_workspace")
    op.execute("DROP TABLE IF EXISTS messages")
    op.execute("DROP TABLE IF EXISTS conversations")
    op.execute("DROP TABLE IF EXISTS settings")
    op.execute("DROP TABLE IF EXISTS workspaces")
    op.execute("DROP TABLE IF EXISTS tools")
