"""提供作者资料、背景图和置顶插件服务。

本模块实现个人空间后端（需求 3 和 4）：

* ``ProfileService.get_profile`` 和 ``update_profile`` 读取、写入作者的
  ``author_profiles`` 记录。资料在首次写入时才创建，无需回填已有账户。
* ``ProfileService.list_pins``、``add_pin``、``update_pin_reason`` 和
  ``remove_pin`` 管理 ``pinned_plugins`` 表，并保证性质 6 的约束：
  每位作者最多置顶 6 个插件；置顶插件必须由该作者拥有或维护；
  展示顺序为 ``pinned_at`` 降序。

业务校验失败时抛出 ``plugin_market_backend.errors.ApiError``。
调用方应使用 ``session_scope`` 包裹调用，以便成功时提交事务、失败时回滚。
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from plugin_market_backend.errors import ApiError
from plugin_market_backend.orm import (
    AuthorProfileORM,
    PinnedPluginORM,
    PluginMaintainerORM,
    PluginORM,
    utc_now,
)
from plugin_market_backend.schemas import (
    AuthorProfile,
    PinnedPluginItem,
    Plugin,
)


MAX_BIO_LENGTH = 2000
MAX_PIN_REASON_LENGTH = 200
MAX_ACTIVE_PINS = 6


class ProfileService:
    """管理 ``author_profiles`` 和 ``pinned_plugins`` 记录。

    本服务将个人空间的写操作集中在职责明确的模块中，统一保证性质 6 的置顶约束。
    """

    def __init__(self, session: AsyncSession) -> None:
        """创建绑定到单个事务会话的服务。"""
        self.session = session

    # ------------------------------------------------------------------
    # 个人资料（简介和背景图）
    # ------------------------------------------------------------------

    async def get_profile(self, author_id: str) -> AuthorProfile:
        """返回 ``author_id`` 对应的个人资料。

        作者尚未更新资料时，返回简介为空、无背景图的默认 ``AuthorProfile`` 实例；
        只有作者保存变更时才创建数据库记录。
        """
        record = await self.session.get(AuthorProfileORM, author_id)
        if record is None:
            return AuthorProfile(author_id=author_id, bio="", background_image_url=None)
        return _profile_to_schema(record)

    async def update_profile(
        self,
        author_id: str,
        *,
        bio: str | None = None,
        background_image_url: str | None = None,
    ) -> AuthorProfile:
        """更新 ``author_id`` 的简介或背景图。

        Args:
            author_id: 个人资料所属作者的 ID。
            bio: 新的简介文本。``None`` 表示不修改，空字符串表示清空；
                长度最多为 2000 个字符（需求 3.2）。
            background_image_url: 新背景图 URL。``None`` 表示不修改，
                空字符串表示清空；支持 HTTPS URL 或内部媒体路径。

        Returns:
            更新后的个人资料数据模型。

        Raises:
            ApiError: 简介过长或背景图 URL 不合法时返回 422，错误码分别为
                ``PROFILE_BIO_TOO_LONG`` 或 ``PROFILE_BACKGROUND_INVALID_URL``。
        """
        if bio is not None and len(bio) > MAX_BIO_LENGTH:
            raise ApiError(
                422,
                "PROFILE_BIO_TOO_LONG",
                f"简介最多为 {MAX_BIO_LENGTH} 个字符。",
                {"max_length": MAX_BIO_LENGTH, "received": len(bio)},
            )
        if background_image_url is not None and background_image_url:
            _assert_https_url(background_image_url)

        record = await self.session.get(AuthorProfileORM, author_id)
        if record is None:
            record = AuthorProfileORM(
                author_id=author_id,
                bio=bio if bio is not None else "",
                background_image_url=background_image_url or None,
                background_image_kind="url",
            )
            self.session.add(record)
        else:
            if bio is not None:
                record.bio = bio
            if background_image_url is not None:
                # 旧背景图若来自上传，替换或清空前删除磁盘上不再被引用的文件。
                from plugin_market_backend.content import delete_profile_background_url

                if record.background_image_kind == "upload" and record.background_image_url:
                    if record.background_image_url != background_image_url:
                        delete_profile_background_url(record.background_image_url)
                record.background_image_url = background_image_url or None
                record.background_image_kind = "url"
        record.updated_at = utc_now()
        await self.session.flush()
        return _profile_to_schema(record)

    async def set_background_from_upload(
        self,
        author_id: str,
        raw_bytes: bytes,
    ) -> AuthorProfile:
        """持久化上传的背景图并更新个人资料。"""
        from plugin_market_backend.content import (
            delete_profile_background_url,
            store_profile_background,
        )

        new_url = store_profile_background(author_id, raw_bytes)

        record = await self.session.get(AuthorProfileORM, author_id)
        if record is None:
            record = AuthorProfileORM(
                author_id=author_id,
                bio="",
                background_image_url=new_url,
                background_image_kind="upload",
            )
            self.session.add(record)
        else:
            # 尽力清理之前上传的图片，避免残留无引用文件。
            if record.background_image_kind == "upload":
                delete_profile_background_url(record.background_image_url)
            record.background_image_url = new_url
            record.background_image_kind = "upload"
        record.updated_at = utc_now()
        await self.session.flush()
        return _profile_to_schema(record)

    # ------------------------------------------------------------------
    # 置顶插件
    # ------------------------------------------------------------------

    async def list_pins(self, author_id: str) -> list[PinnedPluginItem]:
        """按 ``pinned_at`` 降序返回 ``author_id`` 的置顶插件。"""
        stmt = (
            select(PinnedPluginORM)
            .where(PinnedPluginORM.author_id == author_id)
            .order_by(PinnedPluginORM.pinned_at.desc(), PinnedPluginORM.id.desc())
        )
        rows = list((await self.session.scalars(stmt)).all())
        if not rows:
            return []

        plugin_ids = [row.plugin_id for row in rows]
        plugin_stmt = (
            select(PluginORM)
            .options(
                selectinload(PluginORM.maintainers),
                selectinload(PluginORM.owner),
                selectinload(PluginORM.versions),
            )
            .where(PluginORM.plugin_id.in_(plugin_ids))
        )
        plugin_map: dict[str, PluginORM] = {
            plugin.plugin_id: plugin
            for plugin in (await self.session.scalars(plugin_stmt)).all()
        }

        return [
            PinnedPluginItem(
                plugin_id=row.plugin_id,
                pinned_reason=row.pinned_reason,
                pinned_at=row.pinned_at,
                plugin=_plugin_to_schema(plugin_map.get(row.plugin_id)),
            )
            for row in rows
        ]

    async def add_pin(
        self,
        author_id: str,
        plugin_id: str,
        reason: str | None = None,
    ) -> PinnedPluginItem:
        """为 ``author_id`` 添加一个置顶插件。

        校验插件存在且由作者拥有或维护、理由不超过 200 个字符、同一作者不能
        重复置顶同一插件，以及每位作者最多置顶 6 个插件。
        ``pinned_at`` 使用 ``utc_now``，使个人空间优先展示最近置顶的插件
        （需求 4.8、性质 6）。

        Args:
            author_id: 请求置顶的作者 ID。
            plugin_id: 待置顶插件的 ID。
            reason: 可选的置顶理由。

        Returns:
            包含插件信息的新置顶条目。

        Raises:
            ApiError: 插件不存在、作者无权限、理由过长、已置顶或置顶数量达到上限。
        """
        _assert_reason_length(reason)
        await self._assert_can_pin(author_id, plugin_id)

        existing = await self.session.scalar(
            select(PinnedPluginORM).where(
                PinnedPluginORM.author_id == author_id,
                PinnedPluginORM.plugin_id == plugin_id,
            )
        )
        if existing is not None:
            raise ApiError(
                409,
                "PIN_ALREADY_EXISTS",
                "此插件已置顶。",
                {"author_id": author_id, "plugin_id": plugin_id},
            )

        active_count = await self._count_active_pins(author_id)
        if active_count >= MAX_ACTIVE_PINS:
            raise ApiError(
                409,
                "PIN_LIMIT_EXCEEDED",
                f"最多允许置顶 {MAX_ACTIVE_PINS} 个插件。",
                {"limit": MAX_ACTIVE_PINS, "current": active_count},
            )

        pin = PinnedPluginORM(
            author_id=author_id,
            plugin_id=plugin_id,
            pinned_reason=reason,
            pinned_at=utc_now(),
        )
        self.session.add(pin)
        await self.session.flush()

        plugin_row = await self._load_plugin_for_schema(plugin_id)
        return PinnedPluginItem(
            plugin_id=pin.plugin_id,
            pinned_reason=pin.pinned_reason,
            pinned_at=pin.pinned_at,
            plugin=_plugin_to_schema(plugin_row),
        )

    async def update_pin_reason(
        self,
        author_id: str,
        plugin_id: str,
        reason: str | None,
    ) -> PinnedPluginItem:
        """替换已有置顶记录的 ``pinned_reason``，保持 ``pinned_at`` 不变。"""
        _assert_reason_length(reason)
        pin = await self.session.scalar(
            select(PinnedPluginORM).where(
                PinnedPluginORM.author_id == author_id,
                PinnedPluginORM.plugin_id == plugin_id,
            )
        )
        if pin is None:
            raise ApiError(
                404,
                "PIN_NOT_FOUND",
                "未找到置顶插件。",
                {"author_id": author_id, "plugin_id": plugin_id},
            )

        pin.pinned_reason = reason
        await self.session.flush()

        plugin_row = await self._load_plugin_for_schema(plugin_id)
        return PinnedPluginItem(
            plugin_id=pin.plugin_id,
            pinned_reason=pin.pinned_reason,
            pinned_at=pin.pinned_at,
            plugin=_plugin_to_schema(plugin_row),
        )

    async def remove_pin(self, author_id: str, plugin_id: str) -> None:
        """删除 ``(author_id, plugin_id)`` 对应的置顶记录。

        Args:
            author_id: 置顶记录所属作者的 ID。
            plugin_id: 待取消置顶的插件 ID。

        Raises:
            ApiError: 没有匹配的置顶记录时返回 ``PIN_NOT_FOUND``，
                使调用方能够向客户端提供明确错误。
        """
        pin = await self.session.scalar(
            select(PinnedPluginORM).where(
                PinnedPluginORM.author_id == author_id,
                PinnedPluginORM.plugin_id == plugin_id,
            )
        )
        if pin is None:
            raise ApiError(
                404,
                "PIN_NOT_FOUND",
                "未找到置顶插件。",
                {"author_id": author_id, "plugin_id": plugin_id},
            )
        await self.session.delete(pin)
        await self.session.flush()

    # ------------------------------------------------------------------
    # 内部辅助函数
    # ------------------------------------------------------------------

    async def _assert_can_pin(self, author_id: str, plugin_id: str) -> None:
        """确认插件存在，且由 ``author_id`` 对应作者拥有或维护。"""
        plugin = await self.session.get(PluginORM, plugin_id)
        if plugin is None:
            raise ApiError(
                404,
                "PIN_PLUGIN_NOT_FOUND",
                "未找到插件。",
                {"plugin_id": plugin_id},
            )
        if plugin.owner_id == author_id:
            return

        maintainer_stmt = select(PluginMaintainerORM.id).where(
            PluginMaintainerORM.plugin_id == plugin_id,
            PluginMaintainerORM.author_id == author_id,
        )
        if (await self.session.execute(maintainer_stmt)).first() is not None:
            return

        raise ApiError(
            403,
            "PIN_PLUGIN_NOT_OWNED",
            "你不是此插件的所有者或维护者。",
            {"author_id": author_id, "plugin_id": plugin_id},
        )

    async def _count_active_pins(self, author_id: str) -> int:
        """返回 ``author_id`` 当前的置顶插件数量。"""
        from sqlalchemy import func

        stmt = (
            select(func.count())
            .select_from(PinnedPluginORM)
            .where(PinnedPluginORM.author_id == author_id)
        )
        return int((await self.session.scalar(stmt)) or 0)

    async def _load_plugin_for_schema(self, plugin_id: str) -> PluginORM | None:
        """加载插件及 ``Plugin`` 数据模型所需的关联记录。"""
        stmt = (
            select(PluginORM)
            .options(
                selectinload(PluginORM.maintainers),
                selectinload(PluginORM.owner),
                selectinload(PluginORM.versions),
            )
            .where(PluginORM.plugin_id == plugin_id)
        )
        return await self.session.scalar(stmt)


# ----------------------------------------------------------------------
# 模块级私有辅助函数
# ----------------------------------------------------------------------


def _profile_to_schema(record: AuthorProfileORM) -> AuthorProfile:
    """将 ``AuthorProfileORM`` 记录转换为 API 数据模型。"""
    kind = record.background_image_kind if record.background_image_kind in {"url", "upload"} else "url"
    return AuthorProfile(
        author_id=record.author_id,
        bio=record.bio or "",
        background_image_url=record.background_image_url,
        background_image_kind=kind,  # type: ignore[arg-type]
        updated_at=record.updated_at,
    )


def _plugin_to_schema(plugin: PluginORM | None) -> Plugin | None:
    """将 ``PluginORM`` 记录转换为轻量的 ``Plugin`` 数据模型。

    置顶插件响应无需额外查询点赞、评分等社区统计；下载数由已加载版本汇总。
    因此转换逻辑保持独立，不依赖 ``MarketService``。
    """
    if plugin is None:
        return None

    from plugin_market_backend.content import normalize_readme_markdown
    from plugin_market_backend.enums import VersionStatus

    versions = list(plugin.versions or [])
    published = [
        item
        for item in versions
        if item.status == VersionStatus.PUBLISHED and not item.is_yanked
    ]
    latest = max(published, key=lambda item: item.published_at) if published else None
    owner = plugin.owner if getattr(plugin, "owner", None) is not None else None
    return Plugin(
        plugin_id=plugin.plugin_id,
        display_name=plugin.display_name,
        summary=plugin.summary,
        description=plugin.description,
        icon_url=plugin.icon_url,
        has_readme=bool(normalize_readme_markdown(plugin.readme_markdown)),
        homepage=plugin.homepage,
        repository_url=plugin.repository_url,
        license=plugin.license,
        categories=plugin.categories or [],
        tags=plugin.tags or [],
        status=plugin.status,
        owner_id=plugin.owner_id,
        owner_login=owner.github_login if owner is not None else None,
        owner_display_name=owner.display_name if owner is not None else None,
        owner_avatar_url=owner.avatar_url if owner is not None else None,
        maintainers=[item.author_id for item in plugin.maintainers],
        trust_level=plugin.trust_level,
        risk_notice=plugin.risk_notice,
        created_at=plugin.created_at,
        updated_at=plugin.updated_at,
        latest_version=latest.version if latest else None,
        latest_version_published_at=latest.published_at if latest else None,
        downloads_count=sum(int(item.download_count or 0) for item in versions),
    )


def _assert_reason_length(reason: str | None) -> None:
    """拒绝超过 200 个字符的置顶理由。"""
    if reason is None:
        return
    if len(reason) > MAX_PIN_REASON_LENGTH:
        raise ApiError(
            422,
            "PIN_REASON_TOO_LONG",
            f"置顶理由最多为 {MAX_PIN_REASON_LENGTH} 个字符。",
            {"max_length": MAX_PIN_REASON_LENGTH, "received": len(reason)},
        )


def _assert_https_url(url: str) -> None:
    """拒绝既非 HTTPS URL 也非内部媒体路径的背景图地址。"""
    stripped = url.strip()
    if not stripped:
        return
    if stripped.startswith("/plugin-media/"):
        return
    lowered = stripped.lower()
    if not lowered.startswith("https://"):
        raise ApiError(
            422,
            "PROFILE_BACKGROUND_INVALID_URL",
            "背景图 URL 必须使用 HTTPS 协议或内部 /plugin-media/ 路径。",
            {"received": url},
        )
