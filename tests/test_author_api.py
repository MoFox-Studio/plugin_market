"""作者及 CLI API 测试。"""

from __future__ import annotations

from datetime import UTC, datetime

from httpx import AsyncClient
from plugin_market_backend.database import session_scope
from plugin_market_backend.session_auth import create_browser_session
from plugin_market_backend.service import MarketService

AUTHOR_HEADERS = {"Authorization": "Bearer dev-token"}
PNG_BASE64 = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO5W7i8AAAAASUVORK5CYII="


def plugin_payload(plugin_id: str = "sample_plugin", *, display_name: str = "示例插件") -> dict[str, object]:
    """返回有效的插件注册请求体。

    Args:
        plugin_id: 插件标识。
        display_name: 插件展示名称。

    Returns:
        包含插件注册字段的字典。
    """
    return {
        "plugin_id": plugin_id,
        "display_name": display_name,
        "summary": "示例摘要",
        "description": "示例说明",
        "homepage": "https://example.com/sample_plugin",
        "repository_url": "https://github.com/MoFox-Studio/sample_plugin",
        "license": "MIT",
        "categories": ["tool"],
        "tags": ["sample"],
        "maintainers": ["mock-author"],
    }


def version_payload(version: str = "1.0.0") -> dict[str, object]:
    """返回有效的版本提交请求体。

    Args:
        version: 待提交的版本号。

    Returns:
        包含版本提交字段的字典。
    """
    return {
        "version": version,
        "release_tag": f"v{version}",
        "release_title": f"示例插件 {version}",
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
    """将 FastAPI 的 ISO 日期时间字段解析为带时区的日期时间。

    Args:
        value: API 返回的 ISO 日期时间字符串。

    Returns:
        带时区的日期时间；未提供时区时使用 UTC。
    """
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=UTC)


async def test_register_plugin_requires_author_token(client: AsyncClient) -> None:
    """作者端点应拒绝未认证的请求。"""
    response = await client.post("/api/v1/plugins", json=plugin_payload())

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHORIZED"


async def test_register_plugin_and_duplicate_conflict(client: AsyncClient) -> None:
    """注册插件后应立即发布，并拒绝重复注册。"""
    created = await client.post("/api/v1/plugins", json=plugin_payload(), headers=AUTHOR_HEADERS)
    duplicate = await client.post("/api/v1/plugins", json=plugin_payload(), headers=AUTHOR_HEADERS)

    assert created.status_code == 200
    assert created.json()["plugin_id"] == "sample_plugin"
    assert created.json()["status"] == "published"
    assert duplicate.status_code == 409
    assert duplicate.json()["error"]["code"] == "PLUGIN_ALREADY_EXISTS"


async def test_register_plugin_creates_missing_late_maintainer_without_autoflush_fk_error(client: AsyncClient) -> None:
    """注册时应在刷新维护者关系前创建列表后部缺失的维护者。"""
    payload = plugin_payload("group_news", display_name="群聊新闻")
    payload["maintainers"] = ["mock-author", "KKKKKaoriiiii"]

    response = await client.post("/api/v1/plugins", json=payload, headers=AUTHOR_HEADERS)

    assert response.status_code == 200
    assert response.json()["plugin_id"] == "group_news"
    assert response.json()["maintainers"] == ["mock-author", "KKKKKaoriiiii"]


async def test_register_plugin_reuses_canonical_author_id_for_existing_github_login(client: AsyncClient) -> None:
    """注册时应使用已有的规范作者标识保存维护者记录。"""
    async with session_scope() as session:
        await MarketService(session).ensure_author(
            "github:kkkkkaoriiiii",
            github_login="KKKKKaoriiiii",
            display_name="Kaoriiiii",
        )

    payload = plugin_payload("canonical_group_news", display_name="规范作者群聊新闻")
    payload["maintainers"] = ["KKKKKaoriiiii"]

    response = await client.post("/api/v1/plugins", json=payload, headers=AUTHOR_HEADERS)

    assert response.status_code == 200
    assert response.json()["plugin_id"] == "canonical_group_news"
    assert response.json()["maintainers"] == ["github:kkkkkaoriiiii", "mock-author"]


