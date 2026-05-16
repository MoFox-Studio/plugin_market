"""Unit tests for ``InboxService`` (task 6).

These tests exercise each surface of
:class:`plugin_market_backend.services.inbox_service.InboxService` in
isolation, without going through the HTTP layer:

* :meth:`parse_mentions` resolves only existing GitHub logins, drops
  self-mentions, and is order/duplicate stable (Property 10).
* :meth:`fan_out_for_comment` writes ``comment_mentions`` and derives
  exactly the expected ``mention`` / ``reply`` inbox rows. The
  reply-over-mention precedence from Requirement 10.6 is asserted via a
  dedicated test.
* :meth:`fan_out_for_governance` enforces the 5-second sliding-window
  dedupe across owner + maintainer recipients (Requirement 11.7).
* :meth:`fan_out_for_announcement` only emits when ``emit_inbox=True`` and
  refuses otherwise.
* :meth:`revoke_messages_for_comment` flips derived rows to ``revoked``.
* :meth:`list_messages` / :meth:`unread_count` / :meth:`mark_read` /
  :meth:`mark_all_read` honor recipient scoping and the read-state model.

Tests reuse the shared ``conftest.py`` fixtures which spin up an in-memory
SQLite database and seed it before every test.
"""

from __future__ import annotations

from datetime import timedelta

import pytest
from sqlalchemy import select

from plugin_market_backend.database import session_scope
from plugin_market_backend.orm import (
    AnnouncementORM,
    AuthorORM,
    AuthorType,
    CommentMentionORM,
    InboxMessageORM,
    PluginCommentORM,
    PluginMaintainerORM,
    PluginORM,
    utc_now,
)
from plugin_market_backend.schemas import PluginCreate
from plugin_market_backend.service import MarketService
from plugin_market_backend.services.inbox_service import (
    GOVERNANCE_DEDUPE_WINDOW,
    InboxService,
)


# ---------------------------------------------------------------------------
# Setup helpers
# ---------------------------------------------------------------------------


async def _ensure_author(
    session,
    author_id: str,
    *,
    github_login: str | None = None,
    display_name: str | None = None,
) -> AuthorORM:
    """Create or fetch an author row."""

    existing = await session.get(AuthorORM, author_id)
    if existing is not None:
        return existing
    record = AuthorORM(
        author_id=author_id,
        github_user_id=f"id-{author_id}",
        github_login=github_login or author_id,
        display_name=display_name or github_login or author_id,
        author_type=AuthorType.USER,
        verified_at=utc_now(),
        is_admin=False,
    )
    session.add(record)
    await session.flush()
    return record


async def _create_plugin(session, plugin_id: str, owner_id: str) -> PluginORM:
    """Register a plugin owned by ``owner_id`` using the live MarketService."""

    payload = PluginCreate(
        plugin_id=plugin_id,
        display_name=plugin_id,
        summary=f"summary for {plugin_id}",
        description=f"description for {plugin_id}",
        repository_url=f"https://github.com/MoFox-Studio/{plugin_id}",
        license="MIT",
        categories=["tool"],
        tags=["sample"],
        maintainers=[],
    )
    await MarketService(session).register_plugin(payload, owner_id=owner_id)
    plugin = await session.get(PluginORM, plugin_id)
    assert plugin is not None
    return plugin


async def _add_comment(
    session,
    plugin_id: str,
    author_id: str,
    *,
    content: str = "hello",
    parent_id: int | None = None,
) -> PluginCommentORM:
    """Insert a comment row directly so tests do not depend on MarketService."""

    comment = PluginCommentORM(
        plugin_id=plugin_id,
        author_id=author_id,
        parent_id=parent_id,
        content=content,
    )
    session.add(comment)
    await session.flush()
    return comment


# ---------------------------------------------------------------------------
# parse_mentions
# ---------------------------------------------------------------------------


async def test_parse_mentions_resolves_existing_logins_in_order() -> None:
    """Existing GitHub logins should be returned in first-occurrence order."""

    async with session_scope() as session:
        await _ensure_author(session, "u-alpha", github_login="alpha")
        await _ensure_author(session, "u-beta", github_login="beta")
        await _ensure_author(session, "u-sender", github_login="sender")
        await _ensure_author(session, "u-gamma", github_login="gamma")

        service = InboxService(session)
        result = await service.parse_mentions(
            "ping @beta and @alpha (then @gamma again)", sender_id="u-sender"
        )

        assert [author.github_login for author in result] == [
            "beta",
            "alpha",
            "gamma",
        ]


