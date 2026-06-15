"""Skill market domain service.

This module implements the skill market backend operations:

* :class:`SkillService.create_skill` validates a zip package, extracts metadata
  from SKILL.md, persists the package, and records the skill + version in the
  database.
* :class:`SkillService.publish_version` adds a new installable zip version.
* :class:`SkillService.update_skill_meta` patches mutable metadata fields.
* :class:`SkillService.get_skill` / :meth:`list_skills` provide public query
  endpoints with community-stats aggregation.
* Community interactions: like/unlike, rate, comment (CRUD), subscribe/unsubscribe.
* Admin operations: block, set trust level, delete.

All write methods append :class:`ReviewRecordORM` audit records.
"""

from __future__ import annotations

import hashlib
import os

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from plugin_market_backend.content import (
    extract_and_validate_skill,
    store_skill_package,
)
from plugin_market_backend.enums import ReviewAction, SkillStatus, TrustLevel
from plugin_market_backend.errors import ApiError
from plugin_market_backend.orm import (
    AuthorORM,
    ReviewRecordORM,
    SkillCommentORM,
    SkillLikeORM,
    SkillORM,
    SkillRatingORM,
    SkillSubscriptionORM,
    SkillVersionORM,
    utc_now,
)
from plugin_market_backend.schemas import (
    CommentAuthor,
    Skill,
    SkillComment,
    SkillCommentListResponse,
    SkillInstallRecord,
    SkillListResponse,
    SkillRatingInfo,
    SkillUpdate,
    SkillVersion,
    SkillVersionListResponse,
)