async def test_submit_version_status_and_duplicate_conflict(client: AsyncClient) -> None:
    """提交版本后应立即发布，并拒绝重复提交。"""
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
    """同步应更新可变的发布元数据，并标记同步成功。"""
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
    """提交版本应刷新插件更新时间及 README 内容。"""
    payload = plugin_payload()
    payload["readme_markdown"] = "# 示例插件\n\n旧版 README。"
    created = await client.post("/api/v1/plugins", json=payload, headers=AUTHOR_HEADERS)
    original_updated_at = parse_api_datetime(created.json()["updated_at"])

    release_payload = version_payload()
    release_payload["readme_markdown"] = "# 示例插件\n\n新版 README。"
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
    assert "新版 README。" in readme.json()["html"]


async def test_update_plugin_metadata_returns_pending_review(client: AsyncClient) -> None:
    """所有者更新插件元数据后，插件应保持已发布状态。"""
    await client.post("/api/v1/plugins", json=plugin_payload(), headers=AUTHOR_HEADERS)
    response = await client.put(
        "/api/v1/plugins/sample_plugin",
        json={"summary": "更新后的摘要", "tags": ["sample", "updated"]},
        headers=AUTHOR_HEADERS,
    )

    assert response.status_code == 200
    assert response.json()["summary"] == "更新后的摘要"
    assert response.json()["tags"] == ["sample", "updated"]
    assert response.json()["status"] == "published"


async def test_register_plugin_stores_icon_and_readme(client: AsyncClient) -> None:
    """注册插件应规范化上传图标，并返回 README 是否可用。"""
    payload = plugin_payload()
    payload["icon_png_base64"] = PNG_BASE64
    payload["readme_markdown"] = "# 示例插件\n\n**你好**，来自 README。"

    response = await client.post("/api/v1/plugins", json=payload, headers=AUTHOR_HEADERS)
    readme = await client.get("/api/v1/plugins/sample_plugin/readme")

    assert response.status_code == 200
    assert response.json()["icon_url"] == "/plugin-media/icons/sample_plugin.png"
    assert response.json()["has_readme"] is True
    assert readme.status_code == 200
    assert readme.json()["exists"] is True
    assert "<h1>示例插件</h1>" in readme.json()["html"]
    assert "<strong>你好</strong>" in readme.json()["html"]


async def test_register_plugin_stores_plugin_dependencies(client: AsyncClient) -> None:
    """注册插件应持久化依赖元数据，以供详情展示。"""
    await client.post(
        "/api/v1/plugins",
        json=plugin_payload("asr_adapter", display_name="ASR 适配器"),
        headers=AUTHOR_HEADERS,
    )
    payload = plugin_payload("funasr_asr_provider", display_name="FunASR 提供器")
    payload["plugin_dependencies"] = ["asr_adapter>=1.0.0", "missing_plugin"]

    response = await client.post("/api/v1/plugins", json=payload, headers=AUTHOR_HEADERS)
    dependencies = await client.get("/api/v1/plugins/funasr_asr_provider/dependencies")

    assert response.status_code == 200
    assert dependencies.status_code == 200
    assert dependencies.json()["items"][0]["plugin_id"] == "asr_adapter"
    assert dependencies.json()["items"][0]["version_spec"] == ">=1.0.0"
    assert dependencies.json()["items"][0]["exists_in_market"] is True
    assert dependencies.json()["items"][0]["display_name"] == "ASR 适配器"
    assert dependencies.json()["items"][1]["plugin_id"] == "missing_plugin"
    assert dependencies.json()["items"][1]["exists_in_market"] is False


async def test_author_yank_version(client: AsyncClient) -> None:
    """插件所有者应能撤回版本。"""
    await client.post("/api/v1/plugins", json=plugin_payload(), headers=AUTHOR_HEADERS)
    await client.post("/api/v1/plugins/sample_plugin/versions", json=version_payload(), headers=AUTHOR_HEADERS)
    response = await client.post(
        "/api/v1/plugins/sample_plugin/versions/1.0.0/yank",
        json={"reason": "有问题的版本"},
        headers=AUTHOR_HEADERS,
    )

    assert response.status_code == 200
    assert response.json()["status"] == "yanked"
    assert response.json()["is_yanked"] is True


