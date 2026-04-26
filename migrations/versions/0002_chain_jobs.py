"""chain_jobs — add pipeline/chain columns to inference_queue

Revision ID: 0002
Revises: 0001
Create Date: 2026-04-25

Creates inference_queue, inference_queue_attempts, and provider_configs tables
(if they do not already exist), and adds pipeline/chain columns to an existing
inference_queue table when upgrading from a pre-chain deployment.

New columns on inference_queue:
    pipeline_id      TEXT   — UUID grouping all steps in one pipeline
    chain_sequence   INTEGER — 0-indexed position within the pipeline
    parent_job_id    TEXT   — FK to the job whose output feeds this prompt
    output_transform TEXT   — passthrough | append | template

A "waiting" status value is also introduced (enforced at the application layer,
no CHECK constraint added here to keep SQLite compatible).

Indices added:
    ix_queue_pipeline  (pipeline_id, chain_sequence)  — pipeline lookup
    ix_queue_parent    (parent_job_id)                — unblocking scan
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '0002'
down_revision: Union[str, Sequence[str], None] = '0001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = set(inspector.get_table_names())

    # ── provider_configs ──────────────────────────────────────────────────────
    if "provider_configs" not in existing_tables:
        op.execute("""
            CREATE TABLE provider_configs (
                id                TEXT PRIMARY KEY,
                name              TEXT NOT NULL,
                is_enabled        INTEGER NOT NULL DEFAULT 0,
                priority_order    INTEGER NOT NULL,
                timeout_seconds   REAL NOT NULL,
                retry_limit       INTEGER NOT NULL DEFAULT 2,
                cost_per_1k_tokens REAL,
                api_key           TEXT,
                model_id          TEXT,
                extra_metadata    TEXT DEFAULT '{}',
                created_at        TEXT NOT NULL DEFAULT (datetime('now')),
                updated_at        TEXT NOT NULL DEFAULT (datetime('now'))
            )
        """)
        op.execute("CREATE INDEX IF NOT EXISTS ix_provider_configs_enabled  ON provider_configs(is_enabled)")
        op.execute("CREATE INDEX IF NOT EXISTS ix_provider_configs_priority ON provider_configs(priority_order)")
    else:
        # Table exists from an older deployment: rename metadata → extra_metadata if needed
        pc_cols = {c["name"] for c in inspector.get_columns("provider_configs")}
        if "metadata" in pc_cols and "extra_metadata" not in pc_cols:
            with op.batch_alter_table("provider_configs") as batch_op:
                batch_op.alter_column("metadata", new_column_name="extra_metadata")

    # ── inference_queue ───────────────────────────────────────────────────────
    if "inference_queue" not in existing_tables:
        op.execute("""
            CREATE TABLE inference_queue (
                id                TEXT PRIMARY KEY,
                status            TEXT NOT NULL DEFAULT 'queued',
                priority          INTEGER NOT NULL DEFAULT 100,
                prompt            TEXT NOT NULL,
                system_prompt     TEXT,
                task_type         TEXT NOT NULL,
                preferred_provider TEXT,
                max_retries       INTEGER NOT NULL DEFAULT 3,
                retry_count       INTEGER NOT NULL DEFAULT 0,
                backoff_multiplier REAL NOT NULL DEFAULT 2.0,
                last_attempt_at   TEXT,
                next_retry_at     TEXT,
                response          TEXT,
                provider_used     TEXT,
                error_message     TEXT,
                execution_ms      REAL,
                cost_usd          REAL DEFAULT 0.0,
                user_id           TEXT,
                session_id        TEXT,
                extra_metadata    TEXT DEFAULT '{}',
                created_at        TEXT NOT NULL DEFAULT (datetime('now')),
                completed_at      TEXT,
                pipeline_id       TEXT,
                chain_sequence    INTEGER,
                parent_job_id     TEXT REFERENCES inference_queue(id) ON DELETE SET NULL,
                output_transform  TEXT DEFAULT 'passthrough'
            )
        """)
        op.execute("CREATE INDEX IF NOT EXISTS ix_queue_status_priority  ON inference_queue(status, priority, created_at)")
        op.execute("CREATE INDEX IF NOT EXISTS ix_queue_next_retry       ON inference_queue(next_retry_at)")
        op.execute("CREATE INDEX IF NOT EXISTS ix_queue_user_session     ON inference_queue(user_id, session_id)")
        op.execute("CREATE INDEX IF NOT EXISTS ix_queue_status_completed ON inference_queue(status, completed_at)")
        op.execute("CREATE INDEX IF NOT EXISTS ix_queue_pipeline         ON inference_queue(pipeline_id, chain_sequence)")
        op.execute("CREATE INDEX IF NOT EXISTS ix_queue_parent           ON inference_queue(parent_job_id)")
    else:
        # Table exists: apply column renames and additions idempotently
        iq_cols = {c["name"] for c in inspector.get_columns("inference_queue")}

        with op.batch_alter_table("inference_queue") as batch_op:
            if "metadata" in iq_cols and "extra_metadata" not in iq_cols:
                batch_op.alter_column("metadata", new_column_name="extra_metadata")
            if "pipeline_id" not in iq_cols:
                batch_op.add_column(sa.Column("pipeline_id",      sa.String(64),  nullable=True))
            if "chain_sequence" not in iq_cols:
                batch_op.add_column(sa.Column("chain_sequence",   sa.Integer(),   nullable=True))
            if "parent_job_id" not in iq_cols:
                batch_op.add_column(sa.Column("parent_job_id",    sa.String(64),  nullable=True))
            if "output_transform" not in iq_cols:
                batch_op.add_column(sa.Column("output_transform", sa.String(32),  nullable=True))

        existing_indices = {idx["name"] for idx in inspector.get_indexes("inference_queue")}
        if "ix_queue_pipeline" not in existing_indices:
            op.create_index("ix_queue_pipeline", "inference_queue", ["pipeline_id", "chain_sequence"])
        if "ix_queue_parent" not in existing_indices:
            op.create_index("ix_queue_parent",   "inference_queue", ["parent_job_id"])

    # ── inference_queue_attempts ──────────────────────────────────────────────
    if "inference_queue_attempts" not in existing_tables:
        op.execute("""
            CREATE TABLE inference_queue_attempts (
                id               INTEGER PRIMARY KEY AUTOINCREMENT,
                job_id           TEXT NOT NULL REFERENCES inference_queue(id) ON DELETE CASCADE,
                attempt_number   INTEGER NOT NULL,
                provider         TEXT NOT NULL,
                model            TEXT,
                started_at       TEXT NOT NULL DEFAULT (datetime('now')),
                completed_at     TEXT,
                latency_ms       REAL,
                success          INTEGER NOT NULL,
                error            TEXT,
                cost_usd         REAL DEFAULT 0.0,
                prompt_tokens    INTEGER,
                completion_tokens INTEGER
            )
        """)
        op.execute("CREATE INDEX IF NOT EXISTS ix_queue_attempts_job_attempt ON inference_queue_attempts(job_id, attempt_number)")
        op.execute("CREATE INDEX IF NOT EXISTS ix_queue_attempts_provider    ON inference_queue_attempts(provider, success)")

    # ── inference_metrics ─────────────────────────────────────────────────────
    if "inference_metrics" not in existing_tables:
        op.execute("""
            CREATE TABLE inference_metrics (
                id                INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp         TEXT NOT NULL DEFAULT (datetime('now')),
                provider          TEXT NOT NULL,
                model             TEXT NOT NULL,
                task_type         TEXT NOT NULL,
                latency_ms        REAL NOT NULL,
                prompt_tokens     INTEGER DEFAULT 0,
                completion_tokens INTEGER DEFAULT 0,
                total_tokens      INTEGER DEFAULT 0,
                cost              REAL DEFAULT 0.0,
                success           INTEGER NOT NULL DEFAULT 1,
                error             TEXT,
                user_id           TEXT,
                session_id        TEXT
            )
        """)
        op.execute("CREATE INDEX IF NOT EXISTS ix_metrics_timestamp        ON inference_metrics(timestamp)")
        op.execute("CREATE INDEX IF NOT EXISTS ix_metrics_provider_success ON inference_metrics(provider, success)")
        op.execute("CREATE INDEX IF NOT EXISTS ix_metrics_task_type        ON inference_metrics(task_type, timestamp)")
        op.execute("CREATE INDEX IF NOT EXISTS ix_metrics_user_session     ON inference_metrics(user_id, session_id)")


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = set(inspector.get_table_names())

    op.execute("DROP TABLE IF EXISTS inference_metrics")
    op.execute("DROP TABLE IF EXISTS inference_queue_attempts")

    if "inference_queue" in existing_tables:
        existing_indices = {idx["name"] for idx in inspector.get_indexes("inference_queue")}
        if "ix_queue_parent" in existing_indices:
            op.drop_index("ix_queue_parent",   table_name="inference_queue")
        if "ix_queue_pipeline" in existing_indices:
            op.drop_index("ix_queue_pipeline", table_name="inference_queue")

        iq_cols = {c["name"] for c in inspector.get_columns("inference_queue")}
        with op.batch_alter_table("inference_queue") as batch_op:
            for col in ("output_transform", "parent_job_id", "chain_sequence", "pipeline_id"):
                if col in iq_cols:
                    batch_op.drop_column(col)
            if "extra_metadata" in iq_cols:
                batch_op.alter_column("extra_metadata", new_column_name="metadata")

    if "provider_configs" in existing_tables:
        pc_cols = {c["name"] for c in inspector.get_columns("provider_configs")}
        if "extra_metadata" in pc_cols:
            with op.batch_alter_table("provider_configs") as batch_op:
                batch_op.alter_column("extra_metadata", new_column_name="metadata")
