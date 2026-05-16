"""Property tests for review-record audit trail completeness."""

from __future__ import annotations

import asyncio
import os

from hypothesis import given, settings
from hypothesis import strategies as st
from sqlalchemy import func, select

from plugin_market_backend.config import reset_settings_cache
from plugin_market_backend.database import close_database, configure_database, init_database, session_scope
from plugin_market_backend.enums import PluginStatus, ReviewAction, TrustLevel, VersionStatus
from plugin_market_backend.orm import AuthorORM, AuthorType, PluginMaintainerORM, ReviewRecordORM, utc_now
from plugin_market_backend.schemas import AnnouncementCreate, AnnouncementUpdate, CurationEntryCreate, CurationEntryUpdate, PluginCreate, PluginVersionCreate
from plugin_market_backend.services.announcements_service import AnnouncementsService
from plugin_market_backend.services.bulk_ops_service import BulkOpsService
from plugin_market_backend.services.curation_service import CurationService
from plugin_market_backend.services.inline_edit_service import InlineEditService
from plugin_market_backend.service import MarketService


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


def _version_payload(version: str = '1.0.0') -> PluginVersionCreate:
    return PluginVersionCreate(
        version=version,
        release_tag=f'v{version}',
        release_title=f'Release {version}',
        release_url=f'https://github.com/MoFox-Studio/sample/releases/tag/v{version}',
        asset_name=f'sample-{version}.mfp',
        asset_download_url=f'https://github.com/MoFox-Studio/sample/releases/download/v{version}/sample-{version}.mfp',
        checksum_sha256='a' * 64,
        file_size=1234,
        plugin_api_version='1.0',
        min_host_version='1.0.0',
    )


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


async def _count_reviews(session) -> int:
    return int((await session.scalar(select(func.count()).select_from(ReviewRecordORM))) or 0)


async def _run_case(operation: str, affected_targets: int) -> None:
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
        await _ensure_author(session, 'maintainer')

        market = MarketService(session)
        for plugin_id in ('plug-a', 'plug-b', 'plug-c'):
            await market.register_plugin(_plugin_payload(plugin_id), owner_id='owner')
        session.add(PluginMaintainerORM(plugin_id='plug-a', author_id='maintainer'))
        await session.flush()
        await market.submit_version('plug-a', _version_payload(), 'owner')

        curation = CurationService(session)
        announcements = AnnouncementsService(session)

        entry_ids: list[int] = []
        for plugin_id in ('plug-a', 'plug-b', 'plug-c'):
            created = await curation.create(
                CurationEntryCreate(
                    slot_type='featured_plugin',
                    target_type='plugin',
                    target_id=plugin_id,
                ),
                operator_id='admin',
            )
            entry_ids.append(created.id)

        announcement = await announcements.create(
            AnnouncementCreate(
                title='Initial',
                body_markdown='body',
                display_mode='banner',
                audience='all',
            ),
            operator_id='admin',
        )

        before = await _count_reviews(session)

        if operation == 'curation_create':
            await curation.create(
                CurationEntryCreate(
                    slot_type='featured_author',
                    target_type='author',
                    target_id='owner',
                    signature_plugin_id='plug-a',
                ),
                operator_id='admin',
            )
        elif operation == 'curation_update':
            await curation.update(entry_ids[0], CurationEntryUpdate(audience='logged_in'), operator_id='admin')
        elif operation == 'curation_disable':
            await curation.disable(entry_ids[0], operator_id='admin')
        elif operation == 'curation_reorder':
            await curation.reorder(entry_ids[:affected_targets], operator_id='admin')
        elif operation == 'announcement_create':
            await announcements.create(
                AnnouncementCreate(
                    title='Created',
                    body_markdown='body',
                    display_mode='modal',
                    audience='all',
                ),
                operator_id='admin',
            )
        elif operation == 'announcement_update':
            await announcements.update(announcement.id, AnnouncementUpdate(title='Updated'), operator_id='admin')
        elif operation == 'announcement_disable':
            await announcements.disable(announcement.id, operator_id='admin')
        elif operation == 'announcement_resurface':
            await announcements.resurface(announcement.id, operator_id='admin')
        elif operation == 'bulk_publish':
            await BulkOpsService(session).bulk_apply('admin', ['plug-a', 'plug-b', 'plug-c'][:affected_targets], 'publish')
        elif operation == 'metadata_patch':
            await InlineEditService(session).patch_metadata('owner', 'plug-a', {'display_name': 'Renamed'})
        elif operation == 'plugin_block':
            await market.set_plugin_status('plug-a', PluginStatus.BLOCKED, ReviewAction.BLOCK_PLUGIN, 'admin', 'policy')
        elif operation == 'trust_level':
            await market.set_plugin_trust_level('plug-a', TrustLevel.VERIFIED, 'admin', 'trusted')
        elif operation == 'version_block':
            await market.set_version_status('plug-a', '1.0.0', VersionStatus.BLOCKED, ReviewAction.BLOCK_VERSION, 'admin', 'version-policy')
        else:  # pragma: no cover - defensive
            raise AssertionError(f'Unknown operation: {operation}')

        after = await _count_reviews(session)

        expected_delta = affected_targets if operation in {'curation_reorder', 'bulk_publish'} else 1
        if operation == 'metadata_patch':
            expected_delta = 0

        assert after - before == expected_delta


@settings(deadline=None, max_examples=24)
@given(
    operation=st.sampled_from([
        'curation_create',
        'curation_update',
        'curation_disable',
        'curation_reorder',
        'announcement_create',
        'announcement_update',
        'announcement_disable',
        'announcement_resurface',
        'bulk_publish',
        'metadata_patch',
        'plugin_block',
        'trust_level',
        'version_block',
    ]),
    affected_targets=st.integers(min_value=1, max_value=3),
)
def test_audit_trail_completeness(operation: str, affected_targets: int) -> None:
    asyncio.run(_run_case(operation, affected_targets))