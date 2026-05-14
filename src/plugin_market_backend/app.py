"""FastAPI application for the plugin market backend."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlencode, urlparse

from fastapi import Depends, FastAPI, Header, Query, Request, Response, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from plugin_market_backend.auth import require_author_token
from plugin_market_backend.config import get_settings
from plugin_market_backend.database import configure_database, init_database, session_scope
from plugin_market_backend.enums import PluginStatus, ReviewAction, TrustLevel, VersionStatus
from plugin_market_backend.errors import ApiError, api_error_handler, validation_error_handler
from plugin_market_backend.github import verify_github_signature
from plugin_market_backend.github_oauth import exchange_oauth_code
from plugin_market_backend.schemas import (
    AdminDashboard,
    AuthStatus,
    Author,
    Comment,
    CommentCreate,
    CommentListResponse,
    CommunitySnapshot,
    InstallInfo,
    LikeResponse,
    MarketStats,
    Plugin,
    PluginCreate,
    PluginGovernanceSnapshot,
    PluginListResponse,
    PluginUpdate,
    PluginVersion,
    PluginVersionCreate,
    RatingRequest,
    RatingSummary,
    ReviewDecision,
    ReviewRecord,
    TaxonomyResponse,
    TrendingItem,
    VersionListResponse,
    VersionSyncRequest,
    WebhookResponse,
)
from plugin_market_backend.seed import seed_rich_demo
from plugin_market_backend.service import MarketService
from plugin_market_backend.session_auth import (
    author_schema,
    clear_browser_session,
    consume_oauth_state,
    create_browser_session,
    create_oauth_state,
    current_author_from_request,
    require_browser_admin,
    require_browser_author,
    upsert_github_author,
)


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncGenerator[None, None]:
    """Configure database resources on application startup."""

    settings = get_settings()
    db_path = settings.database_path
    if db_path is not None:
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    configure_database(settings.database_url)
    if settings.create_tables_on_startup:
        await init_database()
    if settings.seed_demo_data:
        async with session_scope() as session:
            await seed_rich_demo(session)
    yield


app = FastAPI(
    title="Neo-MoFox Plugin Market API",
    description="Persistent plugin market index and governance backend.",
    version="0.1.0",
    lifespan=lifespan,
)
app.add_exception_handler(ApiError, api_error_handler)
app.add_exception_handler(RequestValidationError, validation_error_handler)

STATIC_DIR = Path(__file__).resolve().parent / "static"
SERVER_STARTED_AT = datetime.now(timezone.utc)
app.mount("/assets", StaticFiles(directory=STATIC_DIR), name="assets")


def frontend_file(name: str = "index.html") -> FileResponse:
    """Return a static frontend file."""

    return FileResponse(STATIC_DIR / name)


async def require_admin_operator(request: Request, authorization: str | None = Header(default=None)) -> str:
    """Accept either the legacy admin token or a GitHub admin browser session."""

    settings = get_settings()
    if authorization == f"Bearer {settings.admin_token}":
        return "mock-admin"
    if authorization:
        raise ApiError(403, "FORBIDDEN", "Admin token is invalid.")
    return await require_browser_admin(request)


def ensure_same_origin_browser_write(request: Request) -> None:
    """Reject cross-origin browser writes for cookie-authenticated endpoints."""

    source = request.headers.get("origin") or request.headers.get("referer")
    if not source:
        return
    parsed = urlparse(source)
    if not parsed.scheme or not parsed.netloc:
        raise ApiError(403, "FORBIDDEN", "Browser request origin is invalid.")
    expected_origin = f"{request.url.scheme}://{request.url.netloc}"
    request_origin = f"{parsed.scheme}://{parsed.netloc}"
    allowed_origins = {expected_origin, *get_settings().cors_origins}
    if request_origin not in allowed_origins:
        raise ApiError(403, "FORBIDDEN", "Cross-origin browser writes are not allowed.")


@app.get("/", include_in_schema=False)
async def marketplace_page() -> FileResponse:
    return frontend_file("index.html")


@app.get("/admin", include_in_schema=False)
async def admin_page() -> FileResponse:
    return frontend_file("index.html")


@app.get("/me", include_in_schema=False)
async def me_page() -> FileResponse:
    return frontend_file("index.html")


@app.get("/plugin/{plugin_id}", include_in_schema=False)
async def plugin_page(plugin_id: str) -> FileResponse:  # noqa: ARG001
    """Serve the SPA for direct plugin detail URLs."""

    return frontend_file("index.html")


@app.get("/author/{author_id}", include_in_schema=False)
async def author_page(author_id: str) -> FileResponse:  # noqa: ARG001
    """Serve the SPA for direct author profile URLs."""

    return frontend_file("index.html")


@app.get("/api/v1/brand")
async def brand_assets() -> dict[str, str | None]:
    """Return optional brand assets available to the frontend."""

    logo_path = STATIC_DIR / "logo.png"
    return {"logo_url": "/assets/logo.png" if logo_path.exists() else None}


@app.get("/health")
async def health() -> dict[str, str]:
    """Return process health."""

    return {"status": "ok", "service": "plugin-market-backend"}


@app.get("/ready")
async def ready() -> dict[str, str]:
    """Return readiness after database startup completed."""

    async with session_scope():
        return {"status": "ready", "database": "ok"}


@app.get("/api/v1/plugins", response_model=PluginListResponse)
async def list_plugins(
    request: Request,
    q: str | None = Query(default=None),
    status: PluginStatus | None = Query(default=None),
    category: str | None = Query(default=None),
    tag: str | None = Query(default=None),
    trust_level: TrustLevel | None = Query(default=None),
    sort: str = Query(default="updated"),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
) -> PluginListResponse:
    """List market plugins."""

    viewer = await current_author_from_request(request)
    viewer_id = viewer.author_id if viewer else None
    async with session_scope() as session:
        items, total = await MarketService(session).list_public_plugins(
            query=q,
            status=status,
            category=category,
            tag=tag,
            trust_level=trust_level,
            sort=sort,
            offset=offset,
            limit=limit,
            viewer_id=viewer_id,
        )
        return PluginListResponse(items=items, total=total)


@app.get("/api/v1/market/featured")
async def featured_plugins(request: Request, limit: int = Query(default=8, ge=1, le=24)) -> dict[str, list[Plugin]]:
    """Return marketplace landing sections."""

    viewer = await current_author_from_request(request)
    viewer_id = viewer.author_id if viewer else None
    async with session_scope() as session:
        return await MarketService(session).featured_plugins(limit=limit, viewer_id=viewer_id)


@app.get("/api/v1/market/trending-authors", response_model=list[TrendingItem])
async def trending_authors(limit: int = Query(default=8, ge=1, le=24)) -> list[TrendingItem]:
    """Return trending plugin authors by engagement."""

    async with session_scope() as session:
        return await MarketService(session).trending_authors(limit=limit)


@app.get("/api/v1/market/stats", response_model=MarketStats)
async def public_market_stats() -> MarketStats:
    """Return public market counters for the landing page."""

    async with session_scope() as session:
        return await MarketService(session).stats()


@app.get("/api/v1/plugins/{plugin_id}", response_model=Plugin)
async def get_plugin(plugin_id: str, request: Request) -> Plugin:
    """Return plugin details."""

    viewer = await current_author_from_request(request)
    viewer_id = viewer.author_id if viewer else None
    async with session_scope() as session:
        return await MarketService(session).get_plugin(plugin_id, viewer_id)


@app.get("/api/v1/plugins/{plugin_id}/community", response_model=CommunitySnapshot)
async def get_plugin_community(plugin_id: str, request: Request) -> CommunitySnapshot:
    """Return a combined snapshot used by the detail page."""

    viewer = await current_author_from_request(request)
    viewer_id = viewer.author_id if viewer else None
    async with session_scope() as session:
        service = MarketService(session)
        plugin = await service.get_plugin(plugin_id, viewer_id)
        rating = await service.rating_summary(plugin_id, viewer_id)
        comments, _ = await service.list_comments(plugin_id, limit=10)
        return CommunitySnapshot(plugin=plugin, rating=rating, recent_comments=comments)


@app.get("/api/v1/plugins/{plugin_id}/rating", response_model=RatingSummary)
async def get_rating_summary(plugin_id: str, request: Request) -> RatingSummary:
    """Return rating aggregate and viewer score."""

    viewer = await current_author_from_request(request)
    viewer_id = viewer.author_id if viewer else None
    async with session_scope() as session:
        return await MarketService(session).rating_summary(plugin_id, viewer_id)


@app.post("/api/v1/plugins/{plugin_id}/rating", response_model=RatingSummary)
async def rate_plugin(plugin_id: str, payload: RatingRequest, request: Request, viewer_id: str = Depends(require_browser_author)) -> RatingSummary:
    """Submit or update the viewer's rating."""

    ensure_same_origin_browser_write(request)
    async with session_scope() as session:
        return await MarketService(session).rate_plugin(plugin_id, viewer_id, payload.score)


