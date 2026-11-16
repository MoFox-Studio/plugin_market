"""AnnouncementsService 的单元测试（任务 7）。

绕过 HTTP 层，验证公告管理、可见性和关闭功能：

* is_visible 纯函数：排期、受众、启用状态和关闭状态。
* list_active：最多显示一个弹窗（属性 3）。
* create、update、disable、resurface：增删改查与审计轨迹。
* dismiss：INSERT OR IGNORE 的幂等性（属性 9）。
* admin_list：分页列表。
"""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from plugin_market_backend.database import session_scope
from plugin_market_backend.enums import ReviewAction
from plugin_market_backend.errors import ApiError
from plugin_market_backend.orm import (
    AnnouncementDismissalORM,
    AnnouncementORM,
    AuthorORM,
    AuthorType,
    ReviewRecordORM,
    utc_now,
)
from plugin_market_backend.schemas import AnnouncementCreate, AnnouncementUpdate
from plugin_market_backend.services.announcements_service import (
    AnnouncementsService,
    is_visible,
)
from sqlalchemy import select


# ---------------------------------------------------------------------------
# 初始化辅助函数
# ---------------------------------------------------------------------------


async def _ensure_author(
    session,
    author_id: str,
    *,
    is_admin: bool = False,
    github_login: str | None = None,
) -> AuthorORM:
    """获取作者记录，并在不存在时创建。

    Args:
        session: 数据库会话。
        author_id: 作者标识。
        is_admin: 是否授予管理员身份。
        github_login: GitHub 登录名；未提供时使用作者标识。

    Returns:
        已有或新建的作者记录。
    """
    existing = await session.get(AuthorORM, author_id)
    if existing is not None:
        return existing
    author = AuthorORM(
        author_id=author_id,
        github_user_id=f"id-{author_id}",
        github_login=github_login or author_id,
        display_name=github_login or author_id,
        author_type=AuthorType.USER,
        verified_at=utc_now(),
        is_admin=is_admin,
    )
    session.add(author)
    await session.flush()
    return author


def _make_announcement_orm(
    *,
    id: int = 1,
    enabled: bool = True,
    display_mode: str = "banner",
    audience: str = "all",
    starts_at: datetime | None = None,
    ends_at: datetime | None = None,
    dismiss_token: int = 0,
    dismissible: bool = True,
) -> AnnouncementORM:
    """为纯函数测试创建内存中的 AnnouncementORM。

    使用标准构造函数，确保 SQLAlchemy 的属性跟踪机制已初始化。

    Args:
        id: 公告标识。
        enabled: 是否启用。
        display_mode: 展示模式。
        audience: 目标受众。
        starts_at: 开始时间；None 表示不限。
        ends_at: 结束时间；None 表示不限。
        dismiss_token: 关闭记录的版本标记。
        dismissible: 是否允许关闭。

    Returns:
        未持久化的公告记录。
    """
    now = utc_now()
    return AnnouncementORM(
        id=id,
        title=f"公告 {id}",
        body_markdown="正文",
        display_mode=display_mode,
        severity="info",
        dismissible=dismissible,
        enabled=enabled,
        starts_at=starts_at,
        ends_at=ends_at,
        audience=audience,
        emit_inbox=False,
        dismiss_token=dismiss_token,
        created_by="admin",
        created_at=now,
        updated_at=now,
    )


# ---------------------------------------------------------------------------
# is_visible 纯函数测试
# ---------------------------------------------------------------------------


