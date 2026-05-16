"""Integration tests for MarketService fan-out hooks (task 18)."""

from __future__ import annotations

import pytest

from plugin_market_backend.database import session_scope
from plugin_market_backend.enums import AuthorType, PluginStatus, ReviewAction, VersionStatus
from plugin_market_backend.errors import ApiError
from plugin_market_backend.orm import AuthorORM, PluginMaintainerORM, utc_now
from plugin_market_backend.schemas import PluginCreate, PluginVersionCreate
from plugin_market_backend.service import MarketService
from plugin_market_backend.services import InboxService


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


def _plugin_payload(plugin_id: str) -> PluginCreate:
    return PluginCreate(
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


def _version_payload(version: str = "1.0.0") -> PluginVersionCreate:
    return PluginVersionCreate(
        version=version,
        release_tag=f"v{version}",
        release_title=f"Release {version}",
        release_url=f"https://github.com/MoFox-Studio/sample/releases/tag/v{version}",
        asset_name=f"sample-{version}.mfp",
        asset_download_url=f"https://github.com/MoFox-Studio/sample/releases/download/v{version}/sample-{version}.mfp",
        checksum_sha256="a" * 64,
        file_size=1234,
        plugin_api_version="1.0",
        min_host_version="1.0.0",
    )


async def test_add_comment_mentions_then_delete_revokes_inbox_rows() -> None:
    async with session_scope() as session:
        await _ensure_author(session, "owner")
        await _ensure_author(session, "sender")
        await _ensure_author(session, "alpha", github_login="alpha")

        service = MarketService(session)
        await service.register_plugin(_plugin_payload("plug-a"), owner_id="owner")

        created = await service.add_comment("plug-a", "sender", "hello @alpha", None)
        messages, total = await InboxService(session).list_messages("alpha")
        assert total == 1
        assert messages[0].type == "mention"
        assert messages[0].status == "unread"

        await service.delete_comment("plug-a", created.id, "sender", False)
        revoked, total_after = await InboxService(session).list_messages("alpha")
        assert total_after == 1
        assert revoked[0].status == "revoked"


async def test_add_comment_rejects_reply_depth_over_one() -> None:
    async with session_scope() as session:
        await _ensure_author(session, "owner")
        await _ensure_author(session, "sender")
        await _ensure_author(session, "other")

        service = MarketService(session)
        await service.register_plugin(_plugin_payload("plug-a"), owner_id="owner")
        top = await service.add_comment("plug-a", "other", "top", None)
        reply = await service.add_comment("plug-a", "sender", "reply", top.id)

        with pytest.raises(ApiError) as ctx:
            await service.add_comment("plug-a", "other", "too deep", reply.id)
        assert ctx.value.status_code == 400
        assert ctx.value.code == "COMMENT_REPLY_DEPTH_EXCEEDED"


async def test_admin_governance_actions_fan_out_to_owner_and_maintainer() -> None:
    async with session_scope() as session:
        await _ensure_author(session, "owner")
        await _ensure_author(session, "maintainer")
        await _ensure_author(session, "admin", is_admin=True)

        service = MarketService(session)
        await service.register_plugin(_plugin_payload("plug-a"), owner_id="owner")
        session.add(PluginMaintainerORM(plugin_id="plug-a", author_id="maintainer"))
        await session.flush()
        await service.submit_version("plug-a", _version_payload(), "owner")

        await service.set_plugin_status(
            "plug-a",
            PluginStatus.BLOCKED,
            ReviewAction.BLOCK_PLUGIN,
            "admin",
            "risk",
        )
        await service.set_version_status(
            "plug-a",
            "1.0.0",
            VersionStatus.BLOCKED,
            ReviewAction.BLOCK_VERSION,
            "admin",
            "risk",
        )

        owner_messages, owner_total = await InboxService(session).list_messages("owner")
        maintainer_messages, maintainer_total = await InboxService(session).list_messages("maintainer")
        assert owner_total == 2
        assert maintainer_total == 2
        assert [item.type for item in owner_messages] == ["governance", "governance"]
        assert [item.type for item in maintainer_messages] == ["governance", "governance"]