@app.delete("/api/v1/plugins/{plugin_id}/rating", response_model=RatingSummary)
async def clear_plugin_rating(plugin_id: str, request: Request, viewer_id: str = Depends(require_browser_author)) -> RatingSummary:
    """Remove the viewer's rating."""

    ensure_same_origin_browser_write(request)
    async with session_scope() as session:
        return await MarketService(session).clear_rating(plugin_id, viewer_id)


@app.post("/api/v1/plugins/{plugin_id}/like", response_model=LikeResponse)
async def toggle_plugin_like(plugin_id: str, request: Request, viewer_id: str = Depends(require_browser_author)) -> LikeResponse:
    """Toggle the viewer's like on a plugin."""

    ensure_same_origin_browser_write(request)
    async with session_scope() as session:
        return await MarketService(session).toggle_like(plugin_id, viewer_id)


@app.get("/api/v1/plugins/{plugin_id}/comments", response_model=CommentListResponse)
async def list_plugin_comments(
    plugin_id: str,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
) -> CommentListResponse:
    """List comments for a plugin."""

    async with session_scope() as session:
        items, total = await MarketService(session).list_comments(plugin_id, offset=offset, limit=limit)
        return CommentListResponse(items=items, total=total)


@app.post("/api/v1/plugins/{plugin_id}/comments", response_model=Comment)
async def add_plugin_comment(plugin_id: str, payload: CommentCreate, request: Request, viewer_id: str = Depends(require_browser_author)) -> Comment:
    """Submit a new comment."""

    ensure_same_origin_browser_write(request)
    async with session_scope() as session:
        return await MarketService(session).add_comment(plugin_id, viewer_id, payload.content, payload.parent_id)


