"""提供服务层写操作共用的授权检查。

每次写入插件元数据，无论来自行内编辑端点、批量操作 API 还是现有的所有者端点，
都必须通过共享辅助函数检查权限，以满足性质 5（插件元数据授权）。
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from plugin_market_backend.errors import ApiError
from plugin_market_backend.orm import AuthorORM, PluginMaintainerORM, PluginORM


async def assert_can_edit_plugin_metadata(
    session: AsyncSession,
    plugin_id: str,
    viewer_id: str,
) -> PluginORM:
    """确保访问者有权编辑 ``plugin_id`` 对应的插件元数据。

    访问者必须是插件所有者（``plugins.owner_id``）、已登记的维护者
    （``plugin_maintainers``）或管理员（``authors.is_admin``）。
    为遵循不暴露资源是否存在的规则，插件不存在与访问者无权限时使用相同错误码，
    防止客户端通过探测枚举插件 ID。

    Args:
        session: 用于查询插件及访问者权限的异步会话。
        plugin_id: 待编辑插件的 ID。
        viewer_id: 请求编辑的访问者 ID。

    Returns:
        已加载的 ``PluginORM`` 记录，供调用方继续使用，无需额外执行 SELECT。

    Raises:
        ApiError: 插件不存在或访问者无权限时，返回 403 和 ``METADATA_FORBIDDEN``。
    """
    plugin = await session.get(PluginORM, plugin_id)
    if plugin is None:
        raise ApiError(
            403,
            "METADATA_FORBIDDEN",
            "你没有权限编辑此插件。",
            {"plugin_id": plugin_id},
        )

    if plugin.owner_id == viewer_id:
        return plugin

    maintainer_stmt = select(PluginMaintainerORM.id).where(
        PluginMaintainerORM.plugin_id == plugin_id,
        PluginMaintainerORM.author_id == viewer_id,
    )
    if (await session.execute(maintainer_stmt)).first() is not None:
        return plugin

    viewer = await session.get(AuthorORM, viewer_id)
    if viewer is not None and bool(viewer.is_admin):
        return plugin

    raise ApiError(
        403,
        "METADATA_FORBIDDEN",
        "你没有权限编辑此插件。",
        {"plugin_id": plugin_id},
    )
