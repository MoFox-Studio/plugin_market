"""插件市场后端的 FastAPI 应用。"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager, suppress
from datetime import datetime, timezone
import hashlib
import json
import logging
from pathlib import Path
from typing import Any
from urllib.parse import urlencode, urlparse

from fastapi import Depends, FastAPI, File, Form, Header, Query, Request, Response, UploadFile, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError

from plugin_market_backend.auth import require_author_token, require_market_access_token
from plugin_market_backend.caching import aget_or_set, cache_bus
from plugin_market_backend.config import get_settings
from plugin_market_backend.content import PLUGIN_MEDIA_DIR, ensure_plugin_media_dirs, ensure_skill_dirs
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
    AccessTokenRotateResponse,
    AccessTokenStatus,
    AuthStatus,
    Author,
    AuthorFollowState,
    AuthorProfile,
    AuthorProfileUpdate,
    BulkActionRequest,
    BulkActionResult,
    CategoryPreviewSection,
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
    MarketHome,
    MarketStats,
    MachineSubscriptionListResponse,
    MyFollowItem,
    MyFollowListResponse,
    MySubscriptionItem,
    MySubscriptionListResponse,
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
    PluginSubscriptionState,
    PluginUpdate,
    PluginVersion,
    PluginVersionCreate,
    PinnedPluginItem,
    RatingRequest,
    RatingSummary,
    ReviewDecision,
    ReviewRecord,
    Skill,
    SkillComment,
    SkillCommentCreate,
    SkillCommentListResponse,
    SkillCreate,
    SkillInstallRecord,
    SkillListResponse,
    SkillRatingInfo,
    SkillUpdate,
    SkillVersion,
    SkillVersionCreate,
    SkillVersionListResponse,
    TaxonomyResponse,
    TrendingItem,
    VersionListResponse,
    VersionSyncRequest,
    WebhookResponse,
)
from plugin_market_backend.seed import seed_rich_demo
from plugin_market_backend.service import MarketService
from plugin_market_backend.recommendation_schemas import (
    RecommendationPreferences, RecommendationPreferencesUpdate,
    RecommendationRequest, RecommendationResponse,
)
from plugin_market_backend.services.recommendation_service import (
    RecommendationService, purge_expired_recommendation_feedback,
)
from plugin_market_backend.services import AnnouncementsService, BulkOpsService, CurationService, InboxService, InlineEditService, ProfileService, SkillService, synchronize_skill_storage
from plugin_market_backend.session_auth import (
    author_schema,
    clear_browser_session,
    consume_oauth_state,
    create_browser_session,
    create_oauth_state,
    validate_oauth_state,
    current_author_from_request,
    require_browser_admin,
    require_browser_author,
    upsert_github_author,
)


def _first_proxy_header_value(value: str | None) -> str | None:
    """返回逗号分隔的代理请求头中的首个值。"""
    if not value:
        return None
    first = value.split(",", 1)[0].strip()
    return first or None


def _forwarded_header_value(value: str | None, key: str) -> str | None:
    """从 RFC 7239 Forwarded 请求头中提取一个字段。"""
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
    """规范化来源地址以便可靠比较。"""
    parsed = urlparse(value)
    if parsed.scheme and parsed.netloc:
        return f"{parsed.scheme.lower()}://{parsed.netloc.lower()}"
    return value.rstrip("/").lower()


def _expected_request_origin(request: Request) -> str:
    """重建浏览器侧来源地址，优先采用代理请求头。"""
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
    """为可序列化为 JSON 的数据返回确定性的 ETag。"""
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


async def _load_home_categories_preview(viewer_id: str | None) -> dict[str, CategoryPreviewSection]:
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


async def _expire_recommendation_feedback() -> None:
    """即使用户不再访问，也清理其过期偏好。"""
    while True:
        try:
            async with session_scope() as session:
                await purge_expired_recommendation_feedback(session)
        except SQLAlchemyError:
            # 数据库暂时不可用不应永久中止过期数据清理。
            # 避免在日志中记录偏好值或 SQL 参数。
            logging.getLogger(__name__).warning("推荐反馈清理失败，将在一分钟后重试。")
            await asyncio.sleep(60)
        else:
            await asyncio.sleep(3600)


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncGenerator[None, None]:
    """在应用启动时配置数据库资源。"""
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
    async with session_scope() as session:
        await synchronize_skill_storage(session)
    expiry_task = asyncio.create_task(_expire_recommendation_feedback())
    try:
        yield
    finally:
        expiry_task.cancel()
        with suppress(asyncio.CancelledError):
            await expiry_task


app = FastAPI(
    title="Neo-MoFox 插件市场 API",
    description="持久化插件市场索引与治理后端。",
    version="0.1.0",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_exception_handler(ApiError, api_error_handler)
app.add_exception_handler(RequestValidationError, validation_error_handler)

STATIC_DIR = Path(__file__).resolve().parent / "static"
SERVER_STARTED_AT = datetime.now(timezone.utc)
ensure_plugin_media_dirs()
ensure_skill_dirs()
app.mount("/assets", StaticFiles(directory=STATIC_DIR / "assets"), name="assets")
app.mount("/plugin-media", StaticFiles(directory=PLUGIN_MEDIA_DIR), name="plugin-media")


def frontend_file(name: str = "index.html") -> FileResponse:
    """返回前端静态文件。"""
    return FileResponse(STATIC_DIR / name)


async def require_admin_operator(request: Request, authorization: str | None = Header(default=None)) -> str:
    """接受旧版管理员令牌或 GitHub 管理员浏览器会话。"""
    settings = get_settings()
    if authorization == f"Bearer {settings.admin_token}":
        return "mock-admin"
    if authorization:
        raise ApiError(403, "FORBIDDEN", "管理员令牌无效。")
    return await require_browser_admin(request)


def ensure_same_origin_browser_write(request: Request) -> None:
    """拒绝基于 Cookie 认证接口的跨源浏览器写入。"""
    source = request.headers.get("origin") or request.headers.get("referer")
    if not source:
        return
    parsed = urlparse(source)
    if not parsed.scheme or not parsed.netloc:
        raise ApiError(403, "FORBIDDEN", "浏览器请求来源无效。")
    expected_origin = _expected_request_origin(request)
    request_origin = _normalize_origin(f"{parsed.scheme}://{parsed.netloc}")
    allowed_origins = {
        expected_origin,
        _normalize_origin(f"{request.url.scheme}://{request.url.netloc}"),
        *(_normalize_origin(item) for item in get_settings().cors_origins),
    }
    if request_origin not in allowed_origins:
        raise ApiError(403, "FORBIDDEN", "不允许跨源浏览器写入。")


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
    """提供 SPA 服务状态面板。"""
    return frontend_file("index.html")


@app.get("/plugin/{plugin_id}", include_in_schema=False)
async def plugin_page(plugin_id: str) -> FileResponse:  # noqa: ARG001
    """为直接访问的插件详情 URL 提供 SPA 页面。"""
    return frontend_file("index.html")


@app.get("/author/{author_id}", include_in_schema=False)
async def author_page(author_id: str) -> FileResponse:  # noqa: ARG001
    """为直接访问的作者资料 URL 提供 SPA 页面。"""
    return frontend_file("index.html")


@app.get("/logo.png", include_in_schema=False)
async def logo_file() -> FileResponse:
    """提供 SPA 框架使用的市场标志。"""
    return frontend_file("logo.png")


@app.get("/api/v1/brand")
async def brand_assets() -> dict[str, str | None]:
    """返回前端可用的可选品牌资源。"""
    logo_path = STATIC_DIR / "logo.png"
    return {"logo_url": "/logo.png" if logo_path.exists() else None}


@app.get("/health")
async def health() -> dict[str, str]:
    """返回进程健康状态。"""
    return {"status": "ok", "service": "plugin-market-backend"}


@app.get("/ready")
async def ready() -> dict[str, str]:
    """在数据库启动完成后返回就绪状态。"""
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
    author_id: str | None = Query(default=None),
    sort: str = Query(default="updated"),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
) -> PluginListResponse:
    """列出市场插件。"""
    viewer = await current_author_from_request(request)
    viewer_id = viewer.author_id if viewer else None
    async with session_scope() as session:
        items, total = await MarketService(session).list_public_plugins(
            query=q,
            status=status,
            category=category,
            tag=tag,
            trust_level=trust_level,
            author_id=author_id,
            sort=sort,
            offset=offset,
            limit=limit,
            viewer_id=viewer_id,
        )
        return PluginListResponse(items=items, total=total)


@app.get("/api/v1/market/featured")
async def featured_plugins(request: Request, limit: int = Query(default=8, ge=1, le=24)) -> dict[str, list[Plugin]]:
    """返回市场首页各分区。"""
    viewer = await current_author_from_request(request)
    viewer_id = viewer.author_id if viewer else None
    async with session_scope() as session:
        return await MarketService(session).featured_plugins(limit=limit, viewer_id=viewer_id)


@app.get("/api/v1/market/trending-authors", response_model=list[TrendingItem])
async def trending_authors(limit: int = Query(default=8, ge=1, le=24)) -> list[TrendingItem]:
    """按互动热度返回热门插件作者。"""
    async with session_scope() as session:
        return await MarketService(session).trending_authors(limit=limit)


@app.get("/api/v1/market/stats", response_model=MarketStats)
async def public_market_stats() -> MarketStats:
    """返回首页使用的公开市场计数。"""
    async with session_scope() as session:
        return await MarketService(session).stats()


@app.get("/api/v1/market/home", response_model=MarketHome)
async def market_home(request: Request) -> Response | MarketHome:
    """返回支持 ETag 的市场首页缓存聚合数据。"""
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


def _recommendation_private_headers(response: Response) -> None:
    response.headers["Cache-Control"] = "private, no-store"
    response.headers["Vary"] = "Cookie, Authorization"


@app.post("/api/v1/recommendations", response_model=RecommendationResponse)
async def recommendations(payload: RecommendationRequest, request: Request, response: Response) -> RecommendationResponse:
    """返回独立的推荐信息流，不改变目录搜索。"""
    ensure_same_origin_browser_write(request)
    _recommendation_private_headers(response)
    viewer = await current_author_from_request(request)
    async with session_scope() as session:
        return await RecommendationService(session).recommend(payload, viewer.author_id if viewer else None)


@app.get("/api/v1/me/recommendation-preferences", response_model=RecommendationPreferences)
async def recommendation_preferences(response: Response, author_id: str = Depends(require_browser_author)) -> RecommendationPreferences:
    _recommendation_private_headers(response)
    async with session_scope() as session:
        return await RecommendationService(session).preferences(author_id)


@app.put("/api/v1/me/recommendation-preferences", response_model=RecommendationPreferences)
async def update_recommendation_preferences(
    payload: RecommendationPreferencesUpdate, request: Request, response: Response,
    author_id: str = Depends(require_browser_author),
) -> RecommendationPreferences:
    ensure_same_origin_browser_write(request)
    _recommendation_private_headers(response)
    async with session_scope() as session:
        return await RecommendationService(session).update_preferences(author_id, payload)


@app.delete("/api/v1/me/recommendation-preferences", response_model=RecommendationPreferences)
async def reset_recommendation_preferences(
    request: Request, response: Response, author_id: str = Depends(require_browser_author),
) -> RecommendationPreferences:
    ensure_same_origin_browser_write(request)
    _recommendation_private_headers(response)
    async with session_scope() as session:
        return await RecommendationService(session).update_preferences(author_id, RecommendationPreferencesUpdate(), reset=True)


@app.get("/api/v1/plugins/{plugin_id}", response_model=Plugin)
async def get_plugin(plugin_id: str, request: Request) -> Plugin:
    """返回插件详情。"""
    viewer = await current_author_from_request(request)
    viewer_id = viewer.author_id if viewer else None
    async with session_scope() as session:
        return await MarketService(session).get_plugin(plugin_id, viewer_id)


@app.get("/api/v1/plugins/{plugin_id}/readme", response_model=PluginReadmeResponse)
async def get_plugin_readme(plugin_id: str) -> PluginReadmeResponse:
    """返回插件详情视图使用的已渲染 README 内容。"""
    async with session_scope() as session:
        return await MarketService(session).get_plugin_readme(plugin_id)


@app.get("/api/v1/plugins/{plugin_id}/dependencies", response_model=PluginDependenciesResponse)
async def get_plugin_dependencies(plugin_id: str) -> PluginDependenciesResponse:
    """返回插件详情视图使用的已解析依赖数据。"""
    async with session_scope() as session:
        return await MarketService(session).get_plugin_dependencies(plugin_id)


@app.get("/api/v1/plugins/{plugin_id}/community", response_model=CommunitySnapshot)
async def get_plugin_community(plugin_id: str, request: Request) -> CommunitySnapshot:
    """返回详情页使用的综合快照。"""
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
    """返回评分聚合统计与访问者评分。"""
    viewer = await current_author_from_request(request)
    viewer_id = viewer.author_id if viewer else None
    async with session_scope() as session:
        return await MarketService(session).rating_summary(plugin_id, viewer_id)


@app.post("/api/v1/plugins/{plugin_id}/rating", response_model=RatingSummary)
async def rate_plugin(plugin_id: str, payload: RatingRequest, request: Request, viewer_id: str = Depends(require_browser_author)) -> RatingSummary:
    """提交或更新访问者的评分。"""
    ensure_same_origin_browser_write(request)
    async with session_scope() as session:
        return await MarketService(session).rate_plugin(plugin_id, viewer_id, payload.score)


@app.delete("/api/v1/plugins/{plugin_id}/rating", response_model=RatingSummary)
async def clear_plugin_rating(plugin_id: str, request: Request, viewer_id: str = Depends(require_browser_author)) -> RatingSummary:
    """删除访问者的评分。"""
    ensure_same_origin_browser_write(request)
    async with session_scope() as session:
        return await MarketService(session).clear_rating(plugin_id, viewer_id)


@app.post("/api/v1/plugins/{plugin_id}/subscribe", response_model=PluginSubscriptionState)
async def toggle_plugin_subscription(plugin_id: str, request: Request, viewer_id: str = Depends(require_browser_author)) -> PluginSubscriptionState:
    """切换访问者对插件的订阅状态。"""
    ensure_same_origin_browser_write(request)
    async with session_scope() as session:
        return await MarketService(session).toggle_subscription(plugin_id, viewer_id)


@app.get("/api/v1/plugins/{plugin_id}/comments", response_model=CommentListResponse)
async def list_plugin_comments(
    plugin_id: str,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
) -> CommentListResponse:
    """列出插件的评论。"""
    async with session_scope() as session:
        items, total = await MarketService(session).list_comments(plugin_id, offset=offset, limit=limit)
        return CommentListResponse(items=items, total=total)


@app.post("/api/v1/plugins/{plugin_id}/comments", response_model=Comment)
async def add_plugin_comment(plugin_id: str, payload: CommentCreate, request: Request, viewer_id: str = Depends(require_browser_author)) -> Comment:
    """提交新评论。"""
    ensure_same_origin_browser_write(request)
    async with session_scope() as session:
        return await MarketService(session).add_comment(plugin_id, viewer_id, payload.content, payload.parent_id)


@app.delete("/api/v1/plugins/{plugin_id}/comments/{comment_id}")
async def delete_plugin_comment(plugin_id: str, comment_id: int, request: Request) -> dict[str, bool]:
    """由评论作者或管理员删除评论。"""
    ensure_same_origin_browser_write(request)
    author = await current_author_from_request(request)
    if author is None:
        raise ApiError(401, "UNAUTHORIZED", "请先登录 GitHub。")
    async with session_scope() as session:
        await MarketService(session).delete_comment(plugin_id, comment_id, author.author_id, bool(author.is_admin))
    return {"ok": True}


@app.post("/api/v1/plugins/{plugin_id}/install-record", response_model=PluginVersion)
async def record_install(
    plugin_id: str,
    version: str | None = Query(default=None),
) -> PluginVersion:
    """在客户端安装版本时增加下载计数。"""
    async with session_scope() as session:
        return await MarketService(session).record_install(plugin_id, version)


@app.get("/api/v1/plugins/{plugin_id}/versions", response_model=VersionListResponse)
async def list_versions(plugin_id: str) -> VersionListResponse:
    """列出插件的版本。"""
    async with session_scope() as session:
        items = await MarketService(session).list_versions(plugin_id)
        return VersionListResponse(items=items, total=len(items))


@app.get("/api/v1/plugins/{plugin_id}/versions/{version}", response_model=PluginVersion)
async def get_version(plugin_id: str, version: str) -> PluginVersion:
    """返回插件版本。"""
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
    """返回推荐的可安装版本。"""
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
    """返回可安装插件及版本元数据。"""
    async with session_scope() as session:
        service = MarketService(session)
        plugin = await service.get_plugin(plugin_id)
        version = await service.get_recommended_version(plugin_id, host_version=host_version, plugin_api_version=plugin_api_version, platform=platform)
        return InstallInfo(plugin=plugin, version=version)


@app.get(
    "/api/v1/machine/authors/{author_id}/subscriptions",
    response_model=MachineSubscriptionListResponse,
)
async def machine_author_subscriptions(
    author_id: str,
    machine_author_id: str = Depends(require_market_access_token),
) -> MachineSubscriptionListResponse:
    """向 Neo-MoFox 返回作者订阅的插件列表。"""
    if machine_author_id != author_id:
        raise ApiError(403, "TOKEN_AUTHOR_MISMATCH", "访问令牌不属于请求中的作者。")
    async with session_scope() as session:
        return await MarketService(session).machine_subscriptions(author_id)


@app.get("/api/v1/categories", response_model=TaxonomyResponse)
async def list_categories() -> TaxonomyResponse:
    """返回已知分类。"""
    async with session_scope() as session:
        return TaxonomyResponse(items=await MarketService(session).categories())


@app.get("/api/v1/tags", response_model=TaxonomyResponse)
async def list_tags() -> TaxonomyResponse:
    """返回已知标签。"""
    async with session_scope() as session:
        return TaxonomyResponse(items=await MarketService(session).tags())


@app.get("/api/v1/auth/github/login", include_in_schema=False)
async def github_login(redirect_to: str = Query(default="/")) -> RedirectResponse:
    """开始 GitHub OAuth 登录。"""
    settings = get_settings()
    if not settings.github_oauth_client_id:
        raise ApiError(503, "GITHUB_OAUTH_NOT_CONFIGURED", "尚未配置 GitHub OAuth。")
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
    """完成 GitHub OAuth 登录。"""
    redirect_to = await validate_oauth_state(state)
    token = await exchange_oauth_code(get_settings(), code)
    author = await upsert_github_author(token)
    # 仅在 GitHub 调用成功后消费一次性 state，使临时网络故障
    # 可以重试，而不是导致状态变为“无效或已过期”。
    await consume_oauth_state(state)
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
    """清除当前浏览器会话。"""
    ensure_same_origin_browser_write(request)
    cookie_name = get_settings().session_cookie_name
    await clear_browser_session(request.cookies.get(cookie_name))
    response = JSONResponse({"ok": True})
    response.delete_cookie(cookie_name, path="/", samesite="lax", secure=request.url.scheme == "https", httponly=True)
    return response


@app.get("/api/v1/me", response_model=AuthStatus)
async def current_user(request: Request) -> AuthStatus:
    """返回当前通过 GitHub 认证的用户。"""
    author = await current_author_from_request(request)
    if author is None:
        return AuthStatus(authenticated=False)
    return AuthStatus(authenticated=True, user=Author(**author_schema(author)))


@app.get("/api/v1/me/profile", response_model=AuthorProfile)
async def my_profile(author_id: str = Depends(require_browser_author)) -> AuthorProfile:
    """返回当前浏览器作者的公开资料字段。"""
    async with session_scope() as session:
        return await ProfileService(session).get_profile(author_id)


@app.put("/api/v1/me/profile", response_model=AuthorProfile)
async def update_my_profile(
    payload: AuthorProfileUpdate,
    request: Request,
    author_id: str = Depends(require_browser_author),
) -> AuthorProfile:
    """更新当前浏览器作者的简介或背景。"""
    ensure_same_origin_browser_write(request)
    async with session_scope() as session:
        return await ProfileService(session).update_profile(
            author_id,
            bio=payload.bio,
            background_image_url=(str(payload.background_image_url) if payload.background_image_url is not None else None),
        )


@app.get("/api/v1/me/access-token", response_model=AccessTokenStatus)
async def my_access_token(author_id: str = Depends(require_browser_author)) -> AccessTokenStatus:
    """返回当前浏览器作者的市场令牌元数据。"""
    async with session_scope() as session:
        return await MarketService(session).access_token_status(author_id)


@app.post("/api/v1/me/access-token", response_model=AccessTokenRotateResponse)
async def rotate_my_access_token(
    request: Request,
    author_id: str = Depends(require_browser_author),
) -> AccessTokenRotateResponse:
    """创建或替换当前浏览器作者的市场令牌。"""
    ensure_same_origin_browser_write(request)
    async with session_scope() as session:
        return await MarketService(session).rotate_access_token(author_id)


@app.delete("/api/v1/me/access-token", response_model=AccessTokenStatus)
async def revoke_my_access_token(
    request: Request,
    author_id: str = Depends(require_browser_author),
) -> AccessTokenStatus:
    """撤销当前浏览器作者的市场令牌。"""
    ensure_same_origin_browser_write(request)
    async with session_scope() as session:
        return await MarketService(session).revoke_access_token(author_id)


@app.get("/api/v1/me/subscriptions", response_model=MySubscriptionListResponse)
async def my_subscriptions(author_id: str = Depends(require_browser_author)) -> MySubscriptionListResponse:
    """返回当前浏览器作者已订阅的插件。"""
    async with session_scope() as session:
        return await MarketService(session).my_subscriptions(author_id)


@app.get("/api/v1/me/follows", response_model=MyFollowListResponse)
async def my_follows(author_id: str = Depends(require_browser_author)) -> MyFollowListResponse:
    """返回当前浏览器作者关注的作者。"""
    async with session_scope() as session:
        return await MarketService(session).my_follows(author_id)


@app.post("/api/v1/me/profile/background", response_model=AuthorProfile)
async def upload_my_background(
    request: Request,
    file: UploadFile = File(...),
    author_id: str = Depends(require_browser_author),
) -> AuthorProfile:
    """接收多部分表单上传，设置新的个人空间背景图片。"""
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
    """接收多部分表单上传以更新插件图标，仅限所有者、维护者或管理员。"""
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
    """返回指定作者的公开个人空间资料。"""
    async with session_scope() as session:
        return await ProfileService(session).get_profile(author_id)


@app.get("/api/v1/authors/{author_id}/follow", response_model=AuthorFollowState)
async def get_author_follow_state(author_id: str, request: Request) -> AuthorFollowState:
    """返回当前访问者对作者的关注状态。"""
    viewer = await current_author_from_request(request)
    async with session_scope() as session:
        return await MarketService(session).author_follow_state(
            author_id,
            viewer.author_id if viewer else None,
        )


@app.post("/api/v1/authors/{author_id}/follow", response_model=AuthorFollowState)
async def toggle_author_follow(author_id: str, request: Request, viewer_id: str = Depends(require_browser_author)) -> AuthorFollowState:
    """切换访问者对作者的关注状态。"""
    ensure_same_origin_browser_write(request)
    async with session_scope() as session:
        return await MarketService(session).toggle_author_follow(author_id, viewer_id)


@app.get("/api/v1/authors/{author_id}/pins", response_model=list[PinnedPluginItem])
async def author_pins(author_id: str) -> list[PinnedPluginItem]:
    """返回指定作者公开的置顶插件。"""
    async with session_scope() as session:
        return await ProfileService(session).list_pins(author_id)


@app.get("/api/v1/authors/search", response_model=list[MentionCandidate])
async def author_search(
    prefix: str = Query(min_length=1, max_length=39),
    limit: int = Query(default=8, ge=1, le=20),
) -> list[MentionCandidate]:
    """返回匹配登录名或显示名称前缀的提及候选项。"""
    async with session_scope() as session:
        return await MarketService(session).search_authors(prefix, limit=limit)


@app.get("/api/v1/me/pins", response_model=list[PinnedPluginItem])
async def my_pins(author_id: str = Depends(require_browser_author)) -> list[PinnedPluginItem]:
    """返回当前浏览器作者的置顶插件。"""
    async with session_scope() as session:
        return await ProfileService(session).list_pins(author_id)


@app.post("/api/v1/me/pins", response_model=PinnedPluginItem)
async def add_my_pin(
    payload: PinCreate,
    request: Request,
    author_id: str = Depends(require_browser_author),
) -> PinnedPluginItem:
    """为当前浏览器作者添加一个置顶插件。"""
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
    """更新已有置顶插件的置顶理由。"""
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
    """从当前浏览器作者的个人空间移除一个置顶插件。"""
    ensure_same_origin_browser_write(request)
    async with session_scope() as session:
        await ProfileService(session).remove_pin(author_id, plugin_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@app.get("/api/v1/me/plugins", response_model=PluginListResponse)
async def my_plugins(author_id: str = Depends(require_browser_author)) -> PluginListResponse:
    """返回当前用户拥有或维护的插件。"""
    async with session_scope() as session:
        items = await MarketService(session).list_owner_plugins(author_id)
        return PluginListResponse(items=items, total=len(items))


@app.get("/api/v1/me/plugins/{plugin_id}", response_model=PluginGovernanceSnapshot)
async def my_plugin_snapshot(plugin_id: str, author_id: str = Depends(require_browser_author)) -> PluginGovernanceSnapshot:
    """返回所拥有插件的治理详情。"""
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
    """允许已登录的所有者或维护者撤回其插件版本。"""
    ensure_same_origin_browser_write(request)
    async with session_scope() as session:
        return await MarketService(session).yank_version(plugin_id, version, author_id, decision.reason if decision else None)


@app.delete("/api/v1/me/plugins/{plugin_id}", status_code=status.HTTP_204_NO_CONTENT)
async def my_plugin_delete(plugin_id: str, request: Request, author_id: str = Depends(require_browser_author)) -> Response:
    """允许已登录的所有者或维护者删除其插件。"""
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
    """允许所有者或维护者行内更新展示用元数据。"""
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
    """返回当前浏览器作者的分页站内信。"""
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
    """返回当前浏览器作者的未读站内信数量。"""
    async with session_scope() as session:
        count = await InboxService(session).unread_count(author_id)
        return InboxUnreadCount(count=count)


@app.post("/api/v1/inbox/messages/{message_id}/read")
async def inbox_mark_read(
    message_id: int,
    request: Request,
    author_id: str = Depends(require_browser_author),
) -> dict[str, int]:
    """为当前浏览器作者将一条站内信标记为已读。"""
    ensure_same_origin_browser_write(request)
    async with session_scope() as session:
        message = await session.get(InboxMessageORM, message_id)
        if message is None:
            raise ApiError(404, "INBOX_MESSAGE_NOT_FOUND", "未找到站内信。")
        if message.recipient_id != author_id:
            raise ApiError(403, "INBOX_FORBIDDEN", "无权访问此站内信。")
        updated = await InboxService(session).mark_read(author_id, [message_id])
        return {"updated": updated}


@app.post("/api/v1/inbox/read-all")
async def inbox_mark_all_read(
    request: Request,
    author_id: str = Depends(require_browser_author),
) -> dict[str, int]:
    """为当前浏览器作者将所有站内信标记为已读。"""
    ensure_same_origin_browser_write(request)
    async with session_scope() as session:
        updated = await InboxService(session).mark_all_read(author_id)
        return {"updated": updated}


@app.get("/api/v1/announcements/active", response_model=list[AnnouncementDTO])
async def active_announcements(request: Request) -> list[AnnouncementDTO]:
    """返回当前访问者可见的公告。"""
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
    """为当前浏览器作者关闭一条公告。"""
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
    """返回管理员公告列表。"""
    async with session_scope() as session:
        items, total = await AnnouncementsService(session).admin_list(offset=offset, limit=limit)
        return AnnouncementListResponse(items=items, total=total)


@app.post("/api/v1/admin/announcements", response_model=AnnouncementDTO)
async def create_announcement(
    payload: AnnouncementCreate,
    _: Request,
    operator_id: str = Depends(require_admin_operator),
) -> AnnouncementDTO:
    """创建一条公告。"""
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
    """更新一条公告。"""
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
    """停用一条公告。"""
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
    """递增公告关闭标记，使公告重新展示。"""
    async with session_scope() as session:
        announcement = await AnnouncementsService(session).resurface(announcement_id, operator_id)
        cache_bus.invalidate("announcements_active")
        return announcement


@app.get("/api/v1/admin/curation/entries", response_model=CurationEntryListResponse)
async def admin_curation_entries(_: str = Depends(require_admin_operator)) -> CurationEntryListResponse:
    """返回管理控制台使用的全部精选条目。"""
    async with session_scope() as session:
        items = await CurationService(session).list_entries()
        return CurationEntryListResponse(items=items, total=len(items))


@app.post("/api/v1/admin/curation/entries", response_model=CurationEntryDTO)
async def create_curation_entry(
    payload: CurationEntryCreate,
    operator_id: str = Depends(require_admin_operator),
) -> CurationEntryDTO:
    """创建一个精选条目。"""
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
    """更新一个精选条目。"""
    async with session_scope() as session:
        entry = await CurationService(session).update(entry_id, payload, operator_id)
        cache_bus.invalidate("home")
        return entry


@app.post("/api/v1/admin/curation/entries/{entry_id}/disable", response_model=CurationEntryDTO)
async def disable_curation_entry(
    entry_id: int,
    operator_id: str = Depends(require_admin_operator),
) -> CurationEntryDTO:
    """停用一个精选条目。"""
    async with session_scope() as session:
        entry = await CurationService(session).disable(entry_id, operator_id)
        cache_bus.invalidate("home")
        return entry


@app.put("/api/v1/admin/curation/order", response_model=list[CurationEntryDTO])
async def reorder_curation_entries(
    payload: CurationOrderUpdate,
    operator_id: str = Depends(require_admin_operator),
) -> list[CurationEntryDTO]:
    """保存新的精选条目排序。"""
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
    """对多个插件应用同一批量治理操作。"""
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
    """通过 CLI 注册插件。"""
    async with session_scope() as session:
        return await MarketService(session).register_plugin(payload, owner_id=operator_id)


@app.put("/api/v1/plugins/{plugin_id}", response_model=Plugin)
async def update_plugin(plugin_id: str, payload: PluginUpdate, operator_id: str = Depends(require_author_token)) -> Plugin:
    """通过 CLI 更新插件元数据。"""
    async with session_scope() as session:
        return await MarketService(session).update_plugin(plugin_id, payload, operator_id)


@app.post("/api/v1/plugins/{plugin_id}/versions", response_model=PluginVersion)
async def submit_version(plugin_id: str, payload: PluginVersionCreate, operator_id: str = Depends(require_author_token)) -> PluginVersion:
    """通过 CLI 提交版本。"""
    async with session_scope() as session:
        return await MarketService(session).submit_version(plugin_id, payload, operator_id)


@app.post("/api/v1/plugins/{plugin_id}/sync", response_model=PluginVersion)
async def sync_version(plugin_id: str, payload: VersionSyncRequest, operator_id: str = Depends(require_author_token)) -> PluginVersion:
    """通过 CLI 同步版本元数据。"""
    async with session_scope() as session:
        return await MarketService(session).sync_version(plugin_id, payload, operator_id)


@app.post("/api/v1/plugins/{plugin_id}/versions/{version}/yank", response_model=PluginVersion)
async def author_yank_version(plugin_id: str, version: str, decision: ReviewDecision | None = None, operator_id: str = Depends(require_author_token)) -> PluginVersion:
    """由插件所有者或维护者撤回版本。"""
    async with session_scope() as session:
        return await MarketService(session).yank_version(plugin_id, version, operator_id, decision.reason if decision else None)


@app.get("/api/v1/plugins/{plugin_id}/status")
async def get_plugin_status(plugin_id: str, _: str = Depends(require_author_token)):
    """返回插件发布与同步状态。"""
    async with session_scope() as session:
        return await MarketService(session).get_status(plugin_id)


@app.get("/api/v1/admin/reviews", response_model=list[ReviewRecord])
async def list_reviews(_: str = Depends(require_admin_operator)) -> list[ReviewRecord]:
    """列出审核记录。"""
    async with session_scope() as session:
        return await MarketService(session).list_reviews()


@app.get("/api/v1/admin/plugins", response_model=PluginListResponse)
async def list_admin_plugins(
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=200),
    _: str = Depends(require_admin_operator),
) -> PluginListResponse:
    """为管理控制台列出所有插件。"""
    async with session_scope() as session:
        items, total = await MarketService(session).list_admin_plugins(offset=offset, limit=limit)
        return PluginListResponse(items=items, total=total)


@app.get("/api/v1/admin/plugins/{plugin_id}", response_model=PluginGovernanceSnapshot)
async def admin_plugin_snapshot(plugin_id: str, _: str = Depends(require_admin_operator)) -> PluginGovernanceSnapshot:
    """返回插件的治理详情。"""
    async with session_scope() as session:
        return await MarketService(session).plugin_governance_snapshot(plugin_id)


@app.get("/api/v1/admin/dashboard", response_model=AdminDashboard)
async def admin_dashboard(_: str = Depends(require_admin_operator)) -> AdminDashboard:
    """返回管理控制台使用的丰富面板数据。"""
    async with session_scope() as session:
        return await MarketService(session).admin_dashboard()


@app.get("/api/v1/admin/system")
async def admin_system_status(_: str = Depends(require_admin_operator)) -> dict[str, Any]:
    """返回管理控制台使用的服务器状态。"""
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
    """返回管理员统计数据。"""
    async with session_scope() as session:
        return await MarketService(session).stats()


@app.post("/api/v1/admin/plugins/{plugin_id}/reject", response_model=Plugin)
async def reject_plugin(plugin_id: str, decision: ReviewDecision | None = None, operator_id: str = Depends(require_admin_operator)) -> Plugin:
    """驳回插件并恢复为草稿状态。"""
    async with session_scope() as session:
        return await MarketService(session).set_plugin_status(plugin_id, PluginStatus.DRAFT, ReviewAction.REJECT_PLUGIN, operator_id, decision.reason if decision else None)


@app.post("/api/v1/admin/plugins/{plugin_id}/publish", response_model=Plugin)
async def publish_plugin(plugin_id: str, decision: ReviewDecision | None = None, operator_id: str = Depends(require_admin_operator)) -> Plugin:
    """发布或重新上架插件。"""
    async with session_scope() as session:
        return await MarketService(session).set_plugin_status(plugin_id, PluginStatus.PUBLISHED, ReviewAction.APPROVE_PLUGIN, operator_id, decision.reason if decision else None)


@app.post("/api/v1/admin/plugins/{plugin_id}/trust-level/{trust_level}", response_model=Plugin)
async def set_plugin_trust_level(
    plugin_id: str,
    trust_level: TrustLevel,
    decision: ReviewDecision | None = None,
    operator_id: str = Depends(require_admin_operator),
) -> Plugin:
    """设置插件展示的信任徽章。"""
    async with session_scope() as session:
        return await MarketService(session).set_plugin_trust_level(plugin_id, trust_level, operator_id, decision.reason if decision else None)


@app.post("/api/v1/admin/plugins/{plugin_id}/block", response_model=Plugin)
async def block_plugin(plugin_id: str, decision: ReviewDecision | None = None, operator_id: str = Depends(require_admin_operator)) -> Plugin:
    """封禁插件。"""
    async with session_scope() as session:
        return await MarketService(session).set_plugin_status(plugin_id, PluginStatus.BLOCKED, ReviewAction.BLOCK_PLUGIN, operator_id, decision.reason if decision else None)


@app.post("/api/v1/admin/plugins/{plugin_id}/deprecate", response_model=Plugin)
async def deprecate_plugin(plugin_id: str, decision: ReviewDecision | None = None, operator_id: str = Depends(require_admin_operator)) -> Plugin:
    """将插件标记为已弃用。"""
    async with session_scope() as session:
        return await MarketService(session).set_plugin_status(plugin_id, PluginStatus.DEPRECATED, ReviewAction.DEPRECATE_PLUGIN, operator_id, decision.reason if decision else None)


@app.delete("/api/v1/admin/plugins/{plugin_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_plugin(plugin_id: str, _: str = Depends(require_admin_operator)) -> Response:
    """删除插件及其关联的全部市场记录。"""
    async with session_scope() as session:
        await MarketService(session).delete_plugin(plugin_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@app.post("/api/v1/admin/plugins/{plugin_id}/versions/{version}/reject", response_model=PluginVersion)
async def reject_version(plugin_id: str, version: str, decision: ReviewDecision | None = None, operator_id: str = Depends(require_admin_operator)) -> PluginVersion:
    """驳回插件版本并恢复为已提交状态。"""
    async with session_scope() as session:
        return await MarketService(session).set_version_status(plugin_id, version, VersionStatus.SUBMITTED, ReviewAction.REJECT_VERSION, operator_id, decision.reason if decision else None)


@app.post("/api/v1/admin/plugins/{plugin_id}/versions/{version}/publish", response_model=PluginVersion)
async def publish_version(plugin_id: str, version: str, decision: ReviewDecision | None = None, operator_id: str = Depends(require_admin_operator)) -> PluginVersion:
    """发布或恢复插件版本。"""
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
    """撤回插件版本。"""
    async with session_scope() as session:
        return await MarketService(session).set_version_status(plugin_id, version, VersionStatus.YANKED, ReviewAction.YANK_VERSION, operator_id, decision.reason if decision else None, is_yanked=True)


@app.post("/api/v1/admin/plugins/{plugin_id}/versions/{version}/block", response_model=PluginVersion)
async def block_version(plugin_id: str, version: str, decision: ReviewDecision | None = None, operator_id: str = Depends(require_admin_operator)) -> PluginVersion:
    """封禁插件版本。"""
    async with session_scope() as session:
        return await MarketService(session).set_version_status(plugin_id, version, VersionStatus.BLOCKED, ReviewAction.BLOCK_VERSION, operator_id, decision.reason if decision else None)


# ══════════════════════════════════════════════════════════════════════════════
# 技能市场路由
# ══════════════════════════════════════════════════════════════════════════════

# ── 公开查询 ───────────────────────────────────────────────────────────


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
    """列出或搜索已发布的技能。"""
    viewer = await current_author_from_request(request)
    viewer_id = viewer.author_id if viewer else None
    async with session_scope() as session:
        return await SkillService(session).list_skills(
            search=search,
            category=category,
            tag=tag,
            sort=sort,
            page=page,
            page_size=page_size,
            viewer_id=viewer_id,
        )


@app.get("/api/v1/skills/categories", response_model=TaxonomyResponse)
async def list_skill_categories() -> TaxonomyResponse:
    """返回去重后的技能分类。"""
    async with session_scope() as session:
        return TaxonomyResponse(items=await SkillService(session).get_categories())


@app.get("/api/v1/skills/tags", response_model=TaxonomyResponse)
async def list_skill_tags() -> TaxonomyResponse:
    """返回去重后的技能标签。"""
    async with session_scope() as session:
        return TaxonomyResponse(items=await SkillService(session).get_tags())


@app.get("/api/v1/skills/{skill_id}", response_model=Skill)
async def get_skill(skill_id: str, request: Request) -> Skill:
    """返回技能详情。"""
    viewer = await current_author_from_request(request)
    viewer_id = viewer.author_id if viewer else None
    async with session_scope() as session:
        return await SkillService(session).get_skill(skill_id, viewer_id)


@app.get("/api/v1/skills/{skill_id}/versions", response_model=SkillVersionListResponse)
async def list_skill_versions(skill_id: str) -> SkillVersionListResponse:
    """列出技能的版本。"""
    async with session_scope() as session:
        return await SkillService(session).get_skill_versions(skill_id)


@app.get("/api/v1/skills/{skill_id}/versions/{version}", response_model=SkillVersion)
async def get_skill_version(skill_id: str, version: str) -> SkillVersion:
    """返回单个技能版本。"""
    async with session_scope() as session:
        versions = await SkillService(session).get_skill_versions(skill_id)
        for item in versions.items:
            if item.version == version:
                return item
        raise ApiError(404, "SKILL_VERSION_NOT_FOUND", "未找到技能版本。", {"skill_id": skill_id, "version": version})


@app.get("/api/v1/skills/{skill_id}/versions/{version}/download")
async def download_skill_version(skill_id: str, version: str) -> FileResponse:
    """下载技能版本的 ZIP 包。"""
    async with session_scope() as session:
        file_path, file_size, checksum = await SkillService(session).get_version_download(skill_id, version)
        await SkillService(session).record_download(skill_id, version)

    safe_skill = "".join(ch for ch in skill_id if ch.isascii() and (ch.isalnum() or ch in "-_.")) or "skill"
    safe_version = "".join(ch for ch in version if ch.isascii() and (ch.isalnum() or ch in "-_.")) or "version"
    filename = f"{safe_skill}-{safe_version}.zip"
    return FileResponse(
        file_path,
        media_type="application/zip",
        filename=filename,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# ── 社区互动（需要登录）──────────────────────────────────


@app.get("/api/v1/skills/{skill_id}/comments", response_model=SkillCommentListResponse)
async def list_skill_comments(
    skill_id: str,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
) -> SkillCommentListResponse:
    """列出技能的评论。"""
    async with session_scope() as session:
        return await SkillService(session).list_comments(skill_id, offset=offset, limit=limit)


@app.post("/api/v1/skills/{skill_id}/comments", response_model=SkillComment)
async def add_skill_comment(
    skill_id: str,
    payload: SkillCommentCreate,
    request: Request,
    viewer_id: str = Depends(require_browser_author),
) -> SkillComment:
    """为技能提交新评论。"""
    ensure_same_origin_browser_write(request)
    async with session_scope() as session:
        return await SkillService(session).add_comment(
            skill_id, viewer_id, payload.content, payload.parent_id
        )


@app.delete("/api/v1/skills/{skill_id}/comments/{comment_id}")
async def delete_skill_comment(skill_id: str, comment_id: int, request: Request) -> dict[str, bool]:
    """由评论作者或管理员删除评论。"""
    ensure_same_origin_browser_write(request)
    author = await current_author_from_request(request)
    if author is None:
        raise ApiError(401, "UNAUTHORIZED", "请先登录 GitHub。")
    async with session_scope() as session:
        await SkillService(session).delete_comment(
            skill_id, comment_id, author.author_id, bool(author.is_admin)
        )
    return {"ok": True}


@app.post("/api/v1/skills/{skill_id}/rating", response_model=SkillRatingInfo)
async def rate_skill(
    skill_id: str,
    payload: RatingRequest,
    request: Request,
    viewer_id: str = Depends(require_browser_author),
) -> SkillRatingInfo:
    """提交或更新访问者的评分。"""
    ensure_same_origin_browser_write(request)
    async with session_scope() as session:
        return await SkillService(session).rate_skill(skill_id, viewer_id, payload.score)


@app.delete("/api/v1/skills/{skill_id}/rating", response_model=SkillRatingInfo)
async def clear_skill_rating(
    skill_id: str,
    request: Request,
    viewer_id: str = Depends(require_browser_author),
) -> SkillRatingInfo:
    """删除访问者的评分。"""
    ensure_same_origin_browser_write(request)
    async with session_scope() as session:
        return await SkillService(session).clear_rating(skill_id, viewer_id)


@app.get("/api/v1/skills/{skill_id}/rating", response_model=SkillRatingInfo)
async def get_skill_rating(skill_id: str, request: Request) -> SkillRatingInfo:
    """返回评分聚合统计与访问者评分。"""
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
    """切换访问者对技能的点赞状态。"""
    ensure_same_origin_browser_write(request)
    async with session_scope() as session:
        return await SkillService(session).toggle_like(skill_id, viewer_id)


@app.post("/api/v1/skills/{skill_id}/subscribe")
async def toggle_skill_subscription(
    skill_id: str,
    request: Request,
    viewer_id: str = Depends(require_browser_author),
) -> dict:
    """切换访问者对技能的订阅状态。"""
    ensure_same_origin_browser_write(request)
    async with session_scope() as session:
        return await SkillService(session).toggle_subscription(skill_id, viewer_id)


@app.post("/api/v1/skills/{skill_id}/install-record", response_model=SkillInstallRecord)
async def record_skill_install(
    skill_id: str,
    version: str | None = Query(default=None),
) -> SkillInstallRecord:
    """在客户端安装版本时增加下载计数。"""
    async with session_scope() as session:
        return await SkillService(session).record_download(skill_id, version)


# ── 作者路由（需要登录）──────────────────────────────────────────


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
    """通过上传 ZIP 包发布新技能。"""
    ensure_same_origin_browser_write(request)

    zip_bytes = await file.read()

    def _parse_form_list(raw: str | None) -> list[str] | None:
        """从 JSON 数组或逗号分隔的表单字段解析分类或标签。"""
        if not raw or not raw.strip():
            return None
        stripped = raw.strip()
        if stripped.startswith("["):
            import json as _json
            try:
                parsed = _json.loads(stripped)
                if isinstance(parsed, list):
                    return [str(item).strip() for item in parsed if str(item).strip()]
            except Exception:
                pass
        return [item.strip() for item in stripped.split(",") if item.strip()]

    parsed_categories = _parse_form_list(categories)
    parsed_tags = _parse_form_list(tags)

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
    """为已有技能发布新版本。"""
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
    """更新技能的可变元数据。"""
    ensure_same_origin_browser_write(request)
    async with session_scope() as session:
        return await SkillService(session).update_skill_meta(skill_id, viewer_id, payload)


@app.delete("/api/v1/skills/{skill_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_skill(
    skill_id: str,
    request: Request,
    viewer_id: str = Depends(require_browser_author),
) -> Response:
    """删除技能，仅限所有者。"""
    ensure_same_origin_browser_write(request)
    async with session_scope() as session:
        await SkillService(session).delete_skill(skill_id, viewer_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@app.get("/api/v1/me/skills", response_model=SkillListResponse)
async def my_skills(
    viewer_id: str = Depends(require_browser_author),
) -> SkillListResponse:
    """返回当前访问者拥有的技能。"""
    async with session_scope() as session:
        return await SkillService(session).my_skills(viewer_id)


# ── 管理员路由 ────────────────────────────────────────────────────────────


@app.post("/api/v1/admin/skills/{skill_id}/block", response_model=Skill)
async def block_skill(
    skill_id: str,
    decision: ReviewDecision | None = None,
    operator_id: str = Depends(require_admin_operator),
) -> Skill:
    """封禁技能。"""
    async with session_scope() as session:
        return await SkillService(session).block_skill(
            skill_id, operator_id, decision.reason if decision else None
        )


@app.post("/api/v1/admin/skills/{skill_id}/trust-level/{trust_level}", response_model=Skill)
async def set_skill_trust_level(
    skill_id: str,
    trust_level: str,
    operator_id: str = Depends(require_admin_operator),
) -> Skill:
    """设置技能展示的信任徽章。"""
    async with session_scope() as session:
        return await SkillService(session).set_skill_trust_level(skill_id, trust_level, operator_id)


@app.post("/api/v1/github/webhooks", response_model=WebhookResponse)
async def github_webhook(
    request: Request,
    x_github_event: str = Header(default="unknown"),
    x_github_delivery: str | None = Header(default=None),
    x_hub_signature_256: str | None = Header(default=None),
) -> WebhookResponse:
    """接收并审计 GitHub Webhook 事件。"""
    body = await request.body()
    verify_github_signature(get_settings().github_webhook_secret, body, x_hub_signature_256)
    payload: dict[str, Any] = await request.json() if body else {}
    event_id = x_github_delivery or f"manual-{x_github_event}"
    async with session_scope() as session:
        await MarketService(session).record_webhook(event_id, x_github_event, payload.get("action"), payload)
    return WebhookResponse(accepted=True, event_id=event_id)


@app.get("/{full_path:path}", include_in_schema=False)
async def spa_fallback(full_path: str) -> FileResponse:
    """为未匹配的前端路由提供 index.html，作为 SPA HTML5 历史路由回退。"""
    if full_path.startswith("api/"):
        raise ApiError(404, "NOT_FOUND", "未找到 API 接口。")

    file_path = STATIC_DIR / full_path
    if file_path.exists() and file_path.is_file():
        return FileResponse(file_path)
    return frontend_file("index.html")