async def test_parse_mentions_filters_unknown_logins() -> None:
    """Tokens that do not match any author are silently dropped (R 9.3)."""

    async with session_scope() as session:
        await _ensure_author(session, "u-alpha", github_login="alpha")
        await _ensure_author(session, "u-sender", github_login="sender")

        service = InboxService(session)
        result = await service.parse_mentions(
            "@alpha is great, but @ghost-user is unknown",
            sender_id="u-sender",
        )

        assert [author.github_login for author in result] == ["alpha"]


async def test_parse_mentions_drops_self_mentions() -> None:
    """Self-mentions are filtered so we never write a self-message."""

    async with session_scope() as session:
        await _ensure_author(session, "u-sender", github_login="sender")

        service = InboxService(session)
        result = await service.parse_mentions(
            "I am @sender and I want to mention myself", sender_id="u-sender"
        )

        assert result == []


async def test_parse_mentions_dedupes_repeated_mentions() -> None:
    """Repeated mentions of the same author appear only once."""

    async with session_scope() as session:
        await _ensure_author(session, "u-alpha", github_login="alpha")
        await _ensure_author(session, "u-sender", github_login="sender")

        service = InboxService(session)
        result = await service.parse_mentions(
            "@alpha @alpha @alpha", sender_id="u-sender"
        )

        assert [author.github_login for author in result] == ["alpha"]


async def test_parse_mentions_handles_dashed_logins() -> None:
    """GitHub logins may contain interior dashes."""

    async with session_scope() as session:
        await _ensure_author(
            session, "u-with-dash", github_login="user-with-dash"
        )
        await _ensure_author(session, "u-sender", github_login="sender")

        service = InboxService(session)
        result = await service.parse_mentions(
            "hi @user-with-dash, please review", sender_id="u-sender"
        )

        assert [author.github_login for author in result] == [
            "user-with-dash"
        ]


async def test_parse_mentions_returns_empty_for_blank_content() -> None:
    """Empty / whitespace content yields no mentions."""

    async with session_scope() as session:
        await _ensure_author(session, "u-sender", github_login="sender")
        service = InboxService(session)
        assert await service.parse_mentions("", sender_id="u-sender") == []
        assert (
            await service.parse_mentions("just some text", sender_id="u-sender")
            == []
        )


# ---------------------------------------------------------------------------
# fan_out_for_comment
# ---------------------------------------------------------------------------


async def test_fan_out_for_comment_writes_mention_messages_and_normalized_rows() -> None:
    """Top-level mention should write comment_mentions + a mention message."""

    async with session_scope() as session:
        await _ensure_author(session, "owner", github_login="owner")
        await _ensure_author(session, "u-alpha", github_login="alpha")
        await _ensure_author(session, "u-sender", github_login="sender")
        plugin = await _create_plugin(session, "plug-a", owner_id="owner")
        comment = await _add_comment(
            session,
            plugin.plugin_id,
            "u-sender",
            content="hey @alpha take a look",
        )

        service = InboxService(session)
        mentions = await service.parse_mentions(
            comment.content, sender_id=comment.author_id
        )
        await service.fan_out_for_comment(comment, mentions)

        # Normalized comment_mentions row exists.
        mention_row = await session.scalar(
            select(CommentMentionORM).where(
                CommentMentionORM.comment_id == comment.id
            )
        )
        assert mention_row is not None

        # Inbox row for u-alpha exists with type=mention.
        rows = list(
            (
                await session.scalars(
                    select(InboxMessageORM)
                    .where(InboxMessageORM.recipient_id == "u-alpha")
                )
            ).all()
        )
        assert len(rows) == 1
        row = rows[0]
        assert row.type == "mention"
        assert row.status == "unread"
        assert row.dedup_key == f"mention:{comment.id}:u-alpha"
        assert row.related_comment_id == comment.id
        assert row.related_plugin_id == "plug-a"
        assert row.source_author_id == "u-sender"


