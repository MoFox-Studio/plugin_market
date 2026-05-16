"""API tests for announcement routes (task 14)."""

from __future__ import annotations

from httpx import AsyncClient

from plugin_market_backend.session_auth import create_browser_session


ADMIN_HEADERS = {"Authorization": "Bearer admin-token"}


async def test_admin_create_list_and_public_active_announcements(client: AsyncClient) -> None:
    created = await client.post(
        "/api/v1/admin/announcements",
        json={
            "title": "Maintenance Window",
            "body_markdown": "Tonight",
            "display_mode": "banner",
            "audience": "all",
        },
        headers=ADMIN_HEADERS,
    )
    listed = await client.get("/api/v1/admin/announcements", headers=ADMIN_HEADERS)
    active = await client.get("/api/v1/announcements/active")

    assert created.status_code == 200
    assert created.json()["title"] == "Maintenance Window"
    assert listed.status_code == 200
    assert listed.json()["total"] >= 1
    assert any(item["title"] == "Maintenance Window" for item in listed.json()["items"])
    assert active.status_code == 200
    assert any(item["title"] == "Maintenance Window" for item in active.json())


async def test_announcement_dismiss_hides_for_same_browser_user(client: AsyncClient) -> None:
    created = await client.post(
        "/api/v1/admin/announcements",
        json={
            "title": "Dismiss Me",
            "body_markdown": "Body",
            "display_mode": "banner",
            "audience": "logged_in",
            "dismissible": True,
        },
        headers=ADMIN_HEADERS,
    )
    session_id = await create_browser_session("mock-author", "browser-test-token")
    client.cookies.set("plugin_market_session", session_id, path="/")

    before = await client.get("/api/v1/announcements/active")
    dismissed = await client.post(f"/api/v1/announcements/{created.json()['id']}/dismiss")
    after = await client.get("/api/v1/announcements/active")

    assert before.status_code == 200
    assert any(item["id"] == created.json()["id"] for item in before.json())
    assert dismissed.status_code == 200
    assert dismissed.json()["announcement_id"] == created.json()["id"]
    assert after.status_code == 200
    assert all(item["id"] != created.json()["id"] for item in after.json())


async def test_admin_update_disable_and_resurface_announcement(client: AsyncClient) -> None:
    created = await client.post(
        "/api/v1/admin/announcements",
        json={
            "title": "Original",
            "body_markdown": "Body",
            "display_mode": "modal",
            "audience": "all",
        },
        headers=ADMIN_HEADERS,
    )
    announcement_id = created.json()["id"]

    updated = await client.put(
        f"/api/v1/admin/announcements/{announcement_id}",
        json={"title": "Updated"},
        headers=ADMIN_HEADERS,
    )
    disabled = await client.post(
        f"/api/v1/admin/announcements/{announcement_id}/disable",
        headers=ADMIN_HEADERS,
    )
    resurfaced = await client.post(
        f"/api/v1/admin/announcements/{announcement_id}/resurface",
        headers=ADMIN_HEADERS,
    )

    assert updated.status_code == 200
    assert updated.json()["title"] == "Updated"
    assert disabled.status_code == 200
    assert disabled.json()["enabled"] is False
    assert resurfaced.status_code == 200
    assert resurfaced.json()["enabled"] is True
    assert resurfaced.json()["dismiss_token"] == disabled.json()["dismiss_token"] + 1