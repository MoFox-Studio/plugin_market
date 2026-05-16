"""Unit tests for ``InlineEditService`` (task 5).

These tests exercise the inline metadata patch surface of
:class:`plugin_market_backend.services.inline_edit_service.InlineEditService`
without going through FastAPI. They cover:

* happy-path patching of every editable field and the resulting audit row,
* the ``updated_at`` bump on success,
* owner / maintainer / admin authorization (Property 5),
* category validation against the live taxonomy,
* tag count cap (``METADATA_TAGS_TOO_MANY``),
* https-only icon_url validation (``METADATA_INVALID_ICON``),
* the no-fields and unknown-fields guards.

Tests reuse the shared fixtures in ``conftest.py`` which spin up an in-memory
SQLite database and call :func:`seed_database` before each test.
"""

from __future__ import annotations

import pytest
from sqlalchemy import func, select

from plugin_market_backend.database import session_scope
from plugin_market_backend.errors import ApiError
from plugin_market_backend.orm import (
    AuthorORM,
    AuthorType,
    PluginMaintainerORM,
    PluginMetadataChangeORM,
    PluginORM,
    utc_now,
)
from plugin_market_backend.schemas import PluginCreate
from plugin_market_backend.service import MarketService
from plugin_market_backend.services import InlineEditService


# ---------------------------------------------------------------------------
# Setup helpers
# ---------------------------------------------------------------------------


async def _ensure_author(
    session,
    author_id: str,
    *,
    github_login: str | None = None,
    is_admin: bool = False,
) -> None:
    """Create an author row if it does not exist."""

    if await session.get(AuthorORM, author_id) is not None:
        return
    session.add(
        AuthorORM(
            author_id=author_id,
            github_user_id=f"id-{author_id}",
            github_login=github_login or author_id,
            display_name=github_login or author_id,
            author_type=AuthorType.USER,
            verified_at=utc_now(),
            is_admin=is_admin,
        )
    )
    await session.flush()


async def _create_plugin(
    session,
    plugin_id: str,
    owner_id: str,
    *,
    categories: list[str] | None = None,
    tags: list[str] | None = None,
) -> None:
    """Register a plugin owned by ``owner_id`` using the live MarketService."""

    payload = PluginCreate(
        plugin_id=plugin_id,
        display_name=plugin_id,
        summary=f"summary for {plugin_id}",
        description=f"description for {plugin_id}",
        repository_url=f"https://github.com/MoFox-Studio/{plugin_id}",
        license="MIT",
        categories=categories if categories is not None else ["tool"],
        tags=tags if tags is not None else ["sample"],
        maintainers=[],
    )
    await MarketService(session).register_plugin(payload, owner_id=owner_id)


async def _count_metadata_changes(session, plugin_id: str) -> int:
    """Return the number of ``plugin_metadata_changes`` rows for ``plugin_id``."""

    stmt = (
        select(func.count())
        .select_from(PluginMetadataChangeORM)
        .where(PluginMetadataChangeORM.plugin_id == plugin_id)
    )
    return int((await session.scalar(stmt)) or 0)


# ---------------------------------------------------------------------------
# Happy paths
# ---------------------------------------------------------------------------


async def test_patch_metadata_updates_all_fields_and_writes_audit_row() -> None:
    """A full patch should mutate the plugin row and append exactly one audit row."""

    async with session_scope() as session:
        await _ensure_author(session, "owner")
        await _create_plugin(session, "plug-a", owner_id="owner", categories=["tool"])
        original_updated_at = (
            await session.get(PluginORM, "plug-a")
        ).updated_at

        service = InlineEditService(session)
        result = await service.patch_metadata(
            "owner",
            "plug-a",
            {
                "display_name": "Renamed Plugin",
                "icon_url": "https://cdn.example.com/icons/plug-a.png",
                "categories": ["tool"],
                "tags": ["alpha", "beta"],
            },
        )

        assert result.display_name == "Renamed Plugin"
        assert result.icon_url == "https://cdn.example.com/icons/plug-a.png"
        assert result.categories == ["tool"]
        assert result.tags == ["alpha", "beta"]
        # SQLite/aiosqlite returns ``updated_at`` as a tz-naive datetime
        # while ``utc_now`` produces a tz-aware one, so we compare wall-clock
        # values to confirm the column was rewritten.
        assert (
            result.updated_at.replace(tzinfo=None)
            >= original_updated_at.replace(tzinfo=None)
        )

        change = await session.scalar(
            select(PluginMetadataChangeORM).where(
                PluginMetadataChangeORM.plugin_id == "plug-a"
            )
        )
        assert change is not None
        assert change.operator_id == "owner"
        assert change.changed_fields == {
            "display_name": "Renamed Plugin",
            "icon_url": "https://cdn.example.com/icons/plug-a.png",
            "categories": ["tool"],
            "tags": ["alpha", "beta"],
        }


