"""Public plugin market API tests."""

from __future__ import annotations

from httpx import AsyncClient
from test_author_api import AUTHOR_HEADERS, plugin_payload, version_payload


async def test_list_plugins_returns_seed_data(client: AsyncClient) -> None:
    """The public list endpoint should expose seeded plugin data."""

    response = await client.get("/api/v1/plugins")
    body = response.json()

    assert response.status_code == 200
    assert body["total"] == 1
    assert body["items"][0]["plugin_id"] == "demo_plugin"


async def test_list_plugins_filters_and_paginates(client: AsyncClient) -> None:
    """Public plugin search should support basic filters and pagination."""

    response = await client.get("/api/v1/plugins", params={"q": "demo", "category": "tool", "tag": "utility", "limit": 1})
    body = response.json()

    assert response.status_code == 200
    assert body["total"] == 1
    assert len(body["items"]) == 1


async def test_public_plugin_detail_and_versions(client: AsyncClient) -> None:
    """Plugin details, versions and recommendation should be available."""

    detail = await client.get("/api/v1/plugins/demo_plugin")
    versions = await client.get("/api/v1/plugins/demo_plugin/versions")
    recommended = await client.get("/api/v1/plugins/demo_plugin/recommended-version")

    assert detail.status_code == 200
    assert detail.json()["status"] == "published"
    assert versions.status_code == 200
    assert versions.json()["items"][0]["version"] == "1.0.0"
    assert recommended.status_code == 200
    assert recommended.json()["version"] == "1.0.0"


async def test_public_plugin_readme_endpoint(client: AsyncClient) -> None:
    """README endpoint should report absence cleanly for plugins without README content."""

    response = await client.get("/api/v1/plugins/demo_plugin/readme")

    assert response.status_code == 200
    assert response.json() == {"plugin_id": "demo_plugin", "exists": False, "html": None}


async def test_public_plugin_dependencies_endpoint(client: AsyncClient) -> None:
    """Dependency endpoint should resolve marketplace matches and preserve version constraints."""

    await client.post("/api/v1/plugins", json=plugin_payload("asr_adapter", display_name="ASR Adapter"), headers=AUTHOR_HEADERS)
    payload = plugin_payload("funasr_asr_provider", display_name="FunASR Provider")
    payload["plugin_dependencies"] = ["asr_adapter>=1.0.0"]
    await client.post("/api/v1/plugins", json=payload, headers=AUTHOR_HEADERS)

    response = await client.get("/api/v1/plugins/funasr_asr_provider/dependencies")

    assert response.status_code == 200
    assert response.json() == {
        "plugin_id": "funasr_asr_provider",
        "items": [
            {
                "plugin_id": "asr_adapter",
                "raw": "asr_adapter>=1.0.0",
                "version_spec": ">=1.0.0",
                "exists_in_market": True,
                "display_name": "ASR Adapter",
                "icon_url": None,
            }
        ],
    }


async def test_public_install_info(client: AsyncClient) -> None:
    """Install info should include plugin and recommended version metadata."""

    response = await client.get("/api/v1/plugins/demo_plugin/install")

    assert response.status_code == 200
    assert response.json()["plugin"]["plugin_id"] == "demo_plugin"
    assert response.json()["version"]["version"] == "1.0.0"


async def test_public_versions_are_visible_immediately_after_publish(client: AsyncClient) -> None:
    """Fresh author submissions should be installable from public endpoints immediately."""

    await client.post("/api/v1/plugins", json=plugin_payload(), headers=AUTHOR_HEADERS)
    await client.post("/api/v1/plugins/sample_plugin/versions", json=version_payload(), headers=AUTHOR_HEADERS)

    detail = await client.get("/api/v1/plugins/sample_plugin")
    versions = await client.get("/api/v1/plugins/sample_plugin/versions")
    recommended = await client.get("/api/v1/plugins/sample_plugin/recommended-version")
    install = await client.get("/api/v1/plugins/sample_plugin/install")

    assert detail.status_code == 200
    assert detail.json()["status"] == "published"
    assert detail.json()["latest_version"] == "1.0.0"
    assert versions.status_code == 200
    assert versions.json()["items"][0]["version"] == "1.0.0"
    assert versions.json()["items"][0]["status"] == "published"
    assert recommended.status_code == 200
    assert recommended.json()["version"] == "1.0.0"
    assert install.status_code == 200
    assert install.json()["version"]["version"] == "1.0.0"


async def test_taxonomy_endpoints(client: AsyncClient) -> None:
    """Categories and tags should be derived from stored plugins."""

    categories = await client.get("/api/v1/categories")
    tags = await client.get("/api/v1/tags")

    assert categories.json()["items"] == ["tool"]
    assert tags.json()["items"] == ["demo", "utility"]


async def test_not_found_uses_error_envelope(client: AsyncClient) -> None:
    """Missing plugins should use the uniform error response."""

    response = await client.get("/api/v1/plugins/missing_plugin")
    body = response.json()

    assert response.status_code == 404
    assert body["error"]["code"] == "PLUGIN_NOT_FOUND"
    assert body["error"]["details"] == {"plugin_id": "missing_plugin"}