class TestIsVisible:
    """模块级 is_visible 纯函数的测试。"""

    def test_enabled_all_audience_no_schedule_visible(self) -> None:
        """已启用且 audience=all、没有排期限制的公告应可见。"""
        ann = _make_announcement_orm(enabled=True, audience="all")
        now = utc_now()
        assert is_visible(ann, None, now) is True

    def test_disabled_not_visible(self) -> None:
        """禁用的公告始终不可见。"""
        ann = _make_announcement_orm(enabled=False)
        now = utc_now()
        assert is_visible(ann, None, now) is False

    def test_before_starts_at_not_visible(self) -> None:
        """公告在 starts_at 之前不可见。"""
        future = utc_now() + timedelta(hours=1)
        ann = _make_announcement_orm(starts_at=future)
        now = utc_now()
        assert is_visible(ann, None, now) is False

    def test_after_ends_at_not_visible(self) -> None:
        """公告在 ends_at 之后不可见。"""
        past = utc_now() - timedelta(hours=1)
        ann = _make_announcement_orm(ends_at=past)
        now = utc_now()
        assert is_visible(ann, None, now) is False

    def test_within_schedule_visible(self) -> None:
        """公告在排期时间范围内应可见。"""
        now = utc_now()
        ann = _make_announcement_orm(
            starts_at=now - timedelta(hours=1),
            ends_at=now + timedelta(hours=1),
        )
        assert is_visible(ann, None, now) is True

    def test_audience_logged_in_rejects_anonymous(self) -> None:
        """audience=logged_in 时应拒绝匿名查看者。"""
        ann = _make_announcement_orm(audience="logged_in")
        now = utc_now()
        assert is_visible(ann, None, now) is False

    def test_audience_logged_in_accepts_viewer(self) -> None:
        """audience=logged_in 时应允许已认证的查看者。"""
        ann = _make_announcement_orm(audience="logged_in")
        now = utc_now()
        viewer = AuthorORM(
            author_id="user-1",
            github_user_id="gh-user-1",
            github_login="user1",
            display_name="用户 1",
            author_type=AuthorType.USER,
            is_admin=False,
        )
        assert is_visible(ann, viewer, now) is True

    def test_audience_admins_rejects_non_admin(self) -> None:
        """audience=admins 时应拒绝非管理员查看者。"""
        ann = _make_announcement_orm(audience="admins")
        now = utc_now()
        viewer = AuthorORM(
            author_id="user-1",
            github_user_id="gh-user-1",
            github_login="user1",
            display_name="用户 1",
            author_type=AuthorType.USER,
            is_admin=False,
        )
        assert is_visible(ann, viewer, now) is False

    def test_audience_admins_accepts_admin(self) -> None:
        """audience=admins 时应允许管理员查看者。"""
        ann = _make_announcement_orm(audience="admins")
        now = utc_now()
        viewer = AuthorORM(
            author_id="admin-1",
            github_user_id="gh-admin-1",
            github_login="admin1",
            display_name="管理员 1",
            author_type=AuthorType.USER,
            is_admin=True,
        )
        assert is_visible(ann, viewer, now) is True

    def test_audience_authors_with_plugin_requires_flag(self) -> None:
        """audience=authors_with_plugin 时要求 viewer_has_plugin=True。"""
        ann = _make_announcement_orm(audience="authors_with_plugin")
        now = utc_now()
        viewer = AuthorORM(
            author_id="user-1",
            github_user_id="gh-user-1",
            github_login="user1",
            display_name="用户 1",
            author_type=AuthorType.USER,
            is_admin=False,
        )
        assert is_visible(ann, viewer, now, viewer_has_plugin=False) is False
        assert is_visible(ann, viewer, now, viewer_has_plugin=True) is True

    def test_dismissed_not_visible(self) -> None:
        """已关闭的公告不可见。"""
        ann = _make_announcement_orm()
        now = utc_now()
        assert is_visible(ann, None, now, is_dismissed=True) is False

    def test_null_starts_at_treated_as_unbounded(self) -> None:
        """starts_at=None 表示公告没有开始时间限制。"""
        ann = _make_announcement_orm(starts_at=None)
        now = utc_now()
        assert is_visible(ann, None, now) is True

    def test_null_ends_at_treated_as_unbounded(self) -> None:
        """ends_at=None 表示公告永不过期。"""
        ann = _make_announcement_orm(ends_at=None)
        now = utc_now()
        assert is_visible(ann, None, now) is True


# ---------------------------------------------------------------------------
# list_active：最多显示一个弹窗（属性 3）
# ---------------------------------------------------------------------------


async def test_list_active_returns_visible_announcements() -> None:
    """list_active 应仅返回可见公告。"""
    async with session_scope() as session:
        admin = await _ensure_author(session, "admin-1", is_admin=True)
        service = AnnouncementsService(session)

        # 创建两条已启用的横幅公告。
        await service.create(
            AnnouncementCreate(title="横幅公告 1", display_mode="banner"),
            operator_id="admin-1",
        )
        await service.create(
            AnnouncementCreate(title="横幅公告 2", display_mode="banner"),
            operator_id="admin-1",
        )
        # 创建一条已禁用的横幅公告。
        await service.create(
            AnnouncementCreate(title="已禁用公告", display_mode="banner", enabled=False),
            operator_id="admin-1",
        )

        active = await service.list_active(admin)
        titles = [a.title for a in active]
        assert "横幅公告 1" in titles
        assert "横幅公告 2" in titles
        assert "已禁用公告" not in titles


