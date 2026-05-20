"""FastAPI application for the plugin market backend."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from typing import Any
from urllib.parse import urlencode, urlparse

from fastapi import Depends, FastAPI, File, Header, Query, Request, Response, UploadFile, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import func, select

from plugin_market_backend.auth import require_author_token
from plugin_market_backend.caching import aget_or_set, cache_bus
from plugin_market_backend.config import get_settings
from plugin_market_backend.content import PLUGIN_MEDIA_DIR, ensure_plugin_media_dirs
from plugin_market_backend.database import configure_database, init_database, session_scope
from plugin_market_backend.enums import PluginStatus, ReviewAction, TrustLevel, VersionStatus
from plugin_market_backend.errors import ApiError, api_error_handler, validation_error_handler
from plugin_market_backend.github import verify_github_signature
from plugin_market_backend.github_oauth import exchange_oauth_code
from plugin_market_backend.orm import InboxMessageORM, PluginORM
from plugin_market_backend.schemas import (
    AdminDashboard,
    AnnouncementCreate,
    AnnouncementDismissResponse,
    AnnouncementDTO,
    AnnouncementListResponse,
    AnnouncementUpdate,
    AuthStatus,
    Author,
    AuthorProfile,
    AuthorProfileUpdate,
    BulkActionRequest,
    BulkActionResult,
    Comment,
    CommentCreate,
    CommentListResponse,
    CommunitySnapshot,
    CurationEntryCreate,
    CurationEntryDTO,
    CurationEntryListResponse,
    CurationEntryUpdate,
    CurationOrderUpdate,
    InstallInfo,
    InboxMessageListResponse,
    InboxUnreadCount,
    LikeResponse,
    MarketHome,
    MarketStats,
    MentionCandidate,
    PinCreate,
    PinUpdate,
    Plugin,
    PluginCreate,
    PluginDependenciesResponse,
    PluginGovernanceSnapshot,
    PluginListResponse,
    PluginMetadataPatch,
    PluginReadmeResponse,
    PluginUpdate,
    PluginVersion,
    PluginVersionCreate,
    PinnedPluginItem,
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
from plugin_market_backend.services import AnnouncementsService, BulkOpsService, CurationService, InboxService, InlineEditService, ProfileService
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


def _first_proxy_header_value(value: str | None) -> str | None:
    """Return the first value from a comma-separated proxy header."""

    if not value:
        return None
    first = value.split(",", 1)[0].strip()
    return first or None


def _forwarded_header_value(value: str | None, key: str) -> str | None:
    """Extract one field from the RFC 7239 Forwarded header."""

    first = _first_proxy_header_value(value)
    if not first:
        return None
    for part in first.split(";"):
        name, _, raw = part.strip().partition("=")
        if name.lower() != key:
            continue
        cleaned = raw.strip().strip('"')
        return cleaned or None
    return None


def _normalize_origin(value: str) -> str:
    """Normalize origins for reliable comparison."""

    parsed = urlparse(value)
    if parsed.scheme and parsed.netloc:
        return f"{parsed.scheme.lower()}://{parsed.netloc.lower()}"
    return value.rstrip("/").lower()


def _expected_request_origin(request: Request) -> str:
    """Reconstruct the browser-facing origin, preferring proxy headers."""

    forwarded = request.headers.get("forwarded")
    scheme = (
        _first_proxy_header_value(request.headers.get("x-forwarded-proto"))
        or _forwarded_header_value(forwarded, "proto")
        or request.url.scheme
    )
    host = (
        _first_proxy_header_value(request.headers.get("x-forwarded-host"))
        or _forwarded_header_value(forwarded, "host")
        or request.headers.get("host")
        or request.url.netloc
    )
    return _normalize_origin(f"{scheme}://{host}")


def _stable_etag(payload: Any) -> str:
    """Return a deterministic ETag for a JSON-serializable payload."""

    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return f'"{hashlib.sha256(encoded).hexdigest()}"'


async def _viewer_owns_plugin(author_id: str | None) -> bool:
    if not author_id:
        return False
    async with session_scope() as session:
        count = await session.scalar(
            select(func.count()).select_from(PluginORM).where(PluginORM.owner_id == author_id)
        )
        return bool(count)


async def _load_home_sections(viewer_id: str | None) -> dict[str, list[Plugin]]:
    async with session_scope() as session:
        return await MarketService(session).featured_plugins(limit=6, viewer_id=viewer_id)


async def _load_home_trending_authors() -> list[TrendingItem]:
    async with session_scope() as session:
        return await MarketService(session).trending_authors(limit=6)


async def _load_home_categories_preview(viewer_id: str | None) -> dict[str, list[Plugin]]:
    async with session_scope() as session:
        return await MarketService(session).home_categories_preview(viewer_id=viewer_id)


async def _load_home_stats() -> MarketStats:
    async with session_scope() as session:
        return await MarketService(session).stats()


async def _load_home_showcase(viewer: Any, viewer_has_plugin: bool) -> list[Any]:
    async with session_scope() as session:
        return await MarketService(session).home_showcase(viewer, viewer_has_plugin=viewer_has_plugin)


async def _load_home_announcements(viewer: Any, viewer_has_plugin: bool) -> list[Any]:
    async with session_scope() as session:
        return await AnnouncementsService(session).list_active(viewer, viewer_has_plugin=viewer_has_plugin)


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
ensure_plugin_media_dirs()
app.mount("/assets", StaticFiles(directory=STATIC_DIR / "assets"), name="assets")
app.mount("/plugin-media", StaticFiles(directory=PLUGIN_MEDIA_DIR), name="plugin-media")


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
    expected_origin = _expected_request_origin(request)
    request_origin = _normalize_origin(f"{parsed.scheme}://{parsed.netloc}")
    allowed_origins = {
        expected_origin,
        _normalize_origin(f"{request.url.scheme}://{request.url.netloc}"),
        *(_normalize_origin(item) for item in get_settings().cors_origins),
    }
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


@app.get("/status", include_in_schema=False)
async def status_page() -> FileResponse:
    """Serve the SPA service-status dashboard."""

    return frontend_file("index.html")


@app.get("/plugin/{plugin_id}", include_in_schema=False)
async def plugin_page(plugin_id: str) -> FileResponse:  # noqa: ARG001
    """Serve the SPA for direct plugin detail URLs."""

    return frontend_file("index.html")


@app.get("/author/{author_id}", include_in_schema=False)
async def author_page(author_id: str) -> FileResponse:  # noqa: ARG001
    """Serve the SPA for direct author profile URLs."""

    return frontend_file("index.html")


@app.get("/logo.png", include_in_schema=False)
async def logo_file() -> FileResponse:
    """Serve the market logo used by the SPA shell."""

    return frontend_file("logo.png")


@app.get("/api/v1/brand")
async def brand_assets() -> dict[str, str | None]:
    """Return optional brand assets available to the frontend."""

    logo_path = STATIC_DIR / "logo.png"
    return {"logo_url": "/logo.png" if logo_path.exists() else None}


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


@app.get("/api/v1/market/home", response_model=MarketHome)
async def market_home(request: Request) -> Response | MarketHome:
    """Return the cached market home aggregate with ETag support."""

    viewer = await current_author_from_request(request)
    viewer_id = viewer.author_id if viewer else None
    viewer_has_plugin = await _viewer_owns_plugin(viewer_id)
    cache_key = ("home", viewer_id or "anonymous")

    async def loader() -> dict[str, Any]:
        sections, trending, categories_preview, stats, showcase, announcements = await asyncio.gather(
            _load_home_sections(viewer_id),
            _load_home_trending_authors(),
            _load_home_categories_preview(viewer_id),
            _load_home_stats(),
            _load_home_showcase(viewer, viewer_has_plugin),
            _load_home_announcements(viewer, viewer_has_plugin),
        )
        body = MarketHome(
            showcase=showcase,
            featured_plugins=sections.get("ranking", []),
            trending_authors=trending,
            latest=sections.get("latest", []),
            top_rated=sections.get("top_rated", []),
            categories_preview=categories_preview,
            stats=stats,
            active_announcements=announcements,
        )
        payload = body.model_dump(mode="json")
        return {"body": payload, "etag": _stable_etag(payload)}

    cached = await aget_or_set(cache_key, 60, loader)
    etag = cached["etag"]
    headers = {"Cache-Control": "private, max-age=60", "ETag": etag}
    if request.headers.get("if-none-match") == etag:
        return Response(status_code=status.HTTP_304_NOT_MODIFIED, headers=headers)
    return JSONResponse(content=cached["body"], headers=headers)


@app.get("/api/v1/plugins/{plugin_id}", response_model=Plugin)
async def get_plugin(plugin_id: str, request: Request) -> Plugin:
    """Return plugin details."""

    viewer = await current_author_from_request(request)
    viewer_id = viewer.author_id if viewer else None
    async with session_scope() as session:
        return await MarketService(session).get_plugin(plugin_id, viewer_id)


@app.get("/api/v1/plugins/{plugin_id}/readme", response_model=PluginReadmeResponse)
async def get_plugin_readme(plugin_id: str) -> PluginReadmeResponse:
    """Return rendered README content for the plugin detail view."""

    async with session_scope() as session:
        return await MarketService(session).get_plugin_readme(plugin_id)


@app.get("/api/v1/plugins/{plugin_id}/dependencies", response_model=PluginDependenciesResponse)
async def get_plugin_dependencies(plugin_id: str) -> PluginDependenciesResponse:
    """Return resolved plugin dependency data for the plugin detail view."""

    async with session_scope() as session:
        return await MarketService(session).get_plugin_dependencies(plugin_id)


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


@app.get("/api/v1/me/profile", response_model=AuthorProfile)
async def my_profile(author_id: str = Depends(require_browser_author)) -> AuthorProfile:
    """Return the current browser author's public profile fields."""

    async with session_scope() as session:
        return await ProfileService(session).get_profile(author_id)


