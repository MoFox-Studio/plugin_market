"""Unit tests for ``CurationService`` (task 8).

These tests cover the task-8 slice only:

* the pure visibility predicate over ``enabled`` / schedule / audience,
* Property 7 signature-plugin ownership checks,
* create / update / disable / reorder happy paths,
* audit-trail fan-out for every curation write.
"""

from __future__ import annotations

from datetime import timedelta

import pytest
from sqlalchemy import select

from plugin_market_backend.database import session_scope
from plugin_market_backend.enums import ReviewAction
from plugin_market_backend.errors import ApiError
from plugin_market_backend.orm import (
    AuthorORM,
    AuthorType,
    PluginMaintainerORM,
    ReviewRecordORM,
    utc_now,
)
from plugin_market_backend.schemas import CurationEntryCreate, CurationEntryUpdate, PluginCreate
from plugin_market_backend.service import MarketService
from plugin_market_backend.services.curation_service import CurationService, is_visible


async def _ensure_author(
    session,
    author_id: str,
    *,
    github_login: str | None = None,
    is_admin: bool = False,
) -> None:
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
) -> None:
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


def _make_entry(
    *,
    enabled: bool = True,
    audience: str = "all",
    starts_at=None,
    ends_at=None,
):
    now = utc_now()
    from plugin_market_backend.orm import CurationEntryORM

    return CurationEntryORM(
        id=1,
        slot_type="featured_plugin",
        target_type="plugin",
        target_id="plug-a",
        signature_plugin_id=None,
        sort_order=0,
        enabled=enabled,
        starts_at=starts_at,
        ends_at=ends_at,
        audience=audience,
        display_meta={},
        created_by="admin",
        created_at=now,
        updated_at=now,
    )


class TestIsVisible:
    def test_enabled_entry_without_schedule_is_visible(self) -> None:
        assert is_visible(_make_entry(), None, utc_now()) is True

    def test_disabled_entry_is_not_visible(self) -> None:
        assert is_visible(_make_entry(enabled=False), None, utc_now()) is False

    def test_schedule_window_is_enforced(self) -> None:
        now = utc_now()
        future = now + timedelta(hours=1)
        past = now - timedelta(hours=1)
        assert is_visible(_make_entry(starts_at=future), None, now) is False
        assert is_visible(_make_entry(ends_at=past), None, now) is False
        assert is_visible(
            _make_entry(starts_at=past, ends_at=future),
            None,
            now,
        ) is True

    def test_audience_rules_are_applied(self) -> None:
        viewer = AuthorORM(
            author_id="viewer",
            github_user_id="gh-viewer",
            github_login="viewer",
            display_name="Viewer",
            author_type=AuthorType.USER,
            is_admin=False,
        )
        admin = AuthorORM(
            author_id="admin",
            github_user_id="gh-admin",
            github_login="admin",
            display_name="Admin",
            author_type=AuthorType.USER,
            is_admin=True,
        )
        assert is_visible(_make_entry(audience="logged_in"), None, utc_now()) is False
        assert is_visible(_make_entry(audience="logged_in"), viewer, utc_now()) is True
        assert is_visible(_make_entry(audience="admins"), viewer, utc_now()) is False
        assert is_visible(_make_entry(audience="admins"), admin, utc_now()) is True
        assert (
            is_visible(
                _make_entry(audience="authors_with_plugin"),
                viewer,
                utc_now(),
                viewer_has_plugin=False,
            )
            is False
        )
        assert (
            is_visible(
                _make_entry(audience="authors_with_plugin"),
                viewer,
                utc_now(),
                viewer_has_plugin=True,
            )
            is True
        )


async def test_create_validates_signature_plugin_is_owned_or_maintained() -> None:
    async with session_scope() as session:
        await _ensure_author(session, "admin", is_admin=True)
        await _ensure_author(session, "target-author")
        await _ensure_author(session, "other-owner")
        await _create_plugin(session, "plug-a", owner_id="other-owner")

        service = CurationService(session)
        with pytest.raises(ApiError) as ctx:
            await service.create(
                CurationEntryCreate(
                    slot_type="featured_author",
                    target_type="author",
                    target_id="target-author",
                    signature_plugin_id="plug-a",
                ),
                operator_id="admin",
            )
        assert ctx.value.status_code == 422
        assert ctx.value.code == "CURATION_SIGNATURE_NOT_OWNED"