async def test_patch_metadata_partial_only_records_supplied_fields() -> None:
    """A patch must only persist the fields the operator supplied."""

    async with session_scope() as session:
        await _ensure_author(session, "owner")
        await _create_plugin(session, "plug-a", owner_id="owner")

        service = InlineEditService(session)
        await service.patch_metadata("owner", "plug-a", {"tags": ["only-tags"]})

        change = await session.scalar(
            select(PluginMetadataChangeORM).where(
                PluginMetadataChangeORM.plugin_id == "plug-a"
            )
        )
        assert change is not None
        # display_name, icon_url and categories must NOT appear in the audit
        # row when they were not supplied.
        assert change.changed_fields == {"tags": ["only-tags"]}

        plugin = await session.get(PluginORM, "plug-a")
        assert plugin is not None
        assert plugin.tags == ["only-tags"]
        # Untouched fields keep their original values.
        assert plugin.display_name == "plug-a"


async def test_patch_metadata_does_not_write_review_record() -> None:
    """Per design, inline edits live in their own log, not ``review_records``."""

    from plugin_market_backend.orm import ReviewRecordORM

    async with session_scope() as session:
        await _ensure_author(session, "owner")
        await _create_plugin(session, "plug-a", owner_id="owner")

        before = int(
            (
                await session.scalar(
                    select(func.count())
                    .select_from(ReviewRecordORM)
                    .where(ReviewRecordORM.target_id == "plug-a")
                )
            )
            or 0
        )
        await InlineEditService(session).patch_metadata(
            "owner", "plug-a", {"display_name": "Fresh Name"}
        )
        after = int(
            (
                await session.scalar(
                    select(func.count())
                    .select_from(ReviewRecordORM)
                    .where(ReviewRecordORM.target_id == "plug-a")
                )
            )
            or 0
        )
        assert before == after


# ---------------------------------------------------------------------------
# Authorization (Property 5)
# ---------------------------------------------------------------------------


async def test_patch_metadata_allows_maintainer() -> None:
    """A registered maintainer should be permitted to edit metadata."""

    async with session_scope() as session:
        await _ensure_author(session, "owner")
        await _ensure_author(session, "co-maintainer")
        await _create_plugin(session, "plug-a", owner_id="owner")
        session.add(
            PluginMaintainerORM(plugin_id="plug-a", author_id="co-maintainer")
        )
        await session.flush()

        result = await InlineEditService(session).patch_metadata(
            "co-maintainer", "plug-a", {"display_name": "Maintained Name"}
        )
        assert result.display_name == "Maintained Name"


async def test_patch_metadata_allows_admin_non_owner() -> None:
    """An admin should be permitted even without owner / maintainer rights."""

    async with session_scope() as session:
        await _ensure_author(session, "owner")
        await _ensure_author(session, "site-admin", is_admin=True)
        await _create_plugin(session, "plug-a", owner_id="owner")

        result = await InlineEditService(session).patch_metadata(
            "site-admin", "plug-a", {"display_name": "Admin Renamed"}
        )
        assert result.display_name == "Admin Renamed"


async def test_patch_metadata_rejects_unrelated_author_with_metadata_forbidden() -> None:
    """Anyone outside owner / maintainer / admin must hit METADATA_FORBIDDEN."""

    async with session_scope() as session:
        await _ensure_author(session, "owner")
        await _ensure_author(session, "stranger")
        await _create_plugin(session, "plug-a", owner_id="owner")

        with pytest.raises(ApiError) as ctx:
            await InlineEditService(session).patch_metadata(
                "stranger", "plug-a", {"display_name": "Hijack"}
            )
        assert ctx.value.status_code == 403
        assert ctx.value.code == "METADATA_FORBIDDEN"


