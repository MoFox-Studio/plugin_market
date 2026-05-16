"""Announcement management, visibility, and dismissal service.

Implements Requirements 12 and 13 — admin-managed announcements with schedule,
audience targeting, dismissal, and the single-modal property (Property 3).

Key design decisions:

* :func:`is_visible` is a **pure function** (Property 2). It does not read the
  session; callers must precompute ``is_dismissed`` and ``viewer_has_plugin``.
* :meth:`AnnouncementsService.list_active` enforces Property 3: at most one
  ``display_mode='modal'`` announcement is returned per viewer, selected by
  ``starts_at desc, id desc``.
* :meth:`AnnouncementsService.dismiss` uses ``INSERT OR IGNORE`` semantics
  (Property 9 — dismissal idempotence) via the unique constraint
  ``(announcement_id, author_id, dismiss_token)``.
* All write paths call :meth:`_audit` to append a ``ReviewRecordORM`` row
  (Property 8 — audit trail completeness).
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
from plugin_market_backend.service import MarketService
from plugin_market_backend.services._audience import audience_matches

if TYPE_CHECKING:
    from plugin_market_backend.orm import AuthorORM


# ---------------------------------------------------------------------------
# Timezone helpers
# ---------------------------------------------------------------------------


def _strip_tz(dt: datetime) -> datetime:
    """Strip timezone info for safe comparison.

    SQLite round-trips tz-aware datetimes as naive (no tzinfo). To avoid
    ``TypeError: can't compare offset-naive and offset-aware datetimes``
    we normalize both sides to naive UTC before comparing.
    """

    if dt.tzinfo is not None:
        return dt.replace(tzinfo=None)
    return dt


# ---------------------------------------------------------------------------
# Pure visibility predicate (Property 2)
# ---------------------------------------------------------------------------


def is_visible(
    announcement: "AnnouncementORM",
    viewer: "AuthorORM | None",
    now: datetime,
    *,
    is_dismissed: bool = False,
    viewer_has_plugin: bool = False,
) -> bool:
    """Return whether ``announcement`` should be shown to ``viewer`` at ``now``.

    This is a **pure function** — it does not read the database session. All
    side-effect-dependent inputs (``is_dismissed``, ``viewer_has_plugin``) must
    be precomputed by the caller.

    The predicate directly encodes Property 2 (Announcement Visibility):

        visible iff enabled ∧ schedule_hit ∧ audience_match ∧ ¬dismissed

    Args:
        announcement: The ORM row to evaluate.
        viewer: The current authenticated author, or ``None`` for anonymous.
        now: The server time to evaluate the schedule against.
        is_dismissed: Whether the viewer has dismissed this announcement at
            the current ``dismiss_token``.
        viewer_has_plugin: Whether the viewer owns at least one plugin.
            Required only when ``audience == 'authors_with_plugin'``.

    Returns:
        ``True`` if the announcement should be shown to the viewer.
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
# Service class
# ---------------------------------------------------------------------------


