"""API tests for inbox browser endpoints (task 13)."""

from __future__ import annotations

from httpx import AsyncClient

from plugin_market_backend.database import session_scope
from plugin_market_backend.orm import InboxMessageORM, utc_now
from plugin_market_backend.session_auth import create_browser_session


async def _seed_message(
    recipient_id: str,
    *,
    type: str = "mention",
    status: str = "unread",
    preview: str = "hello",
    related_plugin_id: str | None = None,
) -> int:
    async with session_scope() as session:
        row = InboxMessageORM(
            recipient_id=recipient_id,
            type=type,
            status=status,
            payload={"preview": preview},
            dedup_key=f"{type}:{recipient_id}:{preview}:{utc_now().timestamp()}",
            related_plugin_id=related_plugin_id,
            created_at=utc_now(),
            read_at=None,
        )
        session.add(row)
        await session.flush()
        return int(row.id)


async def test_inbox_list_and_unread_count_scope_to_browser_user(client: AsyncClient) -> None:
    viewer_session = await create_browser_session("mock-author", "browser-test-token")
    client.cookies.set("plugin_market_session", viewer_session, path="/")

    await _seed_message("mock-author", type="mention", preview="first")
    await _seed_message("mock-author", type="reply", preview="second")
    await _seed_message("mock-admin", type="system", preview="other-user")

    listed = await client.get("/api/v1/inbox/messages")
    unread = await client.get("/api/v1/inbox/unread-count")

    assert listed.status_code == 200
    assert listed.json()["total"] == 2
    assert len(listed.json()["items"]) == 2
    assert {item["type"] for item in listed.json()["items"]} == {"mention", "reply"}
    assert unread.status_code == 200
    assert unread.json()["count"] == 2


async def test_inbox_mark_read_and_mark_all_read(client: AsyncClient) -> None:
    viewer_session = await create_browser_session("mock-author", "browser-test-token")
    client.cookies.set("plugin_market_session", viewer_session, path="/")

    first = await _seed_message("mock-author", preview="first")
    await _seed_message("mock-author", preview="second")

    marked = await client.post(f"/api/v1/inbox/messages/{first}/read")
    after_one = await client.get("/api/v1/inbox/unread-count")
    marked_all = await client.post("/api/v1/inbox/read-all")
    after_all = await client.get("/api/v1/inbox/unread-count")

    assert marked.status_code == 200
    assert marked.json()["updated"] == 1
    assert after_one.json()["count"] == 1
    assert marked_all.status_code == 200
    assert marked_all.json()["updated"] == 1
    assert after_all.json()["count"] == 0


async def test_inbox_mark_read_rejects_other_users_message(client: AsyncClient) -> None:
    viewer_session = await create_browser_session("mock-author", "browser-test-token")
    client.cookies.set("plugin_market_session", viewer_session, path="/")

    foreign_message_id = await _seed_message("mock-admin", preview="foreign")
    response = await client.post(f"/api/v1/inbox/messages/{foreign_message_id}/read")

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "INBOX_FORBIDDEN"