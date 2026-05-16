"""Property tests for curation signature ownership consistency."""

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
from plugin_market_backend.schemas import CurationEntryCreate, PluginCreate
from plugin_market_backend.service import MarketService
from plugin_market_backend.services.curation_service import CurationService


async def _ensure_author(
    session,
    author_id: str,
    *,
    is_admin: bool = False,
) -> None:
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


async def _create_plugin(session, plugin_id: str, owner_id: str) -> None:
    payload = PluginCreate(
        plugin_id=plugin_id,
        display_name=plugin_id,
        summary=f'summary for {plugin_id}',
        description=f'description for {plugin_id}',
        repository_url=f'https://github.com/MoFox-Studio/{plugin_id}',
        license='MIT',
        categories=['tool'],
        tags=['sample'],
        maintainers=[],
    )
    await MarketService(session).register_plugin(payload, owner_id=owner_id)


async def _run_case(target_is_owner: bool, target_is_maintainer: bool) -> None:
    os.environ['PLUGIN_MARKET_AUTHOR_TOKEN'] = 'dev-token'
    os.environ['PLUGIN_MARKET_ADMIN_TOKEN'] = 'admin-token'
    os.environ['PLUGIN_MARKET_REQUIRE_REVIEW'] = 'false'
    reset_settings_cache()
    await close_database()
    configure_database('sqlite+aiosqlite:///:memory:')
    await init_database()

    async with session_scope() as session:
        await _ensure_author(session, 'admin', is_admin=True)
        await _ensure_author(session, 'target-author')
        await _ensure_author(session, 'owner-author')

        owner_id = 'target-author' if target_is_owner else 'owner-author'
        await _create_plugin(session, 'plug-a', owner_id=owner_id)

        if target_is_maintainer and not target_is_owner:
            session.add(
                PluginMaintainerORM(plugin_id='plug-a', author_id='target-author')
            )
            await session.flush()

        payload = CurationEntryCreate(
            slot_type='featured_author',
            target_type='author',
            target_id='target-author',
            signature_plugin_id='plug-a',
        )

        should_pass = target_is_owner or target_is_maintainer
        service = CurationService(session)
        if should_pass:
            created = await service.create(payload, operator_id='admin')
            assert created.target_id == 'target-author'
            assert created.signature_plugin_id == 'plug-a'
            return

        with pytest.raises(ApiError) as ctx:
            await service.create(payload, operator_id='admin')
        assert ctx.value.status_code == 422
        assert ctx.value.code == 'CURATION_SIGNATURE_NOT_OWNED'


@settings(deadline=None, max_examples=8)
@given(
    target_is_owner=st.booleans(),
    target_is_maintainer=st.booleans(),
)
def test_curation_signature_consistency(target_is_owner: bool, target_is_maintainer: bool) -> None:
    asyncio.run(_run_case(target_is_owner, target_is_maintainer))