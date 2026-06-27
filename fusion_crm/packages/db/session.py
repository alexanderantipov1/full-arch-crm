"""Async SQLAlchemy engine and session factory.

There is exactly ONE engine per process. Acquire sessions via
``async_session()`` (context manager) or via the FastAPI dependency
``apps.api.dependencies.get_db``.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from packages.core.config import get_settings
from packages.db import registry as _registry  # noqa: F401


def _build_engine() -> AsyncEngine:
    settings = get_settings()
    return create_async_engine(
        str(settings.database_url),
        pool_pre_ping=True,
        pool_size=10,
        max_overflow=20,
        future=True,
        echo=False,
    )


engine: AsyncEngine = _build_engine()

SessionFactory: async_sessionmaker[AsyncSession] = async_sessionmaker(
    bind=engine,
    expire_on_commit=False,
    autoflush=False,
    autocommit=False,
)


@asynccontextmanager
async def async_session() -> AsyncIterator[AsyncSession]:
    """Yield a session that commits on success and rolls back on error.

    Use for scripts, jobs, and tests. The API uses a per-request dependency.
    """
    session = SessionFactory()
    try:
        yield session
        await session.commit()
    except Exception:
        await session.rollback()
        raise
    finally:
        await session.close()
