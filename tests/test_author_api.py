"""Author and CLI API tests."""

from __future__ import annotations

from datetime import UTC, datetime

from httpx import AsyncClient
from plugin_market_backend.database import session_scope
from plugin_market_backend.session_auth import create_browser_session
from plugin_market_backend.service import MarketService

AUTHOR_HEADERS = {"Authorization": "Bearer dev-token"}
PNG_BASE64 = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO5W7i8AAAAASUVORK5CYII="


def plugin_payload(plugin_id: str = "sample_plugin", *, display_name: str = "Sample Plugin") -> dict[str, object]:
    """Return a valid plugin registration payload."""

    return {
        "plugin_id": plugin_id,
        "display_name": display_name,
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


def parse_api_datetime(value: str) -> datetime:
    """Parse FastAPI ISO datetime payloads into aware datetimes."""

    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=UTC)


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


async def test_submit_version_updates_plugin_timestamp_and_readme(client: AsyncClient) -> None:
    """Version submission should refresh plugin freshness metadata and README content."""

    payload = plugin_payload()
    payload["readme_markdown"] = "# Sample Plugin\n\nOld README."
    created = await client.post("/api/v1/plugins", json=payload, headers=AUTHOR_HEADERS)
    original_updated_at = parse_api_datetime(created.json()["updated_at"])

    release_payload = version_payload()
    release_payload["readme_markdown"] = "# Sample Plugin\n\nNew README."
    submitted = await client.post(
        "/api/v1/plugins/sample_plugin/versions",
        json=release_payload,
        headers=AUTHOR_HEADERS,
    )
    detail = await client.get("/api/v1/plugins/sample_plugin")
    readme = await client.get("/api/v1/plugins/sample_plugin/readme")

    assert submitted.status_code == 200
    assert parse_api_datetime(detail.json()["updated_at"]) >= original_updated_at
    assert readme.status_code == 200
    assert readme.json()["exists"] is True
    assert "New README." in readme.json()["html"]


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


async def test_register_plugin_stores_icon_and_readme(client: AsyncClient) -> None:
    """Plugin registration should normalize icon uploads and expose README availability."""

    payload = plugin_payload()
    payload["icon_png_base64"] = PNG_BASE64
    payload["readme_markdown"] = "# Sample Plugin\n\n**Hello** from the README."

    response = await client.post("/api/v1/plugins", json=payload, headers=AUTHOR_HEADERS)
    readme = await client.get("/api/v1/plugins/sample_plugin/readme")

    assert response.status_code == 200
    assert response.json()["icon_url"] == "/plugin-media/icons/sample_plugin.png"
    assert response.json()["has_readme"] is True
    assert readme.status_code == 200
    assert readme.json()["exists"] is True
    assert "<h1>Sample Plugin</h1>" in readme.json()["html"]
    assert "<strong>Hello</strong>" in readme.json()["html"]


async def test_register_plugin_stores_plugin_dependencies(client: AsyncClient) -> None:
    """Plugin registration should persist dependency metadata for detail views."""

    await client.post(
        "/api/v1/plugins",
        json=plugin_payload("asr_adapter", display_name="ASR Adapter"),
        headers=AUTHOR_HEADERS,
    )
    payload = plugin_payload("funasr_asr_provider", display_name="FunASR Provider")
    payload["plugin_dependencies"] = ["asr_adapter>=1.0.0", "missing_plugin"]

    response = await client.post("/api/v1/plugins", json=payload, headers=AUTHOR_HEADERS)
    dependencies = await client.get("/api/v1/plugins/funasr_asr_provider/dependencies")

    assert response.status_code == 200
    assert dependencies.status_code == 200
    assert dependencies.json()["items"][0]["plugin_id"] == "asr_adapter"
    assert dependencies.json()["items"][0]["version_spec"] == ">=1.0.0"
    assert dependencies.json()["items"][0]["exists_in_market"] is True
    assert dependencies.json()["items"][0]["display_name"] == "ASR Adapter"
    assert dependencies.json()["items"][1]["plugin_id"] == "missing_plugin"
    assert dependencies.json()["items"][1]["exists_in_market"] is False


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


