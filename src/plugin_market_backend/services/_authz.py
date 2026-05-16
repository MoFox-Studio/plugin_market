"""Shared authorization gates for service-layer mutations.

Every plugin metadata write (whether through the inline edit endpoint, the
bulk operations API, or the existing owner endpoints) MUST go through one of
these helpers so Property 5 ("Plugin Metadata Authorization") holds.
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
    """Ensure the viewer may edit metadata for ``plugin_id``.

    The caller must be one of:

    * the plugin's owner (``plugins.owner_id``),
    * a registered maintainer (``plugin_maintainers``), or
    * an admin (``authors.is_admin``).

    On failure the helper raises ``ApiError(403, "METADATA_FORBIDDEN")``. Per
    the design's "do not expose existence" rule, the same code is returned for
    both unknown plugins and unauthorized viewers, so a probing client cannot
    enumerate plugin ids.

    Returns:
        The hydrated ``PluginORM`` row, so callers can keep working without an
        extra SELECT.
    """

    plugin = await session.get(PluginORM, plugin_id)
    if plugin is None:
        raise ApiError(
            403,
            "METADATA_FORBIDDEN",
            "You do not have permission to edit this plugin.",
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
        "You do not have permission to edit this plugin.",
        {"plugin_id": plugin_id},
    )