class SkillService:
    """Manage skill market records, versions, and community interactions.

    The service keeps skill-market writes in a single bounded module so
    audit trails and validation rules are enforced in exactly one place.
    """

    def __init__(self, session: AsyncSession) -> None:
        """Create a service bound to one transactional session."""

        self.session = session

    # ------------------------------------------------------------------
    # Create / publish
    # ------------------------------------------------------------------

    async def create_skill(
        self,
        owner_id: str,
        skill_id: str,
        zip_bytes: bytes,
        version: str,
        *,
        release_notes: str | None = None,
        min_mofox_version: str | None = None,
        categories: list[str] | None = None,
        tags: list[str] | None = None,
    ) -> Skill:
        """Validate a skill zip, extract metadata, persist everything.

        Returns the newly-created skill DTO.
        """

        # Validate and extract metadata from the zip
        name, description, _readme = extract_and_validate_skill(zip_bytes)

        # Check that the skill_id does not already exist
        existing = await self.session.get(SkillORM, skill_id)
        if existing is not None:
            raise ApiError(
                409,
                "SKILL_ALREADY_EXISTS",
                f"A skill with id '{skill_id}' already exists.",
                {"skill_id": skill_id},
            )

        # Store the zip package
        package_path = store_skill_package(skill_id, version, zip_bytes)
        package_size = len(zip_bytes)
        checksum = hashlib.sha256(zip_bytes).hexdigest()

        # Create skill ORM
        now = utc_now()
        skill = SkillORM(
            skill_id=skill_id,
            display_name=name,
            description=description or "",
            readme_markdown=_readme or None,
            owner_id=owner_id,
            categories=categories or [],
            tags=tags or [],
            status=SkillStatus.PUBLISHED,
            trust_level=TrustLevel.COMMUNITY,
            download_count=0,
            created_at=now,
            updated_at=now,
        )
        self.session.add(skill)

        # Create version ORM
        ver = SkillVersionORM(
            skill_id=skill_id,
            version=version,
            package_path=package_path,
            package_size=package_size,
            checksum_sha256=checksum,
            release_notes=release_notes,
            min_mofox_version=min_mofox_version,
            download_count=0,
            created_at=now,
        )
        self.session.add(ver)

        # Audit record
        await _append_audit(
            self.session,
            action=ReviewAction.PUBLISH_SKILL,
            target_type="skill",
            target_id=skill_id,
            operator_id=owner_id,
            status_after=SkillStatus.PUBLISHED.value,
        )

        await self.session.flush()
        owner = await self.session.get(AuthorORM, owner_id)
        return _skill_to_schema(skill, owner=owner, latest_version=version)

    async def publish_version(
        self,
        skill_id: str,
        version: str,
        zip_bytes: bytes,
        operator_id: str,
        *,
        release_notes: str | None = None,
        min_mofox_version: str | None = None,
    ) -> SkillVersion:
        """Publish a new version for an existing skill.

        The zip is validated the same way as :meth:`create_skill`.
        """

        skill = await self.session.get(SkillORM, skill_id)
        if skill is None:
            raise ApiError(404, "SKILL_NOT_FOUND", "Skill not found.", {"skill_id": skill_id})

        # Validate the zip package (we don't use the extracted name/desc here)
        extract_and_validate_skill(zip_bytes)

        # Check version uniqueness
        existing_ver = await self.session.scalar(
            select(SkillVersionORM).where(
                SkillVersionORM.skill_id == skill_id,
                SkillVersionORM.version == version,
            )
        )
        if existing_ver is not None:
            raise ApiError(
                409,
                "SKILL_VERSION_EXISTS",
                f"Version '{version}' already exists for skill '{skill_id}'.",
                {"skill_id": skill_id, "version": version},
            )

        # Store the zip package
        package_path = store_skill_package(skill_id, version, zip_bytes)
        package_size = len(zip_bytes)
        checksum = hashlib.sha256(zip_bytes).hexdigest()

        ver = SkillVersionORM(
            skill_id=skill_id,
            version=version,
            package_path=package_path,
            package_size=package_size,
            checksum_sha256=checksum,
            release_notes=release_notes,
            min_mofox_version=min_mofox_version,
            download_count=0,
            created_at=utc_now(),
        )
        self.session.add(ver)

        # Update skill timestamp
        skill.updated_at = utc_now()

        await _append_audit(
            self.session,
            action=ReviewAction.PUBLISH_SKILL_VERSION,
            target_type="skill_version",
            target_id=f"{skill_id}:{version}",
            operator_id=operator_id,
        )

        await self.session.flush()
        return _version_to_schema(ver)

    # ------------------------------------------------------------------
    # Metadata update
    # ------------------------------------------------------------------

    async def update_skill_meta(
        self,
        skill_id: str,
        operator_id: str,
        update: SkillUpdate,
    ) -> Skill:
        """Patch mutable skill metadata fields.

        Only supplied (non-None) fields are changed.
        """

        skill = await self.session.get(SkillORM, skill_id)
        if skill is None:
            raise ApiError(404, "SKILL_NOT_FOUND", "Skill not found.", {"skill_id": skill_id})

        changed = False
        if update.display_name is not None:
            skill.display_name = update.display_name
            changed = True
        if update.icon_url is not None:
            skill.icon_url = update.icon_url
            changed = True
        if update.categories is not None:
            skill.categories = update.categories
            changed = True
        if update.tags is not None:
            skill.tags = update.tags
            changed = True

        if changed:
            skill.updated_at = utc_now()
            await _append_audit(
                self.session,
                action=ReviewAction.UPDATE_SKILL,
                target_type="skill",
                target_id=skill_id,
                operator_id=operator_id,
            )
            await self.session.flush()

        owner = await self.session.get(AuthorORM, skill.owner_id)
        versions = await self._load_versions_for_skill(skill_id)
        latest = versions[0] if versions else None
        return _skill_to_schema(skill, owner=owner, latest_version=latest.version if latest else None)

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------

    async def get_skill(self, skill_id: str, viewer_id: str | None = None) -> Skill:
        """Return a single skill with community-stats aggregation."""

        skill = await self.session.get(SkillORM, skill_id)
        if skill is None:
            raise ApiError(404, "SKILL_NOT_FOUND", "Skill not found.", {"skill_id": skill_id})

        owner = await self.session.get(AuthorORM, skill.owner_id)
        versions = await self._load_versions_for_skill(skill_id)
        latest = versions[0] if versions else None
        stats = await _aggregate_skill_stats(self.session, skill_id, viewer_id)
        return _skill_to_schema(
            skill, owner=owner, latest_version=latest.version if latest else None, stats=stats,
        )

    async def list_skills(
        self,
        *,
        search: str | None = None,
        category: str | None = None,
        tag: str | None = None,
        sort: str = "updated",
        page: int = 1,
        page_size: int = 50,
        viewer_id: str | None = None,
    ) -> SkillListResponse:
        """Return a paginated, filtered list of published skills."""

        page_size = max(1, min(page_size, 100))
        page = max(1, page)
        offset = (page - 1) * page_size

        base_where = [SkillORM.status == SkillStatus.PUBLISHED]
        like = None
        if search:
            like = f"%{search}%"
            base_where.append(
                (SkillORM.display_name.ilike(like)) | (SkillORM.description.ilike(like))
            )

        stmt = select(SkillORM).where(*base_where)
        count_stmt = select(func.count()).select_from(SkillORM).where(*base_where)

        if category:
            stmt = stmt.where(SkillORM.categories.contains([category]))
            count_stmt = count_stmt.where(SkillORM.categories.contains([category]))
        if tag:
            stmt = stmt.where(SkillORM.tags.contains([tag]))
            count_stmt = count_stmt.where(SkillORM.tags.contains([tag]))

        total = (await self.session.scalar(count_stmt)) or 0

        # Sort
        sort_cols: dict[str, object] = {
            "updated": SkillORM.updated_at.desc(),
            "created": SkillORM.created_at.desc(),
            "downloads": SkillORM.download_count.desc(),
            "name": SkillORM.display_name.asc(),
        }
        order = sort_cols.get(sort, SkillORM.updated_at.desc())
        stmt = stmt.order_by(order).offset(offset).limit(page_size)

        rows = list((await self.session.scalars(stmt)).all())

        # Gather owners, versions and stats
        owner_ids = [row.owner_id for row in rows]
        owner_map = await self._load_authors(owner_ids)

        items: list[Skill] = []
        for row in rows:
            ver_rows = await self._load_versions_for_skill(row.skill_id)
            latest = ver_rows[0] if ver_rows else None
            stats = await _aggregate_skill_stats(self.session, row.skill_id, viewer_id)
            items.append(
                _skill_to_schema(
                    row,
                    owner=owner_map.get(row.owner_id),
                    latest_version=latest.version if latest else None,
                    stats=stats,
                )
            )

        return SkillListResponse(items=items, total=total)

    async def get_skill_versions(self, skill_id: str) -> SkillVersionListResponse:
        """Return all versions for a skill."""

        skill = await self.session.get(SkillORM, skill_id)
        if skill is None:
            raise ApiError(404, "SKILL_NOT_FOUND", "Skill not found.", {"skill_id": skill_id})

        versions = await self._load_versions_for_skill(skill_id)
        return SkillVersionListResponse(
            items=[_version_to_schema(v) for v in versions],
            total=len(versions),
        )

    async def get_version_download(
        self, skill_id: str, version: str
    ) -> tuple[str, int, str]:
        """Return (file_path, file_size, checksum) for a skill version package."""

        ver = await self.session.scalar(
            select(SkillVersionORM).where(
                SkillVersionORM.skill_id == skill_id,
                SkillVersionORM.version == version,
            )
        )
        if ver is None:
            raise ApiError(
                404,
                "SKILL_VERSION_NOT_FOUND",
                "Skill version not found.",
                {"skill_id": skill_id, "version": version},
            )

        file_path = ver.package_path
        if not os.path.isfile(file_path):
            raise ApiError(
                404,
                "SKILL_PACKAGE_MISSING",
                "The package file is missing from storage.",
                {"skill_id": skill_id, "version": version},
            )

        return file_path, ver.package_size, ver.checksum_sha256

    async def record_download(self, skill_id: str, version: str | None = None) -> SkillInstallRecord:
        """Increment the download counter for a skill version.

        If *version* is ``None``, the latest version is used.
        """

        if version is None:
            versions = await self._load_versions_for_skill(skill_id)
            if not versions:
                raise ApiError(
                    404,
                    "SKILL_NO_VERSIONS",
                    "Skill has no versions yet.",
                    {"skill_id": skill_id},
                )
            version = versions[0].version

        ver = await self.session.scalar(
            select(SkillVersionORM).where(
                SkillVersionORM.skill_id == skill_id,
                SkillVersionORM.version == version,
            )
        )
        if ver is None:
            raise ApiError(
                404,
                "SKILL_VERSION_NOT_FOUND",
                "Skill version not found.",
                {"skill_id": skill_id, "version": version},
            )

        ver.download_count = (ver.download_count or 0) + 1

        # Also aggregate to parent skill
        skill = await self.session.get(SkillORM, skill_id)
        if skill is not None:
            skill.download_count = (skill.download_count or 0) + 1

        await self.session.flush()
        return SkillInstallRecord(
            skill_id=skill_id,
            version=version,
            download_count=ver.download_count,
        )

    # ------------------------------------------------------------------
    # Delete / block
    # ------------------------------------------------------------------

    async def delete_skill(self, skill_id: str, operator_id: str) -> None:
        """Delete a skill and all associated records."""

        skill = await self.session.get(SkillORM, skill_id)
        if skill is None:
            raise ApiError(404, "SKILL_NOT_FOUND", "Skill not found.", {"skill_id": skill_id})

        await _append_audit(
            self.session,
            action=ReviewAction.DELETE_SKILL,
            target_type="skill",
            target_id=skill_id,
            operator_id=operator_id,
            status_before=skill.status.value,
        )

        # Delete associated records using ORM delete for cascade-like behavior
        await self.session.execute(
            select(SkillCommentORM).where(SkillCommentORM.skill_id == skill_id)
        )
        await self.session.execute(
            select(SkillRatingORM).where(SkillRatingORM.skill_id == skill_id)
        )
        await self.session.execute(
            select(SkillLikeORM).where(SkillLikeORM.skill_id == skill_id)
        )
        await self.session.execute(
            select(SkillSubscriptionORM).where(SkillSubscriptionORM.skill_id == skill_id)
        )
        await self.session.execute(
            select(SkillVersionORM).where(SkillVersionORM.skill_id == skill_id)
        )

        await self.session.delete(skill)
        await self.session.flush()

    async def block_skill(
        self, skill_id: str, operator_id: str, reason: str | None = None
    ) -> Skill:
        """Block a skill (admin operation)."""

        skill = await self.session.get(SkillORM, skill_id)
        if skill is None:
            raise ApiError(404, "SKILL_NOT_FOUND", "Skill not found.", {"skill_id": skill_id})

        skill.status = SkillStatus.BLOCKED
        skill.updated_at = utc_now()

        await _append_audit(
            self.session,
            action=ReviewAction.BLOCK_SKILL,
            target_type="skill",
            target_id=skill_id,
            operator_id=operator_id,
            status_before=SkillStatus.PUBLISHED.value,
            status_after=SkillStatus.BLOCKED.value,
            reason=reason,
        )

        await self.session.flush()
        owner = await self.session.get(AuthorORM, skill.owner_id)
        return _skill_to_schema(skill, owner=owner)

    async def set_skill_trust_level(
        self,
        skill_id: str,
        trust_level: str,
        operator_id: str,
    ) -> Skill:
        """Set the trust level for a skill."""

        skill = await self.session.get(SkillORM, skill_id)
        if skill is None:
            raise ApiError(404, "SKILL_NOT_FOUND", "Skill not found.", {"skill_id": skill_id})

        try:
            new_level = TrustLevel(trust_level)
        except ValueError:
            raise ApiError(
                422,
                "INVALID_TRUST_LEVEL",
                f"Invalid trust level: {trust_level}.",
                {"valid_values": [e.value for e in TrustLevel]},
            )

        old_level = skill.trust_level.value
        skill.trust_level = new_level
        skill.updated_at = utc_now()

        await _append_audit(
            self.session,
            action=ReviewAction.SET_TRUST_LEVEL,
            target_type="skill",
            target_id=skill_id,
            operator_id=operator_id,
            status_before=old_level,
            status_after=new_level.value,
        )

        await self.session.flush()
        owner = await self.session.get(AuthorORM, skill.owner_id)
        return _skill_to_schema(skill, owner=owner)

    # ------------------------------------------------------------------
    # Community: like / unlike
    # ------------------------------------------------------------------

    async def toggle_like(self, skill_id: str, viewer_id: str) -> dict:
        """Toggle the viewer's like on a skill. Returns {liked, likes_count}."""

        skill = await self.session.get(SkillORM, skill_id)
        if skill is None:
            raise ApiError(404, "SKILL_NOT_FOUND", "Skill not found.", {"skill_id": skill_id})

        existing = await self.session.scalar(
            select(SkillLikeORM).where(
                SkillLikeORM.skill_id == skill_id,
                SkillLikeORM.author_id == viewer_id,
            )
        )

        if existing is not None:
            await self.session.delete(existing)
            liked = False
        else:
            self.session.add(
                SkillLikeORM(skill_id=skill_id, author_id=viewer_id, created_at=utc_now())
            )
            liked = True

        await self.session.flush()

        likes_count = await self.session.scalar(
            select(func.count()).select_from(SkillLikeORM).where(
                SkillLikeORM.skill_id == skill_id
            )
        ) or 0

        return {"liked": liked, "likes_count": int(likes_count)}

    # ------------------------------------------------------------------
    # Community: rate
    # ------------------------------------------------------------------

    async def rate_skill(self, skill_id: str, viewer_id: str, score: int) -> SkillRatingInfo:
        """Submit or update the viewer's rating (1-5)."""

        skill = await self.session.get(SkillORM, skill_id)
        if skill is None:
            raise ApiError(404, "SKILL_NOT_FOUND", "Skill not found.", {"skill_id": skill_id})

        if score < 1 or score > 5:
            raise ApiError(422, "INVALID_RATING", "Score must be between 1 and 5.")

        existing = await self.session.scalar(
            select(SkillRatingORM).where(
                SkillRatingORM.skill_id == skill_id,
                SkillRatingORM.author_id == viewer_id,
            )
        )

        if existing is not None:
            existing.score = score
            existing.updated_at = utc_now()
        else:
            self.session.add(
                SkillRatingORM(
                    skill_id=skill_id,
                    author_id=viewer_id,
                    score=score,
                    created_at=utc_now(),
                    updated_at=utc_now(),
                )
            )

        await self.session.flush()
        return await self.rating_summary(skill_id, viewer_id)

    async def clear_rating(self, skill_id: str, viewer_id: str) -> SkillRatingInfo:
        """Remove the viewer's rating."""

        existing = await self.session.scalar(
            select(SkillRatingORM).where(
                SkillRatingORM.skill_id == skill_id,
                SkillRatingORM.author_id == viewer_id,
            )
        )
        if existing is not None:
            await self.session.delete(existing)
            await self.session.flush()

        return await self.rating_summary(skill_id, viewer_id)

    async def rating_summary(
        self, skill_id: str, viewer_id: str | None = None
    ) -> SkillRatingInfo:
        """Return aggregated rating stats for a skill."""

        agg = await self.session.execute(
            select(
                func.coalesce(func.avg(SkillRatingORM.score), 0.0),
                func.count(SkillRatingORM.id),
            ).where(SkillRatingORM.skill_id == skill_id)
        )
        row = agg.first()
        avg_val = float(row[0]) if row else 0.0
        count_val = int(row[1]) if row else 0

        # Distribution
        dist: dict[str, int] = {}
        for s in range(1, 6):
            c = await self.session.scalar(
                select(func.count()).select_from(SkillRatingORM).where(
                    SkillRatingORM.skill_id == skill_id,
                    SkillRatingORM.score == s,
                )
            )
            dist[str(s)] = c or 0

        viewer_score = None
        if viewer_id:
            v = await self.session.scalar(
                select(SkillRatingORM.score).where(
                    SkillRatingORM.skill_id == skill_id,
                    SkillRatingORM.author_id == viewer_id,
                )
            )
            viewer_score = v

        return SkillRatingInfo(
            skill_id=skill_id,
            rating_avg=round(avg_val, 1),
            rating_count=count_val,
            distribution=dist,
            viewer_rating=viewer_score,
        )

    # ------------------------------------------------------------------
    # Community: comment
    # ------------------------------------------------------------------

    async def list_comments(
        self,
        skill_id: str,
        *,
        offset: int = 0,
        limit: int = 50,
    ) -> SkillCommentListResponse:
        """List comments for a skill, oldest first."""

        skill = await self.session.get(SkillORM, skill_id)
        if skill is None:
            raise ApiError(404, "SKILL_NOT_FOUND", "Skill not found.", {"skill_id": skill_id})

        total = await self.session.scalar(
            select(func.count()).select_from(SkillCommentORM).where(
                SkillCommentORM.skill_id == skill_id,
                SkillCommentORM.is_deleted.is_(False),
            )
        ) or 0

        stmt = (
            select(SkillCommentORM)
            .where(
                SkillCommentORM.skill_id == skill_id,
                SkillCommentORM.is_deleted.is_(False),
            )
            .order_by(SkillCommentORM.created_at.asc())
            .offset(offset)
            .limit(limit)
        )
        rows = list((await self.session.scalars(stmt)).all())
        authors = await self._load_authors([row.author_id for row in rows])
        items = [_comment_to_schema(row, authors) for row in rows]
        return SkillCommentListResponse(items=items, total=int(total))

    async def add_comment(
        self,
        skill_id: str,
        author_id: str,
        content: str,
        parent_id: int | None = None,
    ) -> SkillComment:
        """Submit a new comment on a skill."""

        skill = await self.session.get(SkillORM, skill_id)
        if skill is None:
            raise ApiError(404, "SKILL_NOT_FOUND", "Skill not found.", {"skill_id": skill_id})

        if parent_id is not None:
            parent = await self.session.get(SkillCommentORM, parent_id)
            if parent is None or parent.skill_id != skill_id:
                raise ApiError(
                    422,
                    "INVALID_PARENT",
                    "Parent comment not found or belongs to a different skill.",
                )

        comment = SkillCommentORM(
            skill_id=skill_id,
            author_id=author_id,
            parent_id=parent_id,
            content=content,
            created_at=utc_now(),
            updated_at=utc_now(),
        )
        self.session.add(comment)
        await self.session.flush()

        authors = await self._load_authors([author_id])
        return _comment_to_schema(comment, authors)

    async def delete_comment(
        self,
        skill_id: str,
        comment_id: int,
        viewer_id: str,
        is_admin: bool = False,
    ) -> None:
        """Soft-delete a comment (owner or admin)."""

        comment = await self.session.get(SkillCommentORM, comment_id)
        if comment is None or comment.skill_id != skill_id or comment.is_deleted:
            raise ApiError(404, "COMMENT_NOT_FOUND", "Comment not found.")

        if not is_admin and comment.author_id != viewer_id:
            raise ApiError(403, "FORBIDDEN", "You can only delete your own comments.")

        comment.is_deleted = True
        comment.updated_at = utc_now()
        await self.session.flush()

    # ------------------------------------------------------------------
    # Community: subscribe / unsubscribe
    # ------------------------------------------------------------------

    async def toggle_subscription(self, skill_id: str, viewer_id: str) -> dict:
        """Toggle the viewer's subscription on a skill."""

        skill = await self.session.get(SkillORM, skill_id)
        if skill is None:
            raise ApiError(404, "SKILL_NOT_FOUND", "Skill not found.", {"skill_id": skill_id})

        existing = await self.session.scalar(
            select(SkillSubscriptionORM).where(
                SkillSubscriptionORM.skill_id == skill_id,
                SkillSubscriptionORM.author_id == viewer_id,
            )
        )

        if existing is not None:
            await self.session.delete(existing)
            subscribed = False
        else:
            self.session.add(
                SkillSubscriptionORM(
                    skill_id=skill_id,
                    author_id=viewer_id,
                    created_at=utc_now(),
                )
            )
            subscribed = True

        await self.session.flush()

        count = await self.session.scalar(
            select(func.count()).select_from(SkillSubscriptionORM).where(
                SkillSubscriptionORM.skill_id == skill_id
            )
        ) or 0

        return {"subscribed": subscribed, "subscriptions_count": int(count)}

    # ------------------------------------------------------------------
    # Taxonomy
    # ------------------------------------------------------------------

    async def get_categories(self) -> list[str]:
        """Return distinct categories across all published skills."""

        rows = (
            await self.session.scalars(
                select(SkillORM.categories).where(
                    SkillORM.status == SkillStatus.PUBLISHED
                )
            )
        ).all()

        seen: set[str] = set()
        for cats in rows:
            if cats:
                for c in cats:
                    if isinstance(c, str):
                        seen.add(c)
        if not seen:
            # Preset fallback categories when no skills exist yet
            return ["工具", "娱乐", "开发", "知识", "社交"]
        return sorted(seen)

    async def get_tags(self) -> list[str]:
        """Return distinct tags across all published skills."""

        rows = (
            await self.session.scalars(
                select(SkillORM.tags).where(
                    SkillORM.status == SkillStatus.PUBLISHED
                )
            )
        ).all()

        seen: set[str] = set()
        for tags in rows:
            if tags:
                for t in tags:
                    if isinstance(t, str):
                        seen.add(t)
        return sorted(seen)

    # ------------------------------------------------------------------
    # My skills
    # ------------------------------------------------------------------

    async def my_skills(self, owner_id: str) -> SkillListResponse:
        """Return skills owned by the current viewer."""

        stmt = (
            select(SkillORM)
            .where(SkillORM.owner_id == owner_id)
            .order_by(SkillORM.updated_at.desc())
        )

        rows = list((await self.session.scalars(stmt)).all())
        owner = await self.session.get(AuthorORM, owner_id)
        items: list[Skill] = []
        for row in rows:
            ver_rows = await self._load_versions_for_skill(row.skill_id)
            latest = ver_rows[0] if ver_rows else None
            stats = await _aggregate_skill_stats(self.session, row.skill_id, owner_id)
            items.append(
                _skill_to_schema(
                    row,
                    owner=owner,
                    latest_version=latest.version if latest else None,
                    stats=stats,
                )
            )

        return SkillListResponse(items=items, total=len(items))

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _load_authors(self, author_ids: list[str]) -> dict[str, AuthorORM]:
        """Fetch authors keyed by id for comment / list serialization."""

        unique_ids = [value for value in dict.fromkeys(author_ids)]
        if not unique_ids:
            return {}
        rows = await self.session.scalars(
            select(AuthorORM).where(AuthorORM.author_id.in_(unique_ids))
        )
        return {author.author_id: author for author in rows}

    async def _load_versions_for_skill(self, skill_id: str) -> list[SkillVersionORM]:
        """Return versions for a skill, newest first."""

        rows = (
            await self.session.scalars(
                select(SkillVersionORM)
                .where(SkillVersionORM.skill_id == skill_id)
                .order_by(SkillVersionORM.created_at.desc())
            )
        ).all()
        return list(rows)