async def test_fan_out_for_comment_writes_reply_message_for_parent_author() -> None:
    """A reply with no mentions notifies the parent comment's author once."""

    async with session_scope() as session:
        await _ensure_author(session, "owner", github_login="owner")
        await _ensure_author(session, "u-parent", github_login="parent-user")
        await _ensure_author(session, "u-sender", github_login="sender")
        plugin = await _create_plugin(session, "plug-a", owner_id="owner")
        parent = await _add_comment(
            session, plugin.plugin_id, "u-parent", content="parent comment"
        )
        reply = await _add_comment(
            session,
            plugin.plugin_id,
            "u-sender",
            content="thanks for the input",
            parent_id=parent.id,
        )

        service = InboxService(session)
        await service.fan_out_for_comment(reply, mentions=[])

        rows = list(
            (
                await session.scalars(
                    select(InboxMessageORM)
                    .where(InboxMessageORM.recipient_id == "u-parent")
                )
            ).all()
        )
        assert len(rows) == 1
        assert rows[0].type == "reply"
        assert rows[0].dedup_key == f"reply:{reply.id}:u-parent"


async def test_fan_out_for_comment_reply_over_mention_dedupes_recipient() -> None:
    """When the parent author is also @-mentioned, only ``reply`` is written.

    This is Requirement 10.6 / Property 4: a single comment must produce at
    most one inbox row for any given recipient, with ``reply`` as the
    canonical type.
    """

    async with session_scope() as session:
        await _ensure_author(session, "owner", github_login="owner")
        await _ensure_author(session, "u-parent", github_login="parent-user")
        await _ensure_author(session, "u-other", github_login="other-user")
        await _ensure_author(session, "u-sender", github_login="sender")

        plugin = await _create_plugin(session, "plug-a", owner_id="owner")
        parent = await _add_comment(
            session, plugin.plugin_id, "u-parent", content="parent comment"
        )
        reply = await _add_comment(
            session,
            plugin.plugin_id,
            "u-sender",
            content="thanks @parent-user and @other-user",
            parent_id=parent.id,
        )

        service = InboxService(session)
        mentions = await service.parse_mentions(
            reply.content, sender_id=reply.author_id
        )
        await service.fan_out_for_comment(reply, mentions)

        # u-parent should only have a reply message — no mention message.
        parent_rows = list(
            (
                await session.scalars(
                    select(InboxMessageORM).where(
                        InboxMessageORM.recipient_id == "u-parent"
                    )
                )
            ).all()
        )
        assert [row.type for row in parent_rows] == ["reply"]

        # u-other should still receive a mention message.
        other_rows = list(
            (
                await session.scalars(
                    select(InboxMessageORM).where(
                        InboxMessageORM.recipient_id == "u-other"
                    )
                )
            ).all()
        )
        assert [row.type for row in other_rows] == ["mention"]

        # comment_mentions should still record both mentions for the
        # underlying graph (not just the one whose inbox message survived).
        mention_rows = list(
            (
                await session.scalars(
                    select(CommentMentionORM).where(
                        CommentMentionORM.comment_id == reply.id
                    )
                )
            ).all()
        )
        assert {row.mentioned_author_id for row in mention_rows} == {
            "u-parent",
            "u-other",
        }


async def test_fan_out_for_comment_skips_self_replies() -> None:
    """Replying to your own comment must not create a reply notification."""

    async with session_scope() as session:
        await _ensure_author(session, "owner", github_login="owner")
        await _ensure_author(session, "u-sender", github_login="sender")
        plugin = await _create_plugin(session, "plug-a", owner_id="owner")
        parent = await _add_comment(
            session, plugin.plugin_id, "u-sender", content="my own thread"
        )
        reply = await _add_comment(
            session,
            plugin.plugin_id,
            "u-sender",
            content="self reply",
            parent_id=parent.id,
        )

        service = InboxService(session)
        await service.fan_out_for_comment(reply, mentions=[])

        rows = list(
            (
                await session.scalars(
                    select(InboxMessageORM).where(
                        InboxMessageORM.recipient_id == "u-sender"
                    )
                )
            ).all()
        )
        assert rows == []


