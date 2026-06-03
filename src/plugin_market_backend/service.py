"""Business services for the plugin market backend."""

from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime, timedelta
import re
import secrets
import hashlib
from typing import Any

from packaging.version import InvalidVersion, Version
from sqlalchemy import case, delete, func, or_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from plugin_market_backend.config import get_settings
from plugin_market_backend.content import delete_plugin_icon, normalize_readme_markdown, render_readme_html, store_plugin_icon
from plugin_market_backend.enums import AuthorType, PluginStatus, ReviewAction, SyncStatus, TrustLevel, VersionStatus
from plugin_market_backend.errors import ApiError
from plugin_market_backend.orm import AuthorAccessTokenORM, AuthorFollowORM, AuthorORM, AuthorProfileORM, CommentMentionORM, CurationEntryORM, InboxMessageORM, PluginCommentORM, PluginLikeORM, PluginMaintainerORM, PluginORM, PluginRatingORM, PluginSubscriptionORM, PluginVersionORM, ReviewRecordORM, WebhookEventORM, utc_now
from plugin_market_backend.schemas import (
    AccessTokenRotateResponse,
    AccessTokenStatus,
    ActivityPoint,
    AdminDashboard,
    Author,
    AuthorFollowState,
    Comment,
    CommentAuthor,
    CurationEntryDTO,
    MarketStats,
    MachineSubscriptionItem,
    MachineSubscriptionListResponse,
    MyFollowItem,
    MyFollowListResponse,
    MySubscriptionItem,
    MySubscriptionListResponse,
    MentionCandidate,
    Plugin,
    PluginCreate,
    PluginDependenciesResponse,
    PluginDependency,
    PluginGovernanceSnapshot,
    PluginReadmeResponse,
    PluginStatusResponse,
    PluginSubscriptionState,
    PluginUpdate,
    PluginVersion,
    PluginVersionCreate,
    RatingSummary,
    ReviewRecord,
    TrendingItem,
    TrendingPlugin,
    VersionStatusItem,
    VersionSyncRequest,
)


def _status_text(value: object) -> str | None:
    """Convert enum values into stable audit text."""

    if value is None:
        return None
    enum_value = getattr(value, "value", None)
    if enum_value is not None:
        return str(enum_value)
    return str(value)


def _version_key(value: str) -> tuple[int, Version | str]:
    """Return a sorting key that prefers parsed versions but tolerates arbitrary tags."""

    try:
        return (1, Version(value))
    except InvalidVersion:
        return (0, value)


def _hash_access_token(token: str) -> str:
    """Hash a market access token for storage."""

    return hashlib.sha256(token.encode("utf-8")).hexdigest()


_PLUGIN_DEPENDENCY_PATTERN = re.compile(
    r"^(?P<name>[A-Za-z0-9_-]+)(?P<spec>\s*(?:===|==|!=|~=|>=|<=|>|<).+)?$"
)


