"""管理员模拟 API 测试。"""

from __future__ import annotations

from httpx import AsyncClient
from test_author_api import AUTHOR_HEADERS, plugin_payload, version_payload

ADMIN_HEADERS = {"Authorization": "Bearer admin-token"}


async def test_admin_requires_admin_token(client: AsyncClient) -> None:
    """管理员端点应拒绝作者令牌。"""
    response = await client.get("/api/v1/admin/reviews", headers=AUTHOR_HEADERS)

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "FORBIDDEN"


async def test_admin_yank_version(client: AsyncClient) -> None:
    """管理员应能撤回已发布的版本。"""
    await client.post("/api/v1/plugins", json=plugin_payload(), headers=AUTHOR_HEADERS)
    await client.post("/api/v1/plugins/sample_plugin/versions", json=version_payload(), headers=AUTHOR_HEADERS)
    yanked = await client.post("/api/v1/admin/plugins/sample_plugin/versions/1.0.0/yank", json={"reason": "回归问题"}, headers=ADMIN_HEADERS)

    assert yanked.status_code == 200
    assert yanked.json()["status"] == "yanked"
    assert yanked.json()["is_yanked"] is True


async def test_admin_delete_plugin_clears_market_records(client: AsyncClient) -> None:
    """管理员删除插件时应一并移除相关审核记录。"""
    await client.post("/api/v1/plugins", json=plugin_payload(), headers=AUTHOR_HEADERS)
    await client.post("/api/v1/plugins/sample_plugin/versions", json=version_payload(), headers=AUTHOR_HEADERS)

    deleted = await client.delete("/api/v1/admin/plugins/sample_plugin", headers=ADMIN_HEADERS)
    plugin = await client.get("/api/v1/plugins/sample_plugin")
    versions = await client.get("/api/v1/plugins/sample_plugin/versions")
    status = await client.get("/api/v1/plugins/sample_plugin/status", headers=AUTHOR_HEADERS)
    reviews = await client.get("/api/v1/admin/reviews", headers=ADMIN_HEADERS)

    assert deleted.status_code == 204
    assert plugin.status_code == 404
    assert versions.status_code == 404
    assert status.status_code == 404
    assert all(item["target_id"] != "sample_plugin" and not item["target_id"].startswith("sample_plugin@") for item in reviews.json())


async def test_admin_deprecate_plugin_and_block_version(client: AsyncClient) -> None:
    """管理员应能弃用插件并封禁版本。"""
    await client.post("/api/v1/plugins", json=plugin_payload(), headers=AUTHOR_HEADERS)
    await client.post("/api/v1/plugins/sample_plugin/versions", json=version_payload(), headers=AUTHOR_HEADERS)
    deprecated = await client.post("/api/v1/admin/plugins/sample_plugin/deprecate", json={"reason": "已过时"}, headers=ADMIN_HEADERS)
    blocked = await client.post("/api/v1/admin/plugins/sample_plugin/versions/1.0.0/block", json={"reason": "存在风险"}, headers=ADMIN_HEADERS)

    assert deprecated.status_code == 200
    assert deprecated.json()["status"] == "deprecated"
    assert blocked.status_code == 200
    assert blocked.json()["status"] == "blocked"


async def test_admin_stats(client: AsyncClient) -> None:
    """管理员统计应提供汇总计数。"""
    response = await client.get("/api/v1/admin/stats", headers=ADMIN_HEADERS)

    assert response.status_code == 200
    assert response.json()["plugins_total"] >= 1
    assert response.json()["versions_total"] >= 1


async def test_admin_reviews_include_actions(client: AsyncClient) -> None:
    """审核记录应包含模拟审计操作。"""
    response = await client.get("/api/v1/admin/reviews", headers=ADMIN_HEADERS)

    assert response.status_code == 200
    assert any(item["action"] == "register_plugin" for item in response.json())


async def test_admin_can_republish_plugin_and_restore_version(client: AsyncClient) -> None:
    """管理员应能在治理操作后重新发布插件和版本。"""
    await client.post("/api/v1/plugins", json=plugin_payload(), headers=AUTHOR_HEADERS)
    await client.post("/api/v1/plugins/sample_plugin/versions", json=version_payload(), headers=AUTHOR_HEADERS)
    await client.post("/api/v1/admin/plugins/sample_plugin/block", json={"reason": "存在风险"}, headers=ADMIN_HEADERS)
    await client.post(
        "/api/v1/admin/plugins/sample_plugin/versions/1.0.0/yank",
        json={"reason": "回滚"},
        headers=ADMIN_HEADERS,
    )

    plugin = await client.post("/api/v1/admin/plugins/sample_plugin/publish", json={"reason": "已修复"}, headers=ADMIN_HEADERS)
    version = await client.post(
        "/api/v1/admin/plugins/sample_plugin/versions/1.0.0/publish",
        json={"reason": "已修复"},
        headers=ADMIN_HEADERS,
    )
    dashboard = await client.get("/api/v1/admin/dashboard", headers=ADMIN_HEADERS)

    assert plugin.status_code == 200
    assert plugin.json()["status"] == "published"
    assert version.status_code == 200
    assert version.json()["status"] == "published"
    assert version.json()["is_yanked"] is False
    assert dashboard.status_code == 200
    assert "comments_total" in dashboard.json()["stats"]


async def test_admin_can_switch_plugin_trust_level(client: AsyncClient) -> None:
    """管理员应能更改插件的信任标识。"""
    await client.post("/api/v1/plugins", json=plugin_payload(), headers=AUTHOR_HEADERS)

    updated = await client.post(
        "/api/v1/admin/plugins/sample_plugin/trust-level/official",
        json={"reason": "内部插件"},
        headers=ADMIN_HEADERS,
    )
    reviews = await client.get("/api/v1/admin/reviews", headers=ADMIN_HEADERS)

    assert updated.status_code == 200
    assert updated.json()["trust_level"] == "official"
    assert any(item["action"] == "set_trust_level" for item in reviews.json())
