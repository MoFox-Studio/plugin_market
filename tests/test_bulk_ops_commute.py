"""Property tests for bulk operation commutativity across distinct plugins."""

from __future__ import annotations

import asyncio
import os

from hypothesis import given, settings
from hypothesis import strategies as st

from plugin_market_backend.config import reset_settings_cache
from plugin_market_backend.database import close_database, configure_database, init_database, session_scope
from plugin_market_backend.enums import PluginStatus, ReviewAction, TrustLevel
from plugin_market_backend.orm import AuthorORM, AuthorType, PluginORM, utc_now
from plugin_market_backend.schemas import PluginCreate
from plugin_market_backend.service import MarketService
from plugin_market_backend.services.bulk_ops_service import BulkOpsService


PLUGIN_IDS = ['plug-a', 'plug-b', 'plug-c']
ACTIONS = ['publish', 'reject', 'block', 'deprecate', 'set_trust_level', 'delete']


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


def _plugin_payload(plugin_id: str) -> PluginCreate:
    return PluginCreate(
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


async def _setup_market() -> None:
    os.environ['PLUGIN_MARKET_AUTHOR_TOKEN'] = 'dev-token'
    os.environ['PLUGIN_MARKET_ADMIN_TOKEN'] = 'admin-token'
    os.environ['PLUGIN_MARKET_REQUIRE_REVIEW'] = 'false'
    reset_settings_cache()
    await close_database()
    configure_database('sqlite+aiosqlite:///:memory:')
    await init_database()

    async with session_scope() as session:
        await _ensure_author(session, 'admin', is_admin=True)
        await _ensure_author(session, 'owner')
        market = MarketService(session)
        for plugin_id in PLUGIN_IDS:
            await market.register_plugin(_plugin_payload(plugin_id), owner_id='owner')


async def _project_state() -> dict[str, tuple[bool, str | None, str | None]]:
    async with session_scope() as session:
        result: dict[str, tuple[bool, str | None, str | None]] = {}
        for plugin_id in PLUGIN_IDS:
            plugin = await session.get(PluginORM, plugin_id)
            if plugin is None:
                result[plugin_id] = (False, None, None)
                continue
            result[plugin_id] = (True, str(plugin.status), str(plugin.trust_level))
        return result


async def _run_bulk(assignments: list[tuple[str, str]]) -> dict[str, tuple[bool, str | None, str | None]]:
    await _setup_market()
    grouped: dict[str, list[str]] = {}
    for plugin_id, action in assignments:
        grouped.setdefault(action, []).append(plugin_id)

    async with session_scope() as session:
        service = BulkOpsService(session)
        for action, plugin_ids in grouped.items():
            params = None
            if action == 'set_trust_level':
                params = {'trust_level': 'official', 'reason': 'trusted'}
            elif action == 'delete':
                params = {'reason': 'cleanup'}
            await service.bulk_apply('admin', plugin_ids, action, params)

    return await _project_state()


async def _run_serial(assignments: list[tuple[str, str]], permutation: list[int]) -> dict[str, tuple[bool, str | None, str | None]]:
    await _setup_market()
    ordered = [assignments[index] for index in permutation]

    async with session_scope() as session:
        market = MarketService(session)
        for plugin_id, action in ordered:
            if action == 'publish':
                await market.set_plugin_status(plugin_id, PluginStatus.PUBLISHED, ReviewAction.BULK_PUBLISH, 'admin')
            elif action == 'reject':
                await market.set_plugin_status(plugin_id, PluginStatus.DRAFT, ReviewAction.BULK_REJECT, 'admin')
            elif action == 'block':
                await market.set_plugin_status(plugin_id, PluginStatus.BLOCKED, ReviewAction.BULK_BLOCK, 'admin')
            elif action == 'deprecate':
                await market.set_plugin_status(plugin_id, PluginStatus.DEPRECATED, ReviewAction.BULK_DEPRECATE, 'admin')
            elif action == 'set_trust_level':
                plugin = await market._get_plugin_orm(plugin_id)
                plugin.trust_level = TrustLevel.OFFICIAL
                plugin.updated_at = utc_now()
                await market._record('plugin', plugin_id, ReviewAction.BULK_SET_TRUST_LEVEL, None, TrustLevel.OFFICIAL, 'admin', 'trusted')
                await session.flush()
            elif action == 'delete':
                await market.delete_plugin(plugin_id)
                await market._record('plugin', plugin_id, ReviewAction.BULK_DELETE, None, None, 'admin', 'cleanup')
                await session.flush()

    return await _project_state()


assignment_strategy = st.lists(
    st.tuples(st.sampled_from(PLUGIN_IDS), st.sampled_from(ACTIONS)),
    min_size=1,
    max_size=3,
    unique_by=lambda item: item[0],
)


@settings(deadline=None, max_examples=20)
@given(assignments=assignment_strategy, permutation_seed=st.permutations((0, 1, 2)))
def test_bulk_ops_commute(assignments: list[tuple[str, str]], permutation_seed: tuple[int, int, int]) -> None:
    permutation = [index for index in permutation_seed if index < len(assignments)]
    if len(permutation) != len(assignments):
        permutation = list(range(len(assignments) - 1, -1, -1))

    bulk_state = asyncio.run(_run_bulk(assignments))
    serial_state = asyncio.run(_run_serial(assignments, permutation))
    assert bulk_state == serial_state