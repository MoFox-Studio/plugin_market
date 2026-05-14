"""Bearer-token authentication for author and admin APIs."""

from __future__ import annotations

from fastapi import Header

from plugin_market_backend.config import get_settings
from plugin_market_backend.errors import ApiError
from plugin_market_backend.session_auth import github_author_from_bearer


def _read_bearer_token(authorization: str | None) -> str:
    """Extract a bearer token or raise a uniform auth error."""

    if not authorization:
        raise ApiError(401, "UNAUTHORIZED", "Authorization header is required.")
    prefix = "Bearer "
    if not authorization.startswith(prefix):
        raise ApiError(401, "UNAUTHORIZED", "Authorization must use Bearer token format.")
    return authorization[len(prefix) :]


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