@app.put("/api/v1/me/profile", response_model=AuthorProfile)
async def update_my_profile(
    payload: AuthorProfileUpdate,
    request: Request,
    author_id: str = Depends(require_browser_author),
) -> AuthorProfile:
    """Update the current browser author's bio / background."""

    ensure_same_origin_browser_write(request)
    async with session_scope() as session:
        return await ProfileService(session).update_profile(
            author_id,
            bio=payload.bio,
            background_image_url=(str(payload.background_image_url) if payload.background_image_url is not None else None),
        )


@app.post("/api/v1/me/profile/background", response_model=AuthorProfile)
async def upload_my_background(
    request: Request,
    file: UploadFile = File(...),
    author_id: str = Depends(require_browser_author),
) -> AuthorProfile:
    """Accept a multipart upload as the new personal-space background image."""

    ensure_same_origin_browser_write(request)
    raw = await file.read()
    async with session_scope() as session:
        return await ProfileService(session).set_background_from_upload(author_id, raw)


@app.post("/api/v1/me/plugins/{plugin_id}/icon", response_model=Plugin)
async def upload_my_plugin_icon(
    plugin_id: str,
    request: Request,
    file: UploadFile = File(...),
    author_id: str = Depends(require_browser_author),
) -> Plugin:
    """Accept a multipart upload as the plugin's new icon (owner / maintainer / admin only)."""

    ensure_same_origin_browser_write(request)
    raw = await file.read()
    async with session_scope() as session:
        from plugin_market_backend.content import store_plugin_icon_from_bytes
        from plugin_market_backend.services import assert_can_edit_plugin_metadata

        await assert_can_edit_plugin_metadata(session, plugin_id, author_id)
        new_url = store_plugin_icon_from_bytes(plugin_id, raw)
        await InlineEditService(session).patch_metadata(
            author_id, plugin_id, {"icon_url": new_url}
        )
        cache_bus.invalidate("home")
        return await MarketService(session).get_plugin(plugin_id)


