"""Deployment bootstrap helpers for schema migration hand-off."""

from __future__ import annotations

from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import inspect
from sqlalchemy.ext.asyncio import create_async_engine

from plugin_market_backend.config import get_settings


HEAD_REVISION = "0004_overhaul_phase1"


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _alembic_config() -> Config:
    config = Config(str(_repo_root() / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", get_settings().database_url)
    return config


def _bootstrap_revision(sync_conn) -> str | None:
    inspector = inspect(sync_conn)
    tables = set(inspector.get_table_names())

    if "alembic_version" in tables:
        return None

    if not {"authors", "plugins", "plugin_versions"}.issubset(tables):
        return None

    revision = "0001_initial"

    if {"auth_sessions", "oauth_states"}.issubset(tables):
        revision = "0002_github_sessions"

    plugin_version_columns = {item["name"] for item in inspector.get_columns("plugin_versions")}
    if (
        {"plugin_likes", "plugin_ratings", "plugin_comments"}.issubset(tables)
        and "download_count" in plugin_version_columns
    ):
        revision = "0003_community"

    comment_columns = set()
    if "plugin_comments" in tables:
        comment_columns = {item["name"] for item in inspector.get_columns("plugin_comments")}
    overhaul_tables = {
        "author_profiles",
        "pinned_plugins",
        "curation_entries",
        "announcements",
        "announcement_dismissals",
        "inbox_messages",
        "comment_mentions",
        "plugin_metadata_changes",
    }
    existing_overhaul_tables = overhaul_tables.intersection(tables)
    if existing_overhaul_tables:
        revision = HEAD_REVISION

    return revision


async def _detect_bootstrap_revision() -> str | None:
    engine = create_async_engine(get_settings().database_url, future=True)
    try:
        async with engine.connect() as connection:
            return await connection.run_sync(_bootstrap_revision)
    finally:
        await engine.dispose()


def _run_alembic(revision: str | None) -> None:
    config = _alembic_config()
    if revision is not None:
        command.stamp(config, revision)
    command.upgrade(config, "head")


def main() -> None:
    import asyncio

    revision = asyncio.run(_detect_bootstrap_revision())
    _run_alembic(revision)


if __name__ == "__main__":
    main()