async def test_fan_out_for_comment_skips_replies_to_deleted_parent() -> None:
    """Replies to a tombstoned parent should not notify anyone."""

    async with session_scope() as session:
        await _ensure_author(session, "owner", github_login="owner")
        await _ensure_author(session, "u-parent", github_login="parent_user")
        await _ensure_author(session, "u-sender", github_login="sender")
        plugin = await _create_plugin(session, "plug-a", owner_id="owner")
        parent = await _add_comment(
            session, plugin.plugin_id, "u-parent", content="old"
        )
        parent.is_deleted = True
        await session.flush()

        reply = await _add_comment(
            session,
            plugin.plugin_id,
            "u-sender",
            content="late reply",
            parent_id=parent.id,
        )
        service = InboxService(session)
        await service.fan_out_for_comment(reply, mentions=[])

        rows = list(
            (
                await session.scalars(
                    select(InboxMessageORM).where(
                        InboxMessageORM.recipient_id == "u-parent"
                    )
                )
            ).all()
        )
        assert rows == []


# ---------------------------------------------------------------------------
# fan_out_for_governance
# ---------------------------------------------------------------------------


async def test_fan_out_for_governance_notifies_owner_and_maintainers() -> None:
    """Governance fan-out must reach owner + every maintainer (R 11.4 / 11.5)."""

    async with session_scope() as session:
        await _ensure_author(session, "owner", github_login="owner")
        await _ensure_author(session, "m1", github_login="maintainer-1")
        await _ensure_author(session, "m2", github_login="maintainer-2")
        await _ensure_author(session, "admin", github_login="admin")
        plugin = await _create_plugin(session, "plug-a", owner_id="owner")
        session.add_all(
            [
                PluginMaintainerORM(plugin_id="plug-a", author_id="m1"),
                PluginMaintainerORM(plugin_id="plug-a", author_id="m2"),
            ]
        )
        await session.flush()

        await InboxService(session).fan_out_for_governance(
            plugin,
            action="block_plugin",
            operator_id="admin",
            reason="policy violation",
        )

        rows = list(
            (
                await session.scalars(
                    select(InboxMessageORM).where(
                        InboxMessageORM.related_plugin_id == "plug-a"
                    )
                )
            ).all()
        )
        recipients = {row.recipient_id for row in rows}
        assert recipients == {"owner", "m1", "m2"}
        for row in rows:
            assert row.type == "governance"
            assert row.payload["action"] == "block_plugin"
            assert row.payload["reason"] == "policy violation"
            assert row.source_author_id == "admin"


async def test_fan_out_for_governance_dedupes_within_5s_window() -> None:
    """Two calls within 5s must collapse into one row per recipient."""

    async with session_scope() as session:
        await _ensure_author(session, "owner", github_login="owner")
        await _ensure_author(session, "admin", github_login="admin")
        plugin = await _create_plugin(session, "plug-a", owner_id="owner")

        service = InboxService(session)
        await service.fan_out_for_governance(
            plugin, action="block_plugin", operator_id="admin", reason="r1"
        )
        # Immediately replay the same action — must collapse.
        await service.fan_out_for_governance(
            plugin, action="block_plugin", operator_id="admin", reason="r2"
        )

        rows = list(
            (
                await session.scalars(
                    select(InboxMessageORM).where(
                        InboxMessageORM.recipient_id == "owner",
                        InboxMessageORM.type == "governance",
                    )
                )
            ).all()
        )
        assert len(rows) == 1
        # The latest fan-out's payload wins.
        assert rows[0].payload["reason"] == "r2"


async def test_fan_out_for_governance_creates_new_row_outside_window() -> None:
    """Beyond the dedupe window a fresh row is written."""

    async with session_scope() as session:
        await _ensure_author(session, "owner", github_login="owner")
        await _ensure_author(session, "admin", github_login="admin")
        plugin = await _create_plugin(session, "plug-a", owner_id="owner")

        service = InboxService(session)
        await service.fan_out_for_governance(
            plugin, action="block_plugin", operator_id="admin", reason="first"
        )
        # Backdate the existing row past the dedupe window so the next call
        # is forced to insert.
        existing = await session.scalar(
            select(InboxMessageORM).where(
                InboxMessageORM.recipient_id == "owner",
                InboxMessageORM.type == "governance",
            )
        )
        assert existing is not None
        existing.created_at = (
            existing.created_at - GOVERNANCE_DEDUPE_WINDOW - timedelta(seconds=1)
        )
        await session.flush()

        await service.fan_out_for_governance(
            plugin, action="block_plugin", operator_id="admin", reason="second"
        )

        rows = list(
            (
                await session.scalars(
                    select(InboxMessageORM).where(
                        InboxMessageORM.recipient_id == "owner",
                        InboxMessageORM.type == "governance",
                    )
                )
            ).all()
        )
        assert len(rows) == 2
        reasons = {(row.payload or {}).get("reason") for row in rows}
        assert reasons == {"first", "second"}


