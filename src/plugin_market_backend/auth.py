"""Bearer-token authentication for author and admin APIs."""

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
    """Extract a bearer token or raise a uniform auth error."""

    if not authorization:
        raise ApiError(401, "UNAUTHORIZED", "Authorization header is required.")
    prefix = "Bearer "
    if not authorization.startswith(prefix):
        raise ApiError(401, "UNAUTHORIZED", "Authorization must use Bearer token format.")
    return authorization[len(prefix) :]


def read_bearer_token(authorization: str | None) -> str:
    """Public wrapper for extracting a bearer token."""

    return _read_bearer_token(authorization)


def hash_access_token(token: str) -> str:
    """Hash a market access token for at-rest storage."""

    return hashlib.sha256(token.encode("utf-8")).hexdigest()


async def require_author_token(authorization: str | None = Header(default=None)) -> str:
    """Require either the configured author token or a valid GitHub token."""

    token = _read_bearer_token(authorization)
    settings = get_settings()
    if token != settings.author_token:
        author_id = await github_author_from_bearer(authorization)
        if author_id is None:
            raise ApiError(403, "FORBIDDEN", "Author token is invalid.")
        return author_id
    return "mock-author"


async def require_admin_token(authorization: str | None = Header(default=None)) -> str:
    """Require the configured admin token."""

    token = _read_bearer_token(authorization)
    settings = get_settings()
    if token != settings.admin_token:
        raise ApiError(403, "FORBIDDEN", "Admin token is invalid.")
    return "mock-admin"


async def require_market_access_token(
    authorization: str | None = Header(default=None),
) -> str:
    """Require a valid market access token and return its owner author id."""

    token = _read_bearer_token(authorization)
    token_hash = hash_access_token(token)
    async with session_scope() as session:
        record = await session.scalar(
            select(AuthorAccessTokenORM).where(
                AuthorAccessTokenORM.token_hash == token_hash
            )
        )
        if record is None:
            raise ApiError(403, "FORBIDDEN", "Market access token is invalid.")
        record.last_used_at = utc_now()
        await session.flush()
        return record.author_id
