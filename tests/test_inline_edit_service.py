"""InlineEditService 的单元测试（任务 5）。

不经过 FastAPI，直接验证 InlineEditService 的元数据行内编辑功能，覆盖：

* 成功更新所有可编辑字段，并生成对应审计记录。
* 成功更新后刷新 updated_at。
* 所有者、维护者及管理员的权限验证（属性 5）。
* 根据当前分类体系校验分类。
* 标签数量上限（METADATA_TAGS_TOO_MANY）。
* icon_url 仅允许 HTTPS（METADATA_INVALID_ICON）。
* 拒绝空字段和未知字段。

复用 conftest.py 中的共享夹具，在每个测试前创建内存 SQLite 数据库并调用
seed_database。
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
# 初始化辅助函数
# ---------------------------------------------------------------------------


async def _ensure_author(
    session,
    author_id: str,
    *,
    github_login: str | None = None,
    is_admin: bool = False,
) -> None:
    """在作者不存在时创建记录。

    Args:
        session: 数据库会话。
        author_id: 作者标识。
        github_login: GitHub 登录名；未提供时使用作者标识。
        is_admin: 是否授予管理员身份。
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
    """使用实际的 MarketService 注册指定所有者的插件。

    Args:
        session: 数据库会话。
        plugin_id: 插件标识。
        owner_id: 所有者标识。
        categories: 插件分类；未提供时使用默认分类。
        tags: 插件标签；未提供时使用默认标签。
    """
    payload = PluginCreate(
        plugin_id=plugin_id,
        display_name=plugin_id,
        summary=f"{plugin_id} 的摘要",
        description=f"{plugin_id} 的说明",
        repository_url=f"https://github.com/MoFox-Studio/{plugin_id}",
        license="MIT",
        categories=categories if categories is not None else ["tool"],
        tags=tags if tags is not None else ["sample"],
        maintainers=[],
    )
    await MarketService(session).register_plugin(payload, owner_id=owner_id)


async def _count_metadata_changes(session, plugin_id: str) -> int:
    """统计指定插件的 plugin_metadata_changes 记录数。

    Args:
        session: 数据库会话。
        plugin_id: 插件标识。

    Returns:
        插件元数据变更记录数。
    """
    stmt = (
        select(func.count())
        .select_from(PluginMetadataChangeORM)
        .where(PluginMetadataChangeORM.plugin_id == plugin_id)
    )
    return int((await session.scalar(stmt)) or 0)


# ---------------------------------------------------------------------------
# 成功路径
# ---------------------------------------------------------------------------


async def test_patch_metadata_updates_all_fields_and_writes_audit_row() -> None:
    """完整更新应修改插件记录，并恰好追加一条审计记录。"""
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
                "display_name": "重命名的插件",
                "icon_url": "https://cdn.example.com/icons/plug-a.png",
                "categories": ["tool"],
                "tags": ["alpha", "beta"],
            },
        )

        assert result.display_name == "重命名的插件"
        assert result.icon_url == "https://cdn.example.com/icons/plug-a.png"
        assert result.categories == ["tool"]
        assert result.tags == ["alpha", "beta"]
        # SQLite/aiosqlite 返回的 updated_at 不带时区，而 utc_now 生成带时区的值。
        # 比较不带时区的时间值，以确认该列已更新。
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
            "display_name": "重命名的插件",
            "icon_url": "https://cdn.example.com/icons/plug-a.png",
            "categories": ["tool"],
            "tags": ["alpha", "beta"],
        }


async def test_patch_metadata_partial_only_records_supplied_fields() -> None:
    """更新操作应仅持久化操作者提供的字段。"""
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
        # 未提供 display_name、icon_url 和 categories 时，审计记录不得包含这些字段。
        assert change.changed_fields == {"tags": ["only-tags"]}

        plugin = await session.get(PluginORM, "plug-a")
        assert plugin is not None
        assert plugin.tags == ["only-tags"]
        # 未修改的字段保持原值。
        assert plugin.display_name == "plug-a"


async def test_patch_metadata_does_not_write_review_record() -> None:
    """按设计，行内编辑应写入独立日志，而非 review_records。"""
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
            "owner", "plug-a", {"display_name": "全新名称"}
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
# 权限验证（属性 5）
# ---------------------------------------------------------------------------


