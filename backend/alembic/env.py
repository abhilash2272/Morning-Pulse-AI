"""
alembic/env.py
==============
Alembic migration environment for Morning Pulse AI.
Reads DATABASE_URL from settings so no secrets are hardcoded.
"""

from __future__ import annotations

import sys
from pathlib import Path
from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool
from alembic import context

# ------------------------------------------------------------------ #
# Make sure the backend/ package is importable from this file's location
# ------------------------------------------------------------------ #
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.config.settings import settings
from app.database.database import Base

# Import all models so Alembic sees them in Base.metadata
import app.database.models  # noqa: F401

# ------------------------------------------------------------------ #
# Alembic Config object
# ------------------------------------------------------------------ #
config = context.config

# Override the sqlalchemy.url from alembic.ini with the value from settings
# so we always use the correct DATABASE_URL regardless of what's in alembic.ini
config.set_main_option("sqlalchemy.url", settings.database_url)

# Set up Python logging from the config file (if present)
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# The metadata object for 'autogenerate' support
target_metadata = Base.metadata


# ------------------------------------------------------------------ #
# Offline migrations (no live DB connection)
# ------------------------------------------------------------------ #
def run_migrations_offline() -> None:
    """
    Run migrations in 'offline' mode.
    Generates SQL scripts without connecting to the database.
    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


# ------------------------------------------------------------------ #
# Online migrations (live DB connection)
# ------------------------------------------------------------------ #
def run_migrations_online() -> None:
    """
    Run migrations in 'online' mode.
    Creates an engine and runs migrations against the live database.
    """
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