@app.get("/api/v1/authors/{author_id}/profile", response_model=AuthorProfile)
async def author_profile(author_id: str) -> AuthorProfile:
    """Return the public personal-space profile for any author."""

    async with session_scope() as session:
        return await ProfileService(session).get_profile(author_id)


@app.get("/api/v1/authors/{author_id}/pins", response_model=list[PinnedPluginItem])
async def author_pins(author_id: str) -> list[PinnedPluginItem]:
    """Return the public pinned plugins for any author."""

    async with session_scope() as session:
        return await ProfileService(session).list_pins(author_id)


@app.get("/api/v1/authors/search", response_model=list[MentionCandidate])
async def author_search(
    prefix: str = Query(min_length=1, max_length=39),
    limit: int = Query(default=8, ge=1, le=20),
) -> list[MentionCandidate]:
    """Return mention candidates for a login/display-name prefix."""

    async with session_scope() as session:
        return await MarketService(session).search_authors(prefix, limit=limit)


@app.get("/api/v1/me/pins", response_model=list[PinnedPluginItem])
async def my_pins(author_id: str = Depends(require_browser_author)) -> list[PinnedPluginItem]:
    """Return the current browser author's pinned plugins."""

    async with session_scope() as session:
        return await ProfileService(session).list_pins(author_id)


