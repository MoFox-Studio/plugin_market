"""Skill package storage and download persistence tests."""

from __future__ import annotations

import io
from pathlib import Path
import zipfile

from httpx import AsyncClient
from sqlalchemy import select

from plugin_market_backend.config import reset_settings_cache
from plugin_market_backend.content import resolve_skill_package_path, store_skill_package
from plugin_market_backend.database import session_scope
from plugin_market_backend.orm import SkillVersionORM
from plugin_market_backend.session_auth import create_browser_session


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
    assert version_row.package_path == "skill_packages/demo_skill/1.0.0.zip"
    assert Path("data/skill_packages/demo_skill/1.0.0.zip").read_bytes() == zip_bytes


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


def test_resolve_skill_package_path_supports_legacy_data_prefix(
    monkeypatch,
    tmp_path: Path,
) -> None:
    """Legacy ``data/...`` package paths should still resolve after cwd changes."""

    storage_root = tmp_path / "persisted-storage"
    monkeypatch.setenv("PLUGIN_MARKET_STORAGE_DIR", str(storage_root))
    reset_settings_cache()

    stored_path = store_skill_package("demo_skill", "1.0.0", build_skill_zip())
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    monkeypatch.chdir(elsewhere)

    resolved = resolve_skill_package_path(f"data/{stored_path}")

    assert resolved == (storage_root / stored_path).resolve()