async def test_fan_out_for_governance_distinct_actions_dont_dedupe() -> None:
    """Different actions on the same plugin should each produce a row."""

    async with session_scope() as session:
        await _ensure_author(session, "owner", github_login="owner")
        await _ensure_author(session, "admin", github_login="admin")
        plugin = await _create_plugin(session, "plug-a", owner_id="owner")

        service = InboxService(session)
        await service.fan_out_for_governance(
            plugin, action="block_plugin", operator_id="admin"
        )
        await service.fan_out_for_governance(
            plugin, action="set_trust_level", operator_id="admin"
        )

        rows = list(
            (
                await session.scalars(
                    select(InboxMessageORM).where(
                        InboxMessageORM.recipient_id == "owner",
                        InboxMessageORM.type == "governance",
                    )
                )
            ).all()
        )
        actions = {(row.payload or {}).get("action") for row in rows}
        assert actions == {"block_plugin", "set_trust_level"}


# ---------------------------------------------------------------------------
# fan_out_for_announcement
# ---------------------------------------------------------------------------


async def test_fan_out_for_announcement_writes_inbox_rows_for_each_recipient() -> None:
    """``emit_inbox=True`` writes one inbox row per recipient."""

    async with session_scope() as session:
        await _ensure_author(session, "admin", github_login="admin")
        await _ensure_author(session, "u1", github_login="u1")
        await _ensure_author(session, "u2", github_login="u2")
        announcement = AnnouncementORM(
            title="Maintenance Window",
            body_markdown="we will be down briefly",
            display_mode="banner",
            severity="info",
            dismissible=True,
            enabled=True,
            audience="all",
            emit_inbox=True,
            dismiss_token=0,
            created_by="admin",
        )
        session.add(announcement)
        await session.flush()

        count = await InboxService(session).fan_out_for_announcement(
            announcement, ["u1", "u2", "u1"]
        )
        assert count == 2

        rows = list(
            (
                await session.scalars(
                    select(InboxMessageORM).where(
                        InboxMessageORM.related_announcement_id == announcement.id
                    )
                )
            ).all()
        )
        assert {row.recipient_id for row in rows} == {"u1", "u2"}
        for row in rows:
            assert row.type == "announcement"
            assert row.payload["announcement_id"] == announcement.id
            assert row.payload["title"] == "Maintenance Window"


async def test_fan_out_for_announcement_refuses_when_emit_inbox_false() -> None:
    """Calling with ``emit_inbox=False`` is a programmer error."""

    async with session_scope() as session:
        await _ensure_author(session, "admin", github_login="admin")
        announcement = AnnouncementORM(
            title="Silent Notice",
            body_markdown="",
            display_mode="banner",
            severity="info",
            dismissible=True,
            enabled=True,
            audience="all",
            emit_inbox=False,
            dismiss_token=0,
            created_by="admin",
        )
        session.add(announcement)
        await session.flush()

        with pytest.raises(ValueError):
            await InboxService(session).fan_out_for_announcement(
                announcement, ["admin"]
            )


async def test_fan_out_for_announcement_dedupes_by_dismiss_token() -> None:
    """Same announcement+token replays into the same row; bumping token forks it."""

    async with session_scope() as session:
        await _ensure_author(session, "admin", github_login="admin")
        await _ensure_author(session, "u1", github_login="u1")
        announcement = AnnouncementORM(
            title="Notice",
            body_markdown="",
            display_mode="banner",
            severity="info",
            dismissible=True,
            enabled=True,
            audience="all",
            emit_inbox=True,
            dismiss_token=0,
            created_by="admin",
        )
        session.add(announcement)
        await session.flush()

        service = InboxService(session)
        await service.fan_out_for_announcement(announcement, ["u1"])
        await service.fan_out_for_announcement(announcement, ["u1"])  # replay

        rows = list(
            (
                await session.scalars(
                    select(InboxMessageORM).where(
                        InboxMessageORM.recipient_id == "u1",
                        InboxMessageORM.related_announcement_id
                        == announcement.id,
                    )
                )
            ).all()
        )
        assert len(rows) == 1

        # Resurface: bumping dismiss_token gives a new dedup_key, so a
        # fresh inbox row is written.
        announcement.dismiss_token = 1
        await session.flush()
        await service.fan_out_for_announcement(announcement, ["u1"])

        rows = list(
            (
                await session.scalars(
                    select(InboxMessageORM).where(
                        InboxMessageORM.recipient_id == "u1",
                        InboxMessageORM.related_announcement_id
                        == announcement.id,
                    )
                )
            ).all()
        )
        assert len(rows) == 2


