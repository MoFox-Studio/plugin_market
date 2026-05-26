"""Inbox derivation, fan-out, and query service.

This module owns every derived ``inbox_messages`` row in the system. Its
shape mirrors the surfaces called out in the design document:

* :meth:`InboxService.parse_mentions` — pure-ish content scan that resolves
  ``@<github_login>`` tokens to existing authors (Requirement 9.1-9.3,
  Property 10).
* :meth:`InboxService.fan_out_for_comment` — write ``comment_mentions`` rows
  and derive ``mention`` / ``reply`` inbox messages with the reply-over-mention
  precedence rule from Requirement 10.6 / Property 4.
* :meth:`InboxService.fan_out_for_governance` — derive ``governance`` inbox
  messages for owner + maintainers when an admin governance action lands on
  a plugin, with a 5-second sliding-window dedupe so a noisy admin tab does
  not flood inboxes (Requirements 11.4-11.7).
* :meth:`InboxService.fan_out_for_announcement` — derive ``announcement``
  inbox messages for an explicit recipient iterable; the caller decides
  whether to invoke this based on ``announcement.emit_inbox``.
* :meth:`InboxService.revoke_messages_for_comment` — when a comment is
  deleted, mark any derived inbox messages as ``revoked`` so they remain
  auditable but disappear from active flows (Requirement 9.6).
* :meth:`InboxService.list_messages`,
  :meth:`InboxService.unread_count`,
  :meth:`InboxService.mark_read`,
  :meth:`InboxService.mark_all_read` — viewer-scoped query / mutation
  surface backing ``GET /api/v1/inbox/*`` (Requirements 11.1-11.8).

All write paths leverage the unique constraint
``unique_inbox_dedup(recipient_id, dedup_key)`` declared on
:class:`plugin_market_backend.orm.InboxMessageORM` so duplicate fan-out
events upsert rather than insert. The dedup key formats are stable across
calls so out-of-band callers (e.g. admin retries) can reason about them:

* ``mention:{comment_id}:{recipient_id}`` for mentions,
* ``reply:{comment_id}:{recipient_id}`` for replies,
* ``governance:{plugin_id}:{action}:{ts_micros}`` for governance, where
  the timestamp suffix is the microsecond epoch the row was first created
  in. The 5-second sliding window dedupe is enforced in code (we look up
  any existing governance row for the same (recipient, plugin, action)
  within the last 5 seconds and refresh its ``created_at`` instead of
  inserting). Microsecond resolution ensures that two governance fan-outs
  arriving in the same wall-clock second but separated by more than the
  dedupe window (e.g. a delayed retry) still produce distinct dedup_keys
  and therefore distinct inbox rows.
* ``announcement:{announcement_id}:{recipient_id}:{dismiss_token}`` for
  announcements, so an admin "resurface" (which bumps ``dismiss_token``)
  yields a fresh inbox message without colliding with the prior one.
"""

from __future__ import annotations

import re
from datetime import timedelta
from typing import Any, Iterable

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from plugin_market_backend.orm import (
    AnnouncementORM,
    AuthorFollowORM,
    AuthorORM,
    CommentMentionORM,
    InboxMessageORM,
    PluginCommentORM,
    PluginMaintainerORM,
    PluginORM,
    PluginSubscriptionORM,
    utc_now,
)
from plugin_market_backend.schemas import (
    InboxMessage,
    InboxMessageLink,
    InboxMessageSource,
)


# ---------------------------------------------------------------------------
# Module-level constants
# ---------------------------------------------------------------------------


MENTION_RE = re.compile(
    r"@([A-Za-z0-9](?:[A-Za-z0-9-]{0,38}))(?![A-Za-z0-9-])"
)
"""GitHub-login mention pattern.

Matches ``@<login>`` where ``<login>`` is a 1-39 character GitHub username:
starts with alphanumeric, contains only alphanumerics or single dashes, and
is not followed by another alphanumeric / dash (so ``@foo-bar`` matches once,
not ``foo`` then ``bar``).
"""


GOVERNANCE_DEDUPE_WINDOW = timedelta(seconds=5)
"""Sliding window in which a duplicate governance fan-out is suppressed."""


PREVIEW_MAX_LENGTH = 200
"""Maximum number of characters retained in the inbox payload preview."""


_VALID_TYPES: frozenset[str] = frozenset(
    {"mention", "reply", "governance", "announcement", "author_activity", "plugin_activity", "system"}
)


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------


