"""Unit tests for ``BulkOpsService`` (task 9)."""

from __future__ import annotations

import pytest
from sqlalchemy import select

from plugin_market_backend.database import session_scope
from plugin_market_backend.enums import PluginStatus, ReviewAction, TrustLevel
from plugin_market_backend.errors import ApiError
from plugin_market_backend.orm import AuthorORM, AuthorType, PluginORM, ReviewRecordORM, utc_now
from plugin_market_backend.schemas import PluginCreate
from plugin_market_backend.service import MarketService
from plugin_market_backend.services.bulk_ops_service import BulkOpsService


async def _ensure_author(session, author_id: str, *, is_admin: bool = False) -> None:
    if await session.get(AuthorORM, author_id) is not None:
        return
    session.add(
        AuthorORM(
            author_id=author_id,
            github_user_id=f"id-{author_id}",
            github_login=author_id,
            display_name=author_id,
            author_type=AuthorType.USER,
            verified_at=utc_now(),
            is_admin=is_admin,
        )
    )
    await session.flush()


async def _create_plugin(session, plugin_id: str, owner_id: str) -> None:
    payload = PluginCreate(
        plugin_id=plugin_id,
        display_name=plugin_id,
        summary=f"summary for {plugin_id}",
        description=f"description for {plugin_id}",
        repository_url=f"https://github.com/MoFox-Studio/{plugin_id}",
        license="MIT",
        categories=["tool"],
        tags=["sample"],
        maintainers=[],
    )
    await MarketService(session).register_plugin(payload, owner_id=owner_id)


async def test_bulk_apply_publish_writes_bulk_audit() -> None:
    async with session_scope() as session:
        await _ensure_author(session, "admin", is_admin=True)
        await _ensure_author(session, "owner")
        await _create_plugin(session, "plug-a", owner_id="owner")

        result = await BulkOpsService(session).bulk_apply("admin", ["plug-a"], "publish")
        assert len(result.results) == 1
        assert result.results[0].ok is True
        assert result.results[0].after is not None
        assert result.results[0].after.status == PluginStatus.PUBLISHED

        latest = await session.scalar(
            select(ReviewRecordORM)
            .where(ReviewRecordORM.target_id == "plug-a")
            .order_by(ReviewRecordORM.id.desc())
            .limit(1)
        )
        assert latest is not None
        assert latest.action == ReviewAction.BULK_PUBLISH


async def test_bulk_apply_set_trust_level_requires_param() -> None:
    async with session_scope() as session:
        await _ensure_author(session, "admin", is_admin=True)
        with pytest.raises(ApiError) as ctx:
            await BulkOpsService(session).bulk_apply("admin", ["plug-a"], "set_trust_level")
        assert ctx.value.status_code == 422
        assert ctx.value.code == "BULK_MISSING_TRUST_LEVEL"


async def test_bulk_apply_set_trust_level_updates_plugin() -> None:
    async with session_scope() as session:
        await _ensure_author(session, "admin", is_admin=True)
        await _ensure_author(session, "owner")
        await _create_plugin(session, "plug-a", owner_id="owner")

        result = await BulkOpsService(session).bulk_apply(
            "admin",
            ["plug-a"],
            "set_trust_level",
            {"trust_level": "official", "reason": "internal"},
        )
        assert result.results[0].ok is True
        assert result.results[0].after is not None
        assert result.results[0].after.trust_level == TrustLevel.OFFICIAL

        latest = await session.scalar(
            select(ReviewRecordORM)
            .where(ReviewRecordORM.target_id == "plug-a")
            .order_by(ReviewRecordORM.id.desc())
            .limit(1)
        )
        assert latest is not None
        assert latest.action == ReviewAction.BULK_SET_TRUST_LEVEL


async def test_bulk_apply_delete_requires_reason_and_deletes_plugin() -> None:
    async with session_scope() as session:
        await _ensure_author(session, "admin", is_admin=True)
        await _ensure_author(session, "owner")
        await _create_plugin(session, "plug-a", owner_id="owner")

        with pytest.raises(ApiError) as ctx:
            await BulkOpsService(session).bulk_apply("admin", ["plug-a"], "delete")
        assert ctx.value.code == "BULK_MISSING_REASON"

        result = await BulkOpsService(session).bulk_apply(
            "admin",
            ["plug-a"],
            "delete",
            {"reason": "cleanup"},
        )
        assert result.results[0].ok is True
        assert result.results[0].after is None
        assert await session.get(PluginORM, "plug-a") is None

        latest = await session.scalar(
            select(ReviewRecordORM)
            .where(ReviewRecordORM.target_id == "plug-a")
            .order_by(ReviewRecordORM.id.desc())
            .limit(1)
        )
        assert latest is not None
        assert latest.action == ReviewAction.BULK_DELETE


async def test_bulk_apply_partial_failure_keeps_successes() -> None:
    async with session_scope() as session:
        await _ensure_author(session, "admin", is_admin=True)
        await _ensure_author(session, "owner")
        await _create_plugin(session, "plug-a", owner_id="owner")

        result = await BulkOpsService(session).bulk_apply(
            "admin",
            ["plug-a", "missing-plugin"],
            "block",
            {"reason": "risk"},
        )
        assert [item.ok for item in result.results] == [True, False]
        assert result.results[1].error is not None
        assert result.results[1].error.code == "PLUGIN_NOT_FOUND"

        plugin = await session.get(PluginORM, "plug-a")
        assert plugin is not None
        assert plugin.status == PluginStatus.BLOCKED


async def test_bulk_apply_rejects_more_than_hundred_targets() -> None:
    async with session_scope() as session:
        await _ensure_author(session, "admin", is_admin=True)
        plugin_ids = [f"plug-{index}" for index in range(101)]
        with pytest.raises(ApiError) as ctx:
            await BulkOpsService(session).bulk_apply("admin", plugin_ids, "publish")
        assert ctx.value.status_code == 422
        assert ctx.value.code == "BULK_TOO_MANY_TARGETS"