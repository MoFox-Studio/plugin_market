"""Author and CLI API tests."""

from __future__ import annotations

from httpx import AsyncClient
from plugin_market_backend.session_auth import create_browser_session

AUTHOR_HEADERS = {"Authorization": "Bearer dev-token"}


def plugin_payload(plugin_id: str = "sample_plugin") -> dict[str, object]:
    """Return a valid plugin registration payload."""

    return {
        "plugin_id": plugin_id,
        "display_name": "Sample Plugin",
        "summary": "Sample summary",
        "description": "Sample description",
        "homepage": "https://example.com/sample_plugin",
        "repository_url": "https://github.com/MoFox-Studio/sample_plugin",
        "license": "MIT",
        "categories": ["tool"],
        "tags": ["sample"],
        "maintainers": ["mock-author"],
    }


def version_payload(version: str = "1.0.0") -> dict[str, object]:
    """Return a valid version submission payload."""

    return {
        "version": version,
        "release_tag": f"v{version}",
        "release_title": f"Sample Plugin {version}",
        "release_url": f"https://github.com/MoFox-Studio/sample_plugin/releases/tag/v{version}",
        "asset_name": f"sample_plugin-{version}.mfp",
        "asset_download_url": f"https://github.com/MoFox-Studio/sample_plugin/releases/download/v{version}/sample_plugin-{version}.mfp",
        "checksum_sha256": "b" * 64,
        "file_size": 4567,
        "is_prerelease": False,
        "plugin_api_version": "1.0",
        "min_host_version": "1.0.0",
        "max_host_version": None,
        "supported_platforms": ["all"],
    }


async def test_register_plugin_requires_author_token(client: AsyncClient) -> None:
    """Author endpoints should reject missing auth."""

    response = await client.post("/api/v1/plugins", json=plugin_payload())

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHORIZED"


async def test_register_plugin_and_duplicate_conflict(client: AsyncClient) -> None:
    """Registration should publish immediately and reject duplicates."""

    created = await client.post("/api/v1/plugins", json=plugin_payload(), headers=AUTHOR_HEADERS)
    duplicate = await client.post("/api/v1/plugins", json=plugin_payload(), headers=AUTHOR_HEADERS)

    assert created.status_code == 200
    assert created.json()["plugin_id"] == "sample_plugin"
    assert created.json()["status"] == "published"
    assert duplicate.status_code == 409
    assert duplicate.json()["error"]["code"] == "PLUGIN_ALREADY_EXISTS"


async def test_submit_version_status_and_duplicate_conflict(client: AsyncClient) -> None:
    """Version submission should publish immediately and reject duplicates."""

    await client.post("/api/v1/plugins", json=plugin_payload(), headers=AUTHOR_HEADERS)
    created = await client.post("/api/v1/plugins/sample_plugin/versions", json=version_payload(), headers=AUTHOR_HEADERS)
    duplicate = await client.post("/api/v1/plugins/sample_plugin/versions", json=version_payload(), headers=AUTHOR_HEADERS)
    status = await client.get("/api/v1/plugins/sample_plugin/status", headers=AUTHOR_HEADERS)

    assert created.status_code == 200
    assert created.json()["status"] == "published"
    assert duplicate.status_code == 409
    assert duplicate.json()["error"]["code"] == "VERSION_ALREADY_EXISTS"
    assert status.status_code == 200
    assert status.json()["plugin_status"] == "published"
    assert status.json()["versions"][0]["version"] == "1.0.0"
    assert status.json()["versions"][0]["status"] == "published"


async def test_sync_version_updates_metadata(client: AsyncClient) -> None:
    """Sync should update mutable release metadata and mark sync success."""

    await client.post("/api/v1/plugins", json=plugin_payload(), headers=AUTHOR_HEADERS)
    await client.post("/api/v1/plugins/sample_plugin/versions", json=version_payload(), headers=AUTHOR_HEADERS)
    response = await client.post(
        "/api/v1/plugins/sample_plugin/sync",
        json={"version": "1.0.0", "file_size": 9999, "checksum_sha256": "c" * 64},
        headers=AUTHOR_HEADERS,
    )

    assert response.status_code == 200
    assert response.json()["file_size"] == 9999
    assert response.json()["checksum_sha256"] == "c" * 64
    assert response.json()["last_sync_status"] == "success"


async def test_update_plugin_metadata_returns_pending_review(client: AsyncClient) -> None:
    """Plugin metadata updates should remain published for the owner."""

    await client.post("/api/v1/plugins", json=plugin_payload(), headers=AUTHOR_HEADERS)
    response = await client.put(
        "/api/v1/plugins/sample_plugin",
        json={"summary": "Updated summary", "tags": ["sample", "updated"]},
        headers=AUTHOR_HEADERS,
    )

    assert response.status_code == 200
    assert response.json()["summary"] == "Updated summary"
    assert response.json()["tags"] == ["sample", "updated"]
    assert response.json()["status"] == "published"


async def test_author_yank_version(client: AsyncClient) -> None:
    """Plugin owners should be able to yank a version."""

    await client.post("/api/v1/plugins", json=plugin_payload(), headers=AUTHOR_HEADERS)
    await client.post("/api/v1/plugins/sample_plugin/versions", json=version_payload(), headers=AUTHOR_HEADERS)
    response = await client.post(
        "/api/v1/plugins/sample_plugin/versions/1.0.0/yank",
        json={"reason": "Bad release"},
        headers=AUTHOR_HEADERS,
    )

    assert response.status_code == 200
    assert response.json()["status"] == "yanked"
    assert response.json()["is_yanked"] is True


async def test_me_plugin_management_snapshot_and_delete(client: AsyncClient) -> None:
    """Logged-in browser users should be able to inspect and delete their own plugins."""

    await client.post("/api/v1/plugins", json=plugin_payload(), headers=AUTHOR_HEADERS)
    await client.post("/api/v1/plugins/sample_plugin/versions", json=version_payload(), headers=AUTHOR_HEADERS)
    session_id = await create_browser_session("mock-author", "browser-test-token")
    client.cookies.set("plugin_market_session", session_id, path="/")

    snapshot = await client.get("/api/v1/me/plugins/sample_plugin")
    deleted = await client.delete("/api/v1/me/plugins/sample_plugin")
    missing = await client.get("/api/v1/plugins/sample_plugin")

    assert snapshot.status_code == 200
    assert snapshot.json()["plugin"]["plugin_id"] == "sample_plugin"
    assert snapshot.json()["versions"][0]["version"] == "1.0.0"
    assert deleted.status_code == 204
    assert missing.status_code == 404
