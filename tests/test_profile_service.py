"""Unit tests for ``ProfileService`` (task 4).

These tests exercise the bio / background / pin surface of
:class:`plugin_market_backend.services.profile_service.ProfileService`
without going through the HTTP layer, so each behavior is isolated:

* profile creation and update happy paths,
* https-only background validation,
* bio length cap,
* pin add/list/update/remove happy paths,
* pin reason length cap,
* ownership / maintainer / non-owner authorization for ``add_pin``,
* duplicate pin rejection,
* the 6-pin upper bound (Property 6),
* render order is ``pinned_at`` descending.
"""

from __future__ import annotations

import pytest

from plugin_market_backend.database import session_scope
from plugin_market_backend.errors import ApiError
from plugin_market_backend.orm import AuthorORM, AuthorType, PluginMaintainerORM, utc_now
from plugin_market_backend.schemas import PluginCreate
from plugin_market_backend.service import MarketService
from plugin_market_backend.services import ProfileService


# ---------------------------------------------------------------------------
# Setup helpers
# ---------------------------------------------------------------------------


async def _ensure_author(session, author_id: str, github_login: str | None = None) -> None:
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
            is_admin=False,
        )
    )
    await session.flush()


def _plugin_payload(plugin_id: str, *, display_name: str | None = None) -> PluginCreate:
    """Return a minimal PluginCreate payload for fixture plugins."""

    return PluginCreate(
        plugin_id=plugin_id,
        display_name=display_name or plugin_id,
        summary=f"summary for {plugin_id}",
        description=f"description for {plugin_id}",
        repository_url=f"https://github.com/MoFox-Studio/{plugin_id}",
        license="MIT",
        categories=["tool"],
        tags=["sample"],
        maintainers=[],
    )


async def _create_plugin(session, plugin_id: str, owner_id: str) -> None:
    """Register a plugin owned by ``owner_id`` using the live MarketService."""

    service = MarketService(session)
    await service.register_plugin(_plugin_payload(plugin_id), owner_id=owner_id)


# ---------------------------------------------------------------------------
# Profile (bio / background)
# ---------------------------------------------------------------------------


async def test_get_profile_returns_default_when_missing() -> None:
    """Authors without a profile row should still return a default schema."""

    async with session_scope() as session:
        await _ensure_author(session, "author-a")
        service = ProfileService(session)
        profile = await service.get_profile("author-a")
        assert profile.author_id == "author-a"
        assert profile.bio == ""
        assert profile.background_image_url is None
        assert profile.background_image_kind == "url"


async def test_update_profile_creates_then_updates_row() -> None:
    """The first update creates the row; the second update mutates it."""

    async with session_scope() as session:
        await _ensure_author(session, "author-a")
        service = ProfileService(session)

        first = await service.update_profile(
            "author-a",
            bio="hello world",
            background_image_url="https://cdn.example.com/bg1.png",
        )
        assert first.bio == "hello world"
        assert first.background_image_url == "https://cdn.example.com/bg1.png"
        assert first.updated_at is not None

        second = await service.update_profile(
            "author-a",
            bio="updated",
            background_image_url="https://cdn.example.com/bg2.png",
        )
        assert second.bio == "updated"
        assert second.background_image_url == "https://cdn.example.com/bg2.png"


async def test_update_profile_partial_update_keeps_other_fields() -> None:
    """``None`` arguments should not overwrite the existing field."""

    async with session_scope() as session:
        await _ensure_author(session, "author-a")
        service = ProfileService(session)
        await service.update_profile(
            "author-a",
            bio="hello",
            background_image_url="https://cdn.example.com/bg.png",
        )

        only_bio = await service.update_profile("author-a", bio="hello again")
        assert only_bio.bio == "hello again"
        assert only_bio.background_image_url == "https://cdn.example.com/bg.png"

        only_bg = await service.update_profile(
            "author-a",
            background_image_url="https://cdn.example.com/bg-new.png",
        )
        assert only_bg.bio == "hello again"
        assert only_bg.background_image_url == "https://cdn.example.com/bg-new.png"


async def test_update_profile_clears_background_when_empty_string() -> None:
    """An empty-string background URL should clear the field."""

    async with session_scope() as session:
        await _ensure_author(session, "author-a")
        service = ProfileService(session)
        await service.update_profile(
            "author-a", background_image_url="https://cdn.example.com/bg.png"
        )
        cleared = await service.update_profile("author-a", background_image_url="")
        assert cleared.background_image_url is None


