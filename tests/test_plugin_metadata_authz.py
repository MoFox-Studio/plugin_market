"""Property tests for plugin metadata authorization."""

from __future__ import annotations

import asyncio
import os

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from plugin_market_backend.config import reset_settings_cache
from plugin_market_backend.database import close_database, configure_database, init_database, session_scope
from plugin_market_backend.errors import ApiError
from plugin_market_backend.orm import AuthorORM, AuthorType, PluginMaintainerORM, utc_now
from plugin_market_backend.schemas import PluginCreate
from plugin_market_backend.service import MarketService
from plugin_market_backend.services.inline_edit_service import InlineEditService


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


async def _create_plugin(session, plugin_id: str, owner_id: str, *, categories: list[str]) -> None:
    payload = PluginCreate(
        plugin_id=plugin_id,
        display_name=plugin_id,
        summary=f'summary for {plugin_id}',
        description=f'description for {plugin_id}',
        repository_url=f'https://github.com/MoFox-Studio/{plugin_id}',
        license='MIT',
        categories=categories,
        tags=['sample'],
        maintainers=[],
    )
    await MarketService(session).register_plugin(payload, owner_id=owner_id)


async def _run_case(
    caller_role: str,
    caller_is_owner: bool,
    fields: dict[str, object],
) -> None:
    os.environ['PLUGIN_MARKET_AUTHOR_TOKEN'] = 'dev-token'
    os.environ['PLUGIN_MARKET_ADMIN_TOKEN'] = 'admin-token'
    os.environ['PLUGIN_MARKET_REQUIRE_REVIEW'] = 'false'
    reset_settings_cache()
    await close_database()
    configure_database('sqlite+aiosqlite:///:memory:')
    await init_database()

    try:
        async with session_scope() as session:
            caller_id = 'owner' if caller_is_owner else 'caller'
            await _ensure_author(session, 'owner')
            await _ensure_author(session, caller_id, is_admin=caller_role == 'admin')
            await _create_plugin(session, 'plug-a', owner_id='owner', categories=['tool'])
            await _create_plugin(session, 'plug-b', owner_id='owner', categories=['chat'])

            if caller_role == 'maintainer' and caller_id != 'owner':
                session.add(PluginMaintainerORM(plugin_id='plug-a', author_id=caller_id))
                await session.flush()

            expected_success = caller_is_owner or caller_role in {'maintainer', 'admin'}

            if expected_success:
                result = await InlineEditService(session).patch_metadata(caller_id, 'plug-a', fields)
                for key, value in fields.items():
                    assert getattr(result, key) == value
                return

            with pytest.raises(ApiError) as ctx:
                await InlineEditService(session).patch_metadata(caller_id, 'plug-a', fields)
            assert ctx.value.status_code == 403
            assert ctx.value.code == 'METADATA_FORBIDDEN'
    finally:
        pass


valid_fields = st.fixed_dictionaries(
    {},
    optional={
        'display_name': st.sampled_from(['Renamed Plugin', 'Updated Name']),
        'icon_url': st.just('https://cdn.example.com/icons/plug-a.png'),
        'categories': st.sampled_from([['tool'], ['chat']]),
        'tags': st.sampled_from([['alpha'], ['alpha', 'beta']]),
    },
).filter(bool)


@settings(deadline=None, max_examples=20)
@given(
    caller_role=st.sampled_from(['plain', 'maintainer', 'admin']),
    caller_is_owner=st.booleans(),
    fields=valid_fields,
)
def test_plugin_metadata_authz_matches_role_and_ownership(
    caller_role: str,
    caller_is_owner: bool,
    fields: dict[str, object],
) -> None:
    asyncio.run(_run_case(caller_role, caller_is_owner, fields))