@app.delete("/api/v1/plugins/{plugin_id}/comments/{comment_id}")
async def delete_plugin_comment(plugin_id: str, comment_id: int, request: Request) -> dict[str, bool]:
    """Delete a comment owned by the viewer or by an admin."""

    ensure_same_origin_browser_write(request)
    author = await current_author_from_request(request)
    if author is None:
        raise ApiError(401, "UNAUTHORIZED", "GitHub login is required.")
    async with session_scope() as session:
        await MarketService(session).delete_comment(plugin_id, comment_id, author.author_id, bool(author.is_admin))
    return {"ok": True}


@app.post("/api/v1/plugins/{plugin_id}/install-record", response_model=PluginVersion)
async def record_install(
    plugin_id: str,
    version: str | None = Query(default=None),
) -> PluginVersion:
    """Increment the download counter when a client installs a version."""

    async with session_scope() as session:
        return await MarketService(session).record_install(plugin_id, version)


@app.get("/api/v1/plugins/{plugin_id}/versions", response_model=VersionListResponse)
async def list_versions(plugin_id: str) -> VersionListResponse:
    """List versions for a plugin."""

    async with session_scope() as session:
        items = await MarketService(session).list_versions(plugin_id)
        return VersionListResponse(items=items, total=len(items))


@app.get("/api/v1/plugins/{plugin_id}/versions/{version}", response_model=PluginVersion)
async def get_version(plugin_id: str, version: str) -> PluginVersion:
    """Return a plugin version."""

    async with session_scope() as session:
        return await MarketService(session).get_version(plugin_id, version)