# ----------------------------------------------------------------------
# Module-level helpers (kept private)
# ----------------------------------------------------------------------


def _skill_to_schema(
    skill: SkillORM,
    *,
    owner: AuthorORM | None = None,
    latest_version: str | None = None,
    stats: dict | None = None,
) -> Skill:
    """Convert a SkillORM row into the Skill API schema."""

    return Skill(
        skill_id=skill.skill_id,
        display_name=skill.display_name,
        description=skill.description or "",
        readme_markdown=skill.readme_markdown,
        owner_id=skill.owner_id,
        owner_login=owner.github_login if owner is not None else None,
        owner_display_name=owner.display_name if owner is not None else None,
        owner_avatar_url=owner.avatar_url if owner is not None else None,
        icon_url=skill.icon_url,
        categories=skill.categories or [],
        tags=skill.tags or [],
        status=skill.status.value if hasattr(skill.status, "value") else str(skill.status),
        trust_level=skill.trust_level.value if hasattr(skill.trust_level, "value") else str(skill.trust_level),
        latest_version=latest_version,
        download_count=skill.download_count or 0,
        likes_count=stats.get("likes_count", 0) if stats else 0,
        comments_count=stats.get("comments_count", 0) if stats else 0,
        rating_avg=stats.get("rating_avg", 0.0) if stats else 0.0,
        rating_count=stats.get("rating_count", 0) if stats else 0,
        viewer_has_liked=stats.get("viewer_has_liked", False) if stats else False,
        viewer_rating=stats.get("viewer_rating") if stats else None,
        created_at=skill.created_at,
        updated_at=skill.updated_at,
    )


