"""Alembic environment configuration for Cyber-Red storage schema.

This module configures Alembic to use the SQLAlchemy ORM models defined
in cyberred.storage.schema for database migrations.

Key features:
- SQLite WAL mode enabled by default
- Foreign key enforcement enabled
- Supports both online and offline migration modes
"""

from __future__ import annotations

from logging.config import fileConfig
from pathlib import Path

from alembic import context
from sqlalchemy import create_engine, event, pool

# Import our schema models
from cyberred.storage.schema import Base

# Alembic Config object - only available during alembic commands
config = context.config

# Set up logging if config file available
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# SQLAlchemy metadata for autogenerate support
target_metadata = Base.metadata


def enable_sqlite_fk(dbapi_connection, connection_record) -> None:  # type: ignore[no-untyped-def]
    """Enable foreign keys and WAL mode for SQLite."""
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.close()


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL and not an Engine,
    suitable for generating SQL scripts without connecting to a database.
    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    Creates an Engine and connects to the database to run migrations.
    Enables SQLite foreign keys and WAL mode.
    """
    connectable = create_engine(
        config.get_main_option("sqlalchemy.url", "sqlite:///:memory:"),
        poolclass=pool.NullPool,
    )

    # Enable FK enforcement and WAL mode for SQLite
    event.listen(connectable, "connect", enable_sqlite_fk)

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            render_as_batch=True,  # Required for SQLite ALTER TABLE operations
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()

