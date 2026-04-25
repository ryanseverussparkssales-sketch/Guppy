"""SQLAlchemy ORM models for Guppy database schema.

Maps to Alembic migrations:
    - 0002_provider_registry.py (provider_configs, inference_metrics)
    - 0003_inference_queue.py (inference_queue, inference_queue_attempts)
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import Column, String, Integer, Float, Text, DateTime, ForeignKey, Index
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


class ProviderConfig(Base):
    """Provider registry configuration table."""

    __tablename__ = "provider_configs"

    id = Column(String(32), primary_key=True)  # local, anthropic, openai, google, cohere, mistral
    name = Column(String(128), nullable=False)
    is_enabled = Column(Integer, nullable=False, default=0)  # 1=enabled, 0=disabled
    priority_order = Column(Integer, nullable=False)  # Lower = higher priority
    timeout_seconds = Column(Float, nullable=False)
    retry_limit = Column(Integer, nullable=False, default=2)
    cost_per_1k_tokens = Column(Float, nullable=True)
    api_key = Column(String(512), nullable=True)
    model_id = Column(String(256), nullable=True)
    metadata = Column(Text, nullable=True, default="{}")  # JSON
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    __table_args__ = (
        Index("ix_provider_configs_enabled", "is_enabled"),
        Index("ix_provider_configs_priority", "priority_order"),
    )


class InferenceMetrics(Base):
    """Per-inference metrics for cost attribution and analysis."""

    __tablename__ = "inference_metrics"

    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime, nullable=False, default=datetime.utcnow)
    provider = Column(String(32), nullable=False)  # local, anthropic, openai, etc.
    model = Column(String(256), nullable=False)
    task_type = Column(String(32), nullable=False)  # simple, complex, teaching, code, vault
    latency_ms = Column(Float, nullable=False)
    prompt_tokens = Column(Integer, nullable=True, default=0)
    completion_tokens = Column(Integer, nullable=True, default=0)
    total_tokens = Column(Integer, nullable=True, default=0)
    cost = Column(Float, nullable=True, default=0.0)
    success = Column(Integer, nullable=False, default=1)  # 1=success, 0=failure
    error = Column(Text, nullable=True)
    user_id = Column(String(128), nullable=True)
    session_id = Column(String(128), nullable=True)

    __table_args__ = (
        Index("ix_metrics_timestamp", "timestamp"),
        Index("ix_metrics_provider_success", "provider", "success"),
        Index("ix_metrics_task_type", "task_type", "timestamp"),
        Index("ix_metrics_user_session", "user_id", "session_id"),
    )


class InferenceQueue(Base):
    """Persistent queue for inference jobs with retry tracking."""

    __tablename__ = "inference_queue"

    id = Column(String(64), primary_key=True)  # UUID for idempotency
    status = Column(String(32), nullable=False, default="queued")  # queued, executing, success, failed, timeout
    priority = Column(Integer, nullable=False, default=100)  # 0=highest, 255=lowest
    prompt = Column(Text, nullable=False)
    system_prompt = Column(Text, nullable=True)
    task_type = Column(String(32), nullable=False)  # simple, complex, teaching, code, vault
    preferred_provider = Column(String(32), nullable=True)
    max_retries = Column(Integer, nullable=False, default=3)
    retry_count = Column(Integer, nullable=False, default=0)
    backoff_multiplier = Column(Float, nullable=False, default=2.0)
    last_attempt_at = Column(DateTime, nullable=True)
    next_retry_at = Column(DateTime, nullable=True)  # Scheduled retry time with exponential backoff
    response = Column(Text, nullable=True)
    provider_used = Column(String(32), nullable=True)
    error_message = Column(Text, nullable=True)
    execution_ms = Column(Float, nullable=True)
    cost_usd = Column(Float, nullable=True, default=0.0)
    user_id = Column(String(128), nullable=True)
    session_id = Column(String(128), nullable=True)
    metadata = Column(Text, nullable=True, default="{}")  # JSON
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)

    # Relationship to attempts
    attempts = relationship(
        "InferenceQueueAttempt",
        back_populates="job",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        Index("ix_queue_status_priority", "status", "priority", "created_at"),
        Index("ix_queue_next_retry", "next_retry_at"),
        Index("ix_queue_user_session", "user_id", "session_id"),
        Index("ix_queue_status_completed", "status", "completed_at"),
    )


class InferenceQueueAttempt(Base):
    """Retry attempt history for each inference job."""

    __tablename__ = "inference_queue_attempts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    job_id = Column(String(64), ForeignKey("inference_queue.id", ondelete="CASCADE"), nullable=False)
    attempt_number = Column(Integer, nullable=False)
    provider = Column(String(32), nullable=False)
    model = Column(String(256), nullable=True)
    started_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)
    latency_ms = Column(Float, nullable=True)
    success = Column(Integer, nullable=False)  # 1=success, 0=failed
    error = Column(Text, nullable=True)
    cost_usd = Column(Float, nullable=True, default=0.0)
    prompt_tokens = Column(Integer, nullable=True)
    completion_tokens = Column(Integer, nullable=True)

    # Relationship to job
    job = relationship("InferenceQueue", back_populates="attempts")

    __table_args__ = (
        Index("ix_queue_attempts_job_attempt", "job_id", "attempt_number"),
        Index("ix_queue_attempts_provider", "provider", "success"),
    )
