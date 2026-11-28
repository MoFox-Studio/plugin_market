"""提供公告管理、可见性判断和关闭记录服务。

实现需求 12 和 13：由管理员管理公告，支持展示排期、受众定向、关闭操作，
并保证单弹窗性质（性质 3）。

关键设计如下：

* ``is_visible`` 是纯函数（性质 2），不读取数据库会话；调用方必须预先计算
  ``is_dismissed`` 和 ``viewer_has_plugin``。
* ``AnnouncementsService.list_active`` 保证性质 3：对每位访问者最多返回一条
  ``display_mode='modal'`` 公告，按 ``starts_at desc, id desc`` 选择。
* ``AnnouncementsService.dismiss`` 利用唯一约束
  ``(announcement_id, author_id, dismiss_token)`` 实现 ``INSERT OR IGNORE``
  语义，保证关闭操作的幂等性（性质 9）。
* 公告管理写操作通过 ``_audit`` 追加 ``ReviewRecordORM`` 记录，
  保证审计轨迹完整性（性质 8）。
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Sequence

from sqlalchemy import select, func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from plugin_market_backend.enums import ReviewAction
from plugin_market_backend.errors import ApiError
from plugin_market_backend.orm import (
    AnnouncementDismissalORM,
    AnnouncementORM,
    ReviewRecordORM,
    utc_now,
)
from plugin_market_backend.schemas import (
    AnnouncementCreate,
    AnnouncementDTO,
    AnnouncementUpdate,
)
from plugin_market_backend.services._audience import audience_matches

if TYPE_CHECKING:
    from plugin_market_backend.orm import AuthorORM


# ---------------------------------------------------------------------------
# 时区辅助函数
# ---------------------------------------------------------------------------


def _strip_tz(dt: datetime) -> datetime:
    """移除时区信息，以便安全比较日期时间。

    SQLite 会将存入的带时区日期时间读回为不带 ``tzinfo`` 的值。
    比较前移除时区信息，可避免带时区与不带时区值混合比较导致的 ``TypeError``。
    此操作不转换时间值，调用方应确保输入使用相同的时区基准。
    """
    if dt.tzinfo is not None:
        return dt.replace(tzinfo=None)
    return dt


# ---------------------------------------------------------------------------
# 纯函数可见性判断（性质 2）
# ---------------------------------------------------------------------------


def is_visible(
    announcement: "AnnouncementORM",
    viewer: "AuthorORM | None",
    now: datetime,
    *,
    is_dismissed: bool = False,
    viewer_has_plugin: bool = False,
) -> bool:
    """判断是否应在 ``now`` 时刻向 ``viewer`` 展示 ``announcement``。

    这是不读取数据库会话的纯函数。依赖外部状态的输入 ``is_dismissed`` 和
    ``viewer_has_plugin`` 必须由调用方预先计算。
    此判断直接实现性质 2（公告可见性）：公告可见，当且仅当已启用、
    命中展示时间范围、受众匹配且未被关闭。

    Args:
        announcement: 待判断的公告 ORM 记录。
        viewer: 当前已认证作者，匿名访问时为 ``None``。
        now: 用于判断展示排期的服务器时间。
        is_dismissed: 访问者是否已在当前 ``dismiss_token`` 下关闭此公告。
        viewer_has_plugin: 访问者是否拥有至少一个插件。
            仅在 ``audience == 'authors_with_plugin'`` 时需要。

    Returns:
        应向访问者展示公告时返回 ``True``。
    """
    if not announcement.enabled:
        return False
    if announcement.starts_at is not None:
        starts = _strip_tz(announcement.starts_at)
        now_naive = _strip_tz(now)
        if starts > now_naive:
            return False
    if announcement.ends_at is not None:
        ends = _strip_tz(announcement.ends_at)
        now_naive = _strip_tz(now)
        if now_naive > ends:
            return False
    if not audience_matches(
        announcement.audience, viewer, viewer_has_plugin=viewer_has_plugin
    ):
        return False
    if is_dismissed:
        return False
    return True


# ---------------------------------------------------------------------------
# 服务类
# ---------------------------------------------------------------------------


class AnnouncementsService:
    """管理公告和每位访问者的关闭记录。

    公告管理写操作通过 ``_audit`` 追加审计记录。
    """

    def __init__(self, session: AsyncSession) -> None:
        """将服务绑定到单个异步事务会话。"""
        self.session = session

    # ------------------------------------------------------------------
    # 公开查询：对访问者有效的公告
    # ------------------------------------------------------------------

    async def list_active(
        self,
        viewer: "AuthorORM | None",
        *,
        now: datetime | None = None,
        viewer_has_plugin: bool = False,
    ) -> list[AnnouncementDTO]:
        """返回 ``now`` 时刻对 ``viewer`` 可见的公告。

        保证性质 3（单弹窗）：多个弹窗公告同时符合条件时，仅返回 ``starts_at``
        最新的一条；时间相同时选择 ``id`` 最大的一条。
        横幅公告按相同顺序（``starts_at desc, id desc``）返回，不限制数量。

        Args:
            viewer: 当前已认证作者，匿名访问时为 ``None``。
            now: 判断可见性的时间，默认使用当前 UTC 时间。
            viewer_has_plugin: 访问者是否拥有至少一个插件。

        Returns:
            按展示开始时间和 ID 降序排列的可见公告 DTO 列表。
        """
        if now is None:
            now = utc_now()

        # 读取所有已启用公告，随后判断其展示时间范围。
        stmt = select(AnnouncementORM).where(AnnouncementORM.enabled.is_(True))
        rows: Sequence[AnnouncementORM] = list(
            (await self.session.scalars(stmt)).all()
        )

        # 预先获取访问者的公告关闭记录。
        dismissed_set: set[tuple[int, int]] = set()
        if viewer is not None:
            dismiss_stmt = select(
                AnnouncementDismissalORM.announcement_id,
                AnnouncementDismissalORM.dismiss_token,
            ).where(AnnouncementDismissalORM.author_id == viewer.author_id)
            for row in await self.session.execute(dismiss_stmt):
                dismissed_set.add((row[0], row[1]))

        # 使用纯函数可见性判断进行筛选。
        visible: list[AnnouncementORM] = []
        for ann in rows:
            dismissed = (ann.id, ann.dismiss_token) in dismissed_set
            if is_visible(
                ann,
                viewer,
                now,
                is_dismissed=dismissed,
                viewer_has_plugin=viewer_has_plugin,
            ):
                visible.append(ann)

        # 按 starts_at 降序（空值置后）、id 降序排列，保证顺序确定。
        def _sort_key(a: AnnouncementORM) -> tuple:
            # 用最早日期替代空值，使其在降序排列时位于末尾。
            starts = a.starts_at if a.starts_at is not None else datetime.min
            return (starts, a.id)

        visible.sort(key=_sort_key, reverse=True)

        # 性质 3：最多展示一个弹窗。
        banners: list[AnnouncementORM] = []
        modal_picked: AnnouncementORM | None = None
        for ann in visible:
            if ann.display_mode == "modal":
                if modal_picked is None:
                    modal_picked = ann
                # 跳过其他弹窗公告。
            else:
                banners.append(ann)

        result: list[AnnouncementORM] = banners
        if modal_picked is not None:
            result.append(modal_picked)

        # 再次按 starts_at 降序、id 降序排列最终列表。
        result.sort(key=_sort_key, reverse=True)

        return [_orm_to_dto(ann) for ann in result]

    # ------------------------------------------------------------------
    # 管理员增删改查
    # ------------------------------------------------------------------

    async def create(
        self,
        payload: AnnouncementCreate,
        operator_id: str,
    ) -> AnnouncementDTO:
        """创建公告并追加审计记录。

        Args:
            payload: 已校验的公告创建数据。
            operator_id: 执行操作的管理员 ID。

        Returns:
            新建公告的 DTO。
        """
        # 旧版管理员令牌流程使用合成的操作者 ID。
        # 写入引用该 ID 的公告前，先确保作者记录存在。
        from plugin_market_backend.service import MarketService

        await MarketService(self.session).ensure_author(operator_id, is_admin=True)

        now = utc_now()
        record = AnnouncementORM(
            title=payload.title,
            body_markdown=payload.body_markdown,
            display_mode=payload.display_mode,
            severity=payload.severity,
            dismissible=payload.dismissible,
            enabled=payload.enabled,
            starts_at=payload.starts_at,
            ends_at=payload.ends_at,
            audience=payload.audience,
            emit_inbox=payload.emit_inbox,
            dismiss_token=0,
            created_by=operator_id,
            created_at=now,
            updated_at=now,
        )
        self.session.add(record)
        await self.session.flush()

        self._audit(
            action=ReviewAction.CREATE_ANNOUNCEMENT,
            target_id=str(record.id),
            operator_id=operator_id,
        )
        await self.session.flush()

        return _orm_to_dto(record)

    async def update(
        self,
        announcement_id: int,
        payload: AnnouncementUpdate,
        operator_id: str,
    ) -> AnnouncementDTO:
        """更新已有公告并追加审计记录。

        仅修改 ``payload`` 中明确设置的字段。

        Args:
            announcement_id: 待更新公告的 ID。
            payload: 已校验的公告更新数据。
            operator_id: 执行操作的管理员 ID。

        Returns:
            更新后的公告 DTO。

        Raises:
            ApiError: 公告不存在时返回 404。
        """
        record = await self._get_or_404(announcement_id)

        update_data = payload.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(record, field, value)
        record.updated_at = utc_now()

        self._audit(
            action=ReviewAction.UPDATE_ANNOUNCEMENT,
            target_id=str(record.id),
            operator_id=operator_id,
        )
        await self.session.flush()

        return _orm_to_dto(record)

    async def disable(
        self,
        announcement_id: int,
        operator_id: str,
    ) -> AnnouncementDTO:
        """立即停用并归档公告。

        设置 ``enabled = False``，并追加 ``ARCHIVE_ANNOUNCEMENT`` 审计记录。

        Args:
            announcement_id: 待停用公告的 ID。
            operator_id: 执行操作的管理员 ID。

        Returns:
            停用后的公告 DTO。

        Raises:
            ApiError: 公告不存在时返回 404。
        """
        record = await self._get_or_404(announcement_id)
        record.enabled = False
        record.updated_at = utc_now()

        self._audit(
            action=ReviewAction.ARCHIVE_ANNOUNCEMENT,
            target_id=str(record.id),
            operator_id=operator_id,
        )
        await self.session.flush()

        return _orm_to_dto(record)

    async def resurface(
        self,
        announcement_id: int,
        operator_id: str,
    ) -> AnnouncementDTO:
        """递增公告的 ``dismiss_token``，使公告重新展示。

        此操作使已有关闭记录失效，让访问者能够再次看到公告；
        若公告已停用，也会重新启用。

        Args:
            announcement_id: 待重新展示公告的 ID。
            operator_id: 执行操作的管理员 ID。

        Returns:
            更新后的公告 DTO。

        Raises:
            ApiError: 公告不存在时返回 404。
        """
        record = await self._get_or_404(announcement_id)
        record.dismiss_token += 1
        record.enabled = True
        record.updated_at = utc_now()

        self._audit(
            action=ReviewAction.UPDATE_ANNOUNCEMENT,
            target_id=str(record.id),
            operator_id=operator_id,
        )
        await self.session.flush()

        return _orm_to_dto(record)

    # ------------------------------------------------------------------
    # 关闭公告
    # ------------------------------------------------------------------

    async def dismiss(
        self,
        announcement_id: int,
        viewer_id: str,
    ) -> tuple[int, int]:
        """记录 ``viewer_id`` 对 ``announcement_id`` 的关闭操作。

        使用 ``INSERT OR IGNORE`` 语义保证幂等性（性质 9）：
        若访问者已在当前 ``dismiss_token`` 下关闭公告，则不执行额外操作。

        Args:
            announcement_id: 待关闭公告的 ID。
            viewer_id: 执行关闭操作的访问者 ID。

        Returns:
            用于响应的 ``(announcement_id, dismiss_token)`` 元组。

        Raises:
            ApiError: 公告不存在时返回 404。
        """
        record = await self._get_or_404(announcement_id)

        dismissal = AnnouncementDismissalORM(
            announcement_id=announcement_id,
            author_id=viewer_id,
            dismiss_token=record.dismiss_token,
            created_at=utc_now(),
        )

        # 使用保存点，避免重复关闭导致的 IntegrityError 使外层事务失效。
        try:
            async with self.session.begin_nested():
                self.session.add(dismissal)
        except IntegrityError:
            # 违反唯一约束表示当前令牌下已有关闭记录。
            # 这是预期的幂等处理分支（性质 9）。
            pass

        return (announcement_id, record.dismiss_token)

    # ------------------------------------------------------------------
    # 管理员：分页列出所有公告
    # ------------------------------------------------------------------

    async def admin_list(
        self,
        *,
        offset: int = 0,
        limit: int = 50,
    ) -> tuple[list[AnnouncementDTO], int]:
        """为管理员控制台分页返回所有公告。

        Args:
            offset: 分页起始偏移量。
            limit: 单页最多返回的条目数。

        Returns:
            ``(items, total_count)`` 元组，分别为当前页公告和总数。
        """
        total = int(
            await self.session.scalar(
                select(func.count()).select_from(AnnouncementORM)
            )
            or 0
        )

        stmt = (
            select(AnnouncementORM)
            .order_by(AnnouncementORM.created_at.desc(), AnnouncementORM.id.desc())
            .offset(offset)
            .limit(limit)
        )
        rows = list((await self.session.scalars(stmt)).all())
        return ([_orm_to_dto(row) for row in rows], total)

    # ------------------------------------------------------------------
    # 内部辅助函数
    # ------------------------------------------------------------------

    async def _get_or_404(self, announcement_id: int) -> AnnouncementORM:
        """按 ID 获取公告，不存在时抛出 404 错误。"""
        record = await self.session.get(AnnouncementORM, announcement_id)
        if record is None:
            raise ApiError(
                404,
                "ANNOUNCEMENT_NOT_FOUND",
                "未找到公告。",
                {"announcement_id": announcement_id},
            )
        return record

    def _audit(
        self,
        *,
        action: ReviewAction,
        target_id: str,
        operator_id: str,
        reason: str | None = None,
    ) -> None:
        """为公告写操作追加一条 ``ReviewRecordORM`` 记录。

        此方法同步执行，只将 ORM 对象加入会话；实际 INSERT 在下次 ``flush()`` 时发生。
        """
        self.session.add(
            ReviewRecordORM(
                target_type="announcement",
                target_id=target_id,
                action=action,
                status_before=None,
                status_after=None,
                reason=reason,
                operator_id=operator_id,
            )
        )


# ---------------------------------------------------------------------------
# 模块级辅助函数
# ---------------------------------------------------------------------------


def _orm_to_dto(record: AnnouncementORM) -> AnnouncementDTO:
    """将 ``AnnouncementORM`` 记录转换为 API DTO。"""
    return AnnouncementDTO(
        id=record.id,
        title=record.title,
        body_markdown=record.body_markdown,
        display_mode=record.display_mode,  # type: ignore[arg-type]
        severity=record.severity,  # type: ignore[arg-type]
        dismissible=record.dismissible,
        enabled=record.enabled,
        starts_at=record.starts_at,
        ends_at=record.ends_at,
        audience=record.audience,  # type: ignore[arg-type]
        emit_inbox=record.emit_inbox,
        dismiss_token=record.dismiss_token,
        created_by=record.created_by,
        created_at=record.created_at,
        updated_at=record.updated_at,
    )
