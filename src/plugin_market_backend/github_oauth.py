"""GitHub OAuth and user lookup helpers."""

from __future__ import annotations

from dataclasses import dataclass

import httpx

from plugin_market_backend.config import Settings
from plugin_market_backend.errors import ApiError


@dataclass(frozen=True)
class GitHubUser:
    """Normalized GitHub user identity."""

    github_user_id: str
    github_login: str
    display_name: str
    avatar_url: str | None


async def exchange_oauth_code(settings: Settings, code: str) -> str:
    """Exchange a GitHub OAuth code for an access token."""

    if not settings.github_oauth_client_id or not settings.github_oauth_client_secret:
        raise ApiError(503, "GITHUB_OAUTH_NOT_CONFIGURED", "GitHub OAuth is not configured.")
    try:
        async with httpx.AsyncClient(timeout=15, trust_env=settings.github_trust_env) as client:
            response = await client.post(
                f"{settings.github_login_base_url}/access_token",
                headers={"Accept": "application/json"},
                data={
                    "client_id": settings.github_oauth_client_id,
                    "client_secret": settings.github_oauth_client_secret,
                    "code": code,
                    "redirect_uri": settings.github_oauth_redirect_uri or None,
                },
            )
    except httpx.RequestError as exc:
        raise ApiError(503, "GITHUB_UNAVAILABLE", "GitHub OAuth is temporarily unavailable. Please retry.") from exc
    payload = response.json()
    token = payload.get("access_token")
    if response.status_code >= 400 or not token:
        raise ApiError(401, "GITHUB_OAUTH_FAILED", "GitHub OAuth token exchange failed.", {"error": payload.get("error")})
    return str(token)


async def fetch_github_user(settings: Settings, access_token: str) -> GitHubUser:
    """Fetch the GitHub user attached to an OAuth or personal access token."""

    try:
        async with httpx.AsyncClient(timeout=15, trust_env=settings.github_trust_env) as client:
            response = await client.get(
                f"{settings.github_api_base_url}/user",
                headers={"Accept": "application/vnd.github+json", "Authorization": f"Bearer {access_token}"},
            )
    except httpx.RequestError as exc:
        raise ApiError(503, "GITHUB_UNAVAILABLE", "GitHub user lookup is temporarily unavailable. Please retry.") from exc
    if response.status_code == 401:
        raise ApiError(401, "GITHUB_TOKEN_INVALID", "GitHub token is invalid.")
    if response.status_code >= 400:
        raise ApiError(response.status_code, "GITHUB_USER_LOOKUP_FAILED", "GitHub user lookup failed.")
    payload = response.json()
    login = str(payload.get("login") or "")
    if not login:
        raise ApiError(401, "GITHUB_USER_LOOKUP_FAILED", "GitHub user payload did not include a login.")
    return GitHubUser(
        github_user_id=str(payload.get("id") or login),
        github_login=login,
        display_name=str(payload.get("name") or login),
        avatar_url=payload.get("avatar_url"),
    )
