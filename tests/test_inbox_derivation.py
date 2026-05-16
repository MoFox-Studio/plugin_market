"""Property tests for inbox derivation."""

from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from hypothesis import given, settings
from hypothesis import strategies as st
from sqlalchemy import select

from plugin_market_backend.config import reset_settings_cache
from plugin_market_backend.database import close_database, configure_database, init_database, session_scope
from plugin_market_backend.orm import AuthorORM, AuthorType, InboxMessageORM, PluginCommentORM, PluginMaintainerORM, PluginORM, utc_now
from plugin_market_backend.schemas import PluginCreate
from plugin_market_backend.service import MarketService
from plugin_market_backend.services import inbox_service as inbox_module
from plugin_market_backend.services.inbox_service import GOVERNANCE_DEDUPE_WINDOW, InboxService


COMMENT_AUTHORS = ['alpha', 'beta', 'gamma', 'owner', 'maint']
GOVERNANCE_RECIPIENTS = ['owner', 'maint']
GOVERNANCE_ACTIONS = ['block_plugin', 'set_trust_level', 'reject_plugin']
REASONS = ['', 'policy', 'quality', 'duplicate']


@dataclass(frozen=True)
class EventCase:
    kind: str
    actor: str
    mentions: list[str]
    wants_reply: bool
    reply_target: int
    action: str
    reason: str
    advance_seconds: int


@dataclass(frozen=True)
class DerivedEvent:
    kind: str
    created_at: datetime
    comment_id: int | None = None
    sender: str | None = None
    mentions: tuple[str, ...] = ()
    reply_recipient: str | None = None
    action: str | None = None
    reason: str | None = None


async def _ensure_author(session, author_id: str) -> AuthorORM:
    existing = await session.get(AuthorORM, author_id)
    if existing is not None:
        return existing
    record = AuthorORM(
        author_id=author_id,
        github_user_id=f'id-{author_id}',
        github_login=author_id,
        display_name=author_id,
        author_type=AuthorType.USER,
        verified_at=utc_now(),
        is_admin=False,
    )
    session.add(record)
    await session.flush()
    return record


async def _create_plugin(session, plugin_id: str, owner_id: str) -> PluginORM:
    payload = PluginCreate(
        plugin_id=plugin_id,
        display_name=plugin_id,
        summary=f'summary for {plugin_id}',
        description=f'description for {plugin_id}',
        repository_url=f'https://github.com/MoFox-Studio/{plugin_id}',
        license='MIT',
        categories=['tool'],
        tags=['property'],
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
    content: str,
    parent_id: int | None,
) -> PluginCommentORM:
    comment = PluginCommentORM(
        plugin_id=plugin_id,
        author_id=author_id,
        parent_id=parent_id,
        content=content,
    )
    session.add(comment)
    await session.flush()
    return comment


def _project_rows(rows: list[InboxMessageORM]) -> list[tuple[str, str, int | None, str | None, str | None]]:
    return sorted(
        [
            (
                row.type,
                row.recipient_id,
                row.related_comment_id,
                (row.payload or {}).get('action'),
                (row.payload or {}).get('reason'),
            )
            for row in rows
        ],
        key=lambda item: (
            item[0],
            item[1],
            item[2] or -1,
            item[3] or '',
            item[4] or '',
        ),
    )


def _derive_expected(events: list[DerivedEvent]) -> list[tuple[str, str, int | None, str | None, str | None]]:
    projected: list[dict[str, object]] = []

    for event in events:
        if event.kind == 'comment':
            for mention in event.mentions:
                if mention == event.reply_recipient:
                    continue
                projected.append(
                    {
                        'type': 'mention',
                        'recipient': mention,
                        'comment_id': event.comment_id,
                        'action': None,
                        'reason': None,
                    }
                )
            if event.reply_recipient is not None:
                projected.append(
                    {
                        'type': 'reply',
                        'recipient': event.reply_recipient,
                        'comment_id': event.comment_id,
                        'action': None,
                        'reason': None,
                    }
                )
            continue

        for recipient in GOVERNANCE_RECIPIENTS:
            existing = next(
                (
                    row
                    for row in reversed(projected)
                    if row['type'] == 'governance'
                    and row['recipient'] == recipient
                    and row['action'] == event.action
                    and isinstance(row['created_at'], datetime)
                    and row['created_at'] >= event.created_at - GOVERNANCE_DEDUPE_WINDOW
                ),
                None,
            )
            if existing is not None:
                existing['created_at'] = event.created_at
                existing['reason'] = event.reason or None
                continue
            projected.append(
                {
                    'type': 'governance',
                    'recipient': recipient,
                    'comment_id': None,
                    'action': event.action,
                    'reason': event.reason or None,
                    'created_at': event.created_at,
                }
            )

    return sorted(
        [
            (
                str(row['type']),
                str(row['recipient']),
                row['comment_id'] if isinstance(row['comment_id'], int) else None,
                row['action'] if isinstance(row['action'], str) else None,
                row['reason'] if isinstance(row['reason'], str) else None,
            )
            for row in projected
        ],
        key=lambda item: (
            item[0],
            item[1],
            item[2] or -1,
            item[3] or '',
            item[4] or '',
        ),
    )


