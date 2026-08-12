"""Regression tests for retryable GitHub OAuth failures."""

from __future__ import annotations

import importlib

import pytest
from httpx import AsyncClient

from plugin_market_backend.config import reset_settings_cache
from plugin_market_backend.errors import ApiError
from plugin_market_backend.session_auth import create_oauth_state, validate_oauth_state


async def test_callback_keeps_state_when_github_is_temporarily_unavailable(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A failed token exchange must not turn a retry into an invalid-state error."""

    monkeypatch.setenv("PLUGIN_MARKET_GITHUB_OAUTH_CLIENT_ID", "client-id")
    reset_settings_cache()
    state = await create_oauth_state("/me/profile")
    app_module = importlib.import_module("plugin_market_backend.app")

    async def unavailable(*_args: object, **_kwargs: object) -> str:
        raise ApiError(503, "GITHUB_UNAVAILABLE", "GitHub OAuth is temporarily unavailable. Please retry.")

    monkeypatch.setattr(app_module, "exchange_oauth_code", unavailable)
    response = await client.get(
        "/api/v1/auth/github/callback",
        params={"code": "temporary-code", "state": state},
    )

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "GITHUB_UNAVAILABLE"
    assert await validate_oauth_state(state) == "/me/profile"
