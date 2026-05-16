"""API tests for curation management routes (task 15)."""

from __future__ import annotations

from httpx import AsyncClient

from test_author_api import AUTHOR_HEADERS, plugin_payload


ADMIN_HEADERS = {"Authorization": "Bearer admin-token"}


async def test_admin_curation_crud_and_list(client: AsyncClient) -> None:
    await client.post(
        "/api/v1/plugins",
        json=plugin_payload("curated_plugin", display_name="Curated Plugin"),
        headers=AUTHOR_HEADERS,
    )

    created = await client.post(
        "/api/v1/admin/curation/entries",
        json={
            "slot_type": "featured_plugin",
            "target_type": "plugin",
            "target_id": "curated_plugin",
            "sort_order": 5,
        },
        headers=ADMIN_HEADERS,
    )
    listed = await client.get("/api/v1/admin/curation/entries", headers=ADMIN_HEADERS)
    updated = await client.put(
        f"/api/v1/admin/curation/entries/{created.json()['id']}",
        json={"audience": "logged_in"},
        headers=ADMIN_HEADERS,
    )
    disabled = await client.post(
        f"/api/v1/admin/curation/entries/{created.json()['id']}/disable",
        headers=ADMIN_HEADERS,
    )

    assert created.status_code == 200
    assert created.json()["target_id"] == "curated_plugin"
    assert listed.status_code == 200
    assert listed.json()["total"] >= 1
    assert any(item["id"] == created.json()["id"] for item in listed.json()["items"])
    assert updated.status_code == 200
    assert updated.json()["audience"] == "logged_in"
    assert disabled.status_code == 200
    assert disabled.json()["enabled"] is False


async def test_admin_curation_reorder_persists_order(client: AsyncClient) -> None:
    for plugin_id in ("curation_a", "curation_b", "curation_c"):
        await client.post(
            "/api/v1/plugins",
            json=plugin_payload(plugin_id, display_name=plugin_id),
            headers=AUTHOR_HEADERS,
        )

    first = await client.post(
        "/api/v1/admin/curation/entries",
        json={"slot_type": "featured_plugin", "target_type": "plugin", "target_id": "curation_a"},
        headers=ADMIN_HEADERS,
    )
    second = await client.post(
        "/api/v1/admin/curation/entries",
        json={"slot_type": "featured_plugin", "target_type": "plugin", "target_id": "curation_b"},
        headers=ADMIN_HEADERS,
    )
    third = await client.post(
        "/api/v1/admin/curation/entries",
        json={"slot_type": "featured_plugin", "target_type": "plugin", "target_id": "curation_c"},
        headers=ADMIN_HEADERS,
    )

    reordered = await client.put(
        "/api/v1/admin/curation/order",
        json={"ids_in_order": [third.json()["id"], first.json()["id"], second.json()["id"]]},
        headers=ADMIN_HEADERS,
    )
    listed = await client.get("/api/v1/admin/curation/entries", headers=ADMIN_HEADERS)

    assert reordered.status_code == 200
    assert [item["id"] for item in reordered.json()] == [third.json()["id"], first.json()["id"], second.json()["id"]]
    assert [item["sort_order"] for item in reordered.json()] == [0, 1, 2]
    assert [item["id"] for item in listed.json()["items"][:3]] == [third.json()["id"], first.json()["id"], second.json()["id"]]