# ---------------------------------------------------------------------------
# revoke_messages_for_comment
# ---------------------------------------------------------------------------


async def test_revoke_messages_for_comment_marks_derived_rows_as_revoked() -> None:
    """Deleting a comment must flip every derived inbox row to ``revoked``."""

    async with session_scope() as session:
        await _ensure_author(session, "owner", github_login="owner")
        await _ensure_author(session, "u-alpha", github_login="alpha")
        await _ensure_author(session, "u-sender", github_login="sender")
        plugin = await _create_plugin(session, "plug-a", owner_id="owner")
        comment = await _add_comment(
            session,
            plugin.plugin_id,
            "u-sender",
            content="hi @alpha",
        )

        service = InboxService(session)
        mentions = await service.parse_mentions(
            comment.content, sender_id=comment.author_id
        )
        await service.fan_out_for_comment(comment, mentions)

        affected = await service.revoke_messages_for_comment(comment.id)
        assert affected == 1

        rows = list(
            (
                await session.scalars(
                    select(InboxMessageORM).where(
                        InboxMessageORM.related_comment_id == comment.id
                    )
                )
            ).all()
        )
        assert all(row.status == "revoked" for row in rows)

        # Calling it again is a no-op (already revoked rows are not touched).
        again = await service.revoke_messages_for_comment(comment.id)
        assert again == 0


# ---------------------------------------------------------------------------
# list / unread / mark_read / mark_all_read
# ---------------------------------------------------------------------------


async def test_list_messages_orders_newest_first_and_paginates() -> None:
    """Listing returns rows newest-first with pagination metadata."""

    async with session_scope() as session:
        await _ensure_author(session, "viewer", github_login="viewer")
        # Manually insert messages with deterministic timestamps so the
        # ordering assertion does not depend on insertion order alone.
        now = utc_now()
        for index in range(5):
            session.add(
                InboxMessageORM(
                    recipient_id="viewer",
                    type="system",
                    status="unread",
                    payload={"i": index},
                    dedup_key=f"system:viewer:{index}",
                    created_at=now - timedelta(minutes=5 - index),
                )
            )
        await session.flush()

        service = InboxService(session)
        page1, total = await service.list_messages("viewer", offset=0, limit=2)
        assert total == 5
        assert [int(msg.payload["i"]) for msg in page1] == [4, 3]

        page2, total2 = await service.list_messages("viewer", offset=2, limit=2)
        assert total2 == 5
        assert [int(msg.payload["i"]) for msg in page2] == [2, 1]


async def test_list_messages_filters_by_type() -> None:
    """The type filter must select only matching rows."""

    async with session_scope() as session:
        await _ensure_author(session, "viewer", github_login="viewer")
        session.add_all(
            [
                InboxMessageORM(
                    recipient_id="viewer",
                    type="mention",
                    status="unread",
                    payload={},
                    dedup_key="mention:viewer:1",
                ),
                InboxMessageORM(
                    recipient_id="viewer",
                    type="reply",
                    status="unread",
                    payload={},
                    dedup_key="reply:viewer:1",
                ),
                InboxMessageORM(
                    recipient_id="viewer",
                    type="system",
                    status="unread",
                    payload={},
                    dedup_key="system:viewer:1",
                ),
            ]
        )
        await session.flush()

        service = InboxService(session)
        mentions, total = await service.list_messages("viewer", type="mention")
        assert total == 1
        assert [m.type for m in mentions] == ["mention"]


async def test_list_messages_unknown_type_returns_empty() -> None:
    """Unknown filter values yield an empty page rather than an error."""

    async with session_scope() as session:
        await _ensure_author(session, "viewer", github_login="viewer")
        service = InboxService(session)
        items, total = await service.list_messages("viewer", type="nonsense")
        assert items == []
        assert total == 0


