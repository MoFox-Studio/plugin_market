"""Property tests for announcement visibility against the public API."""

from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass
from datetime import datetime, timezone

from httpx import ASGITransport, AsyncClient
from hypothesis import given, settings
from hypothesis import strategies as st

from plugin_market_backend.app import app
from plugin_market_backend.config import reset_settings_cache
from plugin_market_backend.database import close_database, configure_database, init_database, session_scope
from plugin_market_backend.orm import AnnouncementDismissalORM, AnnouncementORM, AuthorORM, AuthorType, utc_now
from plugin_market_backend.schemas import PluginCreate
from plugin_market_backend.service import MarketService
from plugin_market_backend.services._audience import AUDIENCE_VALUES
from plugin_market_backend.services import announcements_service as announcements_module
from plugin_market_backend.services.announcements_service import is_visible
from plugin_market_backend.session_auth import create_browser_session


@dataclass(frozen=True)
class AnnouncementCase:
    enabled: bool
    display_mode: str
    audience: str
    starts_at: datetime | None
    ends_at: datetime | None
    dismissible: bool
    dismissed: bool


def _normalize(dt: datetime) -> datetime:
    if dt.tzinfo is not None:
        return dt.replace(tzinfo=None)
    return dt


def _make_viewer(kind: str) -> AuthorORM | None:
    if kind == 'anonymous':
        return None
    return AuthorORM(
        author_id=f'{kind}-viewer',
        github_user_id=f'gh-{kind}',
        github_login=kind,
        display_name=kind.title(),
        author_type=AuthorType.USER,
        is_admin=kind == 'admin',
    )


async def _ensure_author(author_id: str, *, is_admin: bool = False) -> None:
    async with session_scope() as session:
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


async def _create_owned_plugin(author_id: str) -> None:
    async with session_scope() as session:
        payload = PluginCreate(
            plugin_id=f'{author_id}-plugin',
            display_name=f'{author_id} plugin',
            summary='property test plugin',
            description='property test plugin',
            repository_url=f'https://github.com/MoFox-Studio/{author_id}-plugin',
            license='MIT',
            categories=['tool'],
            tags=['property'],
            maintainers=[],
        )
        await MarketService(session).register_plugin(payload, owner_id=author_id)


def _expected_ids(
    records: list[tuple[int, AnnouncementCase]],
    viewer: AuthorORM | None,
    now: datetime,
    *,
    viewer_has_plugin: bool,
) -> list[int]:
    visible: list[tuple[int, AnnouncementCase]] = []
    for announcement_id, case in records:
        announcement = AnnouncementORM(
            id=announcement_id,
            title=f'Announcement {announcement_id}',
            body_markdown='body',
            display_mode=case.display_mode,
            severity='info',
            dismissible=case.dismissible,
            enabled=case.enabled,
            starts_at=case.starts_at,
            ends_at=case.ends_at,
            audience=case.audience,
            emit_inbox=False,
            dismiss_token=0,
            created_by='admin',
            created_at=utc_now(),
            updated_at=utc_now(),
        )
        is_dismissed = viewer is not None and case.dismissible and case.dismissed
        if is_visible(
            announcement,
            viewer,
            now,
            is_dismissed=is_dismissed,
            viewer_has_plugin=viewer_has_plugin,
        ):
            visible.append((announcement_id, case))

    def sort_key(item: tuple[int, AnnouncementCase]) -> tuple[datetime, int]:
        starts_at = item[1].starts_at
        normalized = _normalize(starts_at) if starts_at is not None else datetime.min
        return normalized, item[0]

    visible.sort(key=sort_key, reverse=True)

    banners: list[tuple[int, AnnouncementCase]] = []
    modal_pick: tuple[int, AnnouncementCase] | None = None
    for item in visible:
        if item[1].display_mode == 'modal':
            if modal_pick is None:
                modal_pick = item
            continue
        banners.append(item)

    result = banners
    if modal_pick is not None:
        result = [*result, modal_pick]
    result.sort(key=sort_key, reverse=True)
    return [item[0] for item in result]


