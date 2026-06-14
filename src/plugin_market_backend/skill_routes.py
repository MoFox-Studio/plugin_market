"""Skill market API routes registered on the FastAPI application."""

from __future__ import annotations

from fastapi import Depends, File, Form, Query, Request, Response, UploadFile, status
from fastapi.responses import FileResponse

from plugin_market_backend.database import session_scope
from plugin_market_backend.errors import ApiError
from plugin_market_backend.schemas import (
    RatingRequest,
    ReviewDecision,
    Skill,
    SkillComment,
    SkillCommentCreate,
    SkillCommentListResponse,
    SkillInstallRecord,
    SkillListResponse,
    SkillRatingInfo,
    SkillUpdate,
    SkillVersion,
    SkillVersionCreate,
    SkillVersionListResponse,
    TaxonomyResponse,
)
from plugin_market_backend.services import SkillService
from plugin_market_backend.session_auth import (
    current_author_from_request,
    require_browser_author,
)


def register_skill_routes(app):
    """Register all skill-market routes on the application."""

    # Lazy imports to avoid circular dependency with app module
    from plugin_market_backend.app import ensure_same_origin_browser_write, require_admin_operator

    # ---- Public query ----

    @app.get("/api/v1/skills", response_model=SkillListResponse)
    async def list_skills(
        request: Request,
        search: str | None = Query(default=None),
        category: str | None = Query(default=None),
        tag: str | None = Query(default=None),
        sort: str = Query(default="updated"),
        page: int = Query(default=1, ge=1),
        page_size: int = Query(default=50, ge=1, le=100),
    ) -> SkillListResponse:
        viewer = await current_author_from_request(request)
        viewer_id = viewer.author_id if viewer else None
        async with session_scope() as session:
            return await SkillService(session).list_skills(
                search=search, category=category, tag=tag,
                sort=sort, page=page, page_size=page_size, viewer_id=viewer_id,
            )

    @app.get("/api/v1/skills/categories", response_model=TaxonomyResponse)
    async def list_skill_categories() -> TaxonomyResponse:
        async with session_scope() as session:
            return TaxonomyResponse(items=await SkillService(session).get_categories())

    @app.get("/api/v1/skills/tags", response_model=TaxonomyResponse)
    async def list_skill_tags() -> TaxonomyResponse:
        async with session_scope() as session:
            return TaxonomyResponse(items=await SkillService(session).get_tags())

    @app.get("/api/v1/skills/{skill_id}", response_model=Skill)
    async def get_skill(skill_id: str, request: Request) -> Skill:
        viewer = await current_author_from_request(request)
        viewer_id = viewer.author_id if viewer else None
        async with session_scope() as session:
            return await SkillService(session).get_skill(skill_id, viewer_id)

    @app.get("/api/v1/skills/{skill_id}/versions", response_model=SkillVersionListResponse)
    async def list_skill_versions(skill_id: str) -> SkillVersionListResponse:
        async with session_scope() as session:
            return await SkillService(session).get_skill_versions(skill_id)

    @app.get("/api/v1/skills/{skill_id}/versions/{version}", response_model=SkillVersion)
    async def get_skill_version(skill_id: str, version: str) -> SkillVersion:
        async with session_scope() as session:
            versions = await SkillService(session).get_skill_versions(skill_id)
            for item in versions.items:
                if item.version == version:
                    return item
            raise ApiError(404, "SKILL_VERSION_NOT_FOUND", "Skill version not found.",
                           {"skill_id": skill_id, "version": version})

    @app.get("/api/v1/skills/{skill_id}/versions/{version}/download")
    async def download_skill_version(skill_id: str, version: str) -> FileResponse:
        async with session_scope() as session:
            svc = SkillService(session)
            file_path, file_size, checksum = await svc.get_version_download(skill_id, version)
            await svc.record_download(skill_id, version)

        safe_skill = "".join(ch for ch in skill_id if ch.isalnum() or ch in "-_.")
        filename = f"{safe_skill}-{version}.zip"
        return FileResponse(
            file_path,
            media_type="application/zip",
            filename=filename,
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    # ---- Community interactions (login required) ----

    @app.get("/api/v1/skills/{skill_id}/comments", response_model=SkillCommentListResponse)
    async def list_skill_comments(
        skill_id: str,
        offset: int = Query(default=0, ge=0),
        limit: int = Query(default=50, ge=1, le=100),
    ) -> SkillCommentListResponse:
        async with session_scope() as session:
            return await SkillService(session).list_comments(skill_id, offset=offset, limit=limit)

    @app.post("/api/v1/skills/{skill_id}/comments", response_model=SkillComment)
    async def add_skill_comment(
        skill_id: str,
        payload: SkillCommentCreate,
        request: Request,
        viewer_id: str = Depends(require_browser_author),
    ) -> SkillComment:
        ensure_same_origin_browser_write(request)
        async with session_scope() as session:
            return await SkillService(session).add_comment(
                skill_id, viewer_id, payload.content, payload.parent_id,
            )

    @app.delete("/api/v1/skills/{skill_id}/comments/{comment_id}")
    async def delete_skill_comment(skill_id: str, comment_id: int, request: Request) -> dict:
        ensure_same_origin_browser_write(request)
        author = await current_author_from_request(request)
        if author is None:
            raise ApiError(401, "UNAUTHORIZED", "GitHub login is required.")
        async with session_scope() as session:
            await SkillService(session).delete_comment(
                skill_id, comment_id, author.author_id, bool(author.is_admin),
            )
        return {"ok": True}

    @app.post("/api/v1/skills/{skill_id}/rating", response_model=SkillRatingInfo)
    async def rate_skill(
        skill_id: str,
        payload: RatingRequest,
        request: Request,
        viewer_id: str = Depends(require_browser_author),
    ) -> SkillRatingInfo:
        ensure_same_origin_browser_write(request)
        async with session_scope() as session:
            return await SkillService(session).rate_skill(skill_id, viewer_id, payload.score)

    @app.delete("/api/v1/skills/{skill_id}/rating", response_model=SkillRatingInfo)
    async def clear_skill_rating(
        skill_id: str,
        request: Request,
        viewer_id: str = Depends(require_browser_author),
    ) -> SkillRatingInfo:
        ensure_same_origin_browser_write(request)
        async with session_scope() as session:
            return await SkillService(session).clear_rating(skill_id, viewer_id)

    @app.get("/api/v1/skills/{skill_id}/rating", response_model=SkillRatingInfo)
    async def get_skill_rating(skill_id: str, request: Request) -> SkillRatingInfo:
        viewer = await current_author_from_request(request)
        viewer_id = viewer.author_id if viewer else None
        async with session_scope() as session:
            return await SkillService(session).rating_summary(skill_id, viewer_id)

    @app.post("/api/v1/skills/{skill_id}/like")
    async def toggle_skill_like(
        skill_id: str,
        request: Request,
        viewer_id: str = Depends(require_browser_author),
    ) -> dict:
        ensure_same_origin_browser_write(request)
        async with session_scope() as session:
            return await SkillService(session).toggle_like(skill_id, viewer_id)

    @app.post("/api/v1/skills/{skill_id}/subscribe")
    async def toggle_skill_subscription(
        skill_id: str,
        request: Request,
        viewer_id: str = Depends(require_browser_author),
    ) -> dict:
        ensure_same_origin_browser_write(request)
        async with session_scope() as session:
            return await SkillService(session).toggle_subscription(skill_id, viewer_id)

    @app.post("/api/v1/skills/{skill_id}/install-record", response_model=SkillInstallRecord)
    async def record_skill_install(
        skill_id: str,
        version: str = Query(...),
    ) -> SkillInstallRecord:
        async with session_scope() as session:
            return await SkillService(session).record_download(skill_id, version)

    # ---- Author routes (login required) ----

    @app.post("/api/v1/skills", response_model=Skill)
    async def publish_skill(
        request: Request,
        file: UploadFile = File(...),
        skill_id: str = Form(...),
        version: str = Form(...),
        release_notes: str | None = Form(default=None),
        min_mofox_version: str | None = Form(default=None),
        categories: str | None = Form(default=None),
        tags: str | None = Form(default=None),
        viewer_id: str = Depends(require_browser_author),
    ) -> Skill:
        ensure_same_origin_browser_write(request)
        import json as _json

        zip_bytes = await file.read()
        parsed_categories = _json.loads(categories) if categories else None
        parsed_tags = _json.loads(tags) if tags else None

        async with session_scope() as session:
            return await SkillService(session).create_skill(
                owner_id=viewer_id,
                skill_id=skill_id,
                zip_bytes=zip_bytes,
                version=version,
                release_notes=release_notes,
                min_mofox_version=min_mofox_version,
                categories=parsed_categories,
                tags=parsed_tags,
            )

    @app.post("/api/v1/skills/{skill_id}/versions", response_model=SkillVersion)
    async def publish_skill_version(
        skill_id: str,
        request: Request,
        file: UploadFile = File(...),
        version: str = Form(...),
        release_notes: str | None = Form(default=None),
        min_mofox_version: str | None = Form(default=None),
        viewer_id: str = Depends(require_browser_author),
    ) -> SkillVersion:
        ensure_same_origin_browser_write(request)
        zip_bytes = await file.read()

        async with session_scope() as session:
            return await SkillService(session).publish_version(
                skill_id=skill_id,
                version=version,
                zip_bytes=zip_bytes,
                operator_id=viewer_id,
                release_notes=release_notes,
                min_mofox_version=min_mofox_version,
            )

    @app.put("/api/v1/skills/{skill_id}", response_model=Skill)
    async def update_skill(
        skill_id: str,
        payload: SkillUpdate,
        request: Request,
        viewer_id: str = Depends(require_browser_author),
    ) -> Skill:
        ensure_same_origin_browser_write(request)
        async with session_scope() as session:
            return await SkillService(session).update_skill_meta(skill_id, viewer_id, payload)

    @app.delete("/api/v1/skills/{skill_id}", status_code=status.HTTP_204_NO_CONTENT)
    async def delete_skill(
        skill_id: str,
        request: Request,
        viewer_id: str = Depends(require_browser_author),
    ) -> Response:
        ensure_same_origin_browser_write(request)
        async with session_scope() as session:
            await SkillService(session).delete_skill(skill_id, viewer_id)
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    @app.get("/api/v1/me/skills", response_model=SkillListResponse)
    async def my_skills(
        viewer_id: str = Depends(require_browser_author),
    ) -> SkillListResponse:
        async with session_scope() as session:
            return await SkillService(session).my_skills(viewer_id)

    # ---- Admin routes ----

    @app.post("/api/v1/admin/skills/{skill_id}/block", response_model=Skill)
    async def block_skill(
        skill_id: str,
        decision: ReviewDecision | None = None,
        operator_id: str = Depends(require_admin_operator),
    ) -> Skill:
        async with session_scope() as session:
            return await SkillService(session).block_skill(
                skill_id, operator_id, decision.reason if decision else None,
            )

    @app.post("/api/v1/admin/skills/{skill_id}/trust-level/{trust_level}", response_model=Skill)
    async def set_skill_trust_level(
        skill_id: str,
        trust_level: str,
        operator_id: str = Depends(require_admin_operator),
    ) -> Skill:
        async with session_scope() as session:
            return await SkillService(session).set_skill_trust_level(skill_id, trust_level, operator_id)
