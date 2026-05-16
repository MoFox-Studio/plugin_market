"""API tests for the bulk governance route (task 16)."""

from __future__ import annotations

from httpx import AsyncClient

from test_author_api import AUTHOR_HEADERS, plugin_payload


ADMIN_HEADERS = {"Authorization": "Bearer admin-token"}


async def test_bulk_api_returns_207_and_partial_results(client: AsyncClient) -> None:
    await client.post(
        "/api/v1/plugins",
        json=plugin_payload("bulk_plugin_a", display_name="Bulk Plugin A"),
        headers=AUTHOR_HEADERS,
    )

    response = await client.post(
        "/api/v1/admin/plugins/bulk",
        json={
            "plugin_ids": ["bulk_plugin_a", "missing_plugin"],
            "action": "block",
            "params": {"reason": "risk"},
        },
        headers=ADMIN_HEADERS,
    )

    assert response.status_code == 207
    assert response.json()["results"][0]["plugin_id"] == "bulk_plugin_a"
    assert response.json()["results"][0]["ok"] is True
    assert response.json()["results"][0]["after"]["status"] == "blocked"
    assert response.json()["results"][1]["plugin_id"] == "missing_plugin"
    assert response.json()["results"][1]["ok"] is False
    assert response.json()["results"][1]["error"]["code"] == "PLUGIN_NOT_FOUND"


async def test_bulk_api_set_trust_level(client: AsyncClient) -> None:
    await client.post(
        "/api/v1/plugins",
        json=plugin_payload("bulk_plugin_b", display_name="Bulk Plugin B"),
        headers=AUTHOR_HEADERS,
    )

    response = await client.post(
        "/api/v1/admin/plugins/bulk",
        json={
            "plugin_ids": ["bulk_plugin_b"],
            "action": "set_trust_level",
            "params": {"trust_level": "official", "reason": "internal"},
        },
        headers=ADMIN_HEADERS,
    )

    assert response.status_code == 207
    assert response.json()["results"][0]["ok"] is True
    assert response.json()["results"][0]["after"]["trust_level"] == "official"