async def _run_case(
    cases: list[AnnouncementCase],
    viewer_kind: str,
    viewer_has_plugin: bool,
    now: datetime,
) -> None:
    os.environ['PLUGIN_MARKET_AUTHOR_TOKEN'] = 'dev-token'
    os.environ['PLUGIN_MARKET_ADMIN_TOKEN'] = 'admin-token'
    os.environ['PLUGIN_MARKET_REQUIRE_REVIEW'] = 'false'
    reset_settings_cache()
    await close_database()
    configure_database('sqlite+aiosqlite:///:memory:')
    await init_database()

    viewer = _make_viewer(viewer_kind)
    actual_ids: list[int]
    original_utc_now = announcements_module.utc_now
    announcements_module.utc_now = lambda: now

    try:
        await _ensure_author('admin', is_admin=True)
        if viewer is not None:
            await _ensure_author(viewer.author_id, is_admin=bool(viewer.is_admin))
            if viewer_has_plugin:
                await _create_owned_plugin(viewer.author_id)

        async with session_scope() as session:
            records: list[tuple[int, AnnouncementCase]] = []
            for index, case in enumerate(cases, start=1):
                row = AnnouncementORM(
                    title=f'Announcement {index}',
                    body_markdown='body',
                    display_mode=case.display_mode,
                    severity='info',
                    dismissible=case.dismissible,
                    enabled=case.enabled,
                    starts_at=case.starts_at,
                    ends_at=case.ends_at,
                    audience=case.audience,
                    emit_inbox=False,
                    dismiss_token=0,
                    created_by='admin',
                    created_at=utc_now(),
                    updated_at=utc_now(),
                )
                session.add(row)
                await session.flush()
                records.append((int(row.id), case))
                if viewer is not None and case.dismissible and case.dismissed:
                    session.add(
                        AnnouncementDismissalORM(
                            announcement_id=int(row.id),
                            author_id=viewer.author_id,
                            dismiss_token=0,
                        )
                    )
            await session.flush()

        async with AsyncClient(transport=ASGITransport(app=app), base_url='http://testserver') as client:
            if viewer is not None:
                session_id = await create_browser_session(viewer.author_id, f'token-{viewer.author_id}')
                client.cookies.set('plugin_market_session', session_id, path='/')
            response = await client.get('/api/v1/announcements/active')

        assert response.status_code == 200
        actual_ids = [item['id'] for item in response.json()]
        assert actual_ids == _expected_ids(
            records,
            viewer,
            now,
            viewer_has_plugin=viewer is not None and viewer_has_plugin,
        )
    finally:
        announcements_module.utc_now = original_utc_now


date_times = st.datetimes(timezones=st.one_of(st.none(), st.just(timezone.utc)))
viewer_kinds = st.sampled_from(['anonymous', 'user', 'admin'])
announcement_cases = st.lists(
    st.builds(
        AnnouncementCase,
        enabled=st.booleans(),
        display_mode=st.sampled_from(['banner', 'modal']),
        audience=st.sampled_from(sorted(AUDIENCE_VALUES)),
        starts_at=st.one_of(st.none(), date_times),
        ends_at=st.one_of(st.none(), date_times),
        dismissible=st.booleans(),
        dismissed=st.booleans(),
    ),
    min_size=0,
    max_size=5,
)


@settings(deadline=None, max_examples=20)
@given(
    cases=announcement_cases,
    viewer_kind=viewer_kinds,
    viewer_has_plugin=st.booleans(),
    now=date_times,
)
def test_active_announcements_matches_visibility_predicate(
    cases: list[AnnouncementCase],
    viewer_kind: str,
    viewer_has_plugin: bool,
    now: datetime,
) -> None:
    asyncio.run(_run_case(cases, viewer_kind, viewer_has_plugin, now))