async def test_me_plugin_management_snapshot_and_delete(client: AsyncClient) -> None:
    """已登录的浏览器用户应能查看和删除自己的插件。"""
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
    """浏览器用户应能管理自己的资料并公开展示。"""
    session_id = await create_browser_session("mock-author", "browser-test-token")
    client.cookies.set("plugin_market_session", session_id, path="/")

    initial = await client.get("/api/v1/me/profile")
    updated = await client.put(
        "/api/v1/me/profile",
        json={
            "bio": "来自 MoFox 的问候",
            "background_image_url": "https://cdn.example.com/profile-bg.png",
        },
    )
    public = await client.get("/api/v1/authors/mock-author/profile")

    assert initial.status_code == 200
    assert initial.json()["bio"] == ""
    assert initial.json()["background_image_url"] is None
    assert updated.status_code == 200
    assert updated.json()["bio"] == "来自 MoFox 的问候"
    assert updated.json()["background_image_url"] == "https://cdn.example.com/profile-bg.png"
    assert public.status_code == 200
    assert public.json()["author_id"] == "mock-author"
    assert public.json()["bio"] == "来自 MoFox 的问候"


async def test_me_pins_crud_via_browser_session(client: AsyncClient) -> None:
    """浏览器用户应能添加、编辑、列出和移除自己的置顶插件。"""
    await client.post("/api/v1/plugins", json=plugin_payload(), headers=AUTHOR_HEADERS)
    session_id = await create_browser_session("mock-author", "browser-test-token")
    client.cookies.set("plugin_market_session", session_id, path="/")

    created = await client.post(
        "/api/v1/me/pins",
        json={"plugin_id": "sample_plugin", "pinned_reason": "精选推荐"},
    )
    listed = await client.get("/api/v1/me/pins")
    updated = await client.put(
        "/api/v1/me/pins/sample_plugin",
        json={"pinned_reason": "更新后的理由"},
    )
    deleted = await client.delete("/api/v1/me/pins/sample_plugin")
    empty = await client.get("/api/v1/me/pins")

    assert created.status_code == 200
    assert created.json()["plugin_id"] == "sample_plugin"
    assert created.json()["pinned_reason"] == "精选推荐"
    assert listed.status_code == 200
    assert [item["plugin_id"] for item in listed.json()] == ["sample_plugin"]
    assert updated.status_code == 200
    assert updated.json()["pinned_reason"] == "更新后的理由"
    assert deleted.status_code == 204
    assert empty.status_code == 200
    assert empty.json() == []


async def test_me_plugin_metadata_patch_via_browser_session(client: AsyncClient) -> None:
    """浏览器用户应能行内更新用于展示的插件元数据。"""
    await client.post("/api/v1/plugins", json=plugin_payload(), headers=AUTHOR_HEADERS)
    session_id = await create_browser_session("mock-author", "browser-test-token")
    client.cookies.set("plugin_market_session", session_id, path="/")

    response = await client.patch(
        "/api/v1/me/plugins/sample_plugin/metadata",
        json={
            "display_name": "浏览器编辑的插件",
            "tags": ["sample", "browser"],
        },
    )

    assert response.status_code == 200
    assert response.json()["display_name"] == "浏览器编辑的插件"
    assert response.json()["tags"] == ["sample", "browser"]


async def test_comment_submit_accepts_forwarded_https_origin(client: AsyncClient) -> None:
    """通过 HTTPS 反向代理访问时，浏览器写入请求仍应获准。"""
    await client.post("/api/v1/plugins", json=plugin_payload(), headers=AUTHOR_HEADERS)
    session_id = await create_browser_session("mock-author", "browser-test-token")
    client.cookies.set("plugin_market_session", session_id, path="/")

    response = await client.post(
        "/api/v1/plugins/sample_plugin/comments",
        json={"content": "看起来不错。"},
        headers={
            "Origin": "https://market.mofox.chat",
            "X-Forwarded-Proto": "https",
            "X-Forwarded-Host": "market.mofox.chat",
            "Host": "127.0.0.1:8787",
        },
    )

    assert response.status_code == 200
    assert response.json()["content"] == "看起来不错。"