@app.post("/api/v1/me/pins", response_model=PinnedPluginItem)
async def add_my_pin(
    payload: PinCreate,
    request: Request,
    author_id: str = Depends(require_browser_author),
) -> PinnedPluginItem:
    """Add one pinned plugin for the current browser author."""

    ensure_same_origin_browser_write(request)
    async with session_scope() as session:
        return await ProfileService(session).add_pin(
            author_id,
            payload.plugin_id,
            reason=payload.pinned_reason,
        )


@app.put("/api/v1/me/pins/{plugin_id}", response_model=PinnedPluginItem)
async def update_my_pin(
    plugin_id: str,
    payload: PinUpdate,
    request: Request,
    author_id: str = Depends(require_browser_author),
) -> PinnedPluginItem:
    """Update the pinned reason for one existing pin."""

    ensure_same_origin_browser_write(request)
    async with session_scope() as session:
        return await ProfileService(session).update_pin_reason(
            author_id,
            plugin_id,
            payload.pinned_reason,
        )


@app.delete("/api/v1/me/pins/{plugin_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_my_pin(
    plugin_id: str,
    request: Request,
    author_id: str = Depends(require_browser_author),
) -> Response:
    """Remove one pin from the current browser author's personal space."""

    ensure_same_origin_browser_write(request)
    async with session_scope() as session:
        await ProfileService(session).remove_pin(author_id, plugin_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


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


@app.patch("/api/v1/me/plugins/{plugin_id}/metadata", response_model=Plugin)
async def patch_my_plugin_metadata(
    plugin_id: str,
    payload: PluginMetadataPatch,
    request: Request,
    author_id: str = Depends(require_browser_author),
) -> Plugin:
    """Allow the owner / maintainer to patch display-facing metadata inline."""

    ensure_same_origin_browser_write(request)
    async with session_scope() as session:
        await InlineEditService(session).patch_metadata(
            author_id,
            plugin_id,
            payload.model_dump(exclude_unset=True),
        )
        cache_bus.invalidate("home")
        return await MarketService(session).get_plugin(plugin_id)


@app.get("/api/v1/inbox/messages", response_model=InboxMessageListResponse)
async def inbox_messages(
    type: str | None = Query(default=None),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    author_id: str = Depends(require_browser_author),
) -> InboxMessageListResponse:
    """Return the current browser author's inbox page."""

    async with session_scope() as session:
        items, total = await InboxService(session).list_messages(
            author_id,
            type=type,
            offset=offset,
            limit=limit,
        )
        return InboxMessageListResponse(items=items, total=total)


@app.get("/api/v1/inbox/unread-count", response_model=InboxUnreadCount)
async def inbox_unread_count(author_id: str = Depends(require_browser_author)) -> InboxUnreadCount:
    """Return the current browser author's unread inbox count."""

    async with session_scope() as session:
        count = await InboxService(session).unread_count(author_id)
        return InboxUnreadCount(count=count)


@app.post("/api/v1/inbox/messages/{message_id}/read")
async def inbox_mark_read(
    message_id: int,
    request: Request,
    author_id: str = Depends(require_browser_author),
) -> dict[str, int]:
    """Mark one inbox message as read for the current browser author."""

    ensure_same_origin_browser_write(request)
    async with session_scope() as session:
        message = await session.get(InboxMessageORM, message_id)
        if message is None:
            raise ApiError(404, "INBOX_MESSAGE_NOT_FOUND", "Inbox message not found.")
        if message.recipient_id != author_id:
            raise ApiError(403, "INBOX_FORBIDDEN", "Inbox access is forbidden.")
        updated = await InboxService(session).mark_read(author_id, [message_id])
        return {"updated": updated}


@app.post("/api/v1/inbox/read-all")
async def inbox_mark_all_read(
    request: Request,
    author_id: str = Depends(require_browser_author),
) -> dict[str, int]:
    """Mark all inbox messages as read for the current browser author."""

    ensure_same_origin_browser_write(request)
    async with session_scope() as session:
        updated = await InboxService(session).mark_all_read(author_id)
        return {"updated": updated}


@app.get("/api/v1/announcements/active", response_model=list[AnnouncementDTO])
async def active_announcements(request: Request) -> list[AnnouncementDTO]:
    """Return announcements visible to the current viewer."""

    viewer = await current_author_from_request(request)
    async with session_scope() as session:
        viewer_has_plugin = False
        if viewer is not None:
            viewer_plugins = await session.scalar(
                select(func.count()).select_from(PluginORM).where(PluginORM.owner_id == viewer.author_id)
            )
            viewer_has_plugin = bool(viewer_plugins)
        return await AnnouncementsService(session).list_active(
            viewer,
            viewer_has_plugin=viewer_has_plugin,
        )


@app.post("/api/v1/announcements/{announcement_id}/dismiss", response_model=AnnouncementDismissResponse)
async def dismiss_announcement(
    announcement_id: int,
    request: Request,
    author_id: str = Depends(require_browser_author),
) -> AnnouncementDismissResponse:
    """Dismiss one announcement for the current browser author."""

    ensure_same_origin_browser_write(request)
    async with session_scope() as session:
        dismissed_id, dismiss_token = await AnnouncementsService(session).dismiss(
            announcement_id,
            author_id,
        )
        return AnnouncementDismissResponse(
            announcement_id=dismissed_id,
            dismissed=True,
            dismiss_token=dismiss_token,
        )


@app.get("/api/v1/admin/announcements", response_model=AnnouncementListResponse)
async def admin_announcements(
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    _: str = Depends(require_admin_operator),
) -> AnnouncementListResponse:
    """Return the admin announcement list."""

    async with session_scope() as session:
        items, total = await AnnouncementsService(session).admin_list(offset=offset, limit=limit)
        return AnnouncementListResponse(items=items, total=total)


@app.post("/api/v1/admin/announcements", response_model=AnnouncementDTO)
async def create_announcement(
    payload: AnnouncementCreate,
    _: Request,
    operator_id: str = Depends(require_admin_operator),
) -> AnnouncementDTO:
    """Create one announcement."""

    async with session_scope() as session:
        announcement = await AnnouncementsService(session).create(payload, operator_id)
        cache_bus.invalidate("announcements_active")
        return announcement


@app.put("/api/v1/admin/announcements/{announcement_id}", response_model=AnnouncementDTO)
async def update_announcement(
    announcement_id: int,
    payload: AnnouncementUpdate,
    _: Request,
    operator_id: str = Depends(require_admin_operator),
) -> AnnouncementDTO:
    """Update one announcement."""

    async with session_scope() as session:
        announcement = await AnnouncementsService(session).update(announcement_id, payload, operator_id)
        cache_bus.invalidate("announcements_active")
        return announcement


@app.post("/api/v1/admin/announcements/{announcement_id}/disable", response_model=AnnouncementDTO)
async def disable_announcement(
    announcement_id: int,
    _: Request,
    operator_id: str = Depends(require_admin_operator),
) -> AnnouncementDTO:
    """Disable one announcement."""

    async with session_scope() as session:
        announcement = await AnnouncementsService(session).disable(announcement_id, operator_id)
        cache_bus.invalidate("announcements_active")
        return announcement


@app.post("/api/v1/admin/announcements/{announcement_id}/resurface", response_model=AnnouncementDTO)
async def resurface_announcement(
    announcement_id: int,
    _: Request,
    operator_id: str = Depends(require_admin_operator),
) -> AnnouncementDTO:
    """Resurface one announcement by bumping its dismiss token."""

    async with session_scope() as session:
        announcement = await AnnouncementsService(session).resurface(announcement_id, operator_id)
        cache_bus.invalidate("announcements_active")
        return announcement


@app.get("/api/v1/admin/curation/entries", response_model=CurationEntryListResponse)
async def admin_curation_entries(_: str = Depends(require_admin_operator)) -> CurationEntryListResponse:
    """Return all curation entries for the admin console."""

    async with session_scope() as session:
        items = await CurationService(session).list_entries()
        return CurationEntryListResponse(items=items, total=len(items))


@app.post("/api/v1/admin/curation/entries", response_model=CurationEntryDTO)
async def create_curation_entry(
    payload: CurationEntryCreate,
    operator_id: str = Depends(require_admin_operator),
) -> CurationEntryDTO:
    """Create one curation entry."""

    async with session_scope() as session:
        entry = await CurationService(session).create(payload, operator_id)
        cache_bus.invalidate("home")
        return entry


@app.put("/api/v1/admin/curation/entries/{entry_id}", response_model=CurationEntryDTO)
async def update_curation_entry(
    entry_id: int,
    payload: CurationEntryUpdate,
    operator_id: str = Depends(require_admin_operator),
) -> CurationEntryDTO:
    """Update one curation entry."""

    async with session_scope() as session:
        entry = await CurationService(session).update(entry_id, payload, operator_id)
        cache_bus.invalidate("home")
        return entry


@app.post("/api/v1/admin/curation/entries/{entry_id}/disable", response_model=CurationEntryDTO)
async def disable_curation_entry(
    entry_id: int,
    operator_id: str = Depends(require_admin_operator),
) -> CurationEntryDTO:
    """Disable one curation entry."""

    async with session_scope() as session:
        entry = await CurationService(session).disable(entry_id, operator_id)
        cache_bus.invalidate("home")
        return entry


@app.put("/api/v1/admin/curation/order", response_model=list[CurationEntryDTO])
async def reorder_curation_entries(
    payload: CurationOrderUpdate,
    operator_id: str = Depends(require_admin_operator),
) -> list[CurationEntryDTO]:
    """Persist a new curation sort order."""

    async with session_scope() as session:
        items = await CurationService(session).reorder(payload.ids_in_order, operator_id)
        cache_bus.invalidate("home")
        return items


@app.post(
    "/api/v1/admin/plugins/bulk",
    response_model=BulkActionResult,
    status_code=status.HTTP_207_MULTI_STATUS,
)
async def bulk_apply_plugins(
    payload: BulkActionRequest,
    operator_id: str = Depends(require_admin_operator),
) -> BulkActionResult:
    """Apply one bulk governance action across multiple plugins."""

    async with session_scope() as session:
        result = await BulkOpsService(session).bulk_apply(
            operator_id,
            payload.plugin_ids,
            payload.action,
            payload.params,
        )
        cache_bus.invalidate("home")
        return result


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
