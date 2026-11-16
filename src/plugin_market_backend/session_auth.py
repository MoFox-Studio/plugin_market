"""Cookie 与 GitHub 令牌认证辅助工具。"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import secrets
from typing import Any

from fastapi import Header, Request
from sqlalchemy import delete

from plugin_market_backend.config import get_settings
from plugin_market_backend.database import session_scope
from plugin_market_backend.errors import ApiError
from plugin_market_backend.github_oauth import fetch_github_user
from plugin_market_backend.orm import AuthSessionORM, AuthorORM, OAuthStateORM, utc_now
from plugin_market_backend.service import MarketService


SESSION_TTL = timedelta(days=14)
OAUTH_STATE_TTL = timedelta(minutes=10)


def _is_expired(expires_at: datetime, now: datetime | None = None) -> bool:
    """比较过期时间，兼容 SQLite 读写后丢失时区的日期时间。"""
    current_time = now or utc_now()
    normalized_expires_at = expires_at if expires_at.tzinfo is not None else expires_at.replace(tzinfo=timezone.utc)
    normalized_now = current_time if current_time.tzinfo is not None else current_time.replace(tzinfo=timezone.utc)
    return normalized_expires_at < normalized_now


async def create_oauth_state(redirect_to: str) -> str:
    """创建一次性 OAuth state。"""
    state = secrets.token_urlsafe(32)
    now = utc_now()
    async with session_scope() as session:
        await session.execute(delete(OAuthStateORM).where(OAuthStateORM.expires_at < now))
        session.add(OAuthStateORM(state=state, redirect_to=redirect_to or "/", created_at=now, expires_at=now + OAUTH_STATE_TTL))
    return state


async def consume_oauth_state(state: str) -> str:
    """消费 OAuth state 并返回其存储的跳转路径。"""
    async with session_scope() as session:
        record = await session.get(OAuthStateORM, state)
        if record is None or _is_expired(record.expires_at):
            raise ApiError(401, "OAUTH_STATE_INVALID", "GitHub OAuth state 无效或已过期。")
        redirect_to = record.redirect_to
        await session.delete(record)
        return redirect_to


async def validate_oauth_state(state: str) -> str:
    """验证 OAuth state，在远程调用成功前不消费它。"""
    async with session_scope() as session:
        record = await session.get(OAuthStateORM, state)
        if record is None or _is_expired(record.expires_at):
            raise ApiError(401, "OAUTH_STATE_INVALID", "GitHub OAuth state 无效或已过期。")
        return record.redirect_to


async def create_browser_session(author_id: str, access_token: str) -> str:
    """为已认证的作者创建浏览器会话。"""
    session_id = secrets.token_urlsafe(40)
    now = utc_now()
    async with session_scope() as session:
        await session.execute(delete(AuthSessionORM).where(AuthSessionORM.expires_at < now))
        session.add(AuthSessionORM(session_id=session_id, author_id=author_id, access_token=access_token, created_at=now, expires_at=now + SESSION_TTL))
    return session_id


async def clear_browser_session(session_id: str | None) -> None:
    """删除指定浏览器会话（若存在）。"""
    if not session_id:
        return
    async with session_scope() as session:
        record = await session.get(AuthSessionORM, session_id)
        if record is not None:
            await session.delete(record)


async def upsert_github_author(access_token: str) -> AuthorORM:
    """获取 GitHub 用户信息并创建或更新对应作者记录。"""
    settings = get_settings()
    github_user = await fetch_github_user(settings, access_token)
    author_id = f"github:{github_user.github_login.lower()}"
    async with session_scope() as session:
        service = MarketService(session)
        author = await service.ensure_author(
            author_id,
            github_user_id=github_user.github_user_id,
            github_login=github_user.github_login,
            display_name=github_user.display_name,
            avatar_url=github_user.avatar_url,
            is_admin=github_user.github_login.lower() in {item.lower() for item in settings.admin_github_logins},
        )
        return author


async def current_author_from_request(request: Request) -> AuthorORM | None:
    """会话 Cookie 有效时返回当前浏览器作者。"""
    settings = get_settings()
    session_id = request.cookies.get(settings.session_cookie_name)
    if not session_id:
        return None
    async with session_scope() as session:
        record = await session.get(AuthSessionORM, session_id)
        if record is None or _is_expired(record.expires_at):
            return None
        return await session.get(AuthorORM, record.author_id)


async def require_browser_author(request: Request) -> str:
    """验证浏览器会话并返回作者 ID。"""
    author = await current_author_from_request(request)
    if author is None:
        raise ApiError(401, "UNAUTHORIZED", "请先登录 GitHub。")
    return author.author_id


async def require_browser_admin(request: Request) -> str:
    """验证浏览器管理员会话并返回作者 ID。"""
    author = await current_author_from_request(request)
    if author is None:
        raise ApiError(401, "UNAUTHORIZED", "请先登录 GitHub。")
    if not author.is_admin:
        raise ApiError(403, "FORBIDDEN", "需要管理员权限。")
    return author.author_id


async def github_author_from_bearer(authorization: str | None = Header(default=None)) -> str | None:
    """从 Bearer 认证中解析 GitHub 令牌，缺失时返回 None。"""
    if not authorization or not authorization.startswith("Bearer "):
        return None
    token = authorization[len("Bearer ") :]
    author = await upsert_github_author(token)
    return author.author_id


def author_schema(author: AuthorORM) -> dict[str, Any]:
    """将作者 ORM 对象转换为公开 API 字典。"""
    return {
        "author_id": author.author_id,
        "github_user_id": author.github_user_id,
        "github_login": author.github_login,
        "display_name": author.display_name,
        "avatar_url": author.avatar_url,
        "author_type": author.author_type,
        "verified_at": author.verified_at,
        "is_admin": author.is_admin,
    }
