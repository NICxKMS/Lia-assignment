"""Async database session management with connection pooling.

Optimized for serverless PostgreSQL (Neon) with proper pool settings
and connection health checks.
"""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from functools import lru_cache
from typing import Any

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)


@lru_cache
def get_engine() -> AsyncEngine:
    """Get or create the async database engine (cached)."""
    settings = get_settings()

    # Use NullPool for serverless environments (Neon / Supabase handle pooling)
    # For traditional deployments, use standard pooling
    use_null_pool = any(
        host in settings.database_url
        for host in ("neon.tech", "pooler.supabase.com", "supabase.com")
    )

    engine_kwargs: dict[str, Any] = {
        "echo": settings.db_echo,
        "pool_pre_ping": True,  # Verify connections before use
    }

    url = settings.processed_database_url
    # Disable asyncpg prepared statement cache to avoid InvalidCachedStatementError
    # when database schema changes or when using pgbouncer.
    # For SQLite tests, connect_args must be empty.
    if url.startswith("sqlite"):
        connect_args: dict[str, Any] = {}
    else:
        connect_args = {
            "statement_cache_size": 0,
            "prepared_statement_cache_size": 0,
            "timeout": 10,  # 10-second connect timeout
        }

    if use_null_pool:
        # Serverless: let Neon handle connection pooling
        engine_kwargs["poolclass"] = NullPool
        logger.info("Using NullPool for serverless database")
    else:
        # Traditional: use SQLAlchemy connection pool
        engine_kwargs.update({
            "pool_size": settings.db_pool_size,
            "max_overflow": settings.db_max_overflow,
            "pool_timeout": settings.db_pool_timeout,
            "pool_recycle": 300,  # Recycle connections after 5 min (within Supavisor idle timeout)
        })
        logger.info(
            "Using connection pool",
            pool_size=settings.db_pool_size,
            max_overflow=settings.db_max_overflow,
        )

    engine = create_async_engine(
        url,
        connect_args=connect_args,
        **engine_kwargs
    )
    logger.info("Database engine created")
    return engine


@lru_cache
def get_session_factory() -> async_sessionmaker[AsyncSession]:
    """Get or create the async session factory (cached)."""
    return async_sessionmaker(
        bind=get_engine(),
        class_=AsyncSession,
        expire_on_commit=False,
        autocommit=False,
        autoflush=False,
    )


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency that provides an async database session.

    Automatically handles commit on success and rollback on exception.
    """
    session_factory = get_session_factory()
    async with session_factory() as session:
        try:
            yield session
            await session.commit()
        except BaseException:
            await session.rollback()
            raise


@asynccontextmanager
async def get_db_context() -> AsyncGenerator[AsyncSession, None]:
    """Context manager for database sessions outside of FastAPI.

    Useful for background tasks, migrations, etc.
    """
    session_factory = get_session_factory()
    async with session_factory() as session:
        try:
            yield session
            await session.commit()
        except BaseException:
            await session.rollback()
            raise


async def init_db() -> None:
    """Initialize database tables.

    Creates all tables defined in the models if they don't exist.
    For production, use Alembic migrations instead.
    """
    from app.core.config import get_settings
    settings = get_settings()

    if settings.debug:
        from app.db.models import Base

        engine = get_engine()
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    logger.info("Database tables initialized")


async def close_db() -> None:
    """Close database connections and dispose of the engine."""
    try:
        engine = get_engine()
    except Exception:
        return

    await engine.dispose()
    get_engine.cache_clear()
    get_session_factory.cache_clear()
    logger.info("Database connections closed")


async def check_db_health(timeout: float = 5.0) -> bool:
    """Check database connectivity with timeout."""
    import asyncio

    from sqlalchemy import text

    async def _check() -> bool:
        engine = get_engine()
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return True

    try:
        return await asyncio.wait_for(_check(), timeout=timeout)
    except TimeoutError:
        logger.error("Database health check timed out", timeout=timeout)
        return False
    except Exception as e:
        logger.error("Database health check failed", error=str(e))
        return False