async def test_create_ensures_operator_author_exists() -> None:
    """创建公告时，应补建缺失的操作者作者记录。"""
    async with session_scope() as session:
        service = AnnouncementsService(session)

        created = await service.create(
            AnnouncementCreate(title="无预置管理员", display_mode="banner", audience="all"),
            operator_id="mock-admin",
        )

        author = await session.get(AuthorORM, "mock-admin")

        assert created.created_by == "mock-admin"
        assert author is not None
        assert author.is_admin is True


async def test_list_active_single_modal_property() -> None:
    """最多应返回一条弹窗公告（属性 3）。"""
    async with session_scope() as session:
        admin = await _ensure_author(session, "admin-1", is_admin=True)
        service = AnnouncementsService(session)

        now = utc_now()
        # 创建三条 starts_at 不同的弹窗公告。
        await service.create(
            AnnouncementCreate(
                title="Modal Old",
                display_mode="modal",
                starts_at=now - timedelta(hours=3),
            ),
            operator_id="admin-1",
        )
        await service.create(
            AnnouncementCreate(
                title="Modal Mid",
                display_mode="modal",
                starts_at=now - timedelta(hours=2),
            ),
            operator_id="admin-1",
        )
        await service.create(
            AnnouncementCreate(
                title="Modal Recent",
                display_mode="modal",
                starts_at=now - timedelta(hours=1),
            ),
            operator_id="admin-1",
        )

        active = await service.list_active(admin)
        modals = [a for a in active if a.display_mode == "modal"]
        assert len(modals) == 1
        # 应选中 starts_at 最近的公告。
        assert modals[0].title == "Modal Recent"


async def test_list_active_modal_tie_broken_by_id_desc() -> None:
    """starts_at 相同时，应选中 id 最大的公告。"""
    async with session_scope() as session:
        admin = await _ensure_author(session, "admin-1", is_admin=True)
        service = AnnouncementsService(session)

        same_time = utc_now() - timedelta(hours=1)
        await service.create(
            AnnouncementCreate(
                title="Modal A",
                display_mode="modal",
                starts_at=same_time,
            ),
            operator_id="admin-1",
        )
        await service.create(
            AnnouncementCreate(
                title="Modal B",
                display_mode="modal",
                starts_at=same_time,
            ),
            operator_id="admin-1",
        )

        active = await service.list_active(admin)
        modals = [a for a in active if a.display_mode == "modal"]
        assert len(modals) == 1
        # 应选中 id 更大的公告（Modal B 是第二个创建的）。
        assert modals[0].title == "Modal B"


async def test_list_active_banners_not_capped() -> None:
    """多条横幅公告应全部返回。"""
    async with session_scope() as session:
        admin = await _ensure_author(session, "admin-1", is_admin=True)
        service = AnnouncementsService(session)

        for i in range(5):
            await service.create(
                AnnouncementCreate(title=f"横幅公告 {i}", display_mode="banner"),
                operator_id="admin-1",
            )

        active = await service.list_active(admin)
        banners = [a for a in active if a.display_mode == "banner"]
        assert len(banners) == 5


# ---------------------------------------------------------------------------
# 公告创建、更新、禁用与重新展示。
# ---------------------------------------------------------------------------


async def test_create_announcement_persists_and_audits() -> None:
    """创建公告时，应持久化公告并写入审计记录。"""
    async with session_scope() as session:
        await _ensure_author(session, "admin-1", is_admin=True)
        service = AnnouncementsService(session)

        dto = await service.create(
            AnnouncementCreate(
                title="你好，世界",
                body_markdown="# 欢迎",
                display_mode="banner",
                severity="warning",
                audience="logged_in",
            ),
            operator_id="admin-1",
        )

        assert dto.title == "你好，世界"
        assert dto.body_markdown == "# 欢迎"
        assert dto.display_mode == "banner"
        assert dto.severity == "warning"
        assert dto.audience == "logged_in"
        assert dto.enabled is True
        assert dto.dismiss_token == 0

        # 验证审计记录。
        audit_stmt = select(ReviewRecordORM).where(
            ReviewRecordORM.target_type == "announcement",
            ReviewRecordORM.target_id == str(dto.id),
            ReviewRecordORM.action == ReviewAction.CREATE_ANNOUNCEMENT,
        )
        audit = await session.scalar(audit_stmt)
        assert audit is not None
        assert audit.operator_id == "admin-1"


