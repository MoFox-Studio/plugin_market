"""Property tests for announcement dismissal idempotence."""

from __future__ import annotations

import asyncio
import os

from hypothesis import given, settings
from hypothesis import strategies as st
from sqlalchemy import func, select

from plugin_market_backend.config import reset_settings_cache
from plugin_market_backend.database import close_database, configure_database, init_database, session_scope
from plugin_market_backend.orm import AnnouncementDismissalORM, AuthorORM, AuthorType, utc_now
from plugin_market_backend.schemas import AnnouncementCreate
from plugin_market_backend.services.announcements_service import AnnouncementsService


async def _ensure_author(session, author_id: str, *, is_admin: bool = False) -> None:
    if await session.get(AuthorORM, author_id) is not None:
        return
    session.add(
        AuthorORM(
            author_id=author_id,
            github_user_id=f'id-{author_id}',
            github_login=author_id,
            display_name=author_id,
            author_type=AuthorType.USER,
            verified_at=utc_now(),
            is_admin=is_admin,
        )
    )
    await session.flush()


async def _run_case(repeats: int) -> None:
    os.environ['PLUGIN_MARKET_AUTHOR_TOKEN'] = 'dev-token'
    os.environ['PLUGIN_MARKET_ADMIN_TOKEN'] = 'admin-token'
    os.environ['PLUGIN_MARKET_REQUIRE_REVIEW'] = 'false'
    reset_settings_cache()
    await close_database()
    configure_database('sqlite+aiosqlite:///:memory:')
    await init_database()

    async with session_scope() as session:
        await _ensure_author(session, 'admin', is_admin=True)
        await _ensure_author(session, 'viewer')

        service = AnnouncementsService(session)
        created = await service.create(
            AnnouncementCreate(
                title='Dismiss me',
                body_markdown='body',
                display_mode='banner',
                audience='logged_in',
                dismissible=True,
            ),
            operator_id='admin',
        )

        for _ in range(repeats):
            announcement_id, dismiss_token = await service.dismiss(created.id, 'viewer')
            assert announcement_id == created.id
            assert dismiss_token == created.dismiss_token

        count = int(
            (
                await session.scalar(
                    select(func.count())
                    .select_from(AnnouncementDismissalORM)
                    .where(
                        AnnouncementDismissalORM.announcement_id == created.id,
                        AnnouncementDismissalORM.author_id == 'viewer',
                        AnnouncementDismissalORM.dismiss_token == created.dismiss_token,
                    )
                )
            )
            or 0
        )
        assert count == 1


@settings(deadline=None, max_examples=12)
@given(repeats=st.integers(min_value=1, max_value=12))
def test_announcement_dismiss_is_idempotent(repeats: int) -> None:
    asyncio.run(_run_case(repeats))