@app.get("/api/v1/plugins/{plugin_id}/recommended-version", response_model=PluginVersion)
async def get_recommended_version(
    plugin_id: str,
    host_version: str | None = Query(default=None),
    plugin_api_version: str | None = Query(default=None),
    platform: str | None = Query(default=None),
    include_prerelease: bool = Query(default=False),
) -> PluginVersion:
    """Return the recommended installable version."""

    async with session_scope() as session:
        return await MarketService(session).get_recommended_version(
            plugin_id,
            host_version=host_version,
            plugin_api_version=plugin_api_version,
            platform=platform,
            include_prerelease=include_prerelease,
        )


@app.get("/api/v1/plugins/{plugin_id}/install", response_model=InstallInfo)
async def get_install_info(
    plugin_id: str,
    host_version: str | None = Query(default=None),
    plugin_api_version: str | None = Query(default=None),
    platform: str | None = Query(default=None),
) -> InstallInfo:
    """Return installable plugin and version metadata."""

    async with session_scope() as session:
        service = MarketService(session)
        plugin = await service.get_plugin(plugin_id)
        version = await service.get_recommended_version(plugin_id, host_version=host_version, plugin_api_version=plugin_api_version, platform=platform)
        return InstallInfo(plugin=plugin, version=version)


@app.get("/api/v1/categories", response_model=TaxonomyResponse)
async def list_categories() -> TaxonomyResponse:
    """Return known categories."""

    async with session_scope() as session:
        return TaxonomyResponse(items=await MarketService(session).categories())


@app.get("/api/v1/tags", response_model=TaxonomyResponse)
async def list_tags() -> TaxonomyResponse:
    """Return known tags."""

    async with session_scope() as session:
        return TaxonomyResponse(items=await MarketService(session).tags())


@app.get("/api/v1/auth/github/login", include_in_schema=False)
async def github_login(redirect_to: str = Query(default="/")) -> RedirectResponse:
    """Start GitHub OAuth login."""

    settings = get_settings()
    if not settings.github_oauth_client_id:
        raise ApiError(503, "GITHUB_OAUTH_NOT_CONFIGURED", "GitHub OAuth is not configured.")
    state = await create_oauth_state(redirect_to)
    query = {
        "client_id": settings.github_oauth_client_id,
        "state": state,
        "scope": "read:user",
    }
    if settings.github_oauth_redirect_uri:
        query["redirect_uri"] = settings.github_oauth_redirect_uri
    return RedirectResponse(f"{settings.github_login_base_url}/authorize?{urlencode(query)}")


@app.get("/api/v1/auth/github/callback", include_in_schema=False)
async def github_callback(request: Request, code: str, state: str) -> RedirectResponse:
    """Finish GitHub OAuth login."""

    redirect_to = await consume_oauth_state(state)
    token = await exchange_oauth_code(get_settings(), code)
    author = await upsert_github_author(token)
    session_id = await create_browser_session(author.author_id, token)
    response = RedirectResponse(redirect_to or "/")
    response.set_cookie(
        get_settings().session_cookie_name,
        session_id,
        httponly=True,
        samesite="lax",
        secure=request.url.scheme == "https",
        path="/",
        max_age=14 * 24 * 3600,
    )
    return response


@app.post("/api/v1/auth/logout")
async def logout(request: Request) -> JSONResponse:
    """Clear the current browser session."""

    ensure_same_origin_browser_write(request)
    cookie_name = get_settings().session_cookie_name
    await clear_browser_session(request.cookies.get(cookie_name))
    response = JSONResponse({"ok": True})
    response.delete_cookie(cookie_name, path="/", samesite="lax", secure=request.url.scheme == "https", httponly=True)
    return response


@app.get("/api/v1/me", response_model=AuthStatus)
async def current_user(request: Request) -> AuthStatus:
    """Return the current GitHub-authenticated user."""

    author = await current_author_from_request(request)
    if author is None:
        return AuthStatus(authenticated=False)
    return AuthStatus(authenticated=True, user=Author(**author_schema(author)))


