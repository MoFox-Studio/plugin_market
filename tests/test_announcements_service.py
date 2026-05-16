"""Unit tests for ``AnnouncementsService`` (task 7).

These tests exercise the announcement management, visibility, and dismissal
surface of :class:`plugin_market_backend.services.announcements_service.AnnouncementsService`
without going through the HTTP layer:

* ``is_visible`` pure function — schedule, audience, enabled, dismissed
* ``list_active`` — single-modal property (Property 3)
* ``create`` / ``update`` / ``disable`` / ``resurface`` — CRUD + audit trail
* ``dismiss`` — INSERT OR IGNORE idempotence (Property 9)
* ``admin_list`` — paginated listing
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
# Setup helpers
# ---------------------------------------------------------------------------


async def _ensure_author(
    session,
    author_id: str,
    *,
    is_admin: bool = False,
    github_login: str | None = None,
) -> AuthorORM:
    """Create an author row if it does not exist."""

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
    """Create an in-memory AnnouncementORM for pure-function tests.

    Uses the normal constructor so SQLAlchemy instrumentation is initialized.
    """

    now = utc_now()
    return AnnouncementORM(
        id=id,
        title=f"Announcement {id}",
        body_markdown="body",
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
# is_visible pure function tests
# ---------------------------------------------------------------------------


class TestIsVisible:
    """Tests for the module-level ``is_visible`` pure function."""

    def test_enabled_all_audience_no_schedule_visible(self) -> None:
        """An enabled announcement with audience=all and no schedule is visible."""

        ann = _make_announcement_orm(enabled=True, audience="all")
        now = utc_now()
        assert is_visible(ann, None, now) is True

    def test_disabled_not_visible(self) -> None:
        """A disabled announcement is never visible."""

        ann = _make_announcement_orm(enabled=False)
        now = utc_now()
        assert is_visible(ann, None, now) is False

    def test_before_starts_at_not_visible(self) -> None:
        """An announcement before its starts_at is not visible."""

        future = utc_now() + timedelta(hours=1)
        ann = _make_announcement_orm(starts_at=future)
        now = utc_now()
        assert is_visible(ann, None, now) is False

    def test_after_ends_at_not_visible(self) -> None:
        """An announcement after its ends_at is not visible."""

        past = utc_now() - timedelta(hours=1)
        ann = _make_announcement_orm(ends_at=past)
        now = utc_now()
        assert is_visible(ann, None, now) is False

    def test_within_schedule_visible(self) -> None:
        """An announcement within its schedule window is visible."""

        now = utc_now()
        ann = _make_announcement_orm(
            starts_at=now - timedelta(hours=1),
            ends_at=now + timedelta(hours=1),
        )
        assert is_visible(ann, None, now) is True

    def test_audience_logged_in_rejects_anonymous(self) -> None:
        """audience=logged_in should reject anonymous viewers."""

        ann = _make_announcement_orm(audience="logged_in")
        now = utc_now()
        assert is_visible(ann, None, now) is False

    def test_audience_logged_in_accepts_viewer(self) -> None:
        """audience=logged_in should accept authenticated viewers."""

        ann = _make_announcement_orm(audience="logged_in")
        now = utc_now()
        viewer = AuthorORM(
            author_id="user-1",
            github_user_id="gh-user-1",
            github_login="user1",
            display_name="User 1",
            author_type=AuthorType.USER,
            is_admin=False,
        )
        assert is_visible(ann, viewer, now) is True

    def test_audience_admins_rejects_non_admin(self) -> None:
        """audience=admins should reject non-admin viewers."""

        ann = _make_announcement_orm(audience="admins")
        now = utc_now()
        viewer = AuthorORM(
            author_id="user-1",
            github_user_id="gh-user-1",
            github_login="user1",
            display_name="User 1",
            author_type=AuthorType.USER,
            is_admin=False,
        )
        assert is_visible(ann, viewer, now) is False

    def test_audience_admins_accepts_admin(self) -> None:
        """audience=admins should accept admin viewers."""

        ann = _make_announcement_orm(audience="admins")
        now = utc_now()
        viewer = AuthorORM(
            author_id="admin-1",
            github_user_id="gh-admin-1",
            github_login="admin1",
            display_name="Admin 1",
            author_type=AuthorType.USER,
            is_admin=True,
        )
        assert is_visible(ann, viewer, now) is True

    def test_audience_authors_with_plugin_requires_flag(self) -> None:
        """audience=authors_with_plugin needs viewer_has_plugin=True."""

        ann = _make_announcement_orm(audience="authors_with_plugin")
        now = utc_now()
        viewer = AuthorORM(
            author_id="user-1",
            github_user_id="gh-user-1",
            github_login="user1",
            display_name="User 1",
            author_type=AuthorType.USER,
            is_admin=False,
        )
        assert is_visible(ann, viewer, now, viewer_has_plugin=False) is False
        assert is_visible(ann, viewer, now, viewer_has_plugin=True) is True

    def test_dismissed_not_visible(self) -> None:
        """A dismissed announcement is not visible."""

        ann = _make_announcement_orm()
        now = utc_now()
        assert is_visible(ann, None, now, is_dismissed=True) is False

    def test_null_starts_at_treated_as_unbounded(self) -> None:
        """starts_at=None means the announcement is always past its start."""

        ann = _make_announcement_orm(starts_at=None)
        now = utc_now()
        assert is_visible(ann, None, now) is True

    def test_null_ends_at_treated_as_unbounded(self) -> None:
        """ends_at=None means the announcement never expires."""

        ann = _make_announcement_orm(ends_at=None)
        now = utc_now()
        assert is_visible(ann, None, now) is True


# ---------------------------------------------------------------------------
# list_active — single-modal property (Property 3)
# ---------------------------------------------------------------------------


async def test_list_active_returns_visible_announcements() -> None:
    """list_active should return only visible announcements."""

    async with session_scope() as session:
        admin = await _ensure_author(session, "admin-1", is_admin=True)
        service = AnnouncementsService(session)

        # Create two enabled banners.
        await service.create(
            AnnouncementCreate(title="Banner 1", display_mode="banner"),
            operator_id="admin-1",
        )
        await service.create(
            AnnouncementCreate(title="Banner 2", display_mode="banner"),
            operator_id="admin-1",
        )
        # Create one disabled banner.
        await service.create(
            AnnouncementCreate(title="Disabled", display_mode="banner", enabled=False),
            operator_id="admin-1",
        )

        active = await service.list_active(admin)
        titles = [a.title for a in active]
        assert "Banner 1" in titles
        assert "Banner 2" in titles
        assert "Disabled" not in titles


async def test_create_ensures_operator_author_exists() -> None:
    """Create should backfill a missing operator author record."""

    async with session_scope() as session:
        service = AnnouncementsService(session)

        created = await service.create(
            AnnouncementCreate(title="Seedless Admin", display_mode="banner", audience="all"),
            operator_id="mock-admin",
        )

        author = await session.get(AuthorORM, "mock-admin")

        assert created.created_by == "mock-admin"
        assert author is not None
        assert author.is_admin is True


async def test_list_active_single_modal_property() -> None:
    """At most one modal announcement should be returned (Property 3)."""

    async with session_scope() as session:
        admin = await _ensure_author(session, "admin-1", is_admin=True)
        service = AnnouncementsService(session)

        now = utc_now()
        # Create three modal announcements with different starts_at.
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
        # The most recent starts_at should win.
        assert modals[0].title == "Modal Recent"


async def test_list_active_modal_tie_broken_by_id_desc() -> None:
    """When starts_at is the same, the highest id wins."""

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
        # Higher id (Modal B created second) should win.
        assert modals[0].title == "Modal B"


async def test_list_active_banners_not_capped() -> None:
    """Multiple banner announcements should all be returned."""

    async with session_scope() as session:
        admin = await _ensure_author(session, "admin-1", is_admin=True)
        service = AnnouncementsService(session)

        for i in range(5):
            await service.create(
                AnnouncementCreate(title=f"Banner {i}", display_mode="banner"),
                operator_id="admin-1",
            )

        active = await service.list_active(admin)
        banners = [a for a in active if a.display_mode == "banner"]
        assert len(banners) == 5


# ---------------------------------------------------------------------------
# create / update / disable / resurface
# ---------------------------------------------------------------------------


async def test_create_announcement_persists_and_audits() -> None:
    """Creating an announcement should persist it and write an audit record."""

    async with session_scope() as session:
        await _ensure_author(session, "admin-1", is_admin=True)
        service = AnnouncementsService(session)

        dto = await service.create(
            AnnouncementCreate(
                title="Hello World",
                body_markdown="# Welcome",
                display_mode="banner",
                severity="warning",
                audience="logged_in",
            ),
            operator_id="admin-1",
        )

        assert dto.title == "Hello World"
        assert dto.body_markdown == "# Welcome"
        assert dto.display_mode == "banner"
        assert dto.severity == "warning"
        assert dto.audience == "logged_in"
        assert dto.enabled is True
        assert dto.dismiss_token == 0

        # Verify audit record.
        audit_stmt = select(ReviewRecordORM).where(
            ReviewRecordORM.target_type == "announcement",
            ReviewRecordORM.target_id == str(dto.id),
            ReviewRecordORM.action == ReviewAction.CREATE_ANNOUNCEMENT,
        )
        audit = await session.scalar(audit_stmt)
        assert audit is not None
        assert audit.operator_id == "admin-1"


async def test_update_announcement_partial_fields() -> None:
    """Updating should only mutate the fields provided."""

    async with session_scope() as session:
        await _ensure_author(session, "admin-1", is_admin=True)
        service = AnnouncementsService(session)

        created = await service.create(
            AnnouncementCreate(title="Original", display_mode="banner"),
            operator_id="admin-1",
        )

        updated = await service.update(
            created.id,
            AnnouncementUpdate(title="Updated Title"),
            operator_id="admin-1",
        )

        assert updated.title == "Updated Title"
        assert updated.display_mode == "banner"  # unchanged

        # Verify audit record.
        audit_stmt = select(ReviewRecordORM).where(
            ReviewRecordORM.target_type == "announcement",
            ReviewRecordORM.target_id == str(created.id),
            ReviewRecordORM.action == ReviewAction.UPDATE_ANNOUNCEMENT,
        )
        audit = await session.scalar(audit_stmt)
        assert audit is not None


async def test_disable_sets_enabled_false_and_audits() -> None:
    """Disabling should set enabled=False and write ARCHIVE_ANNOUNCEMENT."""

    async with session_scope() as session:
        await _ensure_author(session, "admin-1", is_admin=True)
        service = AnnouncementsService(session)

        created = await service.create(
            AnnouncementCreate(title="Active", display_mode="banner"),
            operator_id="admin-1",
        )
        assert created.enabled is True

        disabled = await service.disable(created.id, operator_id="admin-1")
        assert disabled.enabled is False

        # Verify audit record.
        audit_stmt = select(ReviewRecordORM).where(
            ReviewRecordORM.target_type == "announcement",
            ReviewRecordORM.target_id == str(created.id),
            ReviewRecordORM.action == ReviewAction.ARCHIVE_ANNOUNCEMENT,
        )
        audit = await session.scalar(audit_stmt)
        assert audit is not None


async def test_resurface_bumps_dismiss_token_and_re_enables() -> None:
    """Resurfacing should increment dismiss_token and re-enable."""

    async with session_scope() as session:
        await _ensure_author(session, "admin-1", is_admin=True)
        service = AnnouncementsService(session)

        created = await service.create(
            AnnouncementCreate(title="Resurface Me", display_mode="modal"),
            operator_id="admin-1",
        )
        assert created.dismiss_token == 0

        # Disable first.
        await service.disable(created.id, operator_id="admin-1")

        # Resurface.
        resurfaced = await service.resurface(created.id, operator_id="admin-1")
        assert resurfaced.dismiss_token == 1
        assert resurfaced.enabled is True


async def test_update_nonexistent_raises_404() -> None:
    """Updating a non-existent announcement should raise 404."""

    async with session_scope() as session:
        await _ensure_author(session, "admin-1", is_admin=True)
        service = AnnouncementsService(session)

        with pytest.raises(ApiError) as ctx:
            await service.update(
                9999,
                AnnouncementUpdate(title="Ghost"),
                operator_id="admin-1",
            )
        assert ctx.value.status_code == 404
        assert ctx.value.code == "ANNOUNCEMENT_NOT_FOUND"


# ---------------------------------------------------------------------------
# dismiss — idempotence (Property 9)
# ---------------------------------------------------------------------------


async def test_dismiss_records_dismissal() -> None:
    """Dismissing should create a dismissal record."""

    async with session_scope() as session:
        await _ensure_author(session, "admin-1", is_admin=True)
        await _ensure_author(session, "viewer-1")
        service = AnnouncementsService(session)

        created = await service.create(
            AnnouncementCreate(title="Dismiss Me", display_mode="banner"),
            operator_id="admin-1",
        )

        ann_id, token = await service.dismiss(created.id, viewer_id="viewer-1")
        assert ann_id == created.id
        assert token == 0

        # Verify the dismissal row exists.
        stmt = select(AnnouncementDismissalORM).where(
            AnnouncementDismissalORM.announcement_id == created.id,
            AnnouncementDismissalORM.author_id == "viewer-1",
        )
        row = await session.scalar(stmt)
        assert row is not None
        assert row.dismiss_token == 0


async def test_dismiss_idempotent_no_duplicate_rows() -> None:
    """Repeated dismissals should not create duplicate rows (Property 9)."""

    async with session_scope() as session:
        await _ensure_author(session, "admin-1", is_admin=True)
        await _ensure_author(session, "viewer-1")
        service = AnnouncementsService(session)

        created = await service.create(
            AnnouncementCreate(title="Idempotent", display_mode="banner"),
            operator_id="admin-1",
        )

        # Dismiss multiple times.
        await service.dismiss(created.id, viewer_id="viewer-1")
        await service.dismiss(created.id, viewer_id="viewer-1")
        await service.dismiss(created.id, viewer_id="viewer-1")

        # Count dismissal rows.
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
    """Dismissing a non-existent announcement should raise 404."""

    async with session_scope() as session:
        await _ensure_author(session, "viewer-1")
        service = AnnouncementsService(session)

        with pytest.raises(ApiError) as ctx:
            await service.dismiss(9999, viewer_id="viewer-1")
        assert ctx.value.status_code == 404
        assert ctx.value.code == "ANNOUNCEMENT_NOT_FOUND"


async def test_dismissed_announcement_not_in_list_active() -> None:
    """A dismissed announcement should not appear in list_active."""

    async with session_scope() as session:
        await _ensure_author(session, "admin-1", is_admin=True)
        viewer = await _ensure_author(session, "viewer-1")
        service = AnnouncementsService(session)

        created = await service.create(
            AnnouncementCreate(title="Will Dismiss", display_mode="banner"),
            operator_id="admin-1",
        )

        # Before dismiss — visible.
        active = await service.list_active(viewer)
        assert any(a.id == created.id for a in active)

        # Dismiss.
        await service.dismiss(created.id, viewer_id="viewer-1")

        # After dismiss — not visible.
        active = await service.list_active(viewer)
        assert not any(a.id == created.id for a in active)


async def test_resurface_invalidates_old_dismissals() -> None:
    """After resurface, previously dismissed viewers should see it again."""

    async with session_scope() as session:
        await _ensure_author(session, "admin-1", is_admin=True)
        viewer = await _ensure_author(session, "viewer-1")
        service = AnnouncementsService(session)

        created = await service.create(
            AnnouncementCreate(title="Resurface Test", display_mode="banner"),
            operator_id="admin-1",
        )

        # Dismiss at token 0.
        await service.dismiss(created.id, viewer_id="viewer-1")
        active = await service.list_active(viewer)
        assert not any(a.id == created.id for a in active)

        # Resurface bumps token to 1.
        await service.resurface(created.id, operator_id="admin-1")

        # Now the old dismissal (token=0) no longer matches.
        active = await service.list_active(viewer)
        assert any(a.id == created.id for a in active)


# ---------------------------------------------------------------------------
# admin_list
# ---------------------------------------------------------------------------


async def test_admin_list_returns_all_with_pagination() -> None:
    """admin_list should return all announcements with correct total."""

    async with session_scope() as session:
        await _ensure_author(session, "admin-1", is_admin=True)
        service = AnnouncementsService(session)

        for i in range(5):
            await service.create(
                AnnouncementCreate(title=f"Ann {i}", display_mode="banner"),
                operator_id="admin-1",
            )

        items, total = await service.admin_list(offset=0, limit=3)
        assert total == 5
        assert len(items) == 3

        items2, total2 = await service.admin_list(offset=3, limit=3)
        assert total2 == 5
        assert len(items2) == 2