class AnnouncementsService:
    """Manage announcements and per-viewer dismissals.

    All write methods append an audit trail record via :meth:`_audit`.
    """

    def __init__(self, session: AsyncSession) -> None:
        """Bind the service to one transactional async session."""

        self.session = session

    # ------------------------------------------------------------------
    # Public query: active announcements for a viewer
    # ------------------------------------------------------------------

    async def list_active(
        self,
        viewer: "AuthorORM | None",
        *,
        now: datetime | None = None,
        viewer_has_plugin: bool = False,
    ) -> list[AnnouncementDTO]:
        """Return announcements visible to ``viewer`` at ``now``.

        Enforces **Property 3** (single-modal): if multiple modal
        announcements are eligible, only the one with the most recent
        ``starts_at`` (ties broken by highest ``id``) is included.

        Banner announcements are returned in the same order
        (``starts_at desc, id desc``) without a cap.
        """

        if now is None:
            now = utc_now()

        # Fetch all enabled announcements that are within schedule.
        stmt = select(AnnouncementORM).where(AnnouncementORM.enabled.is_(True))
        rows: Sequence[AnnouncementORM] = list(
            (await self.session.scalars(stmt)).all()
        )

        # Precompute dismissals for the viewer.
        dismissed_set: set[tuple[int, int]] = set()
        if viewer is not None:
            dismiss_stmt = select(
                AnnouncementDismissalORM.announcement_id,
                AnnouncementDismissalORM.dismiss_token,
            ).where(AnnouncementDismissalORM.author_id == viewer.author_id)
            for row in await self.session.execute(dismiss_stmt):
                dismissed_set.add((row[0], row[1]))

        # Filter through the pure visibility predicate.
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

        # Sort by starts_at desc (nulls last), id desc for deterministic order.
        def _sort_key(a: AnnouncementORM) -> tuple:
            # Use a very old date for nulls so they sort last in desc order.
            starts = a.starts_at if a.starts_at is not None else datetime.min
            return (starts, a.id)

        visible.sort(key=_sort_key, reverse=True)

        # Property 3: at most one modal.
        banners: list[AnnouncementORM] = []
        modal_picked: AnnouncementORM | None = None
        for ann in visible:
            if ann.display_mode == "modal":
                if modal_picked is None:
                    modal_picked = ann
                # Skip additional modals.
            else:
                banners.append(ann)

        result: list[AnnouncementORM] = banners
        if modal_picked is not None:
            result.append(modal_picked)

        # Re-sort the final list by starts_at desc, id desc.
        result.sort(key=_sort_key, reverse=True)

        return [_orm_to_dto(ann) for ann in result]

    # ------------------------------------------------------------------
    # Admin: CRUD
    # ------------------------------------------------------------------

    async def create(
        self,
        payload: AnnouncementCreate,
        operator_id: str,
    ) -> AnnouncementDTO:
        """Create a new announcement and append an audit record.

        Args:
            payload: Validated creation payload.
            operator_id: The admin performing the action.

        Returns:
            The created announcement as a DTO.
        """

        # Legacy admin-token flows use a synthetic operator id. Ensure the
        # author row exists before writing an announcement that references it.
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
        """Update an existing announcement and append an audit record.

        Only fields explicitly set in ``payload`` are mutated.
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
        """Disable (archive) an announcement immediately.

        Sets ``enabled = False`` and appends an ``ARCHIVE_ANNOUNCEMENT``
        audit record.
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
        """Resurface an announcement by bumping its ``dismiss_token``.

        This invalidates all existing dismissals so every viewer sees the
        announcement again. The operation also re-enables the announcement
        if it was disabled.
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
    # Dismiss
    # ------------------------------------------------------------------

    async def dismiss(
        self,
        announcement_id: int,
        viewer_id: str,
    ) -> tuple[int, int]:
        """Record a dismissal for ``viewer_id`` on ``announcement_id``.

        Uses INSERT OR IGNORE semantics (Property 9 — idempotence): if the
        viewer has already dismissed this announcement at the current
        ``dismiss_token``, the operation is a no-op.

        Returns:
            A tuple of ``(announcement_id, dismiss_token)`` for the response.

        Raises:
            ApiError(404): if the announcement does not exist.
        """

        record = await self._get_or_404(announcement_id)

        dismissal = AnnouncementDismissalORM(
            announcement_id=announcement_id,
            author_id=viewer_id,
            dismiss_token=record.dismiss_token,
            created_at=utc_now(),
        )

        # Use a savepoint so the IntegrityError (duplicate dismiss) does not
        # invalidate the outer transaction.
        try:
            async with self.session.begin_nested():
                self.session.add(dismissal)
        except IntegrityError:
            # Unique constraint violation — already dismissed at this token.
            # This is the expected idempotent path (Property 9).
            pass

        return (announcement_id, record.dismiss_token)

    # ------------------------------------------------------------------
    # Admin: list all announcements (paginated)
    # ------------------------------------------------------------------

    async def admin_list(
        self,
        *,
        offset: int = 0,
        limit: int = 50,
    ) -> tuple[list[AnnouncementDTO], int]:
        """Return all announcements for the admin console (paginated).

        Returns:
            A tuple of ``(items, total_count)``.
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
    # Internal helpers
    # ------------------------------------------------------------------

    async def _get_or_404(self, announcement_id: int) -> AnnouncementORM:
        """Fetch an announcement by id or raise 404."""

        record = await self.session.get(AnnouncementORM, announcement_id)
        if record is None:
            raise ApiError(
                404,
                "ANNOUNCEMENT_NOT_FOUND",
                "Announcement not found.",
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
        """Append a ``ReviewRecordORM`` row for an announcement write.

        This is synchronous (no await) because it only adds the ORM object to
        the session; the actual INSERT happens on the next ``flush()``.
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
# Module-level helpers
# ---------------------------------------------------------------------------


def _orm_to_dto(record: AnnouncementORM) -> AnnouncementDTO:
    """Project an ``AnnouncementORM`` row into the API DTO."""

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