async def test_list_messages_scope_to_recipient() -> None:
    """``list_messages`` must never leak rows belonging to other recipients."""

    async with session_scope() as session:
        await _ensure_author(session, "alice", github_login="alice")
        await _ensure_author(session, "bob", github_login="bob")
        session.add_all(
            [
                InboxMessageORM(
                    recipient_id="alice",
                    type="system",
                    status="unread",
                    payload={"who": "alice"},
                    dedup_key="system:alice:1",
                ),
                InboxMessageORM(
                    recipient_id="bob",
                    type="system",
                    status="unread",
                    payload={"who": "bob"},
                    dedup_key="system:bob:1",
                ),
            ]
        )
        await session.flush()

        service = InboxService(session)
        alice_items, _ = await service.list_messages("alice")
        assert {item.payload["who"] for item in alice_items} == {"alice"}


async def test_unread_count_only_counts_unread_rows() -> None:
    """Read and revoked messages must not contribute to the unread badge."""

    async with session_scope() as session:
        await _ensure_author(session, "viewer", github_login="viewer")
        session.add_all(
            [
                InboxMessageORM(
                    recipient_id="viewer",
                    type="system",
                    status="unread",
                    payload={},
                    dedup_key="k1",
                ),
                InboxMessageORM(
                    recipient_id="viewer",
                    type="system",
                    status="unread",
                    payload={},
                    dedup_key="k2",
                ),
                InboxMessageORM(
                    recipient_id="viewer",
                    type="system",
                    status="read",
                    payload={},
                    dedup_key="k3",
                ),
                InboxMessageORM(
                    recipient_id="viewer",
                    type="system",
                    status="revoked",
                    payload={},
                    dedup_key="k4",
                ),
            ]
        )
        await session.flush()

        service = InboxService(session)
        assert await service.unread_count("viewer") == 2


async def test_mark_read_only_affects_recipient_unread_rows() -> None:
    """``mark_read`` must scope to the viewer and ignore non-unread rows."""

    async with session_scope() as session:
        await _ensure_author(session, "alice", github_login="alice")
        await _ensure_author(session, "bob", github_login="bob")
        session.add_all(
            [
                InboxMessageORM(
                    recipient_id="alice",
                    type="system",
                    status="unread",
                    payload={},
                    dedup_key="alice-1",
                ),
                InboxMessageORM(
                    recipient_id="alice",
                    type="system",
                    status="unread",
                    payload={},
                    dedup_key="alice-2",
                ),
                InboxMessageORM(
                    recipient_id="bob",
                    type="system",
                    status="unread",
                    payload={},
                    dedup_key="bob-1",
                ),
            ]
        )
        await session.flush()

        alice_ids = list(
            (
                await session.scalars(
                    select(InboxMessageORM).where(
                        InboxMessageORM.recipient_id == "alice"
                    )
                )
            ).all()
        )
        bob_id = (
            await session.scalar(
                select(InboxMessageORM).where(
                    InboxMessageORM.recipient_id == "bob"
                )
            )
        ).id

        service = InboxService(session)
        # Try to mark a row that belongs to bob — must be ignored.
        affected = await service.mark_read(
            "alice", [row.id for row in alice_ids] + [bob_id]
        )
        assert affected == 2

        bob_row = await session.get(InboxMessageORM, bob_id)
        assert bob_row is not None
        assert bob_row.status == "unread"

        # Repeated mark_read is a no-op.
        again = await service.mark_read(
            "alice", [row.id for row in alice_ids]
        )
        assert again == 0
        assert await service.unread_count("alice") == 0


async def test_mark_all_read_marks_only_recipient_unread_rows() -> None:
    """``mark_all_read`` should drain only the viewer's unread queue."""

    async with session_scope() as session:
        await _ensure_author(session, "alice", github_login="alice")
        await _ensure_author(session, "bob", github_login="bob")
        session.add_all(
            [
                InboxMessageORM(
                    recipient_id="alice",
                    type="system",
                    status="unread",
                    payload={},
                    dedup_key="alice-1",
                ),
                InboxMessageORM(
                    recipient_id="alice",
                    type="system",
                    status="read",
                    payload={},
                    dedup_key="alice-2",
                ),
                InboxMessageORM(
                    recipient_id="bob",
                    type="system",
                    status="unread",
                    payload={},
                    dedup_key="bob-1",
                ),
            ]
        )
        await session.flush()

        service = InboxService(session)
        affected = await service.mark_all_read("alice")
        assert affected == 1
        assert await service.unread_count("alice") == 0
        # Bob's unread row is untouched.
        assert await service.unread_count("bob") == 1