@app.get("/api/v1/me/plugins", response_model=PluginListResponse)
async def my_plugins(author_id: str = Depends(require_browser_author)) -> PluginListResponse:
    """Return plugins owned or maintained by the current user."""

    async with session_scope() as session:
        items = await MarketService(session).list_owner_plugins(author_id)
        return PluginListResponse(items=items, total=len(items))


@app.get("/api/v1/me/plugins/{plugin_id}", response_model=PluginGovernanceSnapshot)
async def my_plugin_snapshot(plugin_id: str, author_id: str = Depends(require_browser_author)) -> PluginGovernanceSnapshot:
    """Return detailed governance data for one owned plugin."""

    async with session_scope() as session:
        return await MarketService(session).plugin_governance_snapshot(plugin_id, operator_id=author_id)


@app.post("/api/v1/me/plugins/{plugin_id}/versions/{version}/yank", response_model=PluginVersion)
async def my_plugin_yank_version(
    plugin_id: str,
    version: str,
    request: Request,
    decision: ReviewDecision | None = None,
    author_id: str = Depends(require_browser_author),
) -> PluginVersion:
    """Allow a logged-in owner or maintainer to yank one of their versions."""

    ensure_same_origin_browser_write(request)
    async with session_scope() as session:
        return await MarketService(session).yank_version(plugin_id, version, author_id, decision.reason if decision else None)


@app.delete("/api/v1/me/plugins/{plugin_id}", status_code=status.HTTP_204_NO_CONTENT)
async def my_plugin_delete(plugin_id: str, request: Request, author_id: str = Depends(require_browser_author)) -> Response:
    """Allow a logged-in owner or maintainer to delete one of their plugins."""

    ensure_same_origin_browser_write(request)
    async with session_scope() as session:
        await MarketService(session).delete_owner_plugin(plugin_id, author_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@app.post("/api/v1/plugins", response_model=Plugin)
async def register_plugin(payload: PluginCreate, operator_id: str = Depends(require_author_token)) -> Plugin:
    """Register a plugin from CLI."""

    async with session_scope() as session:
        return await MarketService(session).register_plugin(payload, owner_id=operator_id)


@app.put("/api/v1/plugins/{plugin_id}", response_model=Plugin)
async def update_plugin(plugin_id: str, payload: PluginUpdate, operator_id: str = Depends(require_author_token)) -> Plugin:
    """Update plugin metadata from CLI."""

    async with session_scope() as session:
        return await MarketService(session).update_plugin(plugin_id, payload, operator_id)


@app.post("/api/v1/plugins/{plugin_id}/versions", response_model=PluginVersion)
async def submit_version(plugin_id: str, payload: PluginVersionCreate, operator_id: str = Depends(require_author_token)) -> PluginVersion:
    """Submit a version from CLI."""

    async with session_scope() as session:
        return await MarketService(session).submit_version(plugin_id, payload, operator_id)


@app.post("/api/v1/plugins/{plugin_id}/sync", response_model=PluginVersion)
async def sync_version(plugin_id: str, payload: VersionSyncRequest, operator_id: str = Depends(require_author_token)) -> PluginVersion:
    """Sync version metadata from CLI."""

    async with session_scope() as session:
        return await MarketService(session).sync_version(plugin_id, payload, operator_id)


@app.post("/api/v1/plugins/{plugin_id}/versions/{version}/yank", response_model=PluginVersion)
async def author_yank_version(plugin_id: str, version: str, decision: ReviewDecision | None = None, operator_id: str = Depends(require_author_token)) -> PluginVersion:
    """Yank a version as the plugin owner."""

    async with session_scope() as session:
        return await MarketService(session).yank_version(plugin_id, version, operator_id, decision.reason if decision else None)


@app.get("/api/v1/plugins/{plugin_id}/status")
async def get_plugin_status(plugin_id: str, _: str = Depends(require_author_token)):
    """Return plugin publication and sync status."""

    async with session_scope() as session:
        return await MarketService(session).get_status(plugin_id)


@app.get("/api/v1/admin/reviews", response_model=list[ReviewRecord])
async def list_reviews(_: str = Depends(require_admin_operator)) -> list[ReviewRecord]:
    """List review records."""

    async with session_scope() as session:
        return await MarketService(session).list_reviews()


@app.get("/api/v1/admin/plugins", response_model=PluginListResponse)
async def list_admin_plugins(
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=200),
    _: str = Depends(require_admin_operator),
) -> PluginListResponse:
    """List all plugins for the management console."""

    async with session_scope() as session:
        items, total = await MarketService(session).list_admin_plugins(offset=offset, limit=limit)
        return PluginListResponse(items=items, total=total)


