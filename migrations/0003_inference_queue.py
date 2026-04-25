"""Migration: Add inference queue and job tracking tables.

Alembic migration to add:
    - inference_queue: Persistent queue for inference requests
    - inference_queue_attempts: Track retry history with exponential backoff

Revision ID: 0003_inference_queue
Revises: 0002_provider_registry
Create Date: 2026-04-25
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "0003_inference_queue"
down_revision = "0002_provider_registry"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create inference queue tables."""

    # Main queue table for inference jobs
    op.create_table(
        "inference_queue",
        sa.Column(
            "id",
            sa.String(64),
            primary_key=True,
            comment="UUID for job tracking (idempotency key)",
        ),
        sa.Column(
            "status",
            sa.String(32),
            nullable=False,
            default="queued",
            comment="queued, executing, success, failed, timeout",
        ),
        sa.Column(
            "priority",
            sa.Integer,
            nullable=False,
            default=100,
            comment="Lower=higher priority (0-255)",
        ),
        sa.Column(
            "prompt",
            sa.Text,
            nullable=False,
            comment="User message / inference request",
        ),
        sa.Column(
            "system_prompt",
            sa.Text,
            nullable=True,
            comment="System context for inference",
        ),
        sa.Column(
            "task_type",
            sa.String(32),
            nullable=False,
            comment="Classification: simple, complex, teaching, code, vault",
        ),
        sa.Column(
            "preferred_provider",
            sa.String(32),
            nullable=True,
            comment="Optional provider override (local, anthropic, openai, etc.)",
        ),
        sa.Column(
            "max_retries",
            sa.Integer,
            nullable=False,
            default=3,
            comment="Maximum retry attempts",
        ),
        sa.Column(
            "retry_count",
            sa.Integer,
            nullable=False,
            default=0,
            comment="Number of retries attempted so far",
        ),
        sa.Column(
            "backoff_multiplier",
            sa.Float,
            nullable=False,
            default=2.0,
            comment="Exponential backoff multiplier",
        ),
        sa.Column(
            "last_attempt_at",
            sa.DateTime,
            nullable=True,
            comment="When the last attempt was made",
        ),
        sa.Column(
            "next_retry_at",
            sa.DateTime,
            nullable=True,
            comment="When next retry is scheduled (exponential backoff)",
        ),
        sa.Column(
            "response",
            sa.Text,
            nullable=True,
            comment="Inference response (on success)",
        ),
        sa.Column(
            "provider_used",
            sa.String(32),
            nullable=True,
            comment="Which provider succeeded",
        ),
        sa.Column(
            "error_message",
            sa.Text,
            nullable=True,
            comment="Error details (on failure)",
        ),
        sa.Column(
            "execution_ms",
            sa.Float,
            nullable=True,
            comment="Total execution time in milliseconds",
        ),
        sa.Column(
            "cost_usd",
            sa.Float,
            nullable=True,
            default=0.0,
            comment="Total cost across all attempts",
        ),
        sa.Column(
            "user_id",
            sa.String(128),
            nullable=True,
            comment="User who submitted this request",
        ),
        sa.Column(
            "session_id",
            sa.String(128),
            nullable=True,
            comment="Chat session ID for correlation",
        ),
        sa.Column(
            "metadata",
            sa.Text,
            nullable=True,
            default="{}",
            comment="JSON metadata for custom fields",
        ),
        sa.Column(
            "created_at",
            sa.DateTime,
            nullable=False,
            server_default=sa.func.current_timestamp(),
            comment="When job was created",
        ),
        sa.Column(
            "completed_at",
            sa.DateTime,
            nullable=True,
            comment="When job completed (success or final failure)",
        ),
    )

    # Indices for queue operations
    op.create_index(
        "ix_queue_status_priority",
        "inference_queue",
        ["status", "priority", "created_at"],
        comment="For dequeuing: find next job by status and priority",
    )
    op.create_index(
        "ix_queue_next_retry",
        "inference_queue",
        ["next_retry_at"],
        comment="For retry scheduling: find jobs ready to retry",
    )
    op.create_index(
        "ix_queue_user_session",
        "inference_queue",
        ["user_id", "session_id"],
        comment="For user/session tracking",
    )
    op.create_index(
        "ix_queue_status_completed",
        "inference_queue",
        ["status", "completed_at"],
        comment="For historical analysis",
    )

    # Attempt history table for detailed retry tracking
    op.create_table(
        "inference_queue_attempts",
        sa.Column(
            "id",
            sa.Integer,
            primary_key=True,
            autoincrement=True,
        ),
        sa.Column(
            "job_id",
            sa.String(64),
            nullable=False,
            comment="Foreign key to inference_queue.id",
        ),
        sa.Column(
            "attempt_number",
            sa.Integer,
            nullable=False,
            comment="Which attempt this was (1, 2, 3, ...)",
        ),
        sa.Column(
            "provider",
            sa.String(32),
            nullable=False,
            comment="Which provider was tried",
        ),
        sa.Column(
            "model",
            sa.String(256),
            nullable=True,
            comment="Model used for this attempt",
        ),
        sa.Column(
            "started_at",
            sa.DateTime,
            nullable=False,
            server_default=sa.func.current_timestamp(),
        ),
        sa.Column(
            "completed_at",
            sa.DateTime,
            nullable=True,
            comment="When attempt finished (success or error)",
        ),
        sa.Column(
            "latency_ms",
            sa.Float,
            nullable=True,
            comment="How long this attempt took",
        ),
        sa.Column(
            "success",
            sa.Integer,
            nullable=False,
            comment="1=succeeded, 0=failed/timeout",
        ),
        sa.Column(
            "error",
            sa.Text,
            nullable=True,
            comment="Error message if failed",
        ),
        sa.Column(
            "cost_usd",
            sa.Float,
            nullable=True,
            default=0.0,
            comment="Cost of this attempt",
        ),
        sa.Column(
            "prompt_tokens",
            sa.Integer,
            nullable=True,
            comment="Input tokens (if tracked)",
        ),
        sa.Column(
            "completion_tokens",
            sa.Integer,
            nullable=True,
            comment="Output tokens (if tracked)",
        ),
    )

    op.create_index(
        "ix_queue_attempts_job_attempt",
        "inference_queue_attempts",
        ["job_id", "attempt_number"],
        comment="For retrieving attempt history for a job",
    )
    op.create_index(
        "ix_queue_attempts_provider",
        "inference_queue_attempts",
        ["provider", "success"],
        comment="For per-provider success rate analysis",
    )

    # Add foreign key
    op.create_foreign_key(
        "fk_queue_attempts_job",
        "inference_queue_attempts",
        "inference_queue",
        ["job_id"],
        ["id"],
        ondelete="CASCADE",
    )


def downgrade() -> None:
    """Drop queue tables."""
    op.drop_index("ix_queue_attempts_provider", table_name="inference_queue_attempts")
    op.drop_index("ix_queue_attempts_job_attempt", table_name="inference_queue_attempts")
    op.drop_constraint("fk_queue_attempts_job", "inference_queue_attempts", type_="foreignkey")
    op.drop_table("inference_queue_attempts")

    op.drop_index("ix_queue_status_completed", table_name="inference_queue")
    op.drop_index("ix_queue_user_session", table_name="inference_queue")
    op.drop_index("ix_queue_next_retry", table_name="inference_queue")
    op.drop_index("ix_queue_status_priority", table_name="inference_queue")
    op.drop_table("inference_queue")