async def test_author_search_and_comment_mentions_round_trip(client: AsyncClient) -> None:
    """作者搜索和评论列表应包含已解析的提及元数据。"""
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


async def test_author_follow_toggle_via_browser_session(client: AsyncClient) -> None:
    """浏览器用户应能关注和取消关注其他作者。"""
    async with session_scope() as session:
        await MarketService(session).ensure_author(
            "alpha",
            github_user_id="id-alpha",
            github_login="alpha",
            display_name="Alpha",
        )
    session_id = await create_browser_session("mock-author", "browser-test-token")
    client.cookies.set("plugin_market_session", session_id, path="/")

    initial = await client.get("/api/v1/authors/alpha/follow")
    followed = await client.post("/api/v1/authors/alpha/follow")
    current = await client.get("/api/v1/authors/alpha/follow")
    unfollowed = await client.post("/api/v1/authors/alpha/follow")

    assert initial.status_code == 200
    assert initial.json()["following"] is False
    assert initial.json()["followers_count"] == 0
    assert followed.status_code == 200
    assert followed.json()["following"] is True
    assert followed.json()["followers_count"] == 1
    assert current.status_code == 200
    assert current.json()["following"] is True
    assert current.json()["followers_count"] == 1
    assert unfollowed.status_code == 200
    assert unfollowed.json()["following"] is False
    assert unfollowed.json()["followers_count"] == 0


async def test_subscription_and_rotated_access_token_machine_api(client: AsyncClient) -> None:
    """机器端读取应反映订阅状态，轮换令牌时应撤销旧令牌。"""
    await client.post("/api/v1/plugins", json=plugin_payload(), headers=AUTHOR_HEADERS)
    session_id = await create_browser_session("mock-author", "browser-test-token")
    client.cookies.set("plugin_market_session", session_id, path="/")

    subscribed = await client.post("/api/v1/plugins/sample_plugin/subscribe")
    detail = await client.get("/api/v1/plugins/sample_plugin")
    first_token = await client.post("/api/v1/me/access-token")
    token_status = await client.get("/api/v1/me/access-token")
    second_token = await client.post("/api/v1/me/access-token")
    second_status = await client.get("/api/v1/me/access-token")
    old_machine = await client.get(
        "/api/v1/machine/authors/mock-author/subscriptions",
        headers={"Authorization": f"Bearer {first_token.json()['token']}"},
    )
    new_machine = await client.get(
        "/api/v1/machine/authors/mock-author/subscriptions",
        headers={"Authorization": f"Bearer {second_token.json()['token']}"},
    )

    assert subscribed.status_code == 200
    assert subscribed.json()["subscribed"] is True
    assert subscribed.json()["subscriptions_count"] == 1
    assert detail.status_code == 200
    assert detail.json()["viewer_has_liked"] is True
    assert detail.json()["likes_count"] == 1
    assert first_token.status_code == 200
    assert first_token.json()["token"].startswith("mfox_")
    assert token_status.status_code == 200
    assert token_status.json()["has_token"] is True
    assert token_status.json()["token_preview"] == first_token.json()["token_preview"]
    assert second_token.status_code == 200
    assert second_token.json()["token"] != first_token.json()["token"]
    assert second_status.status_code == 200
    assert second_status.json()["token_preview"] == second_token.json()["token_preview"]
    assert old_machine.status_code == 403
    assert old_machine.json()["error"]["code"] == "FORBIDDEN"
    assert new_machine.status_code == 200
    assert new_machine.json()["author_id"] == "mock-author"
    assert new_machine.json()["total"] == 1
    assert new_machine.json()["items"][0]["plugin_id"] == "sample_plugin"
