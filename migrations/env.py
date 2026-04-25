"""Alembic env.py — configured for Guppy's SQLite user-data database.

The target database is resolved the same way as src/guppy/paths.py:
  - GUPPY_USER_DATA_DIR env var, or
  - %LOCALAPPDATA%/Guppy on Windows, or
  - ~/.guppy on other platforms

Run migrations:
    alembic upgrade head          # apply all pending migrations
    alembic downgrade -1          # roll back one step
    alembic current               # show current revision
    alembic history               # list all revisions
"""
from __future__ import annotations

import os
import sys
from logging.config import fileConfig
from pathlib import Path

from sqlalchemy import engine_from_config, pool
from alembic import context

# ── resolve project root so we can import from src/guppy ─────────────────────
_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


def _get_db_url() -> str:
    """Compute the SQLite URL for the Guppy main database."""
    configured = (os.environ.get("GUPPY_USER_DATA_DIR") or "").strip()
    if configured:
        data_dir = Path(configured).expanduser().resolve()
    else:
        local_app_data = (os.environ.get("LOCALAPPDATA") or "").strip()
        if local_app_data:
            data_dir = Path(local_app_data) / "Guppy"
        elif os.name == "nt":
            data_dir = Path.home() / "AppData" / "Local" / "Guppy"
        else:
            data_dir = Path.home() / ".guppy"

    data_dir.mkdir(parents=True, exist_ok=True)
    db_path = data_dir / "guppy_main.db"
    # SQLite URLs need forward slashes; on Windows the path may have backslashes
    return f"sqlite:///{db_path.as_posix()}"


# ── Alembic config ────────────────────────────────────────────────────────────
config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Inject the computed URL so alembic.ini doesn't need a hard-coded path
config.set_main_option("sqlalchemy.url", _get_db_url())

# No SQLAlchemy models — all migrations use op.execute() with raw SQL
target_metadata = None


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_as_batch=True,  # required for SQLite ALTER TABLE support
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            render_as_batch=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