async def _run_case(events: list[EventCase]) -> None:
    os.environ['PLUGIN_MARKET_AUTHOR_TOKEN'] = 'dev-token'
    os.environ['PLUGIN_MARKET_ADMIN_TOKEN'] = 'admin-token'
    os.environ['PLUGIN_MARKET_REQUIRE_REVIEW'] = 'false'
    reset_settings_cache()
    await close_database()
    configure_database('sqlite+aiosqlite:///:memory:')
    await init_database()

    base_time = datetime(2025, 1, 1, tzinfo=timezone.utc)
    current_time = base_time
    original_utc_now = inbox_module.utc_now

    try:
        async with session_scope() as session:
            for author_id in ['admin', *COMMENT_AUTHORS]:
                await _ensure_author(session, author_id)

            plugin = await _create_plugin(session, 'plug-a', owner_id='owner')
            session.add(PluginMaintainerORM(plugin_id='plug-a', author_id='maint'))
            await session.flush()

            service = InboxService(session)
            top_level_comments: list[tuple[int, str]] = []
            derived_events: list[DerivedEvent] = []

            for event in events:
                current_time = current_time + timedelta(seconds=event.advance_seconds)
                inbox_module.utc_now = lambda current_time=current_time: current_time

                if event.kind == 'comment':
                    parent_id: int | None = None
                    reply_recipient: str | None = None
                    if event.wants_reply and top_level_comments:
                        parent_id, reply_recipient = top_level_comments[event.reply_target % len(top_level_comments)]
                        if reply_recipient == event.actor:
                            reply_recipient = None

                    content = 'hello'
                    if event.mentions:
                        content = f"{content} {' '.join(f'@{login}' for login in event.mentions)}"

                    comment = await _add_comment(
                        session,
                        plugin.plugin_id,
                        event.actor,
                        content=content,
                        parent_id=parent_id,
                    )
                    mentions = await service.parse_mentions(content, sender_id=event.actor)
                    await service.fan_out_for_comment(comment, mentions)

                    if parent_id is None:
                        top_level_comments.append((int(comment.id), event.actor))

                    derived_events.append(
                        DerivedEvent(
                            kind='comment',
                            created_at=current_time,
                            comment_id=int(comment.id),
                            sender=event.actor,
                            mentions=tuple(author.author_id for author in mentions),
                            reply_recipient=reply_recipient,
                        )
                    )
                    continue

                await service.fan_out_for_governance(
                    plugin,
                    action=event.action,
                    operator_id='admin',
                    reason=event.reason or None,
                )
                derived_events.append(
                    DerivedEvent(
                        kind='governance',
                        created_at=current_time,
                        action=event.action,
                        reason=event.reason or None,
                    )
                )

            rows = list((await session.scalars(select(InboxMessageORM))).all())
            assert _project_rows(rows) == _derive_expected(derived_events)
    finally:
        inbox_module.utc_now = original_utc_now


event_cases = st.lists(
    st.builds(
        EventCase,
        kind=st.sampled_from(['comment', 'governance']),
        actor=st.sampled_from(COMMENT_AUTHORS),
        mentions=st.lists(st.sampled_from(COMMENT_AUTHORS), max_size=3),
        wants_reply=st.booleans(),
        reply_target=st.integers(min_value=0, max_value=4),
        action=st.sampled_from(GOVERNANCE_ACTIONS),
        reason=st.sampled_from(REASONS),
        advance_seconds=st.integers(min_value=0, max_value=8),
    ),
    min_size=0,
    max_size=8,
)


@settings(deadline=None, max_examples=20)
@given(events=event_cases)
def test_inbox_derivation_matches_event_sequence(events: list[EventCase]) -> None:
    asyncio.run(_run_case(events))