"""API tests for the cached market home aggregate (task 17)."""

from __future__ import annotations

from httpx import AsyncClient


ADMIN_HEADERS = {"Authorization": "Bearer admin-token"}


async def test_market_home_returns_aggregate_and_etag(client: AsyncClient) -> None:
    created = await client.post(
        "/api/v1/admin/announcements",
        json={
            "title": "Banner One",
            "body_markdown": "Hello",
            "display_mode": "banner",
            "audience": "all",
        },
        headers=ADMIN_HEADERS,
    )
    curated = await client.post(
        "/api/v1/admin/curation/entries",
        json={
            "slot_type": "featured_plugin",
            "target_type": "plugin",
            "target_id": "demo_plugin",
        },
        headers=ADMIN_HEADERS,
    )

    assert created.status_code == 200
    assert curated.status_code == 200

    first = await client.get("/api/v1/market/home")
    etag = first.headers.get("etag")
    second = await client.get("/api/v1/market/home", headers={"If-None-Match": etag})

    assert first.status_code == 200
    assert first.headers.get("cache-control") == "private, max-age=60"
    assert etag is not None

    body = first.json()
    assert body["featured_plugins"]
    assert body["latest"]
    assert body["top_rated"]
    assert body["trending_authors"]
    assert body["stats"]["plugins_total"] >= 1
    assert any(item["title"] == "Banner One" for item in body["active_announcements"])
    assert any(item["target_id"] == "demo_plugin" for item in body["showcase"])

    assert second.status_code == 304
    assert second.headers.get("etag") == etag