"""Property tests for mention parsing round-trip stability."""

from __future__ import annotations

import asyncio
import os

from hypothesis import given, settings
from hypothesis import strategies as st

from plugin_market_backend.config import reset_settings_cache
from plugin_market_backend.database import close_database, configure_database, init_database, session_scope
from plugin_market_backend.orm import AuthorORM, AuthorType, utc_now
from plugin_market_backend.services.inbox_service import InboxService


KNOWN_LOGINS = ['alpha', 'beta', 'gamma', 'user-with-dash', 'sender']


async def _ensure_author(session, author_id: str, github_login: str) -> None:
    if await session.get(AuthorORM, author_id) is not None:
        return
    session.add(
        AuthorORM(
            author_id=author_id,
            github_user_id=f'id-{author_id}',
            github_login=github_login,
            display_name=github_login,
            author_type=AuthorType.USER,
            verified_at=utc_now(),
            is_admin=False,
        )
    )
    await session.flush()


async def _run_case(chunks: list[str]) -> None:
    os.environ['PLUGIN_MARKET_AUTHOR_TOKEN'] = 'dev-token'
    os.environ['PLUGIN_MARKET_ADMIN_TOKEN'] = 'admin-token'
    os.environ['PLUGIN_MARKET_REQUIRE_REVIEW'] = 'false'
    reset_settings_cache()
    await close_database()
    configure_database('sqlite+aiosqlite:///:memory:')
    await init_database()

    async with session_scope() as session:
        await _ensure_author(session, 'u-alpha', 'alpha')
        await _ensure_author(session, 'u-beta', 'beta')
        await _ensure_author(session, 'u-gamma', 'gamma')
        await _ensure_author(session, 'u-dash', 'user-with-dash')
        await _ensure_author(session, 'u-sender', 'sender')

        service = InboxService(session)
        content = ' '.join(chunks)
        first = await service.parse_mentions(content, sender_id='u-sender')
        rendered = ' '.join(f'@{author.github_login}' for author in first)
        second = await service.parse_mentions(rendered, sender_id='u-sender')

        assert [author.author_id for author in second] == [author.author_id for author in first]
        assert [author.github_login for author in second] == [author.github_login for author in first]


chunk_strategy = st.lists(
    st.sampled_from([
        'hello',
        'world',
        '@alpha',
        '@beta',
        '@gamma',
        '@user-with-dash',
        '@sender',
        '@ghost-user',
        '(note)',
        'plain-text',
        '@alpha,',
        '@beta.',
    ]),
    min_size=0,
    max_size=20,
)


@settings(deadline=None, max_examples=20)
@given(chunks=chunk_strategy)
def test_mention_parsing_round_trip(chunks: list[str]) -> None:
    asyncio.run(_run_case(chunks))