async def test_me_profile_get_update_and_public_author_profile(client: AsyncClient) -> None:
    """Browser users should manage their own profile and expose it publicly."""

    session_id = await create_browser_session("mock-author", "browser-test-token")
    client.cookies.set("plugin_market_session", session_id, path="/")

    initial = await client.get("/api/v1/me/profile")
    updated = await client.put(
        "/api/v1/me/profile",
        json={
            "bio": "Hello from MoFox",
            "background_image_url": "https://cdn.example.com/profile-bg.png",
        },
    )
    public = await client.get("/api/v1/authors/mock-author/profile")

    assert initial.status_code == 200
    assert initial.json()["bio"] == ""
    assert initial.json()["background_image_url"] is None
    assert updated.status_code == 200
    assert updated.json()["bio"] == "Hello from MoFox"
    assert updated.json()["background_image_url"] == "https://cdn.example.com/profile-bg.png"
    assert public.status_code == 200
    assert public.json()["author_id"] == "mock-author"
    assert public.json()["bio"] == "Hello from MoFox"


async def test_me_pins_crud_via_browser_session(client: AsyncClient) -> None:
    """Browser users should add, edit, list and remove their own pins."""

    await client.post("/api/v1/plugins", json=plugin_payload(), headers=AUTHOR_HEADERS)
    session_id = await create_browser_session("mock-author", "browser-test-token")
    client.cookies.set("plugin_market_session", session_id, path="/")

    created = await client.post(
        "/api/v1/me/pins",
        json={"plugin_id": "sample_plugin", "pinned_reason": "featured"},
    )
    listed = await client.get("/api/v1/me/pins")
    updated = await client.put(
        "/api/v1/me/pins/sample_plugin",
        json={"pinned_reason": "updated reason"},
    )
    deleted = await client.delete("/api/v1/me/pins/sample_plugin")
    empty = await client.get("/api/v1/me/pins")

    assert created.status_code == 200
    assert created.json()["plugin_id"] == "sample_plugin"
    assert created.json()["pinned_reason"] == "featured"
    assert listed.status_code == 200
    assert [item["plugin_id"] for item in listed.json()] == ["sample_plugin"]
    assert updated.status_code == 200
    assert updated.json()["pinned_reason"] == "updated reason"
    assert deleted.status_code == 204
    assert empty.status_code == 200
    assert empty.json() == []


async def test_me_plugin_metadata_patch_via_browser_session(client: AsyncClient) -> None:
    """Browser users should patch display-facing plugin metadata inline."""

    await client.post("/api/v1/plugins", json=plugin_payload(), headers=AUTHOR_HEADERS)
    session_id = await create_browser_session("mock-author", "browser-test-token")
    client.cookies.set("plugin_market_session", session_id, path="/")

    response = await client.patch(
        "/api/v1/me/plugins/sample_plugin/metadata",
        json={
            "display_name": "Browser Edited Plugin",
            "tags": ["sample", "browser"],
        },
    )

    assert response.status_code == 200
    assert response.json()["display_name"] == "Browser Edited Plugin"
    assert response.json()["tags"] == ["sample", "browser"]


async def test_comment_submit_accepts_forwarded_https_origin(client: AsyncClient) -> None:
    """Browser writes should stay allowed behind an HTTPS reverse proxy."""

    await client.post("/api/v1/plugins", json=plugin_payload(), headers=AUTHOR_HEADERS)
    session_id = await create_browser_session("mock-author", "browser-test-token")
    client.cookies.set("plugin_market_session", session_id, path="/")

    response = await client.post(
        "/api/v1/plugins/sample_plugin/comments",
        json={"content": "Looks good."},
        headers={
            "Origin": "https://market.mofox-sama.com",
            "X-Forwarded-Proto": "https",
            "X-Forwarded-Host": "market.mofox-sama.com",
            "Host": "127.0.0.1:8787",
        },
    )

    assert response.status_code == 200
    assert response.json()["content"] == "Looks good."


async def test_author_search_and_comment_mentions_round_trip(client: AsyncClient) -> None:
    """Author search and listed comments should expose resolved mention metadata."""

    await client.post("/api/v1/plugins", json=plugin_payload(), headers=AUTHOR_HEADERS)
    async with session_scope() as session:
        await MarketService(session).ensure_author(
            "alpha",
            github_user_id="id-alpha",
            github_login="alpha",
            display_name="Alpha",
        )
    session_id = await create_browser_session("mock-author", "browser-test-token")
    client.cookies.set("plugin_market_session", session_id, path="/")

    searched = await client.get("/api/v1/authors/search", params={"prefix": "al"})
    created = await client.post(
        "/api/v1/plugins/sample_plugin/comments",
        json={"content": "请 @alpha 看看这个版本。"},
    )
    listed = await client.get("/api/v1/plugins/sample_plugin/comments")

    assert searched.status_code == 200
    assert searched.json()[0]["author_id"] == "alpha"
    assert created.status_code == 200
    assert created.json()["mentions"][0]["author_id"] == "alpha"
    assert listed.status_code == 200
    assert listed.json()["items"][0]["mentions"][0]["github_login"] == "alpha"
