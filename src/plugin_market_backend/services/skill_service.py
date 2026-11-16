"""提供技能市场的领域服务。

本模块实现技能市场后端操作：

* ``SkillService.create_skill`` 校验 ZIP 包，从 SKILL.md 提取元数据，
  持久化安装包，并在数据库中记录技能和版本。
* ``SkillService.publish_version`` 添加可安装的新 ZIP 版本。
* ``SkillService.update_skill_meta`` 局部更新可修改的元数据字段。
* ``SkillService.get_skill`` 和 ``list_skills`` 提供公开查询并聚合社区统计。
* 社区交互：点赞与取消点赞、评分、评论管理、订阅与取消订阅。
* 管理员操作：封禁、设置信任级别和删除。

技能发布、元数据变更和治理写操作会追加 ``ReviewRecordORM`` 审计记录。
"""

from __future__ import annotations

from datetime import datetime
import hashlib
import os
import shutil

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from plugin_market_backend.content import (
    extract_and_validate_skill,
    infer_skill_storage_identifiers,
    inspect_skill_archive,
    iter_skill_package_files,
    load_skill_package_manifest,
    resolve_skill_package_path,
    skill_package_storage_path,
    store_skill_package,
    validate_skill_id,
    validate_skill_version,
    write_skill_package_manifest,
)
from plugin_market_backend.enums import AuthorType, ReviewAction, SkillStatus, TrustLevel
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
    """管理技能市场记录、版本及社区交互。

    本服务将技能市场写操作集中在职责明确的模块中，统一执行审计和校验规则。
    """

    def __init__(self, session: AsyncSession) -> None:
        """创建绑定到单个事务会话的服务。"""
        self.session = session

    # ------------------------------------------------------------------
    # 创建和发布
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
        """校验技能 ZIP 包、提取元数据并持久化技能与版本。

        Args:
            owner_id: 技能所有者 ID。
            skill_id: 待创建的技能 ID。
            zip_bytes: 技能 ZIP 包的原始字节。
            version: 初始版本号。
            release_notes: 可选的版本说明。
            min_mofox_version: 可选的最低 MoFox 版本要求。
            categories: 可选的分类列表。
            tags: 可选的标签列表。

        Returns:
            新建技能的 DTO。

        Raises:
            ApiError: 技能 ID、版本或安装包校验失败，或技能 ID 已存在。
        """
        skill_id = validate_skill_id(skill_id)
        version = validate_skill_version(version)

        # 校验 ZIP 包并提取元数据。
        name, description, _readme = extract_and_validate_skill(zip_bytes)

        # 检查 skill_id 是否已存在。
        existing = await self.session.get(SkillORM, skill_id)
        if existing is not None:
            raise ApiError(
                409,
                "SKILL_ALREADY_EXISTS",
                f"ID 为 '{skill_id}' 的技能已存在。",
                {"skill_id": skill_id},
            )

        # 存储 ZIP 安装包。
        package_path = store_skill_package(owner_id, skill_id, version, zip_bytes)
        package_size = len(zip_bytes)
        checksum = hashlib.sha256(zip_bytes).hexdigest()

        # 创建技能 ORM 记录。
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

        # 创建版本 ORM 记录。
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
        write_skill_package_manifest(
            package_path,
            {
                "owner_id": owner_id,
                "skill_id": skill_id,
                "version": version,
                "display_name": name,
                "description": description or "",
                "readme_markdown": _readme or None,
                "categories": categories or [],
                "tags": tags or [],
                "status": SkillStatus.PUBLISHED.value,
                "trust_level": TrustLevel.COMMUNITY.value,
                "release_notes": release_notes,
                "min_mofox_version": min_mofox_version,
                "created_at": now.isoformat(),
                "updated_at": now.isoformat(),
                "version_created_at": now.isoformat(),
            },
        )

        # 记录审计信息。
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
        """为已有技能发布新版本。

        ZIP 包使用与 ``create_skill`` 相同的校验方式。

        Args:
            skill_id: 目标技能的 ID。
            version: 待发布的版本号。
            zip_bytes: 技能 ZIP 包的原始字节。
            operator_id: 发布版本的操作者 ID。
            release_notes: 可选的版本说明。
            min_mofox_version: 可选的最低 MoFox 版本要求。

        Returns:
            新建的技能版本数据模型。

        Raises:
            ApiError: 技能不存在、版本重复，或 ID、版本、安装包校验失败。
        """
        skill_id = validate_skill_id(skill_id)
        version = validate_skill_version(version)

        skill = await self.session.get(SkillORM, skill_id)
        if skill is None:
            raise ApiError(404, "SKILL_NOT_FOUND", "未找到技能。", {"skill_id": skill_id})

        # 校验 ZIP 包，此处不使用提取出的名称和描述。
        extract_and_validate_skill(zip_bytes)

        # 检查版本号是否唯一。
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
                f"版本 '{version}' 已存在于技能 '{skill_id}' 中。",
                {"skill_id": skill_id, "version": version},
            )

        # 存储 ZIP 安装包。
        package_path = store_skill_package(skill.owner_id, skill_id, version, zip_bytes)
        package_size = len(zip_bytes)
        checksum = hashlib.sha256(zip_bytes).hexdigest()
        created_at = utc_now()

        ver = SkillVersionORM(
            skill_id=skill_id,
            version=version,
            package_path=package_path,
            package_size=package_size,
            checksum_sha256=checksum,
            release_notes=release_notes,
            min_mofox_version=min_mofox_version,
            download_count=0,
            created_at=created_at,
        )
        self.session.add(ver)
        write_skill_package_manifest(
            package_path,
            {
                "owner_id": skill.owner_id,
                "skill_id": skill_id,
                "version": version,
                "display_name": skill.display_name,
                "description": skill.description or "",
                "readme_markdown": skill.readme_markdown,
                "categories": skill.categories or [],
                "tags": skill.tags or [],
                "status": (
                    skill.status.value if hasattr(skill.status, "value") else str(skill.status)
                ),
                "trust_level": (
                    skill.trust_level.value
                    if hasattr(skill.trust_level, "value")
                    else str(skill.trust_level)
                ),
                "release_notes": release_notes,
                "min_mofox_version": min_mofox_version,
                "created_at": (
                    skill.created_at.isoformat() if skill.created_at is not None else None
                ),
                "updated_at": updated_at.isoformat(),
                "version_created_at": created_at.isoformat(),
            },
        )

        # 更新技能时间戳。
        skill.updated_at = updated_at

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
    # 元数据更新
    # ------------------------------------------------------------------

    async def update_skill_meta(
        self,
        skill_id: str,
        operator_id: str,
        update: SkillUpdate,
    ) -> Skill:
        """局部更新技能中可修改的元数据字段。

        仅修改已提供且不为 ``None`` 的字段。
        """
        skill = await self.session.get(SkillORM, skill_id)
        if skill is None:
            raise ApiError(404, "SKILL_NOT_FOUND", "未找到技能。", {"skill_id": skill_id})

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
    # 查询
    # ------------------------------------------------------------------

    async def get_skill(self, skill_id: str, viewer_id: str | None = None) -> Skill:
        """返回单个技能及聚合后的社区统计。"""
        skill = await self.session.get(SkillORM, skill_id)
        if skill is None:
            raise ApiError(404, "SKILL_NOT_FOUND", "未找到技能。", {"skill_id": skill_id})

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
        """返回经过筛选和分页的已发布技能列表。"""
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

        # 排序
        sort_cols: dict[str, object] = {
            "updated": SkillORM.updated_at.desc(),
            "created": SkillORM.created_at.desc(),
            "downloads": SkillORM.download_count.desc(),
            "name": SkillORM.display_name.asc(),
        }
        order = sort_cols.get(sort, SkillORM.updated_at.desc())
        stmt = stmt.order_by(order).offset(offset).limit(page_size)

        rows = list((await self.session.scalars(stmt)).all())

        # 汇总所有者、版本及统计信息。
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
        """返回指定技能的所有版本。"""
        skill = await self.session.get(SkillORM, skill_id)
        if skill is None:
            raise ApiError(404, "SKILL_NOT_FOUND", "未找到技能。", {"skill_id": skill_id})

        versions = await self._load_versions_for_skill(skill_id)
        return SkillVersionListResponse(
            items=[_version_to_schema(v) for v in versions],
            total=len(versions),
        )

    async def get_version_download(
        self, skill_id: str, version: str
    ) -> tuple[str, int, str]:
        """返回技能版本安装包的路径、大小和校验和元组。"""
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
                "未找到技能版本。",
                {"skill_id": skill_id, "version": version},
            )

        file_path = resolve_skill_package_path(ver.package_path)
        if not os.path.isfile(file_path):
            raise ApiError(
                404,
                "SKILL_PACKAGE_MISSING",
                "存储中缺少安装包文件。",
                {"skill_id": skill_id, "version": version},
            )

        return str(file_path), ver.package_size, ver.checksum_sha256

    async def record_download(self, skill_id: str, version: str | None = None) -> SkillInstallRecord:
        """增加技能版本的下载计数。

        ``version`` 为 ``None`` 时使用最新版本。
        """
        if version is None:
            versions = await self._load_versions_for_skill(skill_id)
            if not versions:
                raise ApiError(
                    404,
                    "SKILL_NO_VERSIONS",
                    "技能尚无版本。",
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
                "未找到技能版本。",
                {"skill_id": skill_id, "version": version},
            )

        ver.download_count = (ver.download_count or 0) + 1

        # 同时累加到所属技能的下载计数。
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
    # 删除和封禁
    # ------------------------------------------------------------------

    async def delete_skill(self, skill_id: str, operator_id: str) -> None:
        """删除技能及其关联记录。"""
        skill = await self.session.get(SkillORM, skill_id)
        if skill is None:
            raise ApiError(404, "SKILL_NOT_FOUND", "未找到技能。", {"skill_id": skill_id})

        await _append_audit(
            self.session,
            action=ReviewAction.DELETE_SKILL,
            target_type="skill",
            target_id=skill_id,
            operator_id=operator_id,
            status_before=skill.status.value,
        )

        # 通过 ORM 删除技能及其关联记录。
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
        """封禁技能，仅供管理员操作。"""
        skill = await self.session.get(SkillORM, skill_id)
        if skill is None:
            raise ApiError(404, "SKILL_NOT_FOUND", "未找到技能。", {"skill_id": skill_id})

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
        """设置技能的信任级别。"""
        skill = await self.session.get(SkillORM, skill_id)
        if skill is None:
            raise ApiError(404, "SKILL_NOT_FOUND", "未找到技能。", {"skill_id": skill_id})

        try:
            new_level = TrustLevel(trust_level)
        except ValueError:
            raise ApiError(
                422,
                "INVALID_TRUST_LEVEL",
                f"无效的信任级别：{trust_level}。",
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
    # 社区交互：点赞和取消点赞
    # ------------------------------------------------------------------

    async def toggle_like(self, skill_id: str, viewer_id: str) -> dict:
        """切换访问者对技能的点赞状态，返回 ``liked`` 和 ``likes_count``。"""
        skill = await self.session.get(SkillORM, skill_id)
        if skill is None:
            raise ApiError(404, "SKILL_NOT_FOUND", "未找到技能。", {"skill_id": skill_id})

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
    # 社区交互：评分
    # ------------------------------------------------------------------

    async def rate_skill(self, skill_id: str, viewer_id: str, score: int) -> SkillRatingInfo:
        """提交或更新访问者的评分，范围为 1 至 5 分。"""
        skill = await self.session.get(SkillORM, skill_id)
        if skill is None:
            raise ApiError(404, "SKILL_NOT_FOUND", "未找到技能。", {"skill_id": skill_id})

        if score < 1 or score > 5:
            raise ApiError(422, "INVALID_RATING", "评分必须在 1 至 5 之间。")

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
        """移除访问者的评分。"""
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
        """返回指定技能的评分汇总统计。"""
        agg = await self.session.execute(
            select(
                func.coalesce(func.avg(SkillRatingORM.score), 0.0),
                func.count(SkillRatingORM.id),
            ).where(SkillRatingORM.skill_id == skill_id)
        )
        row = agg.first()
        avg_val = float(row[0]) if row else 0.0
        count_val = int(row[1]) if row else 0

        # 评分分布
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
    # 社区交互：评论
    # ------------------------------------------------------------------

    async def list_comments(
        self,
        skill_id: str,
        *,
        offset: int = 0,
        limit: int = 50,
    ) -> SkillCommentListResponse:
        """按时间从早到晚列出技能评论。"""
        skill = await self.session.get(SkillORM, skill_id)
        if skill is None:
            raise ApiError(404, "SKILL_NOT_FOUND", "未找到技能。", {"skill_id": skill_id})

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
        """为技能提交新评论。"""
        skill = await self.session.get(SkillORM, skill_id)
        if skill is None:
            raise ApiError(404, "SKILL_NOT_FOUND", "未找到技能。", {"skill_id": skill_id})

        if parent_id is not None:
            parent = await self.session.get(SkillCommentORM, parent_id)
            if parent is None or parent.skill_id != skill_id:
                raise ApiError(
                    422,
                    "INVALID_PARENT",
                    "父评论不存在或属于其他技能。",
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
        """由评论作者或管理员软删除评论。"""
        comment = await self.session.get(SkillCommentORM, comment_id)
        if comment is None or comment.skill_id != skill_id or comment.is_deleted:
            raise ApiError(404, "COMMENT_NOT_FOUND", "未找到评论。")

        if not is_admin and comment.author_id != viewer_id:
            raise ApiError(403, "FORBIDDEN", "你只能删除自己的评论。")

        comment.is_deleted = True
        comment.updated_at = utc_now()
        await self.session.flush()

    # ------------------------------------------------------------------
    # 社区交互：订阅和取消订阅
    # ------------------------------------------------------------------

    async def toggle_subscription(self, skill_id: str, viewer_id: str) -> dict:
        """切换访问者对技能的订阅状态。"""
        skill = await self.session.get(SkillORM, skill_id)
        if skill is None:
            raise ApiError(404, "SKILL_NOT_FOUND", "未找到技能。", {"skill_id": skill_id})

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
    # 分类体系
    # ------------------------------------------------------------------

    async def get_categories(self) -> list[str]:
        """返回所有已发布技能的去重分类列表。"""
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
            # 尚无可用分类时返回预设分类。
            return ["工具", "娱乐", "开发", "知识", "社交"]
        return sorted(seen)

    async def get_tags(self) -> list[str]:
        """返回所有已发布技能的去重标签列表。"""
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
    # 我的技能
    # ------------------------------------------------------------------

    async def my_skills(self, owner_id: str) -> SkillListResponse:
        """返回当前访问者拥有的技能。"""
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
    # 内部辅助函数
    # ------------------------------------------------------------------

    async def _load_authors(self, author_ids: list[str]) -> dict[str, AuthorORM]:
        """按 ID 加载作者映射，用于评论和列表的序列化。"""
        unique_ids = [value for value in dict.fromkeys(author_ids)]
        if not unique_ids:
            return {}
        rows = await self.session.scalars(
            select(AuthorORM).where(AuthorORM.author_id.in_(unique_ids))
        )
        return {author.author_id: author for author in rows}

    async def _load_versions_for_skill(self, skill_id: str) -> list[SkillVersionORM]:
        """按时间从新到旧返回技能版本。"""
        rows = (
            await self.session.scalars(
                select(SkillVersionORM)
                .where(SkillVersionORM.skill_id == skill_id)
                .order_by(SkillVersionORM.created_at.desc())
            )
        ).all()
        return list(rows)


async def synchronize_skill_storage(session: AsyncSession) -> int:
    """回填存储元数据，并从磁盘恢复缺失的技能记录。"""
    await _backfill_skill_storage_metadata(session)
    return await _recover_missing_skills_from_storage(session)


async def _backfill_skill_storage_metadata(session: AsyncSession) -> None:
    """确保已存储的技能包具有稳定路径及配套清单文件。"""
    rows = (
        await session.execute(
            select(SkillORM, SkillVersionORM).join(
                SkillVersionORM,
                SkillVersionORM.skill_id == SkillORM.skill_id,
            )
        )
    ).all()

    for skill, version in rows:
        current_path = resolve_skill_package_path(version.package_path)
        target_path = skill_package_storage_path(skill.owner_id, skill.skill_id, version.version)
        target_abs_path = resolve_skill_package_path(target_path)

        if current_path.exists() and current_path.resolve() != target_abs_path.resolve():
            target_abs_path.parent.mkdir(parents=True, exist_ok=True)
            if not target_abs_path.exists():
                shutil.move(str(current_path), str(target_abs_path))

        if target_abs_path.exists():
            version.package_path = target_path
            write_skill_package_manifest(
                target_path,
                {
                    "owner_id": skill.owner_id,
                    "skill_id": skill.skill_id,
                    "version": version.version,
                    "display_name": skill.display_name,
                    "description": skill.description or "",
                    "readme_markdown": skill.readme_markdown,
                    "categories": skill.categories or [],
                    "tags": skill.tags or [],
                    "status": (
                        skill.status.value if hasattr(skill.status, "value") else str(skill.status)
                    ),
                    "trust_level": (
                        skill.trust_level.value
                        if hasattr(skill.trust_level, "value")
                        else str(skill.trust_level)
                    ),
                    "release_notes": version.release_notes,
                    "min_mofox_version": version.min_mofox_version,
                    "created_at": (
                        skill.created_at.isoformat() if skill.created_at is not None else None
                    ),
                    "updated_at": (
                        skill.updated_at.isoformat() if skill.updated_at is not None else None
                    ),
                    "version_created_at": (
                        version.created_at.isoformat() if version.created_at is not None else None
                    ),
                },
            )

    await session.flush()


async def _recover_missing_skills_from_storage(session: AsyncSession) -> int:
    """从已持久化的 ZIP 包和清单中重建缺失的技能记录。"""
    existing_skills = set((await session.scalars(select(SkillORM.skill_id))).all())
    existing_versions = set(
        tuple(row)
        for row in (
            await session.execute(select(SkillVersionORM.skill_id, SkillVersionORM.version))
        ).all()
    )

    recovered = 0
    for stored_path, absolute_path in iter_skill_package_files():
        manifest = load_skill_package_manifest(stored_path) or {}
        owner_from_path, skill_from_path, version_from_path = infer_skill_storage_identifiers(
            stored_path
        )
        zip_bytes = absolute_path.read_bytes()
        archive = inspect_skill_archive(zip_bytes)

        skill_id = str(
            manifest.get("skill_id")
            or archive.front_matter.get("skill_id")
            or skill_from_path
            or ""
        ).strip()
        version = str(
            manifest.get("version")
            or archive.front_matter.get("version")
            or version_from_path
            or ""
        ).strip()
        owner_id = str(
            manifest.get("owner_id")
            or archive.front_matter.get("owner_id")
            or archive.front_matter.get("author_id")
            or owner_from_path
            or f"recovered:{skill_id or absolute_path.parent.name}"
        ).strip()

        if not skill_id or not version:
            continue

        skill_id = validate_skill_id(skill_id)
        version = validate_skill_version(version)
        owner_id = owner_id or f"recovered:{skill_id}"
        await _ensure_recovery_author(
            session,
            owner_id=owner_id,
            display_name=str(
                manifest.get("owner_display_name")
                or archive.front_matter.get("owner_display_name")
                or archive.front_matter.get("author_name")
                or owner_id
            ).strip()
            or owner_id,
        )

        created_at = (
            _parse_recovery_datetime(
                manifest.get("created_at") or archive.front_matter.get("created_at")
            )
            or utc_now()
        )
        updated_at = (
            _parse_recovery_datetime(
                manifest.get("updated_at") or archive.front_matter.get("updated_at")
            )
            or created_at
        )
        version_created_at = (
            _parse_recovery_datetime(
                manifest.get("version_created_at") or archive.front_matter.get("version_created_at")
            )
            or updated_at
        )

        categories = _coerce_string_list(
            manifest.get("categories") or archive.front_matter.get("categories")
        )
        tags = _coerce_string_list(manifest.get("tags") or archive.front_matter.get("tags"))
        release_notes = _coerce_optional_text(
            manifest.get("release_notes") or archive.front_matter.get("release_notes")
        )
        min_mofox_version = _coerce_optional_text(
            manifest.get("min_mofox_version") or archive.front_matter.get("min_mofox_version")
        )
        display_name = str(manifest.get("display_name") or archive.name).strip() or archive.name
        description = (
            _coerce_optional_text(manifest.get("description") or archive.description) or ""
        )
        readme_markdown = _coerce_optional_text(
            manifest.get("readme_markdown") or archive.readme_text
        )
        status = _parse_skill_status(manifest.get("status"))
        trust_level = _parse_trust_level(manifest.get("trust_level"))

        write_skill_package_manifest(
            stored_path,
            {
                "owner_id": owner_id,
                "skill_id": skill_id,
                "version": version,
                "display_name": display_name,
                "description": description,
                "readme_markdown": readme_markdown,
                "categories": categories,
                "tags": tags,
                "status": status.value,
                "trust_level": trust_level.value,
                "release_notes": release_notes,
                "min_mofox_version": min_mofox_version,
                "created_at": created_at.isoformat(),
                "updated_at": updated_at.isoformat(),
                "version_created_at": version_created_at.isoformat(),
                "owner_display_name": owner_id,
            },
        )

        if skill_id not in existing_skills:
            skill = SkillORM(
                skill_id=skill_id,
                display_name=display_name,
                description=description,
                readme_markdown=readme_markdown,
                owner_id=owner_id,
                categories=categories,
                tags=tags,
                status=status,
                trust_level=trust_level,
                download_count=0,
                created_at=created_at,
                updated_at=updated_at,
            )
            session.add(skill)
            existing_skills.add(skill_id)
            recovered += 1

        version_key = (skill_id, version)
        if version_key not in existing_versions:
            session.add(
                SkillVersionORM(
                    skill_id=skill_id,
                    version=version,
                    package_path=stored_path,
                    package_size=len(zip_bytes),
                    checksum_sha256=hashlib.sha256(zip_bytes).hexdigest(),
                    release_notes=release_notes,
                    min_mofox_version=min_mofox_version,
                    download_count=0,
                    created_at=version_created_at,
                )
            )
            existing_versions.add(version_key)
            recovered += 1

    if recovered:
        await session.flush()
    return recovered


async def _ensure_recovery_author(
    session: AsyncSession,
    *,
    owner_id: str,
    display_name: str,
) -> None:
    """恢复时发现未知所有者，则创建包含最少必要信息的作者记录。"""
    with session.no_autoflush:
        existing = await session.get(AuthorORM, owner_id)
        if existing is not None:
            return
        login = owner_id
        by_login = (
            await session.execute(select(AuthorORM).where(AuthorORM.github_login == login))
        ).scalar_one_or_none()
        if by_login is not None:
            return

    session.add(
        AuthorORM(
            author_id=owner_id,
            github_login=owner_id,
            display_name=display_name or owner_id,
            author_type=AuthorType.USER,
            verified_at=utc_now(),
            created_at=utc_now(),
            updated_at=utc_now(),
        )
    )
    await session.flush()


def _parse_recovery_datetime(value: object) -> datetime | None:
    """解析可选的已存储 ISO 日期时间。"""
    if isinstance(value, str) and value.strip():
        normalized = value.strip().replace("Z", "+00:00")
        try:
            parsed = datetime.fromisoformat(normalized)
        except ValueError:
            return None
        return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=utc_now().tzinfo)
    return None


def _coerce_optional_text(value: object) -> str | None:
    """规范化清单或文档头部元数据中的可选文本值。"""
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _coerce_string_list(value: object) -> list[str]:
    """将清单或文档头部元数据中的列表类值规范化为干净的字符串列表。"""
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str):
        return [item.strip() for item in value.split(",") if item.strip()]
    return []