async def test_update_announcement_partial_fields() -> None:
    """更新时应仅修改已提供的字段。"""
    async with session_scope() as session:
        await _ensure_author(session, "admin-1", is_admin=True)
        service = AnnouncementsService(session)

        created = await service.create(
            AnnouncementCreate(title="原始标题", display_mode="banner"),
            operator_id="admin-1",
        )

        updated = await service.update(
            created.id,
            AnnouncementUpdate(title="更新后的标题"),
            operator_id="admin-1",
        )

        assert updated.title == "更新后的标题"
        assert updated.display_mode == "banner"  # 保持不变

        # 验证审计记录。
        audit_stmt = select(ReviewRecordORM).where(
            ReviewRecordORM.target_type == "announcement",
            ReviewRecordORM.target_id == str(created.id),
            ReviewRecordORM.action == ReviewAction.UPDATE_ANNOUNCEMENT,
        )
        audit = await session.scalar(audit_stmt)
        assert audit is not None


async def test_disable_sets_enabled_false_and_audits() -> None:
    """禁用公告时应设置 enabled=False，并记录 ARCHIVE_ANNOUNCEMENT。"""
    async with session_scope() as session:
        await _ensure_author(session, "admin-1", is_admin=True)
        service = AnnouncementsService(session)

        created = await service.create(
            AnnouncementCreate(title="启用的公告", display_mode="banner"),
            operator_id="admin-1",
        )
        assert created.enabled is True

        disabled = await service.disable(created.id, operator_id="admin-1")
        assert disabled.enabled is False

        # 验证审计记录。
        audit_stmt = select(ReviewRecordORM).where(
            ReviewRecordORM.target_type == "announcement",
            ReviewRecordORM.target_id == str(created.id),
            ReviewRecordORM.action == ReviewAction.ARCHIVE_ANNOUNCEMENT,
        )
        audit = await session.scalar(audit_stmt)
        assert audit is not None


async def test_resurface_bumps_dismiss_token_and_re_enables() -> None:
    """重新展示时应递增 dismiss_token 并重新启用公告。"""
    async with session_scope() as session:
        await _ensure_author(session, "admin-1", is_admin=True)
        service = AnnouncementsService(session)

        created = await service.create(
            AnnouncementCreate(title="重新展示此公告", display_mode="modal"),
            operator_id="admin-1",
        )
        assert created.dismiss_token == 0

        # 先禁用公告。
        await service.disable(created.id, operator_id="admin-1")

        # 重新展示公告。
        resurfaced = await service.resurface(created.id, operator_id="admin-1")
        assert resurfaced.dismiss_token == 1
        assert resurfaced.enabled is True


async def test_update_nonexistent_raises_404() -> None:
    """更新不存在的公告时，应返回 404。"""
    async with session_scope() as session:
        await _ensure_author(session, "admin-1", is_admin=True)
        service = AnnouncementsService(session)

        with pytest.raises(ApiError) as ctx:
            await service.update(
                9999,
                AnnouncementUpdate(title="不存在的公告"),
                operator_id="admin-1",
            )
        assert ctx.value.status_code == 404
        assert ctx.value.code == "ANNOUNCEMENT_NOT_FOUND"


# ---------------------------------------------------------------------------
# dismiss：幂等性（属性 9）
# ---------------------------------------------------------------------------


async def test_dismiss_records_dismissal() -> None:
    """关闭公告时应创建关闭记录。"""
    async with session_scope() as session:
        await _ensure_author(session, "admin-1", is_admin=True)
        await _ensure_author(session, "viewer-1")
        service = AnnouncementsService(session)

        created = await service.create(
            AnnouncementCreate(title="关闭此公告", display_mode="banner"),
            operator_id="admin-1",
        )

        ann_id, token = await service.dismiss(created.id, viewer_id="viewer-1")
        assert ann_id == created.id
        assert token == 0

        # 验证关闭记录存在。
        stmt = select(AnnouncementDismissalORM).where(
            AnnouncementDismissalORM.announcement_id == created.id,
            AnnouncementDismissalORM.author_id == "viewer-1",
        )
        row = await session.scalar(stmt)
        assert row is not None
        assert row.dismiss_token == 0


