"""Alembic environment configuration for async migrations."""

import asyncio
from logging.config import fileConfig
from typing import Any

from sqlalchemy import pool, text
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from alembic import context

# Import models and config
from app.core.config import get_settings
from app.db.models import Base

# Alembic Config object
config = context.config

# Set up Python logging from alembic.ini
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Add model's MetaData for 'autogenerate' support
target_metadata = Base.metadata

# Get database URL from settings
settings = get_settings()


def get_url() -> str:
    """Get database URL from settings."""
    return settings.processed_database_url


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL and not an Engine,
    though an Engine is acceptable here as well. By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the script output.
    """
    url = get_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    """Run migrations with the given connection."""
    context.configure(connection=connection, target_metadata=target_metadata)

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Run migrations in 'online' mode with async engine."""
    configuration = config.get_section(config.config_ini_section, {})
    url = get_url()
    configuration["sqlalchemy.url"] = url

    # Determine connect_args for asyncpg (skip for sqlite)
    connect_args: dict[str, Any] = {}
    if not url.startswith("sqlite"):
        connect_args = {
            "statement_cache_size": 0,
            "prepared_statement_cache_size": 0,
            "timeout": 10,
        }

    connectable = async_engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
        connect_args=connect_args,
    )

    async with connectable.connect() as connection:
        # Prevent concurrent migration runs
        await connection.execute(text("SELECT pg_advisory_lock(12345)"))
        try:
            await connection.run_sync(do_run_migrations)
            await connection.commit()
        finally:
            await connection.execute(text("SELECT pg_advisory_unlock(12345)"))

    await connectable.dispose()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