@app.get("/api/v1/admin/plugins/{plugin_id}", response_model=PluginGovernanceSnapshot)
async def admin_plugin_snapshot(plugin_id: str, _: str = Depends(require_admin_operator)) -> PluginGovernanceSnapshot:
    """Return detailed governance data for one plugin."""

    async with session_scope() as session:
        return await MarketService(session).plugin_governance_snapshot(plugin_id)


@app.get("/api/v1/admin/dashboard", response_model=AdminDashboard)
async def admin_dashboard(_: str = Depends(require_admin_operator)) -> AdminDashboard:
    """Return a richer dashboard payload for the admin console."""

    async with session_scope() as session:
        return await MarketService(session).admin_dashboard()


@app.get("/api/v1/admin/system")
async def admin_system_status(_: str = Depends(require_admin_operator)) -> dict[str, Any]:
    """Return server status for the management console."""

    settings = get_settings()
    async with session_scope() as session:
        stats = await MarketService(session).stats()
    return {
        "status": "ok",
        "environment": settings.env,
        "database": "ok",
        "database_path": str(settings.database_path) if settings.database_path is not None else None,
        "github_oauth_configured": bool(settings.github_oauth_client_id and settings.github_oauth_client_secret),
        "github_webhook_configured": bool(settings.github_webhook_secret),
        "review_required": settings.require_review,
        "started_at": SERVER_STARTED_AT,
        "uptime_seconds": int((datetime.now(timezone.utc) - SERVER_STARTED_AT).total_seconds()),
        "stats": stats,
    }


@app.get("/api/v1/admin/stats", response_model=MarketStats)
async def admin_stats(_: str = Depends(require_admin_operator)) -> MarketStats:
    """Return admin stats."""

    async with session_scope() as session:
        return await MarketService(session).stats()


@app.post("/api/v1/admin/plugins/{plugin_id}/reject", response_model=Plugin)
async def reject_plugin(plugin_id: str, decision: ReviewDecision | None = None, operator_id: str = Depends(require_admin_operator)) -> Plugin:
    """Reject a plugin back to draft."""

    async with session_scope() as session:
        return await MarketService(session).set_plugin_status(plugin_id, PluginStatus.DRAFT, ReviewAction.REJECT_PLUGIN, operator_id, decision.reason if decision else None)


@app.post("/api/v1/admin/plugins/{plugin_id}/publish", response_model=Plugin)
async def publish_plugin(plugin_id: str, decision: ReviewDecision | None = None, operator_id: str = Depends(require_admin_operator)) -> Plugin:
    """Publish or re-list a plugin."""

    async with session_scope() as session:
        return await MarketService(session).set_plugin_status(plugin_id, PluginStatus.PUBLISHED, ReviewAction.APPROVE_PLUGIN, operator_id, decision.reason if decision else None)


@app.post("/api/v1/admin/plugins/{plugin_id}/trust-level/{trust_level}", response_model=Plugin)
async def set_plugin_trust_level(
    plugin_id: str,
    trust_level: TrustLevel,
    decision: ReviewDecision | None = None,
    operator_id: str = Depends(require_admin_operator),
) -> Plugin:
    """Set the trust badge shown for a plugin."""

    async with session_scope() as session:
        return await MarketService(session).set_plugin_trust_level(plugin_id, trust_level, operator_id, decision.reason if decision else None)