async def test_patch_metadata_allows_maintainer() -> None:
    """已登记的维护者应获准编辑元数据。"""
    async with session_scope() as session:
        await _ensure_author(session, "owner")
        await _ensure_author(session, "co-maintainer")
        await _create_plugin(session, "plug-a", owner_id="owner")
        session.add(
            PluginMaintainerORM(plugin_id="plug-a", author_id="co-maintainer")
        )
        await session.flush()

        result = await InlineEditService(session).patch_metadata(
            "co-maintainer", "plug-a", {"display_name": "维护者修改的名称"}
        )
        assert result.display_name == "维护者修改的名称"


async def test_patch_metadata_allows_admin_non_owner() -> None:
    """管理员即使不是所有者或维护者，也应获得编辑权限。"""
    async with session_scope() as session:
        await _ensure_author(session, "owner")
        await _ensure_author(session, "site-admin", is_admin=True)
        await _create_plugin(session, "plug-a", owner_id="owner")

        result = await InlineEditService(session).patch_metadata(
            "site-admin", "plug-a", {"display_name": "管理员重命名"}
        )
        assert result.display_name == "管理员重命名"


async def test_patch_metadata_rejects_unrelated_author_with_metadata_forbidden() -> None:
    """所有者、维护者和管理员以外的用户应收到 METADATA_FORBIDDEN。"""
    async with session_scope() as session:
        await _ensure_author(session, "owner")
        await _ensure_author(session, "stranger")
        await _create_plugin(session, "plug-a", owner_id="owner")

        with pytest.raises(ApiError) as ctx:
            await InlineEditService(session).patch_metadata(
                "stranger", "plug-a", {"display_name": "恶意篡改"}
            )
        assert ctx.value.status_code == 403
        assert ctx.value.code == "METADATA_FORBIDDEN"


async def test_patch_metadata_returns_metadata_forbidden_for_unknown_plugin() -> None:
    """未知插件应返回 403 而非 404，避免泄露插件是否存在。"""
    async with session_scope() as session:
        await _ensure_author(session, "viewer")
        with pytest.raises(ApiError) as ctx:
            await InlineEditService(session).patch_metadata(
                "viewer", "ghost-plugin", {"display_name": "x"}
            )
        assert ctx.value.status_code == 403
        assert ctx.value.code == "METADATA_FORBIDDEN"


# ---------------------------------------------------------------------------
# 输入校验
# ---------------------------------------------------------------------------


async def test_patch_metadata_rejects_unknown_category() -> None:
    """不在当前分类体系内的分类应被拒绝。"""
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
    """其他插件已使用的分类应被接受。"""
    async with session_scope() as session:
        await _ensure_author(session, "owner")
        await _create_plugin(session, "plug-a", owner_id="owner", categories=["tool"])
        await _create_plugin(session, "plug-b", owner_id="owner", categories=["chat"])

        result = await InlineEditService(session).patch_metadata(
            "owner", "plug-a", {"categories": ["chat"]}
        )
        assert result.categories == ["chat"]


async def test_patch_metadata_rejects_too_many_tags() -> None:
    """提供 11 个标签时，应触发 METADATA_TAGS_TOO_MANY。"""
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
    """图标 URL 必须使用 HTTPS 协议。"""
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
    """更新请求体为空时，应拒绝并返回 METADATA_NO_FIELDS。"""
    async with session_scope() as session:
        await _ensure_author(session, "owner")
        await _create_plugin(session, "plug-a", owner_id="owner")

        with pytest.raises(ApiError) as ctx:
            await InlineEditService(session).patch_metadata("owner", "plug-a", {})
        assert ctx.value.status_code == 422
        assert ctx.value.code == "METADATA_NO_FIELDS"
        # 不应写入审计记录。
        assert await _count_metadata_changes(session, "plug-a") == 0


async def test_patch_metadata_rejects_unknown_field() -> None:
    """不支持的字段必须被拒绝，不得放行。"""
    async with session_scope() as session:
        await _ensure_author(session, "owner")
        await _create_plugin(session, "plug-a", owner_id="owner")

        with pytest.raises(ApiError) as ctx:
            await InlineEditService(session).patch_metadata(
                "owner", "plug-a", {"summary": "此字段不可行内编辑"}
            )
        assert ctx.value.status_code == 422
        assert ctx.value.code == "METADATA_INVALID_FIELD"


async def test_patch_metadata_rejects_duplicate_categories() -> None:
    """更新内容中的重复分类应在写入前被拒绝。"""
    async with session_scope() as session:
        await _ensure_author(session, "owner")
        await _create_plugin(session, "plug-a", owner_id="owner", categories=["tool"])

        with pytest.raises(ApiError) as ctx:
            await InlineEditService(session).patch_metadata(
                "owner", "plug-a", {"categories": ["tool", "tool"]}
            )
        assert ctx.value.code == "METADATA_INVALID_CATEGORY"