def _parse_skill_status(value: object) -> SkillStatus:
    """解析已存储的状态，恢复时默认使用已发布状态。"""
    if isinstance(value, str):
        try:
            return SkillStatus(value)
        except ValueError:
            return SkillStatus.PUBLISHED
    return SkillStatus.PUBLISHED


def _parse_trust_level(value: object) -> TrustLevel:
    """解析已存储的信任级别，恢复时默认使用社区级别。"""
    if isinstance(value, str):
        try:
            return TrustLevel(value)
        except ValueError:
            return TrustLevel.COMMUNITY
    return TrustLevel.COMMUNITY


# ----------------------------------------------------------------------
# 模块级私有辅助函数
# ----------------------------------------------------------------------


def _skill_to_schema(
    skill: SkillORM,
    *,
    owner: AuthorORM | None = None,
    latest_version: str | None = None,
    stats: dict | None = None,
) -> Skill:
    """将 SkillORM 记录转换为 Skill API 数据模型。"""
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
    """将 SkillVersionORM 记录转换为 SkillVersion API 数据模型。"""
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
    """将 SkillCommentORM 记录转换为 SkillComment API 数据模型。"""
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
    """计算指定技能的社区统计信息。"""
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
    """追加一条 ReviewRecordORM 审计记录。"""
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