@app.post("/api/v1/admin/plugins/{plugin_id}/block", response_model=Plugin)
async def block_plugin(plugin_id: str, decision: ReviewDecision | None = None, operator_id: str = Depends(require_admin_operator)) -> Plugin:
    """Block a plugin."""

    async with session_scope() as session:
        return await MarketService(session).set_plugin_status(plugin_id, PluginStatus.BLOCKED, ReviewAction.BLOCK_PLUGIN, operator_id, decision.reason if decision else None)


@app.post("/api/v1/admin/plugins/{plugin_id}/deprecate", response_model=Plugin)
async def deprecate_plugin(plugin_id: str, decision: ReviewDecision | None = None, operator_id: str = Depends(require_admin_operator)) -> Plugin:
    """Deprecate a plugin."""

    async with session_scope() as session:
        return await MarketService(session).set_plugin_status(plugin_id, PluginStatus.DEPRECATED, ReviewAction.DEPRECATE_PLUGIN, operator_id, decision.reason if decision else None)


@app.delete("/api/v1/admin/plugins/{plugin_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_plugin(plugin_id: str, _: str = Depends(require_admin_operator)) -> Response:
    """Delete a plugin and all associated market records."""

    async with session_scope() as session:
        await MarketService(session).delete_plugin(plugin_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@app.post("/api/v1/admin/plugins/{plugin_id}/versions/{version}/reject", response_model=PluginVersion)
async def reject_version(plugin_id: str, version: str, decision: ReviewDecision | None = None, operator_id: str = Depends(require_admin_operator)) -> PluginVersion:
    """Reject a plugin version back to submitted state."""

    async with session_scope() as session:
        return await MarketService(session).set_version_status(plugin_id, version, VersionStatus.SUBMITTED, ReviewAction.REJECT_VERSION, operator_id, decision.reason if decision else None)


@app.post("/api/v1/admin/plugins/{plugin_id}/versions/{version}/publish", response_model=PluginVersion)
async def publish_version(plugin_id: str, version: str, decision: ReviewDecision | None = None, operator_id: str = Depends(require_admin_operator)) -> PluginVersion:
    """Publish or restore a plugin version."""

    async with session_scope() as session:
        return await MarketService(session).set_version_status(
            plugin_id,
            version,
            VersionStatus.PUBLISHED,
            ReviewAction.APPROVE_VERSION,
            operator_id,
            decision.reason if decision else None,
            is_yanked=False,
        )


@app.post("/api/v1/admin/plugins/{plugin_id}/versions/{version}/yank", response_model=PluginVersion)
async def yank_version(plugin_id: str, version: str, decision: ReviewDecision | None = None, operator_id: str = Depends(require_admin_operator)) -> PluginVersion:
    """Yank a plugin version."""

    async with session_scope() as session:
        return await MarketService(session).set_version_status(plugin_id, version, VersionStatus.YANKED, ReviewAction.YANK_VERSION, operator_id, decision.reason if decision else None, is_yanked=True)


@app.post("/api/v1/admin/plugins/{plugin_id}/versions/{version}/block", response_model=PluginVersion)
async def block_version(plugin_id: str, version: str, decision: ReviewDecision | None = None, operator_id: str = Depends(require_admin_operator)) -> PluginVersion:
    """Block a plugin version."""

    async with session_scope() as session:
        return await MarketService(session).set_version_status(plugin_id, version, VersionStatus.BLOCKED, ReviewAction.BLOCK_VERSION, operator_id, decision.reason if decision else None)


@app.post("/api/v1/github/webhooks", response_model=WebhookResponse)
async def github_webhook(
    request: Request,
    x_github_event: str = Header(default="unknown"),
    x_github_delivery: str | None = Header(default=None),
    x_hub_signature_256: str | None = Header(default=None),
) -> WebhookResponse:
    """Accept and audit GitHub webhook events."""

    body = await request.body()
    verify_github_signature(get_settings().github_webhook_secret, body, x_hub_signature_256)
    payload: dict[str, Any] = await request.json() if body else {}
    event_id = x_github_delivery or f"manual-{x_github_event}"
    async with session_scope() as session:
        await MarketService(session).record_webhook(event_id, x_github_event, payload.get("action"), payload)
    return WebhookResponse(accepted=True, event_id=event_id)
