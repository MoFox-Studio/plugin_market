"""作者与管理员 API 的 Bearer 令牌认证。"""

from __future__ import annotations

import hashlib

from fastapi import Header
from sqlalchemy import select

from plugin_market_backend.config import get_settings
from plugin_market_backend.database import session_scope
from plugin_market_backend.errors import ApiError
from plugin_market_backend.orm import AuthorAccessTokenORM, utc_now
from plugin_market_backend.session_auth import github_author_from_bearer


def _read_bearer_token(authorization: str | None) -> str:
    """提取 Bearer 令牌，格式无效时抛出统一认证错误。"""
    if not authorization:
        raise ApiError(401, "UNAUTHORIZED", "必须提供 Authorization 请求头。")
    prefix = "Bearer "
    if not authorization.startswith(prefix):
        raise ApiError(401, "UNAUTHORIZED", "Authorization 必须使用 Bearer 令牌格式。")
    return authorization[len(prefix) :]


def read_bearer_token(authorization: str | None) -> str:
    """提供提取 Bearer 令牌的公共入口。"""
    return _read_bearer_token(authorization)


def hash_access_token(token: str) -> str:
    """对市场访问令牌取哈希，用于持久化存储。"""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


async def require_author_token(authorization: str | None = Header(default=None)) -> str:
    """验证已配置的作者令牌或有效的 GitHub 令牌。"""
    token = _read_bearer_token(authorization)
    settings = get_settings()
    if token != settings.author_token:
        author_id = await github_author_from_bearer(authorization)
        if author_id is None:
            raise ApiError(403, "FORBIDDEN", "作者令牌无效。")
        return author_id
    return "mock-author"


async def require_admin_token(authorization: str | None = Header(default=None)) -> str:
    """验证已配置的管理员令牌。"""
    token = _read_bearer_token(authorization)
    settings = get_settings()
    if token != settings.admin_token:
        raise ApiError(403, "FORBIDDEN", "管理员令牌无效。")
    return "mock-admin"


async def require_market_access_token(
    authorization: str | None = Header(default=None),
) -> str:
    """验证市场访问令牌并返回所属作者 ID。"""
    token = _read_bearer_token(authorization)
    token_hash = hash_access_token(token)
    async with session_scope() as session:
        record = await session.scalar(
            select(AuthorAccessTokenORM).where(
                AuthorAccessTokenORM.token_hash == token_hash
            )
        )
        if record is None:
            raise ApiError(403, "FORBIDDEN", "市场访问令牌无效。")
        record.last_used_at = utc_now()
        await session.flush()
        return record.author_id