async def test_update_profile_rejects_non_https_background() -> None:
    """Background URL must use the https scheme."""

    async with session_scope() as session:
        await _ensure_author(session, "author-a")
        service = ProfileService(session)
        with pytest.raises(ApiError) as ctx:
            await service.update_profile(
                "author-a", background_image_url="http://insecure.example.com/bg.png"
            )
        assert ctx.value.status_code == 422
        assert ctx.value.code == "PROFILE_BACKGROUND_INVALID_URL"


async def test_update_profile_rejects_bio_over_limit() -> None:
    """Bio over 2000 chars must be rejected."""

    async with session_scope() as session:
        await _ensure_author(session, "author-a")
        service = ProfileService(session)
        with pytest.raises(ApiError) as ctx:
            await service.update_profile("author-a", bio="x" * 2001)
        assert ctx.value.status_code == 422
        assert ctx.value.code == "PROFILE_BIO_TOO_LONG"


# ---------------------------------------------------------------------------
# Pinned plugins
# ---------------------------------------------------------------------------


async def test_add_pin_happy_path_and_list_returns_it() -> None:
    """Adding a pin should make it appear in the listing with the given reason."""

    async with session_scope() as session:
        await _ensure_author(session, "author-a")
        await _create_plugin(session, "plug-a", owner_id="author-a")

        service = ProfileService(session)
        pin = await service.add_pin("author-a", "plug-a", reason="my favorite")
        assert pin.plugin_id == "plug-a"
        assert pin.pinned_reason == "my favorite"
        assert pin.plugin is not None
        assert pin.plugin.plugin_id == "plug-a"

        listed = await service.list_pins("author-a")
        assert [item.plugin_id for item in listed] == ["plug-a"]
        assert listed[0].pinned_reason == "my favorite"


async def test_list_pins_orders_by_pinned_at_descending() -> None:
    """``list_pins`` must render the most recently pinned plugin first."""

    async with session_scope() as session:
        await _ensure_author(session, "author-a")
        for plugin_id in ("plug-a", "plug-b", "plug-c"):
            await _create_plugin(session, plugin_id, owner_id="author-a")

        service = ProfileService(session)
        await service.add_pin("author-a", "plug-a")
        await service.add_pin("author-a", "plug-b")
        await service.add_pin("author-a", "plug-c")

        listed = await service.list_pins("author-a")
        # Most recently pinned (plug-c) should appear first.
        assert [item.plugin_id for item in listed] == ["plug-c", "plug-b", "plug-a"]


async def test_add_pin_rejects_non_owner_with_pin_plugin_not_owned() -> None:
    """A viewer who is not owner / maintainer must not be allowed to pin."""

    async with session_scope() as session:
        await _ensure_author(session, "owner")
        await _ensure_author(session, "stranger")
        await _create_plugin(session, "plug-a", owner_id="owner")

        service = ProfileService(session)
        with pytest.raises(ApiError) as ctx:
            await service.add_pin("stranger", "plug-a")
        assert ctx.value.status_code == 403
        assert ctx.value.code == "PIN_PLUGIN_NOT_OWNED"


async def test_add_pin_allows_maintainer() -> None:
    """A registered maintainer should be able to pin a plugin they help maintain."""

    async with session_scope() as session:
        await _ensure_author(session, "owner")
        await _ensure_author(session, "co-maintainer")
        await _create_plugin(session, "plug-a", owner_id="owner")
        session.add(PluginMaintainerORM(plugin_id="plug-a", author_id="co-maintainer"))
        await session.flush()

        service = ProfileService(session)
        pin = await service.add_pin("co-maintainer", "plug-a", reason="co-maintaining")
        assert pin.plugin_id == "plug-a"
        listed = await service.list_pins("co-maintainer")
        assert [item.plugin_id for item in listed] == ["plug-a"]


async def test_add_pin_rejects_unknown_plugin() -> None:
    """Pinning a plugin that does not exist must surface ``PIN_PLUGIN_NOT_FOUND``."""

    async with session_scope() as session:
        await _ensure_author(session, "author-a")
        service = ProfileService(session)
        with pytest.raises(ApiError) as ctx:
            await service.add_pin("author-a", "ghost-plugin")
        assert ctx.value.status_code == 404
        assert ctx.value.code == "PIN_PLUGIN_NOT_FOUND"


