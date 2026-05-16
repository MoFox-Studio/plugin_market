"""Database engine, session, and schema helpers."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from sqlalchemy import inspect, text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine


_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def configure_database(database_url: str, *, echo: bool = False) -> None:
    """Configure the global async database engine."""

    global _engine, _session_factory
    if _engine is not None:
        return
    _engine = create_async_engine(database_url, echo=echo, future=True)
    _session_factory = async_sessionmaker(bind=_engine, class_=AsyncSession, expire_on_commit=False)


def get_engine() -> AsyncEngine:
    """Return the configured database engine."""

    if _engine is None:
        raise RuntimeError("Database is not configured.")
    return _engine


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    """Return the configured async session factory."""

    if _session_factory is None:
        raise RuntimeError("Database is not configured.")
    return _session_factory


@asynccontextmanager
async def session_scope() -> AsyncGenerator[AsyncSession, None]:
    """Yield a transactional async session."""

    session_factory = get_session_factory()
    async with session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def init_database() -> None:
    """Create all tables for deployments that do not use migrations yet."""

    from plugin_market_backend.orm import Base

    async with get_engine().begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        plugin_columns = await conn.run_sync(
            lambda sync_conn: {item["name"] for item in inspect(sync_conn).get_columns("plugins")}
        )
        if "readme_markdown" not in plugin_columns:
            await conn.execute(text("ALTER TABLE plugins ADD COLUMN readme_markdown TEXT"))
        if "plugin_dependencies" not in plugin_columns:
            await conn.execute(text("ALTER TABLE plugins ADD COLUMN plugin_dependencies JSON"))
        comment_columns = await conn.run_sync(
            lambda sync_conn: {item["name"] for item in inspect(sync_conn).get_columns("plugin_comments")}
        )
        if "mention_payload" not in comment_columns:
            await conn.execute(text("ALTER TABLE plugin_comments ADD COLUMN mention_payload JSON"))


async def drop_database() -> None:
    """Drop all tables. Intended for tests only."""

    from plugin_market_backend.orm import Base

    async with get_engine().begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


async def close_database() -> None:
    """Dispose the configured engine and clear globals."""

    global _engine, _session_factory
    if _engine is not None:
        await _engine.dispose()
    _engine = None
    _session_factory = None