class MarketService:
    """Persistent market service using SQLAlchemy sessions."""

    def __init__(self, session: AsyncSession) -> None:
        """Create a service bound to one transactional session."""

        self.session = session

    def _review_required(self) -> bool:
        """Return whether author submissions should wait for manual review."""

        return get_settings().require_review

    async def ensure_author(
        self,
        author_id: str,
        *,
        github_user_id: str | None = None,
        github_login: str | None = None,
        display_name: str | None = None,
        avatar_url: str | None = None,
        is_admin: bool = False,
    ) -> AuthorORM:
        """Return an author, creating a verified local record when missing."""

        # Avoid query-triggered autoflush while the caller may still have
        # pending relationship rows that point at this author.
        with self.session.no_autoflush:
            record = await self.session.get(AuthorORM, author_id)
        if record is not None:
            if github_user_id is not None:
                record.github_user_id = github_user_id
            if github_login is not None:
                record.github_login = github_login
            if display_name is not None:
                record.display_name = display_name
            if avatar_url is not None:
                record.avatar_url = avatar_url
            if is_admin and not record.is_admin:
                record.is_admin = True
            record.verified_at = record.verified_at or utc_now()
            record.updated_at = utc_now()
            return record
        login = github_login or author_id
        # Check by github_login to avoid unique-constraint violation.
        # Use no_autoflush so pending PluginMaintainerORM rows (whose
        # author_id may not be in the DB yet) don't get flushed here.
        with self.session.no_autoflush:
            stmt = select(AuthorORM).where(AuthorORM.github_login == login)
            existing = (await self.session.execute(stmt)).scalar_one_or_none()
        if existing is not None:
            return existing
        record = AuthorORM(
            author_id=author_id,
            github_user_id=github_user_id,
            github_login=login,
            display_name=display_name or author_id,
            avatar_url=avatar_url,
            author_type=AuthorType.USER,
            verified_at=utc_now(),
            is_admin=is_admin,
        )
        try:
            async with self.session.begin_nested():
                self.session.add(record)
                await self.session.flush()
        except IntegrityError:
            # Savepoint was rolled back; author already exists with different id
            with self.session.no_autoflush:
                stmt = select(AuthorORM).where(AuthorORM.github_login == login)
                return (await self.session.execute(stmt)).scalar_one()
        return record

    async def search_authors(self, prefix: str, *, limit: int = 8) -> list[MentionCandidate]:
        """Return authors matching a GitHub login or display-name prefix."""

        normalized = prefix.strip().lower()
        if not normalized:
            return []
        prefix_like = f"{normalized}%"
        stmt = (
            select(AuthorORM)
            .where(
                or_(
                    func.lower(AuthorORM.github_login).like(prefix_like),
                    func.lower(AuthorORM.display_name).like(prefix_like),
                )
            )
            .order_by(
                case(
                    (func.lower(AuthorORM.github_login) == normalized, 0),
                    (func.lower(AuthorORM.github_login).like(prefix_like), 1),
                    else_=2,
                ),
                func.lower(AuthorORM.github_login),
            )
            .limit(limit)
        )
        rows = list((await self.session.scalars(stmt)).all())
        return [self._mention_candidate_schema(author) for author in rows]

    async def register_plugin(self, payload: PluginCreate, owner_id: str) -> Plugin:
        """Register a plugin and publish it immediately."""

        owner_id = await self._canonical_author_id(owner_id)
        if await self.session.get(PluginORM, payload.plugin_id) is not None:
            raise ApiError(409, "PLUGIN_ALREADY_EXISTS", "Plugin already exists.", {"plugin_id": payload.plugin_id})
        now = utc_now()
        icon_url = store_plugin_icon(payload.plugin_id, payload.icon_png_base64) if payload.icon_png_base64 else (str(payload.icon_url) if payload.icon_url else None)
        plugin = PluginORM(
            plugin_id=payload.plugin_id,
            display_name=payload.display_name,
            summary=payload.summary,
            description=payload.description,
            readme_markdown=normalize_readme_markdown(payload.readme_markdown),
            plugin_dependencies=self._normalize_plugin_dependencies(payload.plugin_dependencies),
            icon_url=icon_url,
            homepage=str(payload.homepage) if payload.homepage else None,
            repository_url=str(payload.repository_url),
            license=payload.license,
            categories=payload.categories,
            tags=payload.tags,
            status=PluginStatus.PENDING_REVIEW if self._review_required() else PluginStatus.PUBLISHED,
            owner_id=owner_id,
            trust_level=TrustLevel.COMMUNITY,
            created_at=now,
            updated_at=now,
        )
        self.session.add(plugin)
        await self.session.flush()
        for maintainer_id in await self._canonical_author_ids(self._maintainer_ids(payload.maintainers, owner_id)):
            self.session.add(PluginMaintainerORM(plugin_id=plugin.plugin_id, author_id=maintainer_id))
        await self._record("plugin", plugin.plugin_id, ReviewAction.REGISTER_PLUGIN, None, plugin.status, owner_id)
        await self.session.flush()
        return await self.get_plugin(plugin.plugin_id)

    async def list_public_plugins(
        self,
        *,
        query: str | None = None,
        status: PluginStatus | None = None,
        category: str | None = None,
        tag: str | None = None,
        trust_level: TrustLevel | None = None,
        sort: str = "updated",
        offset: int = 0,
        limit: int = 50,
        viewer_id: str | None = None,
    ) -> tuple[list[Plugin], int]:
        """List public plugins with filters and pagination."""

        effective_status = status or PluginStatus.PUBLISHED
        stmt = (
            select(PluginORM)
            .options(selectinload(PluginORM.maintainers), selectinload(PluginORM.owner), selectinload(PluginORM.versions))
            .where(PluginORM.status == effective_status)
        )
        if query:
            normalized = f"%{query.lower()}%"
            stmt = stmt.where(
                or_(
                    func.lower(PluginORM.plugin_id).like(normalized),
                    func.lower(PluginORM.display_name).like(normalized),
                    func.lower(PluginORM.summary).like(normalized),
                    func.lower(PluginORM.description).like(normalized),
                )
            )
        if trust_level is not None:
            stmt = stmt.where(PluginORM.trust_level == trust_level)
        rows = list((await self.session.scalars(stmt)).all())
        if category:
            rows = [plugin for plugin in rows if category in (plugin.categories or [])]
        if tag:
            rows = [plugin for plugin in rows if tag in (plugin.tags or [])]
        total = len(rows)
        stats = await self._community_stats_for([plugin.plugin_id for plugin in rows], viewer_id)
        rows = self._sort_plugins(rows, stats, sort)
        paged = rows[offset : offset + limit]
        return [self._plugin_schema(plugin, stats.get(plugin.plugin_id)) for plugin in paged], total

    async def list_admin_plugins(self, *, offset: int = 0, limit: int = 100) -> tuple[list[Plugin], int]:
        """List all plugins for the admin console."""

        stmt = (
            select(PluginORM)
            .options(selectinload(PluginORM.maintainers), selectinload(PluginORM.owner), selectinload(PluginORM.versions))
            .order_by(PluginORM.updated_at.desc())
        )
        rows = list((await self.session.scalars(stmt)).all())
        stats = await self._community_stats_for([plugin.plugin_id for plugin in rows], None)
        return [self._plugin_schema(plugin, stats.get(plugin.plugin_id)) for plugin in rows[offset : offset + limit]], len(rows)

    async def list_owner_plugins(self, owner_id: str) -> list[Plugin]:
        """List plugins owned or maintained by one author."""

        stmt = (
            select(PluginORM)
            .options(selectinload(PluginORM.maintainers), selectinload(PluginORM.owner), selectinload(PluginORM.versions))
            .order_by(PluginORM.updated_at.desc())
        )
        rows = list((await self.session.scalars(stmt)).all())
        owned = [plugin for plugin in rows if plugin.owner_id == owner_id or owner_id in {item.author_id for item in plugin.maintainers}]
        stats = await self._community_stats_for([plugin.plugin_id for plugin in owned], owner_id)
        return [self._plugin_schema(plugin, stats.get(plugin.plugin_id)) for plugin in owned]

    async def featured_plugins(self, *, limit: int = 8, viewer_id: str | None = None) -> dict[str, list[Plugin]]:
        """Return marketplace landing sections."""

        stmt = (
            select(PluginORM)
            .options(selectinload(PluginORM.maintainers), selectinload(PluginORM.owner), selectinload(PluginORM.versions))
            .where(PluginORM.status == PluginStatus.PUBLISHED)
        )
        rows = list((await self.session.scalars(stmt)).all())
        stats = await self._community_stats_for([plugin.plugin_id for plugin in rows], viewer_id)
        latest = sorted(rows, key=lambda item: item.updated_at, reverse=True)[:limit]
        ranking = self._sort_plugins(rows, stats, "popular")[:limit]
        top_rated = self._sort_plugins(rows, stats, "rating")[:limit]
        most_downloaded = self._sort_plugins(rows, stats, "downloads")[:limit]
        trending = self._sort_plugins(rows, stats, "trending")[:limit]
        return {
            "ranking": [self._plugin_schema(item, stats.get(item.plugin_id)) for item in ranking],
            "latest": [self._plugin_schema(item, stats.get(item.plugin_id)) for item in latest],
            "top_rated": [self._plugin_schema(item, stats.get(item.plugin_id)) for item in top_rated],
            "most_downloaded": [self._plugin_schema(item, stats.get(item.plugin_id)) for item in most_downloaded],
            "trending": [self._plugin_schema(item, stats.get(item.plugin_id)) for item in trending],
        }

    async def home_categories_preview(
        self,
        *,
        per_category_limit: int = 6,
        categories_limit: int = 6,
        viewer_id: str | None = None,
    ) -> dict[str, list[Plugin]]:
        """Return preview buckets for the most populated published categories."""

        stmt = (
            select(PluginORM)
            .options(
                selectinload(PluginORM.maintainers),
                selectinload(PluginORM.owner),
                selectinload(PluginORM.versions),
            )
            .where(PluginORM.status == PluginStatus.PUBLISHED)
        )
        rows = list((await self.session.scalars(stmt)).all())
        if not rows:
            return {}

        stats = await self._community_stats_for([plugin.plugin_id for plugin in rows], viewer_id)
        counts: dict[str, int] = {}
        for plugin in rows:
            for category in plugin.categories or []:
                counts[category] = counts.get(category, 0) + 1

        category_order = sorted(counts, key=lambda item: (-counts[item], item))[:categories_limit]
        preview: dict[str, list[Plugin]] = {}
        for category in category_order:
            matching = [plugin for plugin in rows if category in (plugin.categories or [])]
            ranked = self._sort_plugins(matching, stats, "trending")[:per_category_limit]
            preview[category] = [self._plugin_schema(plugin, stats.get(plugin.plugin_id)) for plugin in ranked]
        return preview

    async def home_showcase(
        self,
        viewer: AuthorORM | None,
        *,
        viewer_has_plugin: bool = False,
        now: datetime | None = None,
    ) -> list[CurationEntryDTO]:
        """Return visible curation entries expanded for the home aggregate."""

        from plugin_market_backend.services.curation_service import is_visible as curation_is_visible

        when = now or utc_now()
        stmt = select(CurationEntryORM).order_by(
            CurationEntryORM.sort_order.asc(),
            CurationEntryORM.created_at.asc(),
            CurationEntryORM.id.asc(),
        )
        entries = list((await self.session.scalars(stmt)).all())
        if not entries:
            return []

        plugin_ids: set[str] = set()
        author_ids: set[str] = set()
        for entry in entries:
            if entry.target_type == "plugin":
                plugin_ids.add(entry.target_id)
            if entry.target_type == "author":
                author_ids.add(entry.target_id)
            if entry.signature_plugin_id:
                plugin_ids.add(entry.signature_plugin_id)

        plugin_map: dict[str, PluginORM] = {}
        if plugin_ids:
            plugin_stmt = (
                select(PluginORM)
                .options(
                    selectinload(PluginORM.maintainers),
                    selectinload(PluginORM.owner),
                    selectinload(PluginORM.versions),
                )
                .where(
                    PluginORM.plugin_id.in_(sorted(plugin_ids)),
                    PluginORM.status == PluginStatus.PUBLISHED,
                )
            )
            plugin_rows = list((await self.session.scalars(plugin_stmt)).all())
            plugin_map = {plugin.plugin_id: plugin for plugin in plugin_rows}
        plugin_stats = await self._community_stats_for(list(plugin_map), viewer.author_id if viewer else None)

        author_map: dict[str, AuthorORM] = {}
        if author_ids:
            author_rows = list((await self.session.scalars(select(AuthorORM).where(AuthorORM.author_id.in_(sorted(author_ids))))).all())
            author_map = {author.author_id: author for author in author_rows}

        result: list[CurationEntryDTO] = []
        for entry in entries:
            if not curation_is_visible(entry, viewer, when, viewer_has_plugin=viewer_has_plugin):
                continue

            plugin_schema: Plugin | None = None
            author_schema: Author | None = None
            signature_schema: Plugin | None = None

            if entry.target_type == "plugin":
                plugin_row = plugin_map.get(entry.target_id)
                if plugin_row is None:
                    continue
                plugin_schema = self._plugin_schema(plugin_row, plugin_stats.get(plugin_row.plugin_id))
            else:
                author_row = author_map.get(entry.target_id)
                if author_row is None:
                    continue
                author_schema = self._author_schema(author_row)
                if entry.signature_plugin_id is not None:
                    signature_row = plugin_map.get(entry.signature_plugin_id)
                    if signature_row is None:
                        continue
                    signature_schema = self._plugin_schema(signature_row, plugin_stats.get(signature_row.plugin_id))

            result.append(
                CurationEntryDTO(
                    id=entry.id,
                    slot_type=entry.slot_type,  # type: ignore[arg-type]
                    target_type=entry.target_type,  # type: ignore[arg-type]
                    target_id=entry.target_id,
                    signature_plugin_id=entry.signature_plugin_id,
                    sort_order=entry.sort_order,
                    enabled=entry.enabled,
                    starts_at=entry.starts_at,
                    ends_at=entry.ends_at,
                    audience=entry.audience,  # type: ignore[arg-type]
                    display_meta=dict(entry.display_meta or {}),
                    plugin=plugin_schema,
                    author=author_schema,
                    signature_plugin=signature_schema,
                    created_by=entry.created_by,
                    created_at=entry.created_at,
                    updated_at=entry.updated_at,
                )
            )
        return result

    async def get_plugin(self, plugin_id: str, viewer_id: str | None = None) -> Plugin:
        """Return plugin details or raise not found."""

        plugin = await self._get_plugin_orm(plugin_id)
        stats = await self._community_stats_for([plugin_id], viewer_id)
        return self._plugin_schema(plugin, stats.get(plugin_id))

    async def get_plugin_dependencies(self, plugin_id: str) -> PluginDependenciesResponse:
        """Return resolved plugin dependency data for one plugin detail page."""

        plugin = await self._get_plugin_orm(plugin_id)
        raw_items = self._normalize_plugin_dependencies(plugin.plugin_dependencies)
        parsed_items: list[tuple[str, str, str | None]] = []
        referenced_ids: list[str] = []

        for raw in raw_items:
            dependency_id, version_spec = self._parse_plugin_dependency_ref(raw)
            parsed_items.append((raw, dependency_id or raw, version_spec))
            if dependency_id:
                referenced_ids.append(dependency_id)

        existing: dict[str, PluginORM] = {}
        if referenced_ids:
            stmt = select(PluginORM).where(PluginORM.plugin_id.in_(sorted(set(referenced_ids))))
            existing = {
                item.plugin_id: item
                for item in list((await self.session.scalars(stmt)).all())
            }

        return PluginDependenciesResponse(
            plugin_id=plugin.plugin_id,
            items=[
                PluginDependency(
                    plugin_id=dependency_id,
                    raw=raw,
                    version_spec=version_spec,
                    exists_in_market=dependency_id in existing,
                    display_name=existing[dependency_id].display_name if dependency_id in existing else None,
                    icon_url=existing[dependency_id].icon_url if dependency_id in existing else None,
                )
                for raw, dependency_id, version_spec in parsed_items
            ],
        )

    async def update_plugin(self, plugin_id: str, payload: PluginUpdate, operator_id: str) -> Plugin:
        """Update mutable plugin metadata and keep it published unless blocked."""

        plugin = await self._get_plugin_orm(plugin_id)
        await self._ensure_owner(plugin, operator_id)
        update_data = payload.model_dump(exclude_unset=True)
        if not update_data:
            return self._plugin_schema(plugin)
        before = plugin.status
        if "icon_png_base64" in update_data:
            icon_data = update_data.pop("icon_png_base64")
            if icon_data:
                plugin.icon_url = store_plugin_icon(plugin_id, icon_data)
            else:
                delete_plugin_icon(plugin_id)
                plugin.icon_url = None
        if "readme_markdown" in update_data:
            plugin.readme_markdown = normalize_readme_markdown(update_data.pop("readme_markdown"))
        if "plugin_dependencies" in update_data:
            plugin.plugin_dependencies = self._normalize_plugin_dependencies(update_data.pop("plugin_dependencies"))
        for key, value in update_data.items():
            if key in {"icon_url", "homepage", "repository_url"} and value is not None:
                value = str(value)
            if key == "maintainers":
                continue
            if key == "icon_url" and value is None:
                delete_plugin_icon(plugin_id)
            setattr(plugin, key, value)
        if plugin.status != PluginStatus.BLOCKED:
            plugin.status = PluginStatus.PENDING_REVIEW if self._review_required() else PluginStatus.PUBLISHED
        plugin.updated_at = utc_now()
        if payload.maintainers is not None:
            await self._replace_maintainers(plugin.plugin_id, self._maintainer_ids(payload.maintainers, plugin.owner_id))
        await self._record("plugin", plugin_id, ReviewAction.UPDATE_PLUGIN, before, plugin.status, operator_id)
        await self.session.flush()
        return await self.get_plugin(plugin_id)

    async def submit_version(self, plugin_id: str, payload: PluginVersionCreate, operator_id: str) -> PluginVersion:
        """Submit a plugin version and publish it immediately."""

        plugin = await self._get_plugin_orm(plugin_id)
        await self._ensure_owner(plugin, operator_id)
        if plugin.status == PluginStatus.BLOCKED:
            raise ApiError(409, "PLUGIN_BLOCKED", "Blocked plugins cannot accept new versions.", {"plugin_id": plugin_id})
        existing = await self._get_version_orm_or_none(plugin_id, payload.version)
        if existing is not None:
            raise ApiError(409, "VERSION_ALREADY_EXISTS", "Plugin version already exists.", {"plugin_id": plugin_id, "version": payload.version})
        now = utc_now()
        version = PluginVersionORM(
            plugin_id=plugin_id,
            version=payload.version,
            release_tag=payload.release_tag,
            release_title=payload.release_title,
            release_url=str(payload.release_url),
            asset_name=payload.asset_name,
            asset_download_url=str(payload.asset_download_url),
            checksum_sha256=payload.checksum_sha256,
            file_size=payload.file_size,
            published_at=now,
            is_prerelease=payload.is_prerelease,
            is_yanked=False,
            status=VersionStatus.PUBLISHED,
            plugin_api_version=payload.plugin_api_version,
            min_host_version=payload.min_host_version,
            max_host_version=payload.max_host_version,
            supported_platforms=payload.supported_platforms,
        )
        self.session.add(version)
        if "readme_markdown" in payload.model_fields_set:
            plugin.readme_markdown = normalize_readme_markdown(payload.readme_markdown)
        plugin.updated_at = now
        await self._record("version", f"{plugin_id}@{payload.version}", ReviewAction.SUBMIT_VERSION, None, version.status, operator_id)
        await self.session.flush()
        await self._fan_out_plugin_event(
            plugin,
            event="version_published",
            preview=f"{plugin.display_name} published {payload.version}",
            source_author_id=plugin.owner_id,
            version=payload.version,
        )
        return self._version_schema(version)

    def _is_public_version(self, version: PluginVersionORM) -> bool:
        """Return whether a version should appear on public endpoints."""

        return version.status in {VersionStatus.PUBLISHED, VersionStatus.YANKED}

    async def list_versions(self, plugin_id: str) -> list[PluginVersion]:
        """List versions for a plugin."""

        await self._get_plugin_orm(plugin_id)
        stmt = select(PluginVersionORM).where(PluginVersionORM.plugin_id == plugin_id).order_by(PluginVersionORM.published_at.desc())
        versions = list((await self.session.scalars(stmt)).all())
        return [self._version_schema(item) for item in versions if self._is_public_version(item)]

    async def get_version(self, plugin_id: str, version: str) -> PluginVersion:
        """Return a plugin version or raise not found."""

        record = await self._get_version_orm(plugin_id, version)
        if not self._is_public_version(record):
            raise ApiError(404, "VERSION_NOT_FOUND", "Plugin version was not found.", {"plugin_id": plugin_id, "version": version})
        return self._version_schema(record)

    async def get_recommended_version(
        self,
        plugin_id: str,
        *,
        host_version: str | None = None,
        plugin_api_version: str | None = None,
        platform: str | None = None,
        include_prerelease: bool = False,
    ) -> PluginVersion:
        """Return the newest compatible published version."""

        plugin = await self._get_plugin_orm(plugin_id)
        if plugin.status == PluginStatus.BLOCKED:
            raise ApiError(404, "VERSION_NOT_FOUND", "No installable version found.", {"plugin_id": plugin_id})
        versions = list((await self.session.scalars(select(PluginVersionORM).where(PluginVersionORM.plugin_id == plugin_id))).all())
        candidates = [
            version
            for version in versions
            if version.status == VersionStatus.PUBLISHED
            and not version.is_yanked
            and (include_prerelease or not version.is_prerelease)
            and self._matches_host(version, host_version)
            and self._matches_api(version, plugin_api_version)
            and self._matches_platform(version, platform)
        ]
        if not candidates:
            code = "NO_COMPATIBLE_VERSION" if host_version or plugin_api_version or platform else "VERSION_NOT_FOUND"
            raise ApiError(404, code, "No installable version found.", {"plugin_id": plugin_id})
        candidates.sort(key=lambda item: (_version_key(item.version), item.published_at), reverse=True)
        return self._version_schema(candidates[0])

    async def get_status(self, plugin_id: str) -> PluginStatusResponse:
        """Return plugin and version status for CLI."""

        plugin = await self._get_plugin_orm(plugin_id)
        records = list((await self.session.scalars(select(PluginVersionORM).where(PluginVersionORM.plugin_id == plugin_id))).all())
        return PluginStatusResponse(
            plugin_id=plugin.plugin_id,
            plugin_status=plugin.status,
            versions=[
                VersionStatusItem(
                    version=record.version,
                    status=record.status,
                    is_yanked=record.is_yanked,
                    last_sync_status=record.last_sync_status,
                    last_sync_error=record.last_sync_error,
                )
                for record in sorted(records, key=lambda item: (_version_key(item.version), item.published_at), reverse=True)
            ],
        )

    async def sync_version(self, plugin_id: str, payload: VersionSyncRequest, operator_id: str) -> PluginVersion:
        """Apply CLI sync metadata to an existing version."""

        plugin = await self._get_plugin_orm(plugin_id)
        await self._ensure_owner(plugin, operator_id)
        version = await self._get_version_orm(plugin_id, payload.version)
        for key, value in payload.model_dump(exclude_none=True, exclude={"version"}).items():
            if key in {"release_url", "asset_download_url"} and value is not None:
                value = str(value)
            setattr(version, key, value)
        before = version.last_sync_status
        version.last_sync_status = SyncStatus.SUCCESS
        version.last_sync_error = None
        version.updated_at = utc_now()
        await self._record("version", f"{plugin_id}@{payload.version}", ReviewAction.SYNC_VERSION, before, SyncStatus.SUCCESS, operator_id)
        await self.session.flush()
        return self._version_schema(version)

    async def yank_version(self, plugin_id: str, version: str, operator_id: str, reason: str | None = None) -> PluginVersion:
        """Allow a plugin owner to yank a version."""

        plugin = await self._get_plugin_orm(plugin_id)
        await self._ensure_owner(plugin, operator_id)
        return await self.set_version_status(plugin_id, version, VersionStatus.YANKED, ReviewAction.YANK_VERSION, operator_id, reason, is_yanked=True)

    async def delete_owner_plugin(self, plugin_id: str, operator_id: str) -> None:
        """Allow a plugin owner or maintainer to delete one of their plugins."""

        plugin = await self._get_plugin_orm(plugin_id)
        await self._ensure_owner(plugin, operator_id)
        await self.delete_plugin(plugin_id)

    async def plugin_governance_snapshot(
        self,
        plugin_id: str,
        *,
        viewer_id: str | None = None,
        operator_id: str | None = None,
        review_limit: int = 25,
    ) -> PluginGovernanceSnapshot:
        """Return a management snapshot for admin or owner workflows."""

        plugin = await self._get_plugin_orm(plugin_id)
        if operator_id is not None:
            await self._ensure_owner(plugin, operator_id)
        stats = await self._community_stats_for([plugin_id], viewer_id or operator_id)
        versions_stmt = (
            select(PluginVersionORM)
            .where(PluginVersionORM.plugin_id == plugin_id)
            .order_by(PluginVersionORM.published_at.desc())
        )
        versions = [self._version_schema(item) for item in await self.session.scalars(versions_stmt)]
        reviews = await self._plugin_reviews(plugin_id, limit=review_limit)
        return PluginGovernanceSnapshot(
            plugin=self._plugin_schema(plugin, stats.get(plugin_id)),
            versions=versions,
            recent_reviews=reviews,
        )

    async def delete_plugin(self, plugin_id: str) -> None:
        """Delete a plugin and all marketplace records associated with it."""

        plugin = await self._get_plugin_orm(plugin_id)
        await self.session.execute(delete(PluginLikeORM).where(PluginLikeORM.plugin_id == plugin_id))
        await self.session.execute(delete(PluginSubscriptionORM).where(PluginSubscriptionORM.plugin_id == plugin_id))
        await self.session.execute(delete(PluginRatingORM).where(PluginRatingORM.plugin_id == plugin_id))
        comment_ids = (await self.session.execute(select(PluginCommentORM.id).where(PluginCommentORM.plugin_id == plugin_id))).scalars().all()
        if comment_ids:
            await self.session.execute(update(PluginCommentORM).where(PluginCommentORM.parent_id.in_(comment_ids)).values(parent_id=None))
            await self.session.execute(update(InboxMessageORM).where(InboxMessageORM.related_comment_id.in_(comment_ids)).values(related_comment_id=None))
            await self.session.execute(delete(CommentMentionORM).where(CommentMentionORM.comment_id.in_(comment_ids)))
        await self.session.execute(update(InboxMessageORM).where(InboxMessageORM.related_plugin_id == plugin_id).values(related_plugin_id=None))
        await self.session.execute(delete(PluginCommentORM).where(PluginCommentORM.plugin_id == plugin_id))
        await self.session.execute(
            delete(ReviewRecordORM).where(
                or_(
                    ReviewRecordORM.target_id == plugin_id,
                    ReviewRecordORM.target_id.like(f"{plugin_id}@%"),
                )
            )
        )
        await self.session.delete(plugin)
        await self.session.flush()

    async def set_plugin_status(self, plugin_id: str, status: PluginStatus, action: ReviewAction, operator_id: str, reason: str | None = None) -> Plugin:
        """Set plugin status and record the action."""

        plugin = await self._get_plugin_orm(plugin_id)
        before = plugin.status
        plugin.status = status
        plugin.updated_at = utc_now()
        await self._record("plugin", plugin_id, action, before, status, operator_id, reason)
        if await self._is_admin_operator(operator_id):
            from plugin_market_backend.services.inbox_service import InboxService

            await InboxService(self.session).fan_out_for_governance(plugin, action.value, operator_id, reason)
        await self.session.flush()
        await self._fan_out_plugin_event(
            plugin,
            event=f"plugin_{status.value}",
            preview=f"{plugin.display_name} status changed to {status.value}",
            source_author_id=plugin.owner_id,
        )
        return await self.get_plugin(plugin_id)

    async def set_plugin_trust_level(
        self,
        plugin_id: str,
        trust_level: TrustLevel,
        operator_id: str,
        reason: str | None = None,
    ) -> Plugin:
        """Set plugin trust level and record the action."""

        plugin = await self._get_plugin_orm(plugin_id)
        before = plugin.trust_level
        plugin.trust_level = trust_level
        plugin.updated_at = utc_now()
        await self._record("plugin", plugin_id, ReviewAction.SET_TRUST_LEVEL, before, trust_level, operator_id, reason)
        if await self._is_admin_operator(operator_id):
            from plugin_market_backend.services.inbox_service import InboxService

            await InboxService(self.session).fan_out_for_governance(plugin, ReviewAction.SET_TRUST_LEVEL.value, operator_id, reason)
        await self.session.flush()
        return await self.get_plugin(plugin_id)

    async def set_version_status(
        self,
        plugin_id: str,
        version: str,
        status: VersionStatus,
        action: ReviewAction,
        operator_id: str,
        reason: str | None = None,
        is_yanked: bool | None = None,
    ) -> PluginVersion:
        """Set version status and record the action."""

        record = await self._get_version_orm(plugin_id, version)
        before = record.status
        record.status = status
        if is_yanked is not None:
            record.is_yanked = is_yanked
        record.updated_at = utc_now()
        await self._record("version", f"{plugin_id}@{version}", action, before, status, operator_id, reason)
        if action in {ReviewAction.YANK_VERSION, ReviewAction.BLOCK_VERSION} and await self._is_admin_operator(operator_id):
            from plugin_market_backend.services.inbox_service import InboxService

            plugin = await self._get_plugin_orm(plugin_id)
            await InboxService(self.session).fan_out_for_governance(plugin, action.value, operator_id, reason)
        await self.session.flush()
        plugin = await self._get_plugin_orm(plugin_id)
        await self._fan_out_plugin_event(
            plugin,
            event=f"version_{status.value}",
            preview=f"{plugin.display_name} version {version} status changed to {status.value}",
            source_author_id=plugin.owner_id,
            version=version,
        )
        return self._version_schema(record)

    async def list_reviews(self) -> list[ReviewRecord]:
        """List audit records newest last to match existing mock behavior."""

        stmt = select(ReviewRecordORM).order_by(ReviewRecordORM.id.asc())
        return [self._review_schema(item) for item in await self.session.scalars(stmt)]

    async def stats(self) -> MarketStats:
        """Return aggregate market stats."""

        plugins_total = await self.session.scalar(select(func.count()).select_from(PluginORM))
        versions_total = await self.session.scalar(select(func.count()).select_from(PluginVersionORM))
        comments_total = await self.session.scalar(
            select(func.count()).select_from(PluginCommentORM).where(PluginCommentORM.is_deleted.is_(False))
        )
        ratings_total = await self.session.scalar(select(func.count()).select_from(PluginRatingORM))
        likes_total = await self.session.scalar(select(func.count()).select_from(PluginSubscriptionORM))
        downloads_total = await self.session.scalar(select(func.coalesce(func.sum(PluginVersionORM.download_count), 0)))
        pending_plugins = await self.session.scalar(select(func.count()).select_from(PluginORM).where(PluginORM.status == PluginStatus.PENDING_REVIEW))
        pending_versions = await self.session.scalar(select(func.count()).select_from(PluginVersionORM).where(PluginVersionORM.status == VersionStatus.PENDING_REVIEW))
        published_plugins = await self.session.scalar(select(func.count()).select_from(PluginORM).where(PluginORM.status == PluginStatus.PUBLISHED))
        blocked_plugins = await self.session.scalar(select(func.count()).select_from(PluginORM).where(PluginORM.status == PluginStatus.BLOCKED))
        deprecated_plugins = await self.session.scalar(select(func.count()).select_from(PluginORM).where(PluginORM.status == PluginStatus.DEPRECATED))
        archived_plugins = await self.session.scalar(select(func.count()).select_from(PluginORM).where(PluginORM.status == PluginStatus.ARCHIVED))
        authors_total = await self.session.scalar(select(func.count()).select_from(AuthorORM))
        webhooks_total = await self.session.scalar(select(func.count()).select_from(WebhookEventORM))
        latest_review_at = await self.session.scalar(select(func.max(ReviewRecordORM.created_at)))
        return MarketStats(
            plugins_total=plugins_total or 0,
            versions_total=versions_total or 0,
            comments_total=comments_total or 0,
            ratings_total=ratings_total or 0,
            likes_total=likes_total or 0,
            downloads_total=int(downloads_total or 0),
            pending_plugins=pending_plugins or 0,
            pending_versions=pending_versions or 0,
            published_plugins=published_plugins or 0,
            blocked_plugins=blocked_plugins or 0,
            deprecated_plugins=deprecated_plugins or 0,
            archived_plugins=archived_plugins or 0,
            authors_total=authors_total or 0,
            webhooks_total=webhooks_total or 0,
            latest_review_at=latest_review_at,
        )

    async def admin_dashboard(self, *, days: int = 7, top_limit: int = 6) -> AdminDashboard:
        """Return a richer management dashboard payload."""

        stats = await self.stats()
        plugin_status_breakdown = {status.value: 0 for status in PluginStatus}
        version_status_breakdown = {status.value: 0 for status in VersionStatus}

        plugin_status_rows = await self.session.execute(select(PluginORM.status, func.count()).group_by(PluginORM.status))
        for status_value, count in plugin_status_rows:
            key = status_value.value if hasattr(status_value, "value") else str(status_value)
            plugin_status_breakdown[key] = int(count or 0)

        version_status_rows = await self.session.execute(select(PluginVersionORM.status, func.count()).group_by(PluginVersionORM.status))
        for status_value, count in version_status_rows:
            key = status_value.value if hasattr(status_value, "value") else str(status_value)
            version_status_breakdown[key] = int(count or 0)

        today = utc_now().date()
        days_in_window = [today - timedelta(days=offset) for offset in reversed(range(max(days, 1)))]
        buckets = {
            day.isoformat(): ActivityPoint(date=day.isoformat())
            for day in days_in_window
        }

        def mark(rows: list[datetime], field_name: str) -> None:
            for created_at in rows:
                day_key = created_at.date().isoformat()
                bucket = buckets.get(day_key)
                if bucket is not None:
                    setattr(bucket, field_name, getattr(bucket, field_name) + 1)

        mark(list(await self.session.scalars(select(PluginORM.created_at))), "plugins_created")
        mark(list(await self.session.scalars(select(PluginVersionORM.created_at))), "versions_created")
        mark(list(await self.session.scalars(select(PluginCommentORM.created_at).where(PluginCommentORM.is_deleted.is_(False)))), "comments_created")
        mark(list(await self.session.scalars(select(PluginRatingORM.created_at))), "ratings_created")
        mark(list(await self.session.scalars(select(ReviewRecordORM.created_at))), "review_events")

        stmt = (
            select(PluginORM)
            .options(selectinload(PluginORM.maintainers), selectinload(PluginORM.owner), selectinload(PluginORM.versions))
            .order_by(PluginORM.updated_at.desc())
        )
        plugins = list((await self.session.scalars(stmt)).all())
        plugin_stats = await self._community_stats_for([plugin.plugin_id for plugin in plugins], None)
        popular_plugins = [
            self._plugin_schema(item, plugin_stats.get(item.plugin_id))
            for item in self._sort_plugins(plugins, plugin_stats, "trending")[:top_limit]
        ]

        return AdminDashboard(
            stats=stats,
            plugin_status_breakdown=plugin_status_breakdown,
            version_status_breakdown=version_status_breakdown,
            activity=[buckets[day.isoformat()] for day in days_in_window],
            popular_plugins=popular_plugins,
        )

    async def categories(self) -> list[str]:
        """Return all known categories."""

        rows = await self.session.scalars(select(PluginORM.categories))
        return sorted({category for categories in rows for category in (categories or [])})

    async def tags(self) -> list[str]:
        """Return all known tags."""

        rows = await self.session.scalars(select(PluginORM.tags))
        return sorted({tag for tags in rows for tag in (tags or [])})

    async def record_webhook(self, event_id: str, event_name: str, action: str | None, payload: dict[str, Any]) -> None:
        """Persist a GitHub webhook event and audit marker."""

        if await self.session.get(WebhookEventORM, event_id) is not None:
            return
        self.session.add(WebhookEventORM(event_id=event_id, event_name=event_name, action=action, payload=payload))
        await self._record("webhook", event_id, ReviewAction.WEBHOOK_RECEIVED, None, action or event_name, "github")

    async def _get_plugin_orm(self, plugin_id: str) -> PluginORM:
        """Return a plugin ORM object with maintainers, owner and versions loaded."""

        stmt = (
            select(PluginORM)
            .options(
                selectinload(PluginORM.maintainers),
                selectinload(PluginORM.owner),
                selectinload(PluginORM.versions),
            )
            .where(PluginORM.plugin_id == plugin_id)
        )
        plugin = await self.session.scalar(stmt)
        if plugin is None:
            raise ApiError(404, "PLUGIN_NOT_FOUND", "Plugin not found.", {"plugin_id": plugin_id})
        return plugin

    async def _get_version_orm_or_none(self, plugin_id: str, version: str) -> PluginVersionORM | None:
        """Return a version ORM object or None."""

        return await self.session.scalar(select(PluginVersionORM).where(PluginVersionORM.plugin_id == plugin_id, PluginVersionORM.version == version))

    async def _get_version_orm(self, plugin_id: str, version: str) -> PluginVersionORM:
        """Return a version ORM object or raise not found."""

        await self._get_plugin_orm(plugin_id)
        record = await self._get_version_orm_or_none(plugin_id, version)
        if record is None:
            raise ApiError(404, "VERSION_NOT_FOUND", "Plugin version not found.", {"plugin_id": plugin_id, "version": version})
        return record

    async def _ensure_owner(self, plugin: PluginORM, operator_id: str) -> None:
        """Require the operator to own or maintain the plugin."""

        maintainer_ids = {item.author_id for item in plugin.maintainers}
        if plugin.owner_id != operator_id and operator_id not in maintainer_ids:
            raise ApiError(403, "FORBIDDEN", "You do not have permission to modify this plugin.", {"plugin_id": plugin.plugin_id})

    async def _replace_maintainers(self, plugin_id: str, maintainer_ids: Iterable[str]) -> None:
        """Replace plugin maintainer records."""

        await self.session.execute(delete(PluginMaintainerORM).where(PluginMaintainerORM.plugin_id == plugin_id))
        for maintainer_id in await self._canonical_author_ids(maintainer_ids):
            self.session.add(PluginMaintainerORM(plugin_id=plugin_id, author_id=maintainer_id))
        try:
            await self.session.flush()
        except IntegrityError as exc:
            raise ApiError(409, "MAINTAINER_CONFLICT", "Maintainer mapping already exists.", {"plugin_id": plugin_id}) from exc

    async def _record(
        self,
        target_type: str,
        target_id: str,
        action: ReviewAction,
        before: object,
        after: object,
        operator_id: str,
        reason: str | None = None,
    ) -> None:
        """Append a review record."""

        self.session.add(
            ReviewRecordORM(
                target_type=target_type,
                target_id=target_id,
                action=action,
                status_before=_status_text(before),
                status_after=_status_text(after),
                reason=reason,
                operator_id=operator_id,
            )
        )

    async def _plugin_reviews(self, plugin_id: str, *, limit: int = 25) -> list[ReviewRecord]:
        """Return recent review records for one plugin and its versions."""

        stmt = (
            select(ReviewRecordORM)
            .where(
                or_(
                    ReviewRecordORM.target_id == plugin_id,
                    ReviewRecordORM.target_id.like(f"{plugin_id}@%"),
                )
            )
            .order_by(ReviewRecordORM.created_at.desc())
            .limit(limit)
        )
        return [self._review_schema(item) for item in await self.session.scalars(stmt)]

    async def get_plugin_readme(self, plugin_id: str) -> PluginReadmeResponse:
        """Return rendered README content for a plugin detail page."""

        plugin = await self._get_plugin_orm(plugin_id)
        html = render_readme_html(plugin.readme_markdown)
        return PluginReadmeResponse(plugin_id=plugin.plugin_id, exists=html is not None, html=html)

    async def _fan_out_plugin_event(
        self,
        plugin: PluginORM,
        *,
        event: str,
        preview: str,
        source_author_id: str,
        version: str | None = None,
    ) -> None:
        """Fan out plugin and author activity events to subscribers / followers."""

        from plugin_market_backend.services.inbox_service import InboxService

        inbox_service = InboxService(self.session)
        payload = {
            "event": event,
            "plugin_id": plugin.plugin_id,
            "plugin_display_name": plugin.display_name,
            "version": version,
            "preview": preview,
        }
        if plugin.owner_id:
            await inbox_service.fan_out_for_author_activity(
                author_id=plugin.owner_id,
                source_author_id=source_author_id,
                dedup_key=f"author-activity:{event}:{plugin.plugin_id}:{version or 'none'}",
                payload=payload,
                related_plugin_id=plugin.plugin_id,
            )
        await inbox_service.fan_out_for_plugin_activity(
            plugin_id=plugin.plugin_id,
            source_author_id=source_author_id,
            dedup_key=f"plugin-activity:{event}:{plugin.plugin_id}:{version or 'none'}",
            payload=payload,
        )

    def _latest_public_version(self, plugin: PluginORM) -> PluginVersionORM | None:
        """Return the latest published non-yanked version for a plugin."""

        published = [
            item
            for item in (plugin.versions or [])
            if item.status == VersionStatus.PUBLISHED and not item.is_yanked
        ]
        if not published:
            return None
        return max(published, key=lambda item: (_version_key(item.version), item.published_at))

    def _plugin_schema(self, plugin: PluginORM, stats: dict[str, Any] | None = None) -> Plugin:
        """Convert a plugin ORM object to API schema."""

        stats = stats or {}
        owner = plugin.owner if getattr(plugin, "owner", None) is not None else None
        versions = list(plugin.versions or [])
        latest = self._latest_public_version(plugin)
        downloads_count = stats.get("downloads_count", sum(int(item.download_count or 0) for item in versions))
        return Plugin(
            plugin_id=plugin.plugin_id,
            display_name=plugin.display_name,
            summary=plugin.summary,
            description=plugin.description,
            icon_url=plugin.icon_url,
            has_readme=bool(normalize_readme_markdown(plugin.readme_markdown)),
            homepage=plugin.homepage,
            repository_url=plugin.repository_url,
            license=plugin.license,
            categories=plugin.categories or [],
            tags=plugin.tags or [],
            status=plugin.status,
            owner_id=plugin.owner_id,
            owner_login=owner.github_login if owner is not None else None,
            owner_display_name=owner.display_name if owner is not None else None,
            owner_avatar_url=owner.avatar_url if owner is not None else None,
            maintainers=[item.author_id for item in plugin.maintainers],
            trust_level=plugin.trust_level,
            risk_notice=plugin.risk_notice,
            created_at=plugin.created_at,
            updated_at=plugin.updated_at,
            likes_count=int(stats.get("likes_count", 0) or 0),
            rating_avg=float(stats.get("rating_avg", 0.0) or 0.0),
            rating_count=int(stats.get("rating_count", 0) or 0),
            comments_count=int(stats.get("comments_count", 0) or 0),
            downloads_count=int(downloads_count or 0),
            latest_version=latest.version if latest else None,
            latest_version_published_at=latest.published_at if latest else None,
            viewer_has_liked=bool(stats.get("viewer_has_liked", False)),
            viewer_rating=stats.get("viewer_rating"),
        )

    def _normalize_plugin_dependencies(self, values: Iterable[str] | None) -> list[str]:
        """Normalize plugin dependency references from manifest payloads."""

        normalized: list[str] = []
        for value in values or []:
            item = str(value).strip()
            if item:
                normalized.append(item)
        return normalized

    def _parse_plugin_dependency_ref(self, ref: str) -> tuple[str, str | None]:
        """Split a dependency reference into plugin id and version spec."""

        value = str(ref or "").strip()
        if not value:
            return "", None

        name, separator, remainder = value.partition(":")
        if separator and remainder.lstrip().startswith(("===", "==", "!=", "~=", ">=", "<=", ">", "<")):
            return name.strip(), remainder.strip() or None

        match = _PLUGIN_DEPENDENCY_PATTERN.match(value)
        if match:
            return match.group("name"), (match.group("spec") or "").strip() or None
        return value, None

    def _version_schema(self, version: PluginVersionORM) -> PluginVersion:
        """Convert a version ORM object to API schema."""

        return PluginVersion(
            plugin_id=version.plugin_id,
            version=version.version,
            release_tag=version.release_tag,
            release_title=version.release_title,
            release_url=version.release_url,
            asset_name=version.asset_name,
            asset_download_url=version.asset_download_url,
            checksum_sha256=version.checksum_sha256,
            file_size=version.file_size,
            published_at=version.published_at,
            is_prerelease=version.is_prerelease,
            is_yanked=version.is_yanked,
            status=version.status,
            plugin_api_version=version.plugin_api_version,
            min_host_version=version.min_host_version,
            max_host_version=version.max_host_version,
            supported_platforms=version.supported_platforms or [],
            last_sync_status=version.last_sync_status,
            last_sync_error=version.last_sync_error,
            download_count=int(version.download_count or 0),
        )

    def _review_schema(self, record: ReviewRecordORM) -> ReviewRecord:
        """Convert an audit ORM object to API schema."""

        return ReviewRecord(
            target_type=record.target_type,
            target_id=record.target_id,
            action=record.action,
            status_before=record.status_before,
            status_after=record.status_after,
            reason=record.reason,
            operator_id=record.operator_id,
            created_at=record.created_at,
        )

    def _author_schema(self, author: AuthorORM) -> Author:
        """Convert an author ORM object to the public author schema."""

        return Author(
            author_id=author.author_id,
            github_user_id=author.github_user_id,
            github_login=author.github_login,
            display_name=author.display_name,
            avatar_url=author.avatar_url,
            author_type=author.author_type,
            verified_at=author.verified_at,
            is_admin=author.is_admin,
        )

    def _maintainer_ids(self, maintainers: Iterable[str], owner_id: str) -> list[str]:
        """Normalize maintainer lists and always include the owner."""

        values = [item for item in maintainers if item]
        if owner_id not in values:
            values.append(owner_id)
        return list(dict.fromkeys(values))

    async def _canonical_author_id(self, author_id: str) -> str:
        """Resolve one author identifier to the persisted canonical author id."""

        return (await self.ensure_author(author_id)).author_id

    async def _canonical_author_ids(self, author_ids: Iterable[str]) -> list[str]:
        """Resolve author identifiers and de-duplicate by canonical id."""

        resolved: list[str] = []
        seen: set[str] = set()
        for author_id in author_ids:
            canonical_id = await self._canonical_author_id(author_id)
            if canonical_id in seen:
                continue
            seen.add(canonical_id)
            resolved.append(canonical_id)
        return resolved

    async def _is_admin_operator(self, operator_id: str) -> bool:
        """Return whether ``operator_id`` currently belongs to an admin."""

        author = await self.session.get(AuthorORM, operator_id)
        return bool(author and author.is_admin)

    def _matches_host(self, version: PluginVersionORM, host_version: str | None) -> bool:
        """Return whether the version supports the requested host version."""

        if not host_version:
            return True
        try:
            host = Version(host_version)
            minimum = Version(version.min_host_version)
            maximum = Version(version.max_host_version) if version.max_host_version else None
        except InvalidVersion:
            return True
        if host < minimum:
            return False
        return maximum is None or host <= maximum

    def _matches_api(self, version: PluginVersionORM, plugin_api_version: str | None) -> bool:
        """Return whether the version supports the requested plugin API version."""

        return not plugin_api_version or version.plugin_api_version == plugin_api_version

    def _matches_platform(self, version: PluginVersionORM, platform: str | None) -> bool:
        """Return whether the version supports the requested platform."""

        if not platform:
            return True
        platforms = {item.lower() for item in (version.supported_platforms or [])}
        return "all" in platforms or platform.lower() in platforms

    # ------------------------------------------------------------------
    # Community features: likes, ratings, comments, downloads, authors
    # ------------------------------------------------------------------

    async def _community_stats_for(self, plugin_ids: list[str], viewer_id: str | None) -> dict[str, dict[str, Any]]:
        """Aggregate community counters for a batch of plugins."""

        if not plugin_ids:
            return {}
        stats: dict[str, dict[str, Any]] = {
            plugin_id: {
                "likes_count": 0,
                "rating_avg": 0.0,
                "rating_count": 0,
                "comments_count": 0,
                "downloads_count": 0,
                "viewer_has_liked": False,
                "viewer_rating": None,
            }
            for plugin_id in plugin_ids
        }
        likes_rows = await self.session.execute(
            select(PluginSubscriptionORM.plugin_id, func.count(PluginSubscriptionORM.id))
            .where(PluginSubscriptionORM.plugin_id.in_(plugin_ids))
            .group_by(PluginSubscriptionORM.plugin_id)
        )
        for plugin_id, count in likes_rows.all():
            stats[plugin_id]["likes_count"] = int(count or 0)
        rating_rows = await self.session.execute(
            select(
                PluginRatingORM.plugin_id,
                func.avg(PluginRatingORM.score),
                func.count(PluginRatingORM.id),
            )
            .where(PluginRatingORM.plugin_id.in_(plugin_ids))
            .group_by(PluginRatingORM.plugin_id)
        )
        for plugin_id, avg, count in rating_rows.all():
            stats[plugin_id]["rating_avg"] = round(float(avg or 0.0), 2)
            stats[plugin_id]["rating_count"] = int(count or 0)
        comment_rows = await self.session.execute(
            select(PluginCommentORM.plugin_id, func.count(PluginCommentORM.id))
            .where(PluginCommentORM.plugin_id.in_(plugin_ids), PluginCommentORM.is_deleted.is_(False))
            .group_by(PluginCommentORM.plugin_id)
        )
        for plugin_id, count in comment_rows.all():
            stats[plugin_id]["comments_count"] = int(count or 0)
        download_rows = await self.session.execute(
            select(PluginVersionORM.plugin_id, func.coalesce(func.sum(PluginVersionORM.download_count), 0))
            .where(PluginVersionORM.plugin_id.in_(plugin_ids))
            .group_by(PluginVersionORM.plugin_id)
        )
        for plugin_id, total in download_rows.all():
            stats[plugin_id]["downloads_count"] = int(total or 0)
        if viewer_id:
            viewer_likes = await self.session.execute(
                select(PluginSubscriptionORM.plugin_id)
                .where(PluginSubscriptionORM.plugin_id.in_(plugin_ids), PluginSubscriptionORM.author_id == viewer_id)
            )
            for (plugin_id,) in viewer_likes.all():
                stats[plugin_id]["viewer_has_liked"] = True
            viewer_ratings = await self.session.execute(
                select(PluginRatingORM.plugin_id, PluginRatingORM.score)
                .where(PluginRatingORM.plugin_id.in_(plugin_ids), PluginRatingORM.author_id == viewer_id)
            )
            for plugin_id, score in viewer_ratings.all():
                stats[plugin_id]["viewer_rating"] = int(score)
        return stats

    def _sort_plugins(
        self, rows: list[PluginORM], stats: dict[str, dict[str, Any]], sort: str
    ) -> list[PluginORM]:
        """Sort plugins by a named strategy using pre-computed community stats."""

        def score(plugin: PluginORM) -> tuple:
            data = stats.get(plugin.plugin_id, {})
            likes = data.get("likes_count", 0)
            rating_avg = data.get("rating_avg", 0.0)
            rating_count = data.get("rating_count", 0)
            comments = data.get("comments_count", 0)
            downloads = data.get("downloads_count", 0)
            updated = plugin.updated_at.timestamp() if plugin.updated_at else 0
            if sort == "popular":
                composite = likes * 3 + downloads + comments * 2 + rating_count * 2
                return (composite, updated)
            if sort == "rating":
                weighted = rating_avg * min(rating_count, 50)
                return (weighted, rating_count, updated)
            if sort == "downloads":
                return (downloads, updated)
            if sort == "likes":
                return (likes, updated)
            if sort == "trending":
                composite = likes * 2 + comments * 3 + downloads * 0.5
                return (composite, updated)
            if sort == "name":
                return (-ord(plugin.display_name[:1].lower()[0]) if plugin.display_name else 0,)
            return (updated,)

        reverse = sort != "name"
        return sorted(rows, key=score, reverse=reverse)

    async def toggle_subscription(self, plugin_id: str, viewer_id: str) -> PluginSubscriptionState:
        """Toggle a subscription for the given user and return current state."""

        plugin = await self._get_plugin_orm(plugin_id)
        viewer_id = await self._canonical_author_id(viewer_id)
        existing = await self.session.scalar(
            select(PluginSubscriptionORM).where(
                PluginSubscriptionORM.plugin_id == plugin_id,
                PluginSubscriptionORM.author_id == viewer_id,
            )
        )
        if existing is None:
            self.session.add(PluginSubscriptionORM(plugin_id=plugin_id, author_id=viewer_id))
            subscribed = True
        else:
            await self.session.delete(existing)
            subscribed = False
        await self.session.flush()
        total = await self.session.scalar(
            select(func.count()).select_from(PluginSubscriptionORM).where(PluginSubscriptionORM.plugin_id == plugin_id)
        )
        return PluginSubscriptionState(
            plugin_id=plugin.plugin_id,
            subscribed=subscribed,
            subscriptions_count=int(total or 0),
        )

    async def author_follow_state(
        self,
        author_id: str,
        viewer_id: str | None,
    ) -> AuthorFollowState:
        """Return the current follow state for one author."""

        author = await self.session.get(AuthorORM, author_id)
        if author is None:
            raise ApiError(404, "AUTHOR_NOT_FOUND", "Author was not found.", {"author_id": author_id})
        followers_count = await self.session.scalar(
            select(func.count()).select_from(AuthorFollowORM).where(AuthorFollowORM.author_id == author_id)
        )
        following = False
        if viewer_id:
            following = (
                await self.session.scalar(
                    select(AuthorFollowORM.id).where(
                        AuthorFollowORM.follower_id == viewer_id,
                        AuthorFollowORM.author_id == author_id,
                    )
                )
            ) is not None
        return AuthorFollowState(
            author_id=author_id,
            following=following,
            followers_count=int(followers_count or 0),
        )

    async def toggle_author_follow(
        self,
        author_id: str,
        viewer_id: str,
    ) -> AuthorFollowState:
        """Toggle a follow relationship between viewer and author."""

        viewer_id = await self._canonical_author_id(viewer_id)
        if author_id == viewer_id:
            raise ApiError(400, "CANNOT_FOLLOW_SELF", "You cannot follow yourself.")
        author = await self.session.get(AuthorORM, author_id)
        if author is None:
            raise ApiError(404, "AUTHOR_NOT_FOUND", "Author was not found.", {"author_id": author_id})
        existing = await self.session.scalar(
            select(AuthorFollowORM).where(
                AuthorFollowORM.follower_id == viewer_id,
                AuthorFollowORM.author_id == author_id,
            )
        )
        if existing is None:
            self.session.add(AuthorFollowORM(follower_id=viewer_id, author_id=author_id))
        else:
            await self.session.delete(existing)
        await self.session.flush()
        return await self.author_follow_state(author_id, viewer_id)

    async def access_token_status(self, author_id: str) -> AccessTokenStatus:
        """Return metadata for the author's current market token."""

        record = await self.session.get(AuthorAccessTokenORM, author_id)
        if record is None:
            return AccessTokenStatus(author_id=author_id, has_token=False)
        return AccessTokenStatus(
            author_id=author_id,
            has_token=True,
            token_preview=record.token_preview,
            created_at=record.created_at,
            updated_at=record.updated_at,
            last_used_at=record.last_used_at,
        )

    async def rotate_access_token(self, author_id: str) -> AccessTokenRotateResponse:
        """Create or replace the author's single active market token."""

        author_id = await self._canonical_author_id(author_id)
        plain_token = f"mfox_{secrets.token_urlsafe(32)}"
        token_hash = _hash_access_token(plain_token)
        token_preview = f"{plain_token[:8]}...{plain_token[-4:]}"
        now = utc_now()
        record = await self.session.get(AuthorAccessTokenORM, author_id)
        if record is None:
            record = AuthorAccessTokenORM(
                author_id=author_id,
                token_hash=token_hash,
                token_preview=token_preview,
                created_at=now,
                updated_at=now,
                last_used_at=None,
            )
            self.session.add(record)
        else:
            record.token_hash = token_hash
            record.token_preview = token_preview
            record.created_at = now
            record.updated_at = now
            record.last_used_at = None
        await self.session.flush()
        return AccessTokenRotateResponse(
            author_id=author_id,
            token=plain_token,
            token_preview=token_preview,
            created_at=record.created_at,
            updated_at=record.updated_at,
        )

    async def revoke_access_token(self, author_id: str) -> AccessTokenStatus:
        """Delete the author's current market token."""

        record = await self.session.get(AuthorAccessTokenORM, author_id)
        if record is not None:
            await self.session.delete(record)
            await self.session.flush()
        return AccessTokenStatus(author_id=author_id, has_token=False)

    async def machine_subscriptions(
        self,
        author_id: str,
    ) -> MachineSubscriptionListResponse:
        """Return published plugin subscriptions for one machine author."""

        stmt = (
            select(PluginORM)
            .options(
                selectinload(PluginORM.versions),
                selectinload(PluginORM.owner),
                selectinload(PluginORM.maintainers),
            )
            .join(
                PluginSubscriptionORM,
                PluginSubscriptionORM.plugin_id == PluginORM.plugin_id,
            )
            .where(
                PluginSubscriptionORM.author_id == author_id,
                PluginORM.status == PluginStatus.PUBLISHED,
            )
            .order_by(PluginORM.updated_at.desc())
        )
        plugins = list((await self.session.scalars(stmt)).all())
        items: list[MachineSubscriptionItem] = []
        for plugin in plugins:
            latest = self._latest_public_version(plugin)
            items.append(
                MachineSubscriptionItem(
                    plugin_id=plugin.plugin_id,
                    display_name=plugin.display_name,
                    latest_version=latest.version if latest is not None else None,
                    updated_at=plugin.updated_at,
                )
            )
        return MachineSubscriptionListResponse(
            author_id=author_id,
            items=items,
            total=len(items),
        )

    async def my_subscriptions(
        self,
        author_id: str,
    ) -> MySubscriptionListResponse:
        """Return plugins the viewer has subscribed to."""

        subq = (
            select(PluginSubscriptionORM)
            .where(PluginSubscriptionORM.author_id == author_id)
            .subquery()
        )
        stmt = (
            select(PluginORM, subq.c.created_at.label("subscribed_at"))
            .options(selectinload(PluginORM.owner), selectinload(PluginORM.versions))
            .join(subq, PluginORM.plugin_id == subq.c.plugin_id)
            .order_by(subq.c.created_at.desc())
        )
        rows = list((await self.session.execute(stmt)).all())
        items: list[MySubscriptionItem] = []
        for plugin, subscribed_at in rows:
            latest = self._latest_public_version(plugin)
            items.append(
                MySubscriptionItem(
                    plugin_id=plugin.plugin_id,
                    display_name=plugin.display_name,
                    summary=plugin.summary or "",
                    icon_url=plugin.icon_url,
                    status=plugin.status,
                    owner_id=plugin.owner_id,
                    owner_login=plugin.owner.github_login if plugin.owner else None,
                    owner_display_name=plugin.owner.display_name if plugin.owner else None,
                    latest_version=latest.version if latest else None,
                    updated_at=plugin.updated_at,
                    subscribed_at=subscribed_at,
                )
            )
        return MySubscriptionListResponse(
            author_id=author_id,
            items=items,
            total=len(items),
        )

    async def my_follows(
        self,
        author_id: str,
    ) -> MyFollowListResponse:
        """Return authors the viewer follows."""

        subq = (
            select(AuthorFollowORM)
            .where(AuthorFollowORM.follower_id == author_id)
            .subquery()
        )
        stmt = (
            select(AuthorORM, subq.c.created_at.label("followed_at"))
            .join(subq, AuthorORM.author_id == subq.c.author_id)
            .order_by(subq.c.created_at.desc())
        )
        rows = list((await self.session.execute(stmt)).all())
        items: list[MyFollowItem] = []
        for author, followed_at in rows:
            items.append(
                MyFollowItem(
                    author_id=author.author_id,
                    github_login=author.github_login,
                    display_name=author.display_name,
                    avatar_url=author.avatar_url,
                    author_type=author.author_type,
                    followed_at=followed_at,
                )
            )
        return MyFollowListResponse(
            author_id=author_id,
            items=items,
            total=len(items),
        )

    async def rate_plugin(self, plugin_id: str, viewer_id: str, score: int) -> RatingSummary:
        """Upsert the viewer's rating and return aggregate stats."""

        plugin = await self._get_plugin_orm(plugin_id)
        viewer_id = await self._canonical_author_id(viewer_id)
        existing = await self.session.scalar(
            select(PluginRatingORM).where(
                PluginRatingORM.plugin_id == plugin_id,
                PluginRatingORM.author_id == viewer_id,
            )
        )
        if existing is None:
            self.session.add(PluginRatingORM(plugin_id=plugin_id, author_id=viewer_id, score=score))
        else:
            existing.score = score
            existing.updated_at = utc_now()
        await self.session.flush()
        return await self.rating_summary(plugin.plugin_id, viewer_id)

    async def clear_rating(self, plugin_id: str, viewer_id: str) -> RatingSummary:
        """Remove the viewer's rating and return aggregate stats."""

        plugin = await self._get_plugin_orm(plugin_id)
        existing = await self.session.scalar(
            select(PluginRatingORM).where(
                PluginRatingORM.plugin_id == plugin_id,
                PluginRatingORM.author_id == viewer_id,
            )
        )
        if existing is not None:
            await self.session.delete(existing)
            await self.session.flush()
        return await self.rating_summary(plugin.plugin_id, viewer_id)

    async def rating_summary(self, plugin_id: str, viewer_id: str | None) -> RatingSummary:
        """Return rating aggregate and viewer's own score."""

        await self._get_plugin_orm(plugin_id)
        avg = await self.session.scalar(
            select(func.avg(PluginRatingORM.score)).where(PluginRatingORM.plugin_id == plugin_id)
        )
        count = await self.session.scalar(
            select(func.count()).select_from(PluginRatingORM).where(PluginRatingORM.plugin_id == plugin_id)
        )
        distribution = {"1": 0, "2": 0, "3": 0, "4": 0, "5": 0}
        dist_rows = await self.session.execute(
            select(PluginRatingORM.score, func.count(PluginRatingORM.id))
            .where(PluginRatingORM.plugin_id == plugin_id)
            .group_by(PluginRatingORM.score)
        )
        for score, total in dist_rows.all():
            distribution[str(int(score))] = int(total or 0)
        viewer_rating: int | None = None
        if viewer_id:
            record = await self.session.scalar(
                select(PluginRatingORM.score).where(
                    PluginRatingORM.plugin_id == plugin_id,
                    PluginRatingORM.author_id == viewer_id,
                )
            )
            viewer_rating = int(record) if record is not None else None
        return RatingSummary(
            plugin_id=plugin_id,
            rating_avg=round(float(avg or 0.0), 2),
            rating_count=int(count or 0),
            distribution=distribution,
            viewer_rating=viewer_rating,
        )

    async def list_comments(
        self, plugin_id: str, *, offset: int = 0, limit: int = 50
    ) -> tuple[list[Comment], int]:
        """List comments for a plugin, newest first."""

        await self._get_plugin_orm(plugin_id)
        total = await self.session.scalar(
            select(func.count()).select_from(PluginCommentORM).where(
                PluginCommentORM.plugin_id == plugin_id, PluginCommentORM.is_deleted.is_(False)
            )
        )
        stmt = (
            select(PluginCommentORM)
            .where(PluginCommentORM.plugin_id == plugin_id, PluginCommentORM.is_deleted.is_(False))
            .order_by(PluginCommentORM.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        rows = list((await self.session.scalars(stmt)).all())
        authors = await self._load_authors([row.author_id for row in rows])
        mentions = await self._load_comment_mentions([row.id for row in rows])
        return [self._comment_schema(row, authors, mentions) for row in rows], int(total or 0)

    async def add_comment(self, plugin_id: str, viewer_id: str, content: str, parent_id: int | None) -> Comment:
        """Create a new comment on a plugin."""

        plugin = await self._get_plugin_orm(plugin_id)
        viewer_id = await self._canonical_author_id(viewer_id)
        normalized_content = content.strip()
        if parent_id is not None:
            parent = await self.session.get(PluginCommentORM, parent_id)
            if parent is None or parent.plugin_id != plugin.plugin_id or parent.is_deleted:
                raise ApiError(404, "COMMENT_NOT_FOUND", "Parent comment was not found.", {"parent_id": parent_id})
            if parent.parent_id is not None:
                raise ApiError(400, "COMMENT_REPLY_DEPTH_EXCEEDED", "Replies may only target top-level comments.", {"parent_id": parent_id})
        comment = PluginCommentORM(
            plugin_id=plugin.plugin_id,
            author_id=viewer_id,
            parent_id=parent_id,
            content=normalized_content,
        )
        self.session.add(comment)
        await self.session.flush()
        from plugin_market_backend.services.inbox_service import InboxService

        inbox_service = InboxService(self.session)
        mentions = await inbox_service.parse_mentions(normalized_content, viewer_id)
        await inbox_service.fan_out_for_comment(comment, mentions)
        authors = await self._load_authors([viewer_id])
        comment_mentions = await self._load_comment_mentions([comment.id])
        return self._comment_schema(comment, authors, comment_mentions)

    async def delete_comment(self, plugin_id: str, comment_id: int, viewer_id: str, is_admin: bool) -> None:
        """Soft-delete a comment owned by the author or by an admin."""

        comment = await self.session.get(PluginCommentORM, comment_id)
        if comment is None or comment.plugin_id != plugin_id or comment.is_deleted:
            raise ApiError(404, "COMMENT_NOT_FOUND", "Comment was not found.", {"comment_id": comment_id})
        if comment.author_id != viewer_id and not is_admin:
            raise ApiError(403, "FORBIDDEN", "You cannot delete this comment.", {"comment_id": comment_id})
        comment.is_deleted = True
        comment.content = ""
        comment.updated_at = utc_now()
        await self.session.flush()
        from plugin_market_backend.services.inbox_service import InboxService

        await InboxService(self.session).revoke_messages_for_comment(comment_id)

    async def record_install(self, plugin_id: str, version: str | None = None) -> PluginVersion:
        """Increment the download counter and return the affected version."""

        plugin = await self._get_plugin_orm(plugin_id)
        if version is not None:
            version_row = await self._get_version_orm(plugin_id, version)
        else:
            recommended = await self.get_recommended_version(plugin.plugin_id)
            version_row = await self._get_version_orm(plugin_id, recommended.version)
        version_row.download_count = int(version_row.download_count or 0) + 1
        version_row.updated_at = utc_now()
        await self.session.flush()
        return self._version_schema(version_row)

    async def trending_authors(self, *, limit: int = 8) -> list[TrendingItem]:
        """Return authors ranked by engagement on their plugins."""

        stmt = (
            select(PluginORM)
            .options(selectinload(PluginORM.owner), selectinload(PluginORM.versions))
        )
        rows = list((await self.session.scalars(stmt)).all())
        stats = await self._community_stats_for([plugin.plugin_id for plugin in rows], None)
        buckets: dict[str, dict[str, Any]] = {}
        # Track each author's plugin metrics so we can pick a "best" one as a
        # fallback signature plugin for the home page.
        plugins_by_author: dict[str, list[tuple[float, PluginORM]]] = {}
        for plugin in rows:
            owner = plugin.owner
            if owner is None:
                continue
            data = stats.get(plugin.plugin_id, {})
            bucket = buckets.setdefault(
                owner.author_id,
                {
                    "author_id": owner.author_id,
                    "github_login": owner.github_login,
                    "display_name": owner.display_name,
                    "avatar_url": owner.avatar_url,
                    "plugins_count": 0,
                    "likes_received": 0,
                    "downloads_total": 0,
                    "rating_score_total": 0.0,
                    "rating_count": 0,
                },
            )
            bucket["plugins_count"] += 1
            likes = int(data.get("likes_count", 0) or 0)
            downloads = int(data.get("downloads_count", 0) or 0)
            rating_avg = float(data.get("rating_avg", 0) or 0)
            rating_count = int(data.get("rating_count", 0) or 0)
            bucket["likes_received"] += likes
            bucket["downloads_total"] += downloads
            bucket["rating_score_total"] += rating_avg * rating_count
            bucket["rating_count"] += rating_count
            # Score is biased toward published plugins so we don't surface
            # drafts as someone's signature work.
            published_bonus = 0.0
            if plugin.status == PluginStatus.PUBLISHED:
                published_bonus = 1.0
            score = (
                published_bonus * 1000
                + likes * 3
                + downloads
                + rating_avg * 50
            )
            plugins_by_author.setdefault(owner.author_id, []).append((score, plugin))

        items: list[TrendingItem] = []
        # Batch-load profiles for bio enrichment.
        author_ids = list(buckets.keys())
        bios: dict[str, str] = {}
        if author_ids:
            profiles = (await self.session.scalars(
                select(AuthorProfileORM).where(AuthorProfileORM.author_id.in_(author_ids))
            )).all()
            for profile in profiles:
                if profile.bio and profile.bio.strip():
                    bios[profile.author_id] = profile.bio.strip()
        for bucket in buckets.values():
            best_plugin: TrendingPlugin | None = None
            rating_count = int(bucket.get("rating_count", 0) or 0)
            rating_score_total = float(bucket.pop("rating_score_total", 0.0) or 0.0)
            bucket["rating_avg"] = (rating_score_total / rating_count) if rating_count else 0.0
            ranked = plugins_by_author.get(bucket["author_id"], [])
            if ranked:
                ranked.sort(key=lambda pair: pair[0], reverse=True)
                top = ranked[0][1]
                latest_version: str | None = None
                if top.versions:
                    latest_published = max(
                        (v for v in top.versions if v.status == VersionStatus.PUBLISHED and not v.is_yanked),
                        key=lambda v: v.published_at,
                        default=None,
                    )
                    if latest_published is not None:
                        latest_version = latest_published.version
                best_plugin = TrendingPlugin(
                    plugin_id=top.plugin_id,
                    display_name=top.display_name,
                    summary=top.summary,
                    icon_url=top.icon_url,
                    latest_version=latest_version,
                )
            items.append(TrendingItem(**bucket, best_plugin=best_plugin, bio=bios.get(bucket["author_id"])))
        items.sort(key=lambda item: (item.likes_received, item.downloads_total, item.plugins_count), reverse=True)
        return items[:limit]

    async def _load_authors(self, author_ids: list[str]) -> dict[str, AuthorORM]:
        """Fetch authors keyed by id for comment serialization."""

        unique_ids = [value for value in dict.fromkeys(author_ids)]
        if not unique_ids:
            return {}
        rows = await self.session.scalars(select(AuthorORM).where(AuthorORM.author_id.in_(unique_ids)))
        return {author.author_id: author for author in rows}

    async def _load_comment_mentions(self, comment_ids: list[int]) -> dict[int, list[MentionCandidate]]:
        """Fetch resolved mentions for each comment keyed by comment id."""

        unique_ids = [value for value in dict.fromkeys(comment_ids)]
        if not unique_ids:
            return {}
        stmt = (
            select(CommentMentionORM.comment_id, AuthorORM)
            .join(AuthorORM, AuthorORM.author_id == CommentMentionORM.mentioned_author_id)
            .where(CommentMentionORM.comment_id.in_(unique_ids))
            .order_by(CommentMentionORM.comment_id.asc(), CommentMentionORM.created_at.asc())
        )
        rows = (await self.session.execute(stmt)).all()
        bucket: dict[int, list[MentionCandidate]] = {}
        for comment_id, author in rows:
            bucket.setdefault(int(comment_id), []).append(self._mention_candidate_schema(author))
        return bucket

    def _comment_schema(
        self,
        comment: PluginCommentORM,
        authors: dict[str, AuthorORM],
        mentions: dict[int, list[MentionCandidate]],
    ) -> Comment:
        """Convert a comment ORM object to schema."""

        author = authors.get(comment.author_id)
        return Comment(
            id=comment.id,
            plugin_id=comment.plugin_id,
            parent_id=comment.parent_id,
            content=comment.content,
            created_at=comment.created_at,
            updated_at=comment.updated_at,
            is_deleted=comment.is_deleted,
            author=CommentAuthor(
                author_id=author.author_id if author else comment.author_id,
                github_login=author.github_login if author else comment.author_id,
                display_name=author.display_name if author else comment.author_id,
                avatar_url=author.avatar_url if author else None,
                is_admin=bool(author.is_admin) if author else False,
            ),
            mentions=mentions.get(comment.id, []),
        )

    def _mention_candidate_schema(self, author: AuthorORM) -> MentionCandidate:
        """Convert an author ORM object into a mention candidate payload."""

        return MentionCandidate(
            author_id=author.author_id,
            github_login=author.github_login,
            display_name=author.display_name,
            avatar_url=author.avatar_url,
        )
