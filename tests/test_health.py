"""健康检查端点测试。"""

from __future__ import annotations

from httpx import AsyncClient


async def test_health_returns_ok(client: AsyncClient) -> None:
    """健康检查应标识模拟服务。"""
    response = await client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "plugin-market-backend"}


async def test_status_route_serves_spa(client: AsyncClient) -> None:
    """/status 应提供 SPA 页面外壳以支持直接访问深层链接。"""
    response = await client.get("/status")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert b'<div id="app">' in response.content