class InboxService:
    """Derive and serve per-recipient inbox messages."""

    def __init__(self, session: AsyncSession) -> None:
        """Bind the service to one transactional async session."""

        self.session = session

    # ------------------------------------------------------------------
    # Mention parsing (Property 10 / Requirements 9.1-9.3)
    # ------------------------------------------------------------------

    async def parse_mentions(
        self, content: str, sender_id: str
    ) -> list[AuthorORM]:
        """Resolve ``@<login>`` tokens in ``content`` to existing authors.

        Tokens that do not match an existing author are silently dropped
        (Requirement 9.3). The sender's own author row is filtered out so
        we never write a self-mention to the inbox (Requirement 9.4 /
        Property 4). The result is deduplicated by ``author_id``.

        Args:
            content: The raw comment content.
            sender_id: The author submitting the comment. Self-mentions
                are filtered out.

        Returns:
            A list of :class:`AuthorORM` rows for the resolved mentions, in
            the order their first matching ``@<login>`` token appeared.
        """

        if not content:
            return []

        # Preserve first-occurrence order so the resulting list is stable.
        ordered_logins: list[str] = []
        seen_logins: set[str] = set()
        for match in MENTION_RE.finditer(content):
            login = match.group(1)
            if login in seen_logins:
                continue
            seen_logins.add(login)
            ordered_logins.append(login)

        if not ordered_logins:
            return []

        rows = list(
            (
                await self.session.scalars(
                    select(AuthorORM).where(
                        AuthorORM.github_login.in_(ordered_logins)
                    )
                )
            ).all()
        )
        by_login: dict[str, AuthorORM] = {row.github_login: row for row in rows}

        result: list[AuthorORM] = []
        seen_ids: set[str] = set()
        for login in ordered_logins:
            author = by_login.get(login)
            if author is None:
                continue
            if author.author_id == sender_id:
                continue
            if author.author_id in seen_ids:
                continue
            seen_ids.add(author.author_id)
            result.append(author)
        return result

    # ------------------------------------------------------------------
    # Fan-out: comments (Requirements 9.4, 10.5, 10.6)
    # ------------------------------------------------------------------

    async def fan_out_for_comment(
        self,
        comment: PluginCommentORM,
        mentions: Iterable[AuthorORM],
    ) -> None:
        """Persist ``comment_mentions`` rows and derive mention/reply messages.

        The fan-out follows Property 4's reply-over-mention rule: when a
        single comment both replies to and mentions the same recipient, only
        the ``reply`` message is emitted; the mention message is suppressed
        for that recipient. All other mentioned authors still receive a
        ``mention`` message.

        Args:
            comment: The freshly-flushed comment ORM row. Must have an
                assigned ``id`` (i.e. caller has flushed the session).
            mentions: Author rows for every resolved mention. Self-mentions
                must already be filtered out by the caller (typically via
                :meth:`parse_mentions`).
        """

        if comment.id is None:  # pragma: no cover - defensive
            raise ValueError(
                "fan_out_for_comment requires a flushed comment with an id"
            )

        sender_id = comment.author_id
        mention_authors: list[AuthorORM] = [
            author
            for author in mentions
            if author.author_id != sender_id
        ]

        # Persist normalized comment_mentions rows for every resolved mention
        # (even the one whose inbox message is suppressed by the reply rule),
        # so downstream queries / property tests see a complete graph.
        for author in mention_authors:
            already = await self.session.scalar(
                select(CommentMentionORM.id).where(
                    CommentMentionORM.comment_id == comment.id,
                    CommentMentionORM.mentioned_author_id == author.author_id,
                )
            )
            if already is None:
                self.session.add(
                    CommentMentionORM(
                        comment_id=comment.id,
                        mentioned_author_id=author.author_id,
                        created_at=utc_now(),
                    )
                )

        # Resolve the reply target (if any).
        reply_recipient_id: str | None = None
        if comment.parent_id is not None:
            parent = await self.session.get(
                PluginCommentORM, comment.parent_id
            )
            if (
                parent is not None
                and not parent.is_deleted
                and parent.author_id != sender_id
            ):
                reply_recipient_id = parent.author_id

        # Mention fan-out: skip the one author who will receive a reply
        # message instead (Requirement 10.6).
        for author in mention_authors:
            if author.author_id == reply_recipient_id:
                continue
            await self._upsert_message(
                recipient_id=author.author_id,
                type="mention",
                dedup_key=f"mention:{comment.id}:{author.author_id}",
                payload=self._comment_payload(comment, kind="mention"),
                related_comment_id=comment.id,
                related_plugin_id=comment.plugin_id,
                source_author_id=sender_id,
            )

        if reply_recipient_id is not None:
            await self._upsert_message(
                recipient_id=reply_recipient_id,
                type="reply",
                dedup_key=f"reply:{comment.id}:{reply_recipient_id}",
                payload=self._comment_payload(comment, kind="reply"),
                related_comment_id=comment.id,
                related_plugin_id=comment.plugin_id,
                source_author_id=sender_id,
            )

        await self.session.flush()

    # ------------------------------------------------------------------
    # Fan-out: governance (Requirements 11.4, 11.5, 11.7)
    # ------------------------------------------------------------------

    async def fan_out_for_governance(
        self,
        plugin: PluginORM,
        action: str,
        operator_id: str,
        reason: str | None = None,
    ) -> None:
        """Derive governance messages for a plugin's owner and maintainers.

        Within a 5-second sliding window, repeated calls for the same
        ``(recipient, plugin_id, action)`` are coalesced: instead of
        inserting a new row we refresh the existing message's ``created_at``
        so the recipient sees one notification per noisy burst rather than
        N (Requirement 11.7). The unique constraint ``unique_inbox_dedup``
        backstops same-second collisions.

        Args:
            plugin: The targeted plugin ORM row.
            action: A short identifier of the governance action (e.g.
                ``"block_plugin"`` or ``"set_trust_level"``).
            operator_id: The admin who performed the action; recorded as
                ``source_author_id`` so the UI can render an attribution.
            reason: Optional free-text reason supplied by the operator.
        """

        recipients = await self._collect_governance_recipients(plugin)
        if not recipients:
            return

        now = utc_now()
        window_start = now - GOVERNANCE_DEDUPE_WINDOW
        payload_template = {
            "action": action,
            "reason": reason,
            "plugin_id": plugin.plugin_id,
            "plugin_display_name": plugin.display_name,
            "operator_id": operator_id,
        }

        for recipient_id in recipients:
            # Look for any governance message for this recipient/plugin
            # within the dedupe window and refresh it instead of inserting.
            recent_rows = list(
                (
                    await self.session.scalars(
                        select(InboxMessageORM)
                        .where(
                            InboxMessageORM.recipient_id == recipient_id,
                            InboxMessageORM.type == "governance",
                            InboxMessageORM.related_plugin_id
                            == plugin.plugin_id,
                            InboxMessageORM.created_at >= window_start,
                        )
                        .order_by(InboxMessageORM.created_at.desc())
                    )
                ).all()
            )
            existing = next(
                (
                    row
                    for row in recent_rows
                    if (row.payload or {}).get("action") == action
                ),
                None,
            )
            if existing is not None:
                existing.created_at = now
                existing.payload = payload_template
                if existing.status == "revoked":
                    existing.status = "unread"
                continue

            dedup_key = (
                f"governance:{plugin.plugin_id}:{action}"
                f":{int(now.timestamp() * 1_000_000)}"
            )
            await self._upsert_message(
                recipient_id=recipient_id,
                type="governance",
                dedup_key=dedup_key,
                payload=payload_template,
                related_plugin_id=plugin.plugin_id,
                source_author_id=operator_id,
                created_at=now,
            )

        await self.session.flush()

    # ------------------------------------------------------------------
    # Fan-out: announcements (Requirement 11.3)
    # ------------------------------------------------------------------

    async def fan_out_for_announcement(
        self,
        announcement: AnnouncementORM,
        recipients_iter: Iterable[str | AuthorORM],
    ) -> int:
        """Derive announcement messages for the supplied recipients.

        The caller is responsible for honoring ``announcement.emit_inbox`` —
        invoking this method implies the admin has opted into inbox fan-out.
        A no-op announcement (``emit_inbox=False``) raises ``ValueError`` so
        accidental calls fail fast in development.

        Args:
            announcement: The announcement to broadcast.
            recipients_iter: An iterable of author ids (str) or
                :class:`AuthorORM` rows. Duplicates are deduped by id.

        Returns:
            The number of newly written / refreshed inbox messages.
        """

        if not announcement.emit_inbox:
            raise ValueError(
                "fan_out_for_announcement called for an announcement with "
                "emit_inbox=False; the caller must guard this."
            )

        recipient_ids: list[str] = []
        seen: set[str] = set()
        for entry in recipients_iter:
            recipient_id = (
                entry.author_id if isinstance(entry, AuthorORM) else entry
            )
            if not recipient_id or recipient_id in seen:
                continue
            seen.add(recipient_id)
            recipient_ids.append(recipient_id)

        if not recipient_ids:
            return 0

        payload = {
            "announcement_id": announcement.id,
            "title": announcement.title,
            "severity": announcement.severity,
            "display_mode": announcement.display_mode,
            "preview": (announcement.body_markdown or "")[:PREVIEW_MAX_LENGTH],
        }

        count = 0
        for recipient_id in recipient_ids:
            dedup_key = (
                f"announcement:{announcement.id}:{recipient_id}"
                f":{announcement.dismiss_token}"
            )
            await self._upsert_message(
                recipient_id=recipient_id,
                type="announcement",
                dedup_key=dedup_key,
                payload=payload,
                related_announcement_id=announcement.id,
                source_author_id=None,
            )
            count += 1
        await self.session.flush()
        return count

    async def fan_out_for_author_activity(
        self,
        *,
        author_id: str,
        source_author_id: str,
        dedup_key: str,
        payload: dict[str, Any],
        related_plugin_id: str | None = None,
    ) -> int:
        """Derive author activity messages for followers of one author."""

        follower_ids = list(
            (
                await self.session.scalars(
                    select(AuthorFollowORM.follower_id).where(
                        AuthorFollowORM.author_id == author_id
                    )
                )
            ).all()
        )
        count = 0
        for follower_id in dict.fromkeys(follower_ids):
            if not follower_id or follower_id == source_author_id:
                continue
            await self._upsert_message(
                recipient_id=follower_id,
                type="author_activity",
                dedup_key=f"{dedup_key}:{follower_id}",
                payload=payload,
                related_plugin_id=related_plugin_id,
                source_author_id=source_author_id,
            )
            count += 1
        if count:
            await self.session.flush()
        return count

    async def fan_out_for_plugin_activity(
        self,
        *,
        plugin_id: str,
        source_author_id: str,
        dedup_key: str,
        payload: dict[str, Any],
    ) -> int:
        """Derive plugin activity messages for plugin subscribers."""

        subscriber_ids = list(
            (
                await self.session.scalars(
                    select(PluginSubscriptionORM.author_id).where(
                        PluginSubscriptionORM.plugin_id == plugin_id
                    )
                )
            ).all()
        )
        count = 0
        for subscriber_id in dict.fromkeys(subscriber_ids):
            if not subscriber_id or subscriber_id == source_author_id:
                continue
            await self._upsert_message(
                recipient_id=subscriber_id,
                type="plugin_activity",
                dedup_key=f"{dedup_key}:{subscriber_id}",
                payload=payload,
                related_plugin_id=plugin_id,
                source_author_id=source_author_id,
            )
            count += 1
        if count:
            await self.session.flush()
        return count

    # ------------------------------------------------------------------
    # Revocation (Requirement 9.6)
    # ------------------------------------------------------------------

    async def revoke_messages_for_comment(self, comment_id: int) -> int:
        """Mark every inbox message derived from ``comment_id`` as ``revoked``.

        Returns the number of rows affected. Already-revoked rows are left
        untouched so the audit trail records the *first* revocation time in
        ``read_at``-adjacent state.
        """

        rows = list(
            (
                await self.session.scalars(
                    select(InboxMessageORM).where(
                        InboxMessageORM.related_comment_id == comment_id,
                        InboxMessageORM.status != "revoked",
                    )
                )
            ).all()
        )
        for row in rows:
            row.status = "revoked"
        if rows:
            await self.session.flush()
        return len(rows)

    # ------------------------------------------------------------------
    # Read surface (Requirements 11.1, 11.2, 11.6, 11.7, 11.8)
    # ------------------------------------------------------------------

    async def list_messages(
        self,
        viewer_id: str,
        *,
        type: str | None = None,
        offset: int = 0,
        limit: int = 50,
    ) -> tuple[list[InboxMessage], int]:
        """Return the paginated inbox for ``viewer_id`` ordered newest-first.

        Args:
            viewer_id: The viewing author. Only messages whose ``recipient_id``
                matches are returned (cross-recipient access is impossible by
                construction here, in addition to the authorization check the
                route layer performs).
            type: Optional message-type filter. When supplied, must be one of
                ``mention | reply | governance | announcement | system``.
                Unknown values yield an empty result rather than raising, so
                a misconfigured client cannot crash the endpoint.
            offset: Pagination offset (>= 0).
            limit: Page size (>= 1).

        Returns:
            ``(messages, total)`` where ``messages`` is the page projected
            into :class:`InboxMessage` and ``total`` is the unfiltered
            count for the same query.
        """

        if limit <= 0:
            return [], 0

        base_filters = [InboxMessageORM.recipient_id == viewer_id]
        if type is not None:
            if type not in _VALID_TYPES:
                return [], 0
            base_filters.append(InboxMessageORM.type == type)

        total_stmt = (
            select(func.count())
            .select_from(InboxMessageORM)
            .where(*base_filters)
        )
        total = int((await self.session.scalar(total_stmt)) or 0)
        if total == 0:
            return [], 0

        page_stmt = (
            select(InboxMessageORM)
            .where(*base_filters)
            .order_by(
                InboxMessageORM.created_at.desc(),
                InboxMessageORM.id.desc(),
            )
            .offset(max(offset, 0))
            .limit(limit)
        )
        rows = list((await self.session.scalars(page_stmt)).all())
        return await self._project_messages(rows), total

    async def unread_count(self, viewer_id: str) -> int:
        """Return the number of ``unread`` messages for ``viewer_id``.

        Revoked and read messages are excluded so the navbar bell reflects
        actionable items only.
        """

        stmt = (
            select(func.count())
            .select_from(InboxMessageORM)
            .where(
                InboxMessageORM.recipient_id == viewer_id,
                InboxMessageORM.status == "unread",
            )
        )
        return int((await self.session.scalar(stmt)) or 0)

    async def mark_read(
        self, viewer_id: str, ids: Iterable[int]
    ) -> int:
        """Mark the given inbox messages as read.

        Only rows where ``recipient_id == viewer_id`` and ``status='unread'``
        are mutated. ``revoked`` messages are left alone so we never resurrect
        a soft-deleted thread by mistake. Already-read messages are no-ops.

        Returns the number of rows actually transitioned to ``read``.
        """

        ids_list = [int(i) for i in ids if i is not None]
        if not ids_list:
            return 0

        rows = list(
            (
                await self.session.scalars(
                    select(InboxMessageORM).where(
                        InboxMessageORM.recipient_id == viewer_id,
                        InboxMessageORM.id.in_(ids_list),
                        InboxMessageORM.status == "unread",
                    )
                )
            ).all()
        )
        now = utc_now()
        for row in rows:
            row.status = "read"
            row.read_at = now
        if rows:
            await self.session.flush()
        return len(rows)

    async def mark_all_read(self, viewer_id: str) -> int:
        """Mark every unread message for ``viewer_id`` as read."""

        result = await self.session.execute(
            update(InboxMessageORM)
            .where(
                InboxMessageORM.recipient_id == viewer_id,
                InboxMessageORM.status == "unread",
            )
            .values(status="read", read_at=utc_now())
        )
        await self.session.flush()
        return int(result.rowcount or 0)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _collect_governance_recipients(
        self, plugin: PluginORM
    ) -> list[str]:
        """Return the deduplicated owner + maintainer ids for ``plugin``."""

        recipients: list[str] = []
        seen: set[str] = set()
        if plugin.owner_id:
            recipients.append(plugin.owner_id)
            seen.add(plugin.owner_id)

        maintainer_ids = list(
            (
                await self.session.scalars(
                    select(PluginMaintainerORM.author_id).where(
                        PluginMaintainerORM.plugin_id == plugin.plugin_id
                    )
                )
            ).all()
        )
        for maintainer_id in maintainer_ids:
            if maintainer_id and maintainer_id not in seen:
                recipients.append(maintainer_id)
                seen.add(maintainer_id)
        return recipients

    async def _upsert_message(
        self,
        *,
        recipient_id: str,
        type: str,
        dedup_key: str,
        payload: dict[str, Any],
        related_comment_id: int | None = None,
        related_plugin_id: str | None = None,
        related_announcement_id: int | None = None,
        source_author_id: str | None = None,
        created_at: Any | None = None,
    ) -> InboxMessageORM:
        """Insert or refresh an inbox message keyed by ``(recipient, dedup_key)``.

        When a row already exists (same recipient + dedup_key) we update the
        payload, bump ``created_at``, and resurrect any ``revoked`` row to
        ``unread``. This honors the design note that the unique constraint
        is the source of truth for fan-out idempotency.
        """

        existing = await self.session.scalar(
            select(InboxMessageORM).where(
                InboxMessageORM.recipient_id == recipient_id,
                InboxMessageORM.dedup_key == dedup_key,
            )
        )
        when = created_at or utc_now()
        if existing is not None:
            existing.payload = payload
            existing.created_at = when
            existing.related_comment_id = related_comment_id
            existing.related_plugin_id = related_plugin_id
            existing.related_announcement_id = related_announcement_id
            existing.source_author_id = source_author_id
            if existing.status == "revoked":
                existing.status = "unread"
            return existing

        message = InboxMessageORM(
            recipient_id=recipient_id,
            type=type,
            status="unread",
            payload=payload,
            dedup_key=dedup_key,
            related_comment_id=related_comment_id,
            related_plugin_id=related_plugin_id,
            related_announcement_id=related_announcement_id,
            source_author_id=source_author_id,
            created_at=when,
        )
        self.session.add(message)
        return message

    @staticmethod
    def _comment_payload(
        comment: PluginCommentORM, *, kind: str
    ) -> dict[str, Any]:
        """Build the JSON payload stored alongside mention/reply messages."""

        text = (comment.content or "").strip()
        return {
            "kind": kind,
            "comment_id": comment.id,
            "plugin_id": comment.plugin_id,
            "preview": text[:PREVIEW_MAX_LENGTH],
        }

    async def _project_messages(
        self, rows: list[InboxMessageORM]
    ) -> list[InboxMessage]:
        """Convert ORM rows to :class:`InboxMessage` schemas."""

        if not rows:
            return []

        source_ids = {
            row.source_author_id
            for row in rows
            if row.source_author_id is not None
        }
        sources: dict[str, AuthorORM] = {}
        if source_ids:
            source_rows = list(
                (
                    await self.session.scalars(
                        select(AuthorORM).where(
                            AuthorORM.author_id.in_(source_ids)
                        )
                    )
                ).all()
            )
            sources = {row.author_id: row for row in source_rows}

        out: list[InboxMessage] = []
        for row in rows:
            payload = dict(row.payload or {})
            preview_value = payload.get("preview", "")
            preview = (
                str(preview_value) if preview_value is not None else ""
            )

            source: InboxMessageSource | None = None
            if row.source_author_id is not None:
                source_row = sources.get(row.source_author_id)
                if source_row is not None:
                    source = InboxMessageSource(
                        author_id=source_row.author_id,
                        github_login=source_row.github_login,
                        display_name=source_row.display_name,
                        avatar_url=source_row.avatar_url,
                    )

            out.append(
                InboxMessage(
                    id=row.id,
                    type=row.type,  # type: ignore[arg-type]
                    status=row.status,  # type: ignore[arg-type]
                    preview=preview,
                    payload=payload,
                    source=source,
                    link=_build_link(row),
                    related_plugin_id=row.related_plugin_id,
                    related_comment_id=row.related_comment_id,
                    related_announcement_id=row.related_announcement_id,
                    created_at=row.created_at,
                    read_at=row.read_at,
                )
            )
        return out


# ---------------------------------------------------------------------------
# Module-level helpers
# ---------------------------------------------------------------------------


def _build_link(row: InboxMessageORM) -> InboxMessageLink:
    """Synthesize a navigation hint for an inbox message.

    The frontend uses this to deep-link mentions and replies to the comment
    anchor, governance to the plugin page, and announcements to the modal.
    """

    if row.related_comment_id is not None:
        return InboxMessageLink(
            kind="comment",
            plugin_id=row.related_plugin_id,
            comment_id=row.related_comment_id,
        )
    if row.related_announcement_id is not None:
        return InboxMessageLink(
            kind="announcement",
            announcement_id=row.related_announcement_id,
        )
    if row.related_plugin_id is not None:
        return InboxMessageLink(kind="plugin", plugin_id=row.related_plugin_id)
    return InboxMessageLink(kind="system")
