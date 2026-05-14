"""Health endpoint tests."""

from __future__ import annotations

from httpx import AsyncClient


async def test_health_returns_ok(client: AsyncClient) -> None:
    """Health check should identify the mock service."""

    response = await client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "plugin-market-backend"}