async def test_add_pin_rejects_duplicate_pin() -> None:
    """Pinning the same plugin twice should produce ``PIN_ALREADY_EXISTS``."""

    async with session_scope() as session:
        await _ensure_author(session, "author-a")
        await _create_plugin(session, "plug-a", owner_id="author-a")
        service = ProfileService(session)
        await service.add_pin("author-a", "plug-a")
        with pytest.raises(ApiError) as ctx:
            await service.add_pin("author-a", "plug-a")
        assert ctx.value.status_code == 409
        assert ctx.value.code == "PIN_ALREADY_EXISTS"


async def test_add_pin_enforces_six_pin_limit() -> None:
    """The seventh active pin must be rejected with ``PIN_LIMIT_EXCEEDED`` (Property 6)."""

    async with session_scope() as session:
        await _ensure_author(session, "author-a")
        for index in range(7):
            await _create_plugin(session, f"plug-{index}", owner_id="author-a")

        service = ProfileService(session)
        for index in range(6):
            await service.add_pin("author-a", f"plug-{index}")

        with pytest.raises(ApiError) as ctx:
            await service.add_pin("author-a", "plug-6")
        assert ctx.value.status_code == 409
        assert ctx.value.code == "PIN_LIMIT_EXCEEDED"


async def test_add_pin_rejects_long_reason() -> None:
    """Pin reason over 200 chars must be rejected before any DB mutation."""

    async with session_scope() as session:
        await _ensure_author(session, "author-a")
        await _create_plugin(session, "plug-a", owner_id="author-a")
        service = ProfileService(session)
        with pytest.raises(ApiError) as ctx:
            await service.add_pin("author-a", "plug-a", reason="x" * 201)
        assert ctx.value.code == "PIN_REASON_TOO_LONG"
        # The pin must not have been created.
        assert await service.list_pins("author-a") == []


async def test_update_pin_reason_does_not_change_pinned_at() -> None:
    """Updating the reason must not bump ``pinned_at`` (Requirement 4.7)."""

    async with session_scope() as session:
        await _ensure_author(session, "author-a")
        await _create_plugin(session, "plug-a", owner_id="author-a")
        service = ProfileService(session)
        added = await service.add_pin("author-a", "plug-a", reason="initial")
        original_pinned_at = added.pinned_at

        updated = await service.update_pin_reason("author-a", "plug-a", "updated reason")
        assert updated.pinned_reason == "updated reason"
        # ``pinned_at`` is a tz-aware UTC datetime in memory but SQLite/aiosqlite
        # round-trips it back without tzinfo, so we compare the wall-clock value
        # to confirm the column was not rewritten.
        assert updated.pinned_at.replace(tzinfo=None) == original_pinned_at.replace(tzinfo=None)


async def test_update_pin_reason_returns_404_when_pin_missing() -> None:
    """Updating a non-existent pin must surface ``PIN_NOT_FOUND``."""

    async with session_scope() as session:
        await _ensure_author(session, "author-a")
        await _create_plugin(session, "plug-a", owner_id="author-a")
        service = ProfileService(session)
        with pytest.raises(ApiError) as ctx:
            await service.update_pin_reason("author-a", "plug-a", "new")
        assert ctx.value.status_code == 404
        assert ctx.value.code == "PIN_NOT_FOUND"


async def test_remove_pin_drops_row_and_frees_slot() -> None:
    """After removing a pin, a previously rejected one can be added again."""

    async with session_scope() as session:
        await _ensure_author(session, "author-a")
        for index in range(7):
            await _create_plugin(session, f"plug-{index}", owner_id="author-a")
        service = ProfileService(session)
        for index in range(6):
            await service.add_pin("author-a", f"plug-{index}")

        # Adding plug-6 currently fails.
        with pytest.raises(ApiError):
            await service.add_pin("author-a", "plug-6")

        # Free up a slot and retry.
        await service.remove_pin("author-a", "plug-0")
        added = await service.add_pin("author-a", "plug-6")
        assert added.plugin_id == "plug-6"

        listed = await service.list_pins("author-a")
        assert {item.plugin_id for item in listed} == {
            "plug-1", "plug-2", "plug-3", "plug-4", "plug-5", "plug-6"
        }


async def test_remove_pin_returns_404_when_pin_missing() -> None:
    """Removing a non-existent pin must surface ``PIN_NOT_FOUND``."""

    async with session_scope() as session:
        await _ensure_author(session, "author-a")
        service = ProfileService(session)
        with pytest.raises(ApiError) as ctx:
            await service.remove_pin("author-a", "ghost")
        assert ctx.value.status_code == 404
        assert ctx.value.code == "PIN_NOT_FOUND"