async def test_create_allows_signature_plugin_for_maintainer() -> None:
    async with session_scope() as session:
        await _ensure_author(session, "admin", is_admin=True)
        await _ensure_author(session, "target-author")
        await _ensure_author(session, "owner")
        await _create_plugin(session, "plug-a", owner_id="owner")
        session.add(PluginMaintainerORM(plugin_id="plug-a", author_id="target-author"))
        await session.flush()

        created = await CurationService(session).create(
            CurationEntryCreate(
                slot_type="featured_author",
                target_type="author",
                target_id="target-author",
                signature_plugin_id="plug-a",
                audience="logged_in",
            ),
            operator_id="admin",
        )
        assert created.signature_plugin_id == "plug-a"
        assert created.target_id == "target-author"


async def test_create_update_disable_and_reorder_write_audit_rows() -> None:
    async with session_scope() as session:
        await _ensure_author(session, "admin", is_admin=True)
        await _ensure_author(session, "author-a")
        await _create_plugin(session, "plug-a", owner_id="author-a")
        await _create_plugin(session, "plug-b", owner_id="author-a")
        await _create_plugin(session, "plug-c", owner_id="author-a")

        service = CurationService(session)
        first = await service.create(
            CurationEntryCreate(
                slot_type="featured_plugin",
                target_type="plugin",
                target_id="plug-a",
                sort_order=10,
            ),
            operator_id="admin",
        )
        second = await service.create(
            CurationEntryCreate(
                slot_type="featured_plugin",
                target_type="plugin",
                target_id="plug-b",
                sort_order=20,
            ),
            operator_id="admin",
        )
        third = await service.create(
            CurationEntryCreate(
                slot_type="featured_plugin",
                target_type="plugin",
                target_id="plug-c",
                sort_order=30,
            ),
            operator_id="admin",
        )

        updated = await service.update(
            first.id,
            CurationEntryUpdate(audience="admins", display_meta={"headline": "Top pick"}),
            operator_id="admin",
        )
        assert updated.audience == "admins"
        assert updated.display_meta == {"headline": "Top pick"}

        disabled = await service.disable(second.id, operator_id="admin")
        assert disabled.enabled is False

        reordered = await service.reorder([third.id, first.id, second.id], operator_id="admin")
        assert [item.id for item in reordered] == [third.id, first.id, second.id]
        assert [item.sort_order for item in reordered] == [0, 1, 2]

        listed = await service.list_entries()
        assert [item.id for item in listed] == [third.id, first.id, second.id]

        actions = list(
            (
                await session.scalars(
                    select(ReviewRecordORM.action)
                    .where(ReviewRecordORM.target_type == "curation")
                    .order_by(ReviewRecordORM.id.asc())
                )
            ).all()
        )
        assert actions == [
            ReviewAction.CREATE_CURATION,
            ReviewAction.CREATE_CURATION,
            ReviewAction.CREATE_CURATION,
            ReviewAction.UPDATE_CURATION,
            ReviewAction.DISABLE_CURATION,
            ReviewAction.UPDATE_CURATION,
            ReviewAction.UPDATE_CURATION,
            ReviewAction.UPDATE_CURATION,
        ]


async def test_reorder_rejects_missing_ids() -> None:
    async with session_scope() as session:
        await _ensure_author(session, "admin", is_admin=True)
        await _ensure_author(session, "author-a")
        await _create_plugin(session, "plug-a", owner_id="author-a")

        created = await CurationService(session).create(
            CurationEntryCreate(
                slot_type="featured_plugin",
                target_type="plugin",
                target_id="plug-a",
            ),
            operator_id="admin",
        )

        with pytest.raises(ApiError) as ctx:
            await CurationService(session).reorder([created.id, created.id + 999], operator_id="admin")
        assert ctx.value.status_code == 404
        assert ctx.value.code == "CURATION_NOT_FOUND"