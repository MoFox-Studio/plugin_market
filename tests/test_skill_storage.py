"""Skill package storage and download persistence tests."""

from __future__ import annotations

import io
from pathlib import Path
import zipfile

from httpx import AsyncClient
from sqlalchemy import select
from urllib.parse import quote

from plugin_market_backend.config import reset_settings_cache
from plugin_market_backend.content import (
    load_skill_package_manifest,
    resolve_skill_package_path,
    store_skill_package,
)
from plugin_market_backend.database import close_database, configure_database, init_database, session_scope
from plugin_market_backend.orm import SkillORM, SkillVersionORM
from plugin_market_backend.session_auth import create_browser_session
from plugin_market_backend.services.skill_service import synchronize_skill_storage


def build_skill_zip(
    *,
    name: str = "Demo Skill",
    description: str = "Demo skill package.",
) -> bytes:
    """Create a minimal valid skill zip for upload tests."""

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr(
            "SKILL.md",
            (
                "---\n"
                f"name: {name}\n"
                f"description: {description}\n"
                "---\n"
                "# Demo Skill\n\n"
                "This is a packaged skill.\n"
            ),
        )
    return buffer.getvalue()


async def test_publish_skill_stores_storage_relative_package_path(client: AsyncClient) -> None:
    """Uploaded skills should persist under the shared storage root."""

    session_id = await create_browser_session("mock-author", "browser-test-token")
    client.cookies.set("plugin_market_session", session_id, path="/")
    zip_bytes = build_skill_zip()

    created = await client.post(
        "/api/v1/skills",
        data={"skill_id": "demo_skill", "version": "1.0.0"},
        files={"file": ("demo_skill.zip", zip_bytes, "application/zip")},
    )
    downloaded = await client.get("/api/v1/skills/demo_skill/versions/1.0.0/download")

    assert created.status_code == 200
    assert created.json()["skill_id"] == "demo_skill"
    assert downloaded.status_code == 200
    assert downloaded.content == zip_bytes

    async with session_scope() as session:
        version_row = await session.scalar(
            select(SkillVersionORM).where(
                SkillVersionORM.skill_id == "demo_skill",
                SkillVersionORM.version == "1.0.0",
            )
        )

    assert version_row is not None
    assert version_row.package_path == "skill_packages/mock-author/demo_skill/1.0.0.zip"
    assert Path("data/skill_packages/mock-author/demo_skill/1.0.0.zip").read_bytes() == zip_bytes
    assert load_skill_package_manifest(version_row.package_path)["owner_id"] == "mock-author"


