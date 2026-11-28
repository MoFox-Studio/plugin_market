"""ProfileService 的单元测试（任务 4）。

绕过 HTTP 层，独立验证 ProfileService 的简介、背景和置顶功能：

* 成功创建与更新资料。
* 背景图片仅允许 HTTPS。
* 简介长度上限。
* 成功添加、列出、更新和移除置顶。
* 置顶理由长度上限。
* add_pin 对所有者、维护者及非所有者的权限验证。
* 拒绝重复置顶。
* 最多置顶 6 个插件（属性 6）。
* 按 pinned_at 降序展示。
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
# 初始化辅助函数
# ---------------------------------------------------------------------------


async def _ensure_author(session, author_id: str, github_login: str | None = None) -> None:
    """在作者不存在时创建记录。

    Args:
        session: 数据库会话。
        author_id: 作者标识。
        github_login: GitHub 登录名；未提供时使用作者标识。
    """
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
    """返回测试插件所需的最小 PluginCreate 请求体。

    Args:
        plugin_id: 插件标识。
        display_name: 展示名称；未提供时使用插件标识。

    Returns:
        用于创建插件的请求模型。
    """
    return PluginCreate(
        plugin_id=plugin_id,
        display_name=display_name or plugin_id,
        summary=f"{plugin_id} 的摘要",
        description=f"{plugin_id} 的说明",
        repository_url=f"https://github.com/MoFox-Studio/{plugin_id}",
        license="MIT",
        categories=["tool"],
        tags=["sample"],
        maintainers=[],
    )


async def _create_plugin(session, plugin_id: str, owner_id: str) -> None:
    """使用实际的 MarketService 注册指定所有者的插件。

    Args:
        session: 数据库会话。
        plugin_id: 插件标识。
        owner_id: 所有者标识。
    """
    service = MarketService(session)
    await service.register_plugin(_plugin_payload(plugin_id), owner_id=owner_id)


# ---------------------------------------------------------------------------
# 资料（简介与背景）
# ---------------------------------------------------------------------------


async def test_get_profile_returns_default_when_missing() -> None:
    """作者没有资料记录时，仍应返回默认资料模型。"""
    async with session_scope() as session:
        await _ensure_author(session, "author-a")
        service = ProfileService(session)
        profile = await service.get_profile("author-a")
        assert profile.author_id == "author-a"
        assert profile.bio == ""
        assert profile.background_image_url is None
        assert profile.background_image_kind == "url"


async def test_update_profile_creates_then_updates_row() -> None:
    """首次更新应创建记录，第二次更新应修改已有记录。"""
    async with session_scope() as session:
        await _ensure_author(session, "author-a")
        service = ProfileService(session)

        first = await service.update_profile(
            "author-a",
            bio="你好，世界",
            background_image_url="https://cdn.example.com/bg1.png",
        )
        assert first.bio == "你好，世界"
        assert first.background_image_url == "https://cdn.example.com/bg1.png"
        assert first.updated_at is not None

        second = await service.update_profile(
            "author-a",
            bio="已更新",
            background_image_url="https://cdn.example.com/bg2.png",
        )
        assert second.bio == "已更新"
        assert second.background_image_url == "https://cdn.example.com/bg2.png"


async def test_update_profile_partial_update_keeps_other_fields() -> None:
    """值为 None 的参数不应覆盖已有字段。"""
    async with session_scope() as session:
        await _ensure_author(session, "author-a")
        service = ProfileService(session)
        await service.update_profile(
            "author-a",
            bio="你好",
            background_image_url="https://cdn.example.com/bg.png",
        )

        only_bio = await service.update_profile("author-a", bio="再次问好")
        assert only_bio.bio == "再次问好"
        assert only_bio.background_image_url == "https://cdn.example.com/bg.png"

        only_bg = await service.update_profile(
            "author-a",
            background_image_url="https://cdn.example.com/bg-new.png",
        )
        assert only_bg.bio == "再次问好"
        assert only_bg.background_image_url == "https://cdn.example.com/bg-new.png"


async def test_update_profile_clears_background_when_empty_string() -> None:
    """背景 URL 为空字符串时，应清空该字段。"""
    async with session_scope() as session:
        await _ensure_author(session, "author-a")
        service = ProfileService(session)
        await service.update_profile(
            "author-a", background_image_url="https://cdn.example.com/bg.png"
        )
        cleared = await service.update_profile("author-a", background_image_url="")
        assert cleared.background_image_url is None


async def test_update_profile_rejects_non_https_background() -> None:
    """背景 URL 必须使用 HTTPS 协议。"""
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
    """简介超过 2000 个字符时应被拒绝。"""
    async with session_scope() as session:
        await _ensure_author(session, "author-a")
        service = ProfileService(session)
        with pytest.raises(ApiError) as ctx:
            await service.update_profile("author-a", bio="x" * 2001)
        assert ctx.value.status_code == 422
        assert ctx.value.code == "PROFILE_BIO_TOO_LONG"


# ---------------------------------------------------------------------------
# 置顶插件
# ---------------------------------------------------------------------------


async def test_add_pin_happy_path_and_list_returns_it() -> None:
    """添加置顶后，列表应包含该插件及指定理由。"""
    async with session_scope() as session:
        await _ensure_author(session, "author-a")
        await _create_plugin(session, "plug-a", owner_id="author-a")

        service = ProfileService(session)
        pin = await service.add_pin("author-a", "plug-a", reason="我的最爱")
        assert pin.plugin_id == "plug-a"
        assert pin.pinned_reason == "我的最爱"
        assert pin.plugin is not None
        assert pin.plugin.plugin_id == "plug-a"

        listed = await service.list_pins("author-a")
        assert [item.plugin_id for item in listed] == ["plug-a"]
        assert listed[0].pinned_reason == "我的最爱"


async def test_list_pins_orders_by_pinned_at_descending() -> None:
    """list_pins 应优先展示最近置顶的插件。"""
    async with session_scope() as session:
        await _ensure_author(session, "author-a")
        for plugin_id in ("plug-a", "plug-b", "plug-c"):
            await _create_plugin(session, plugin_id, owner_id="author-a")

        service = ProfileService(session)
        await service.add_pin("author-a", "plug-a")
        await service.add_pin("author-a", "plug-b")
        await service.add_pin("author-a", "plug-c")

        listed = await service.list_pins("author-a")
        # 最近置顶的 plug-c 应排在最前面。
        assert [item.plugin_id for item in listed] == ["plug-c", "plug-b", "plug-a"]


async def test_add_pin_rejects_non_owner_with_pin_plugin_not_owned() -> None:
    """不是所有者或维护者的查看者不应获准置顶插件。"""
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
    """已登记的维护者应能置顶自己参与维护的插件。"""
    async with session_scope() as session:
        await _ensure_author(session, "owner")
        await _ensure_author(session, "co-maintainer")
        await _create_plugin(session, "plug-a", owner_id="owner")
        session.add(PluginMaintainerORM(plugin_id="plug-a", author_id="co-maintainer"))
        await session.flush()

        service = ProfileService(session)
        pin = await service.add_pin("co-maintainer", "plug-a", reason="共同维护")
        assert pin.plugin_id == "plug-a"
        listed = await service.list_pins("co-maintainer")
        assert [item.plugin_id for item in listed] == ["plug-a"]


async def test_add_pin_rejects_unknown_plugin() -> None:
    """置顶不存在的插件时，应返回 PIN_PLUGIN_NOT_FOUND。"""
    async with session_scope() as session:
        await _ensure_author(session, "author-a")
        service = ProfileService(session)
        with pytest.raises(ApiError) as ctx:
            await service.add_pin("author-a", "ghost-plugin")
        assert ctx.value.status_code == 404
        assert ctx.value.code == "PIN_PLUGIN_NOT_FOUND"


async def test_add_pin_rejects_duplicate_pin() -> None:
    """重复置顶同一插件时，应返回 PIN_ALREADY_EXISTS。"""
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
    """第七个有效置顶应被拒绝，并返回 PIN_LIMIT_EXCEEDED（属性 6）。"""
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
    """置顶理由超过 200 个字符时，应在修改数据库前拒绝。"""
    async with session_scope() as session:
        await _ensure_author(session, "author-a")
        await _create_plugin(session, "plug-a", owner_id="author-a")
        service = ProfileService(session)
        with pytest.raises(ApiError) as ctx:
            await service.add_pin("author-a", "plug-a", reason="x" * 201)
        assert ctx.value.code == "PIN_REASON_TOO_LONG"
        # 不应创建置顶记录。
        assert await service.list_pins("author-a") == []


async def test_update_pin_reason_does_not_change_pinned_at() -> None:
    """更新理由不应改变 pinned_at（需求 4.7）。"""
    async with session_scope() as session:
        await _ensure_author(session, "author-a")
        await _create_plugin(session, "plug-a", owner_id="author-a")
        service = ProfileService(session)
        added = await service.add_pin("author-a", "plug-a", reason="初始理由")
        original_pinned_at = added.pinned_at

        updated = await service.update_pin_reason("author-a", "plug-a", "更新后的理由")
        assert updated.pinned_reason == "更新后的理由"
        # pinned_at 在内存中是带时区的 UTC 日期时间，但 SQLite/aiosqlite 读回时
        # 不保留 tzinfo，因此比较不带时区的时间值，以确认该列未被改写。
        assert updated.pinned_at.replace(tzinfo=None) == original_pinned_at.replace(tzinfo=None)


async def test_update_pin_reason_returns_404_when_pin_missing() -> None:
    """更新不存在的置顶时，应返回 PIN_NOT_FOUND。"""
    async with session_scope() as session:
        await _ensure_author(session, "author-a")
        await _create_plugin(session, "plug-a", owner_id="author-a")
        service = ProfileService(session)
        with pytest.raises(ApiError) as ctx:
            await service.update_pin_reason("author-a", "plug-a", "新理由")
        assert ctx.value.status_code == 404
        assert ctx.value.code == "PIN_NOT_FOUND"


async def test_remove_pin_drops_row_and_frees_slot() -> None:
    """移除一个置顶后，之前被拒绝的插件应能再次添加。"""
    async with session_scope() as session:
        await _ensure_author(session, "author-a")
        for index in range(7):
            await _create_plugin(session, f"plug-{index}", owner_id="author-a")
        service = ProfileService(session)
        for index in range(6):
            await service.add_pin("author-a", f"plug-{index}")

        # 此时添加 plug-6 应失败。
        with pytest.raises(ApiError):
            await service.add_pin("author-a", "plug-6")

        # 释放一个置顶名额后重试。
        await service.remove_pin("author-a", "plug-0")
        added = await service.add_pin("author-a", "plug-6")
        assert added.plugin_id == "plug-6"

        listed = await service.list_pins("author-a")
        assert {item.plugin_id for item in listed} == {
            "plug-1", "plug-2", "plug-3", "plug-4", "plug-5", "plug-6"
        }


async def test_remove_pin_returns_404_when_pin_missing() -> None:
    """移除不存在的置顶时，应返回 PIN_NOT_FOUND。"""
    async with session_scope() as session:
        await _ensure_author(session, "author-a")
        service = ProfileService(session)
        with pytest.raises(ApiError) as ctx:
            await service.remove_pin("author-a", "ghost")
        assert ctx.value.status_code == 404
        assert ctx.value.code == "PIN_NOT_FOUND"