def _version_to_schema(ver: SkillVersionORM) -> SkillVersion:
    """Convert a SkillVersionORM row into the SkillVersion API schema."""

    return SkillVersion(
        version=ver.version,
        package_size=ver.package_size,
        checksum_sha256=ver.checksum_sha256,
        release_notes=ver.release_notes,
        min_mofox_version=ver.min_mofox_version,
        download_count=ver.download_count or 0,
        created_at=ver.created_at,
    )


def _comment_to_schema(
    comment: SkillCommentORM,
    authors: dict[str, AuthorORM],
) -> SkillComment:
    """Convert a SkillCommentORM row into the SkillComment API schema."""

    author = authors.get(comment.author_id)
    return SkillComment(
        id=comment.id,
        skill_id=comment.skill_id,
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
        mentions=[],
    )


async def _aggregate_skill_stats(
    session: AsyncSession,
    skill_id: str,
    viewer_id: str | None = None,
) -> dict:
    """Compute community stats for a skill."""

    likes_count = await session.scalar(
        select(func.count()).select_from(SkillLikeORM).where(
            SkillLikeORM.skill_id == skill_id
        )
    ) or 0

    comments_count = await session.scalar(
        select(func.count()).select_from(SkillCommentORM).where(
            SkillCommentORM.skill_id == skill_id,
            SkillCommentORM.is_deleted.is_(False),
        )
    ) or 0

    agg = await session.execute(
        select(
            func.coalesce(func.avg(SkillRatingORM.score), 0.0),
            func.count(SkillRatingORM.id),
        ).where(SkillRatingORM.skill_id == skill_id)
    )
    row = agg.first()
    rating_avg = round(float(row[0]), 1) if row else 0.0
    rating_count = int(row[1]) if row else 0

    viewer_has_liked = False
    viewer_rating: int | None = None
    if viewer_id:
        like = await session.scalar(
            select(SkillLikeORM.id).where(
                SkillLikeORM.skill_id == skill_id,
                SkillLikeORM.author_id == viewer_id,
            )
        )
        viewer_has_liked = like is not None

        vrating = await session.scalar(
            select(SkillRatingORM.score).where(
                SkillRatingORM.skill_id == skill_id,
                SkillRatingORM.author_id == viewer_id,
            )
        )
        viewer_rating = vrating

    return {
        "likes_count": int(likes_count),
        "comments_count": int(comments_count),
        "rating_avg": rating_avg,
        "rating_count": rating_count,
        "viewer_has_liked": viewer_has_liked,
        "viewer_rating": viewer_rating,
    }


async def _append_audit(
    session: AsyncSession,
    *,
    action: ReviewAction,
    target_type: str,
    target_id: str,
    operator_id: str,
    status_before: str | None = None,
    status_after: str | None = None,
    reason: str | None = None,
) -> None:
    """Append a ReviewRecordORM audit row."""

    record = ReviewRecordORM(
        target_type=target_type,
        target_id=target_id,
        action=action,
        status_before=status_before,
        status_after=status_after,
        reason=reason,
        operator_id=operator_id,
        created_at=utc_now(),
    )
    session.add(record)
    await session.flush()