async def test_publish_skill_rejects_invalid_skill_id(client: AsyncClient) -> None:
    """Multipart skill uploads should reject path-like identifiers."""

    session_id = await create_browser_session("mock-author", "browser-test-token")
    client.cookies.set("plugin_market_session", session_id, path="/")

    response = await client.post(
        "/api/v1/skills",
        data={"skill_id": "../escape", "version": "1.0.0"},
        files={"file": ("escape.zip", build_skill_zip(), "application/zip")},
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "INVALID_SKILL_ID"


async def test_publish_skill_allows_chinese_and_uppercase_identifiers(client: AsyncClient) -> None:
    """Skill storage should accept Chinese and uppercase ids via encoded paths."""

    session_id = await create_browser_session("mock-author", "browser-test-token")
    client.cookies.set("plugin_market_session", session_id, path="/")
    skill_id = "科研助手AI"
    version = "V1.测试"
    zip_bytes = build_skill_zip(name="科研助手 AI")

    created = await client.post(
        "/api/v1/skills",
        data={"skill_id": skill_id, "version": version},
        files={"file": ("research-helper.zip", zip_bytes, "application/zip")},
    )
    downloaded = await client.get(f"/api/v1/skills/{skill_id}/versions/{version}/download")

    expected_path = (
        Path("skill_packages")
        / "mock-author"
        / quote(skill_id, safe="")
        / f"{quote(version, safe='')}.zip"
    ).as_posix()

    assert created.status_code == 200
    assert created.json()["skill_id"] == skill_id
    assert downloaded.status_code == 200
    assert downloaded.content == zip_bytes

    async with session_scope() as session:
        version_row = await session.scalar(
            select(SkillVersionORM).where(
                SkillVersionORM.skill_id == skill_id,
                SkillVersionORM.version == version,
            )
        )

    assert version_row is not None
    assert version_row.package_path == expected_path
    assert resolve_skill_package_path(expected_path).read_bytes() == zip_bytes


async def test_recover_skill_from_storage_manifest_after_database_reset(
    client: AsyncClient,
    monkeypatch,
    tmp_path: Path,
) -> None:
    """Recovery should recreate skill rows from persisted packages when the DB is reset."""

    storage_root = tmp_path / "storage"
    monkeypatch.setenv("PLUGIN_MARKET_STORAGE_DIR", str(storage_root))
    reset_settings_cache()
    session_id = await create_browser_session("mock-author", "browser-test-token")
    client.cookies.set("plugin_market_session", session_id, path="/")
    zip_bytes = build_skill_zip(name="Recovered Skill")

    created = await client.post(
        "/api/v1/skills",
        data={"skill_id": "Recovered技能", "version": "V2.0"},
        files={"file": ("recovered.zip", zip_bytes, "application/zip")},
    )

    assert created.status_code == 200
    assert resolve_skill_package_path(
        "skill_packages/mock-author/Recovered%E6%8A%80%E8%83%BD/V2.0.zip"
    ).exists()

    await close_database()
    configure_database("sqlite+aiosqlite:///:memory:")
    await init_database()

    async with session_scope() as session:
        recovered = await synchronize_skill_storage(session)
        skill_row = await session.scalar(
            select(SkillVersionORM).where(
                SkillVersionORM.skill_id == "Recovered技能",
                SkillVersionORM.version == "V2.0",
            )
        )

    assert recovered >= 2
    assert skill_row is not None


async def test_recover_legacy_skill_package_without_manifest_uses_fallback_owner(
    monkeypatch,
    tmp_path: Path,
) -> None:
    """Legacy packages without sidecar metadata should still be recovered."""

    storage_root = tmp_path / "legacy-storage"
    monkeypatch.setenv("PLUGIN_MARKET_STORAGE_DIR", str(storage_root))
    reset_settings_cache()
    legacy_dir = storage_root / "skill_packages" / "Legacy技能"
    legacy_dir.mkdir(parents=True, exist_ok=True)
    (legacy_dir / "V1.zip").write_bytes(build_skill_zip(name="Legacy Skill"))

    await close_database()
    configure_database("sqlite+aiosqlite:///:memory:")
    await init_database()

    async with session_scope() as session:
        recovered = await synchronize_skill_storage(session)
        skill_row = await session.get(SkillORM, "Legacy技能")
        version_row = await session.scalar(
            select(SkillVersionORM).where(
                SkillVersionORM.skill_id == "Legacy技能",
                SkillVersionORM.version == "V1",
            )
        )

    assert recovered >= 2
    assert skill_row is not None
    assert skill_row.owner_id == "recovered:Legacy技能"
    assert version_row is not None
    assert version_row.package_path == "skill_packages/Legacy技能/V1.zip"


def test_resolve_skill_package_path_supports_legacy_data_prefix(
    monkeypatch,
    tmp_path: Path,
) -> None:
    """Legacy ``data/...`` package paths should still resolve after cwd changes."""

    storage_root = tmp_path / "persisted-storage"
    monkeypatch.setenv("PLUGIN_MARKET_STORAGE_DIR", str(storage_root))
    reset_settings_cache()

    stored_path = store_skill_package("mock-author", "demo_skill", "1.0.0", build_skill_zip())
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    monkeypatch.chdir(elsewhere)

    resolved = resolve_skill_package_path(f"data/{stored_path}")

    assert resolved == (storage_root / stored_path).resolve()
