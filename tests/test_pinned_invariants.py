"""Property tests for pinned plugin invariants."""

from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from hypothesis import given, settings
from hypothesis import strategies as st

from plugin_market_backend.config import reset_settings_cache
from plugin_market_backend.database import close_database, configure_database, init_database, session_scope
from plugin_market_backend.errors import ApiError
from plugin_market_backend.orm import AuthorORM, AuthorType, PluginMaintainerORM, utc_now
from plugin_market_backend.schemas import PluginCreate
from plugin_market_backend.service import MarketService
from plugin_market_backend.services import profile_service as profile_module
from plugin_market_backend.services.profile_service import MAX_ACTIVE_PINS, ProfileService


ELIGIBLE_PLUGIN_IDS = [f'plug-{index}' for index in range(7)]
FOREIGN_PLUGIN_ID = 'plug-foreign'
ALL_PLUGIN_IDS = [*ELIGIBLE_PLUGIN_IDS, FOREIGN_PLUGIN_ID]


@dataclass(frozen=True)
class PinOperation:
    kind: str
    plugin_id: str
    reason: str | None


async def _ensure_author(session, author_id: str) -> None:
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
            is_admin=False,
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


def _derive_expected(operations: list[PinOperation]) -> tuple[list[str], dict[str, str | None]]:
    eligible = set(ELIGIBLE_PLUGIN_IDS)
    pinned: dict[str, tuple[str | None, int]] = {}
    add_order = 0

    for operation in operations:
      if operation.kind == 'add':
        if operation.plugin_id not in eligible:
          continue
        if operation.plugin_id in pinned:
          continue
        if len(pinned) >= MAX_ACTIVE_PINS:
          continue
        add_order += 1
        pinned[operation.plugin_id] = (operation.reason, add_order)
        continue

      if operation.kind == 'update':
        if operation.plugin_id not in pinned:
          continue
        _, order = pinned[operation.plugin_id]
        pinned[operation.plugin_id] = (operation.reason, order)
        continue

      pinned.pop(operation.plugin_id, None)

    ordered = sorted(pinned.items(), key=lambda item: item[1][1], reverse=True)
    return [plugin_id for plugin_id, _ in ordered], {plugin_id: reason for plugin_id, (reason, _) in pinned.items()}


async def _run_case(operations: list[PinOperation]) -> None:
    os.environ['PLUGIN_MARKET_AUTHOR_TOKEN'] = 'dev-token'
    os.environ['PLUGIN_MARKET_ADMIN_TOKEN'] = 'admin-token'
    os.environ['PLUGIN_MARKET_REQUIRE_REVIEW'] = 'false'
    reset_settings_cache()
    await close_database()
    configure_database('sqlite+aiosqlite:///:memory:')
    await init_database()

    current_time = datetime(2025, 1, 1, tzinfo=timezone.utc)
    original_utc_now = profile_module.utc_now

    try:
        async with session_scope() as session:
            for author_id in ['author-a', 'foreign-owner']:
                await _ensure_author(session, author_id)

            for plugin_id in ELIGIBLE_PLUGIN_IDS[:6]:
                await _create_plugin(session, plugin_id, owner_id='author-a')
            await _create_plugin(session, 'plug-6', owner_id='foreign-owner')
            await _create_plugin(session, FOREIGN_PLUGIN_ID, owner_id='foreign-owner')
            session.add(PluginMaintainerORM(plugin_id='plug-6', author_id='author-a'))
            await session.flush()

            service = ProfileService(session)
            for operation in operations:
                current_time = current_time + timedelta(seconds=1)
                profile_module.utc_now = lambda current_time=current_time: current_time
                try:
                    if operation.kind == 'add':
                        await service.add_pin('author-a', operation.plugin_id, reason=operation.reason)
                    elif operation.kind == 'update':
                        await service.update_pin_reason('author-a', operation.plugin_id, operation.reason)
                    else:
                        await service.remove_pin('author-a', operation.plugin_id)
                except ApiError:
                    pass

            listed = await service.list_pins('author-a')
            expected_order, expected_reasons = _derive_expected(operations)

            assert len(listed) <= MAX_ACTIVE_PINS
            assert [item.plugin_id for item in listed] == expected_order
            assert all(item.plugin_id in ELIGIBLE_PLUGIN_IDS for item in listed)
            assert [item.pinned_at for item in listed] == sorted([item.pinned_at for item in listed], reverse=True)
            assert {item.plugin_id: item.pinned_reason for item in listed} == expected_reasons
    finally:
        profile_module.utc_now = original_utc_now


operations_strategy = st.lists(
    st.builds(
        PinOperation,
        kind=st.sampled_from(['add', 'update', 'remove']),
        plugin_id=st.sampled_from(ALL_PLUGIN_IDS),
        reason=st.one_of(st.none(), st.sampled_from(['top pick', 'fresh', 'updated'])),
    ),
    min_size=0,
    max_size=16,
)


@settings(deadline=None, max_examples=20)
@given(operations=operations_strategy)
def test_pinned_invariants_hold_after_operation_sequence(operations: list[PinOperation]) -> None:
    asyncio.run(_run_case(operations))