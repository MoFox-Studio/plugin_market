"""初始化时识别技能表迁移版本的回归测试。"""

from __future__ import annotations

from sqlalchemy import create_engine

from plugin_market_backend.bootstrap import (
    SKILL_MARKET_REVISION,
    SKILL_README_REVISION,
    _bootstrap_revision,
)


def _create_base_market_tables(connection) -> None:
    connection.exec_driver_sql(
        """
        CREATE TABLE authors (
            author_id VARCHAR(120) PRIMARY KEY
        )
        """
    )
    connection.exec_driver_sql(
        """
        CREATE TABLE plugins (
            plugin_id VARCHAR(120) PRIMARY KEY
        )
        """
    )
    connection.exec_driver_sql(
        """
        CREATE TABLE plugin_versions (
            id INTEGER PRIMARY KEY,
            plugin_id VARCHAR(120),
            version VARCHAR(80),
            download_count INTEGER
        )
        """
    )
    connection.exec_driver_sql(
        """
        CREATE TABLE author_follows (
            id INTEGER PRIMARY KEY
        )
        """
    )
    connection.exec_driver_sql(
        """
        CREATE TABLE plugin_subscriptions (
            id INTEGER PRIMARY KEY
        )
        """
    )
    connection.exec_driver_sql(
        """
        CREATE TABLE author_access_tokens (
            id INTEGER PRIMARY KEY
        )
        """
    )


def _create_skill_tables(connection, *, with_readme: bool) -> None:
    readme_column = ", readme_markdown TEXT" if with_readme else ""
    connection.exec_driver_sql(
        f"""
        CREATE TABLE skills (
            skill_id VARCHAR(120) PRIMARY KEY,
            display_name VARCHAR(200),
            description TEXT,
            owner_id VARCHAR(120),
            categories JSON,
            tags JSON,
            status VARCHAR(20),
            trust_level VARCHAR(20),
            download_count INTEGER,
            created_at DATETIME,
            updated_at DATETIME
            {readme_column}
        )
        """
    )
    connection.exec_driver_sql(
        """
        CREATE TABLE skill_versions (
            id INTEGER PRIMARY KEY,
            skill_id VARCHAR(120),
            version VARCHAR(80),
            package_path VARCHAR(500),
            package_size INTEGER,
            checksum_sha256 VARCHAR(64),
            created_at DATETIME
        )
        """
    )
    connection.exec_driver_sql("CREATE TABLE skill_likes (id INTEGER PRIMARY KEY)")
    connection.exec_driver_sql("CREATE TABLE skill_ratings (id INTEGER PRIMARY KEY)")
    connection.exec_driver_sql("CREATE TABLE skill_comments (id INTEGER PRIMARY KEY)")
    connection.exec_driver_sql("CREATE TABLE skill_subscriptions (id INTEGER PRIMARY KEY)")


def test_bootstrap_detects_skill_readme_revision_without_alembic_version() -> None:
    """已有技能表应识别为 0007，而不是误标为 0005。"""
    engine = create_engine("sqlite:///:memory:")
    with engine.begin() as connection:
        _create_base_market_tables(connection)
        _create_skill_tables(connection, with_readme=True)

        assert _bootstrap_revision(connection) == SKILL_README_REVISION


def test_bootstrap_upgrades_stale_alembic_version_to_skill_readme_revision() -> None:
    """已标记为 0005 但包含技能表的数据库应重新标记为 0007。"""
    engine = create_engine("sqlite:///:memory:")
    with engine.begin() as connection:
        _create_base_market_tables(connection)
        _create_skill_tables(connection, with_readme=True)
        connection.exec_driver_sql(
            """
            CREATE TABLE alembic_version (
                version_num VARCHAR(32) NOT NULL
            )
            """
        )
        connection.exec_driver_sql(
            "INSERT INTO alembic_version (version_num) VALUES ('0005_subscriptions_and_tokens')"
        )

        assert _bootstrap_revision(connection) == SKILL_README_REVISION


def test_bootstrap_detects_pre_readme_skill_revision() -> None:
    """缺少 readme_markdown 的技能表应对应 0006。"""
    engine = create_engine("sqlite:///:memory:")
    with engine.begin() as connection:
        _create_base_market_tables(connection)
        _create_skill_tables(connection, with_readme=False)

        assert _bootstrap_revision(connection) == SKILL_MARKET_REVISION
