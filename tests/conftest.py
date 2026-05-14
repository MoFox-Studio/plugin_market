"""Test fixtures for the plugin market backend."""

from __future__ import annotations

from collections.abc import AsyncGenerator

import pytest
from httpx import ASGITransport, AsyncClient
from plugin_market_backend.app import app
from plugin_market_backend.config import reset_settings_cache
from plugin_market_backend.database import close_database, configure_database, drop_database, init_database, session_scope
from plugin_market_backend.seed import seed_database


@pytest.fixture(autouse=True)
async def reset_database(monkeypatch: pytest.MonkeyPatch) -> AsyncGenerator[None, None]:
    """Reset the database before each test."""

    monkeypatch.setenv("PLUGIN_MARKET_AUTHOR_TOKEN", "dev-token")
    monkeypatch.setenv("PLUGIN_MARKET_ADMIN_TOKEN", "admin-token")
    monkeypatch.setenv("PLUGIN_MARKET_REQUIRE_REVIEW", "false")
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    reset_settings_cache()
    await close_database()
    configure_database("sqlite+aiosqlite:///:memory:")
    await init_database()
    async with session_scope() as session:
        await seed_database(session)
    yield
    await drop_database()
    await close_database()


@pytest.fixture
async def client() -> AsyncGenerator[AsyncClient, None]:
    """Create an ASGI test client."""

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as http_client:
        yield http_client