async def test_patch_metadata_returns_metadata_forbidden_for_unknown_plugin() -> None:
    """Unknown plugins must surface 403 instead of 404 (no enumeration)."""

    async with session_scope() as session:
        await _ensure_author(session, "viewer")
        with pytest.raises(ApiError) as ctx:
            await InlineEditService(session).patch_metadata(
                "viewer", "ghost-plugin", {"display_name": "x"}
            )
        assert ctx.value.status_code == 403
        assert ctx.value.code == "METADATA_FORBIDDEN"


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


async def test_patch_metadata_rejects_unknown_category() -> None:
    """Categories outside the live taxonomy must be rejected."""

    async with session_scope() as session:
        await _ensure_author(session, "owner")
        await _create_plugin(session, "plug-a", owner_id="owner", categories=["tool"])

        with pytest.raises(ApiError) as ctx:
            await InlineEditService(session).patch_metadata(
                "owner", "plug-a", {"categories": ["not-a-real-category"]}
            )
        assert ctx.value.status_code == 422
        assert ctx.value.code == "METADATA_INVALID_CATEGORY"


async def test_patch_metadata_accepts_known_category() -> None:
    """Categories present in any other plugin's taxonomy must be accepted."""

    async with session_scope() as session:
        await _ensure_author(session, "owner")
        await _create_plugin(session, "plug-a", owner_id="owner", categories=["tool"])
        await _create_plugin(session, "plug-b", owner_id="owner", categories=["chat"])

        result = await InlineEditService(session).patch_metadata(
            "owner", "plug-a", {"categories": ["chat"]}
        )
        assert result.categories == ["chat"]


async def test_patch_metadata_rejects_too_many_tags() -> None:
    """Eleven tags must trip METADATA_TAGS_TOO_MANY."""

    async with session_scope() as session:
        await _ensure_author(session, "owner")
        await _create_plugin(session, "plug-a", owner_id="owner")

        too_many = [f"tag-{index}" for index in range(11)]
        with pytest.raises(ApiError) as ctx:
            await InlineEditService(session).patch_metadata(
                "owner", "plug-a", {"tags": too_many}
            )
        assert ctx.value.status_code == 422
        assert ctx.value.code == "METADATA_TAGS_TOO_MANY"


async def test_patch_metadata_rejects_non_https_icon() -> None:
    """Icon URLs must use the https scheme."""

    async with session_scope() as session:
        await _ensure_author(session, "owner")
        await _create_plugin(session, "plug-a", owner_id="owner")

        with pytest.raises(ApiError) as ctx:
            await InlineEditService(session).patch_metadata(
                "owner",
                "plug-a",
                {"icon_url": "http://insecure.example.com/icon.png"},
            )
        assert ctx.value.status_code == 422
        assert ctx.value.code == "METADATA_INVALID_ICON"


async def test_patch_metadata_rejects_no_fields() -> None:
    """An empty patch body must be rejected with METADATA_NO_FIELDS."""

    async with session_scope() as session:
        await _ensure_author(session, "owner")
        await _create_plugin(session, "plug-a", owner_id="owner")

        with pytest.raises(ApiError) as ctx:
            await InlineEditService(session).patch_metadata("owner", "plug-a", {})
        assert ctx.value.status_code == 422
        assert ctx.value.code == "METADATA_NO_FIELDS"
        # No audit row should have been written.
        assert await _count_metadata_changes(session, "plug-a") == 0


async def test_patch_metadata_rejects_unknown_field() -> None:
    """Unsupported keys must fail closed."""

    async with session_scope() as session:
        await _ensure_author(session, "owner")
        await _create_plugin(session, "plug-a", owner_id="owner")

        with pytest.raises(ApiError) as ctx:
            await InlineEditService(session).patch_metadata(
                "owner", "plug-a", {"summary": "I am not editable inline"}
            )
        assert ctx.value.status_code == 422
        assert ctx.value.code == "METADATA_INVALID_FIELD"


async def test_patch_metadata_rejects_duplicate_categories() -> None:
    """Duplicate categories within the patch must be rejected up-front."""

    async with session_scope() as session:
        await _ensure_author(session, "owner")
        await _create_plugin(session, "plug-a", owner_id="owner", categories=["tool"])

        with pytest.raises(ApiError) as ctx:
            await InlineEditService(session).patch_metadata(
                "owner", "plug-a", {"categories": ["tool", "tool"]}
            )
        assert ctx.value.code == "METADATA_INVALID_CATEGORY"