async def test_dismiss_idempotent_no_duplicate_rows() -> None:
    """重复关闭公告不应创建重复记录（属性 9）。"""
    async with session_scope() as session:
        await _ensure_author(session, "admin-1", is_admin=True)
        await _ensure_author(session, "viewer-1")
        service = AnnouncementsService(session)

        created = await service.create(
            AnnouncementCreate(title="幂等性测试", display_mode="banner"),
            operator_id="admin-1",
        )

        # 多次关闭公告。
        await service.dismiss(created.id, viewer_id="viewer-1")
        await service.dismiss(created.id, viewer_id="viewer-1")
        await service.dismiss(created.id, viewer_id="viewer-1")

        # 统计关闭记录数。
        from sqlalchemy import func

        count = await session.scalar(
            select(func.count())
            .select_from(AnnouncementDismissalORM)
            .where(
                AnnouncementDismissalORM.announcement_id == created.id,
                AnnouncementDismissalORM.author_id == "viewer-1",
            )
        )
        assert count == 1


async def test_dismiss_nonexistent_raises_404() -> None:
    """关闭不存在的公告时，应返回 404。"""
    async with session_scope() as session:
        await _ensure_author(session, "viewer-1")
        service = AnnouncementsService(session)

        with pytest.raises(ApiError) as ctx:
            await service.dismiss(9999, viewer_id="viewer-1")
        assert ctx.value.status_code == 404
        assert ctx.value.code == "ANNOUNCEMENT_NOT_FOUND"


async def test_dismissed_announcement_not_in_list_active() -> None:
    """已关闭的公告不应出现在 list_active 中。"""
    async with session_scope() as session:
        await _ensure_author(session, "admin-1", is_admin=True)
        viewer = await _ensure_author(session, "viewer-1")
        service = AnnouncementsService(session)

        created = await service.create(
            AnnouncementCreate(title="即将关闭的公告", display_mode="banner"),
            operator_id="admin-1",
        )

        # 关闭前应可见。
        active = await service.list_active(viewer)
        assert any(a.id == created.id for a in active)

        # 关闭公告。
        await service.dismiss(created.id, viewer_id="viewer-1")

        # 关闭后应不可见。
        active = await service.list_active(viewer)
        assert not any(a.id == created.id for a in active)


async def test_resurface_invalidates_old_dismissals() -> None:
    """重新展示后，曾关闭公告的查看者应能再次看到公告。"""
    async with session_scope() as session:
        await _ensure_author(session, "admin-1", is_admin=True)
        viewer = await _ensure_author(session, "viewer-1")
        service = AnnouncementsService(session)

        created = await service.create(
            AnnouncementCreate(title="重新展示测试", display_mode="banner"),
            operator_id="admin-1",
        )

        # 在 token 为 0 时关闭公告。
        await service.dismiss(created.id, viewer_id="viewer-1")
        active = await service.list_active(viewer)
        assert not any(a.id == created.id for a in active)

        # 重新展示会将 token 递增为 1。
        await service.resurface(created.id, operator_id="admin-1")

        # 此时旧的关闭记录（token=0）不再匹配。
        active = await service.list_active(viewer)
        assert any(a.id == created.id for a in active)


# ---------------------------------------------------------------------------
# admin_list
# ---------------------------------------------------------------------------


async def test_admin_list_returns_all_with_pagination() -> None:
    """admin_list 应返回所有公告，并提供正确的总数。"""
    async with session_scope() as session:
        await _ensure_author(session, "admin-1", is_admin=True)
        service = AnnouncementsService(session)

        for i in range(5):
            await service.create(
                AnnouncementCreate(title=f"公告 {i}", display_mode="banner"),
                operator_id="admin-1",
            )

        items, total = await service.admin_list(offset=0, limit=3)
        assert total == 5
        assert len(items) == 3

        items2, total2 = await service.admin_list(offset=3, limit=3)
        assert total2 == 5
        assert len(items2) == 2
