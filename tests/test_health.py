"""Health endpoint tests."""

from __future__ import annotations

from httpx import AsyncClient


async def test_health_returns_ok(client: AsyncClient) -> None:
    """Health check should identify the mock service."""

    response = await client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "plugin-market-backend"}


async def test_status_route_serves_spa(client: AsyncClient) -> None:
    """/status should serve the SPA shell so deep-linking works."""

    response = await client.get("/status")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert b'<div id="app">' in response.content
