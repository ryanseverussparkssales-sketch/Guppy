"""Migration: Add provider registry and inference metrics tables.

Alembic migration to add:
    - provider_configs: Registry of enabled/disabled providers and their settings
    - inference_metrics: Track all inferences for cost attribution and analysis

Revision ID: 0002_provider_registry
Revises: 0001
Create Date: 2026-04-25
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "0002_provider_registry"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create provider registry and metrics tables."""

    # Provider configurations table
    op.create_table(
        "provider_configs",
        sa.Column(
            "id",
            sa.String(32),
            primary_key=True,
            comment="Provider identifier: local, anthropic, openai, google, cohere, mistral",
        ),
        sa.Column("name", sa.String(128), nullable=False, comment="Display name"),
        sa.Column(
            "is_enabled",
            sa.Integer,
            nullable=False,
            default=0,
            comment="1=enabled, 0=disabled",
        ),
        sa.Column(
            "priority_order",
            sa.Integer,
            nullable=False,
            comment="Lower=higher priority in fallback chain",
        ),
        sa.Column(
            "timeout_seconds",
            sa.Float,
            nullable=False,
            comment="Request timeout in seconds",
        ),
        sa.Column(
            "retry_limit",
            sa.Integer,
            nullable=False,
            default=2,
            comment="Retries on timeout before falling back",
        ),
        sa.Column(
            "cost_per_1k_tokens",
            sa.Float,
            nullable=True,
            comment="Optional cost estimation per 1k tokens",
        ),
        sa.Column(
            "api_key",
            sa.String(512),
            nullable=True,
            comment="API key (encrypted in production)",
        ),
        sa.Column(
            "model_id",
            sa.String(256),
            nullable=True,
            comment="Default model for this provider",
        ),
        sa.Column(
            "metadata",
            sa.Text,
            nullable=True,
            default="{}",
            comment="JSON metadata for provider-specific settings",
        ),
        sa.Column(
            "created_at",
            sa.DateTime,
            nullable=False,
            server_default=sa.func.current_timestamp(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime,
            nullable=False,
            server_default=sa.func.current_timestamp(),
            onupdate=sa.func.current_timestamp(),
        ),
    )
    op.create_index("ix_provider_configs_enabled", "provider_configs", ["is_enabled"])
    op.create_index("ix_provider_configs_priority", "provider_configs", ["priority_order"])

    # Inference metrics table
    op.create_table(
        "inference_metrics",
        sa.Column(
            "id",
            sa.Integer,
            primary_key=True,
            autoincrement=True,
        ),
        sa.Column(
            "timestamp",
            sa.DateTime,
            nullable=False,
            server_default=sa.func.current_timestamp(),
            comment="When the inference occurred",
        ),
        sa.Column(
            "provider",
            sa.String(32),
            nullable=False,
            comment="Provider used (local, anthropic, openai, etc.)",
        ),
        sa.Column(
            "model",
            sa.String(256),
            nullable=False,
            comment="Model ID that processed this request",
        ),
        sa.Column(
            "task_type",
            sa.String(32),
            nullable=False,
            comment="Task classification: simple, complex, teaching, code, vault",
        ),
        sa.Column(
            "latency_ms",
            sa.Float,
            nullable=False,
            comment="Total latency in milliseconds",
        ),
        sa.Column(
            "prompt_tokens",
            sa.Integer,
            nullable=True,
            default=0,
            comment="Input token count (if available)",
        ),
        sa.Column(
            "completion_tokens",
            sa.Integer,
            nullable=True,
            default=0,
            comment="Output token count (if available)",
        ),
        sa.Column(
            "total_tokens",
            sa.Integer,
            nullable=True,
            default=0,
            comment="Total token count",
        ),
        sa.Column(
            "cost",
            sa.Float,
            nullable=True,
            default=0.0,
            comment="Estimated cost in USD",
        ),
        sa.Column(
            "success",
            sa.Integer,
            nullable=False,
            default=1,
            comment="1=success, 0=failure",
        ),
        sa.Column(
            "error",
            sa.Text,
            nullable=True,
            comment="Error message if failure",
        ),
        sa.Column(
            "user_id",
            sa.String(128),
            nullable=True,
            comment="User ID if tracking per-user metrics",
        ),
        sa.Column(
            "session_id",
            sa.String(128),
            nullable=True,
            comment="Session ID for correlation with chat history",
        ),
    )

    # Composite indices for metrics analysis
    op.create_index(
        "ix_metrics_timestamp",
        "inference_metrics",
        ["timestamp"],
        comment="For time-series queries",
    )
    op.create_index(
        "ix_metrics_provider_success",
        "inference_metrics",
        ["provider", "success"],
        comment="For per-provider success rate analysis",
    )
    op.create_index(
        "ix_metrics_task_type",
        "inference_metrics",
        ["task_type", "timestamp"],
        comment="For task-type performance analysis",
    )
    op.create_index(
        "ix_metrics_user_session",
        "inference_metrics",
        ["user_id", "session_id"],
        comment="For per-user/session cost tracking",
    )


def downgrade() -> None:
    """Drop provider registry and metrics tables."""
    op.drop_index("ix_metrics_user_session", table_name="inference_metrics")
    op.drop_index("ix_metrics_task_type", table_name="inference_metrics")
    op.drop_index("ix_metrics_provider_success", table_name="inference_metrics")
    op.drop_index("ix_metrics_timestamp", table_name="inference_metrics")
    op.drop_table("inference_metrics")

    op.drop_index("ix_provider_configs_priority", table_name="provider_configs")
    op.drop_index("ix_provider_configs_enabled", table_name="provider_configs")
    op.drop_table("provider_configs")
