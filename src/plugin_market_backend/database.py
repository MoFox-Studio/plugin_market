"""数据库引擎、会话与表结构辅助工具。"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from sqlalchemy import inspect, text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine


_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def configure_database(database_url: str, *, echo: bool = False) -> None:
    """配置全局异步数据库引擎。"""
    global _engine, _session_factory
    if _engine is not None:
        return
    _engine = create_async_engine(database_url, echo=echo, future=True)
    _session_factory = async_sessionmaker(bind=_engine, class_=AsyncSession, expire_on_commit=False)


def get_engine() -> AsyncEngine:
    """返回已配置的数据库引擎。

    Raises:
        RuntimeError: 数据库尚未配置。
    """
    if _engine is None:
        raise RuntimeError("数据库尚未配置。")
    return _engine


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    """返回已配置的异步会话工厂。

    Raises:
        RuntimeError: 数据库尚未配置。
    """
    if _session_factory is None:
        raise RuntimeError("数据库尚未配置。")
    return _session_factory


@asynccontextmanager
async def session_scope() -> AsyncGenerator[AsyncSession, None]:
    """提供带事务管理的异步会话。

    Yields:
        异步数据库会话，正常退出时提交，发生异常时回滚。
    """
    session_factory = get_session_factory()
    async with session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def init_database() -> None:
    """为尚未使用迁移的部署创建所有表。"""
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
    """删除所有表，仅供测试使用。"""
    from plugin_market_backend.orm import Base

    async with get_engine().begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


async def close_database() -> None:
    """释放已配置的引擎并清空全局状态。"""
    global _engine, _session_factory
    if _engine is not None:
        await _engine.dispose()
    _engine = None
    _session_factory = None
