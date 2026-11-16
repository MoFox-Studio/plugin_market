"""InboxService 的单元测试（任务 6）。

绕过 HTTP 层，独立验证 InboxService 的各项功能：

* parse_mentions 仅解析已有的 GitHub 登录名，过滤自我提及，并保持顺序和去重
  结果稳定（属性 10）。
* fan_out_for_comment 写入 comment_mentions，并准确派生预期的 mention 和 reply
  收件箱记录；独立测试验证回复优先于提及的规则（需求 10.6）。
* fan_out_for_governance 对所有者及维护者接收者执行 5 秒滑动窗口去重（需求 11.7）。
* fan_out_for_announcement 仅在 emit_inbox=True 时发送消息。
* revoke_messages_for_comment 将派生记录标记为 revoked。
* list_messages、unread_count、mark_read 和 mark_all_read 遵守接收者范围及已读状态模型。

复用 conftest.py 中的共享夹具，在每个测试前创建内存 SQLite 数据库并填充种子数据。
"""

from __future__ import annotations

from datetime import timedelta

import pytest
from sqlalchemy import select

from plugin_market_backend.database import session_scope
from plugin_market_backend.orm import (
    AnnouncementORM,
    AuthorORM,
    AuthorType,
    CommentMentionORM,
    InboxMessageORM,
    PluginCommentORM,
    PluginMaintainerORM,
    PluginORM,
    utc_now,
)
from plugin_market_backend.schemas import PluginCreate
from plugin_market_backend.service import MarketService
from plugin_market_backend.services.inbox_service import (
    GOVERNANCE_DEDUPE_WINDOW,
    InboxService,
)


# ---------------------------------------------------------------------------
# 初始化辅助函数
# ---------------------------------------------------------------------------


async def _ensure_author(
    session,
    author_id: str,
    *,
    github_login: str | None = None,
    display_name: str | None = None,
) -> AuthorORM:
    """创建或获取作者记录。

    Args:
        session: 数据库会话。
        author_id: 作者标识。
        github_login: GitHub 登录名；未提供时使用作者标识。
        display_name: 展示名称；未提供时使用登录名或作者标识。

    Returns:
        已有或新建的作者记录。
    """
    existing = await session.get(AuthorORM, author_id)
    if existing is not None:
        return existing
    record = AuthorORM(
        author_id=author_id,
        github_user_id=f"id-{author_id}",
        github_login=github_login or author_id,
        display_name=display_name or github_login or author_id,
        author_type=AuthorType.USER,
        verified_at=utc_now(),
        is_admin=False,
    )
    session.add(record)
    await session.flush()
    return record


async def _create_plugin(session, plugin_id: str, owner_id: str) -> PluginORM:
    """使用实际的 MarketService 注册指定所有者的插件。

    Args:
        session: 数据库会话。
        plugin_id: 插件标识。
        owner_id: 所有者标识。

    Returns:
        已注册的插件记录。
    """
    payload = PluginCreate(
        plugin_id=plugin_id,
        display_name=plugin_id,
        summary=f"{plugin_id} 的摘要",
        description=f"{plugin_id} 的说明",
        repository_url=f"https://github.com/MoFox-Studio/{plugin_id}",
        license="MIT",
        categories=["tool"],
        tags=["sample"],
        maintainers=[],
    )
    await MarketService(session).register_plugin(payload, owner_id=owner_id)
    plugin = await session.get(PluginORM, plugin_id)
    assert plugin is not None
    return plugin


async def _add_comment(
    session,
    plugin_id: str,
    author_id: str,
    *,
    content: str = "你好",
    parent_id: int | None = None,
) -> PluginCommentORM:
    """直接插入评论记录，避免测试依赖 MarketService。

    Args:
        session: 数据库会话。
        plugin_id: 插件标识。
        author_id: 评论作者标识。
        content: 评论内容。
        parent_id: 父评论标识；None 表示顶层评论。

    Returns:
        新建的评论记录。
    """
    comment = PluginCommentORM(
        plugin_id=plugin_id,
        author_id=author_id,
        parent_id=parent_id,
        content=content,
    )
    session.add(comment)
    await session.flush()
    return comment


# ---------------------------------------------------------------------------
# parse_mentions
# ---------------------------------------------------------------------------


async def test_parse_mentions_resolves_existing_logins_in_order() -> None:
    """已有 GitHub 登录名应按首次出现的顺序返回。"""
    async with session_scope() as session:
        await _ensure_author(session, "u-alpha", github_login="alpha")
        await _ensure_author(session, "u-beta", github_login="beta")
        await _ensure_author(session, "u-sender", github_login="sender")
        await _ensure_author(session, "u-gamma", github_login="gamma")

        service = InboxService(session)
        result = await service.parse_mentions(
            "ping @beta and @alpha (then @gamma again)", sender_id="u-sender"
        )

        assert [author.github_login for author in result] == [
            "beta",
            "alpha",
            "gamma",
        ]


async def test_parse_mentions_filters_unknown_logins() -> None:
    """未匹配到任何作者的提及标记应被静默忽略（需求 9.3）。"""
    async with session_scope() as session:
        await _ensure_author(session, "u-alpha", github_login="alpha")
        await _ensure_author(session, "u-sender", github_login="sender")

        service = InboxService(session)
        result = await service.parse_mentions(
            "@alpha is great, but @ghost-user is unknown",
            sender_id="u-sender",
        )

        assert [author.github_login for author in result] == ["alpha"]


async def test_parse_mentions_drops_self_mentions() -> None:
    """应过滤自我提及，避免向自己发送消息。"""
    async with session_scope() as session:
        await _ensure_author(session, "u-sender", github_login="sender")

        service = InboxService(session)
        result = await service.parse_mentions(
            "I am @sender and I want to mention myself", sender_id="u-sender"
        )

        assert result == []


async def test_parse_mentions_dedupes_repeated_mentions() -> None:
    """同一作者被重复提及时，应只出现一次。"""
    async with session_scope() as session:
        await _ensure_author(session, "u-alpha", github_login="alpha")
        await _ensure_author(session, "u-sender", github_login="sender")

        service = InboxService(session)
        result = await service.parse_mentions(
            "@alpha @alpha @alpha", sender_id="u-sender"
        )

        assert [author.github_login for author in result] == ["alpha"]


async def test_parse_mentions_handles_dashed_logins() -> None:
    """GitHub 登录名中间可以包含连字符。"""
    async with session_scope() as session:
        await _ensure_author(
            session, "u-with-dash", github_login="user-with-dash"
        )
        await _ensure_author(session, "u-sender", github_login="sender")

        service = InboxService(session)
        result = await service.parse_mentions(
            "hi @user-with-dash, please review", sender_id="u-sender"
        )

        assert [author.github_login for author in result] == [
            "user-with-dash"
        ]


async def test_parse_mentions_returns_empty_for_blank_content() -> None:
    """空内容或空白内容不应解析出提及。"""
    async with session_scope() as session:
        await _ensure_author(session, "u-sender", github_login="sender")
        service = InboxService(session)
        assert await service.parse_mentions("", sender_id="u-sender") == []
        assert (
            await service.parse_mentions("just some text", sender_id="u-sender")
            == []
        )


# ---------------------------------------------------------------------------
# 评论触发的消息分发（fan_out_for_comment）。
# ---------------------------------------------------------------------------


async def test_fan_out_for_comment_writes_mention_messages_and_normalized_rows() -> None:
    """顶层评论中的提及应写入 comment_mentions 和一条 mention 消息。"""
    async with session_scope() as session:
        await _ensure_author(session, "owner", github_login="owner")
        await _ensure_author(session, "u-alpha", github_login="alpha")
        await _ensure_author(session, "u-sender", github_login="sender")
        plugin = await _create_plugin(session, "plug-a", owner_id="owner")
        comment = await _add_comment(
            session,
            plugin.plugin_id,
            "u-sender",
            content="hey @alpha take a look",
        )

        service = InboxService(session)
        mentions = await service.parse_mentions(
            comment.content, sender_id=comment.author_id
        )
        await service.fan_out_for_comment(comment, mentions)

        # 规范化的 comment_mentions 记录应存在。
        mention_row = await session.scalar(
            select(CommentMentionORM).where(
                CommentMentionORM.comment_id == comment.id
            )
        )
        assert mention_row is not None

        # u-alpha 应收到一条 type=mention 的收件箱记录。
        rows = list(
            (
                await session.scalars(
                    select(InboxMessageORM)
                    .where(InboxMessageORM.recipient_id == "u-alpha")
                )
            ).all()
        )
        assert len(rows) == 1
        row = rows[0]
        assert row.type == "mention"
        assert row.status == "unread"
        assert row.dedup_key == f"mention:{comment.id}:u-alpha"
        assert row.related_comment_id == comment.id
        assert row.related_plugin_id == "plug-a"
        assert row.source_author_id == "u-sender"


async def test_fan_out_for_comment_writes_reply_message_for_parent_author() -> None:
    """不含提及的回复应仅通知父评论作者一次。"""
    async with session_scope() as session:
        await _ensure_author(session, "owner", github_login="owner")
        await _ensure_author(session, "u-parent", github_login="parent-user")
        await _ensure_author(session, "u-sender", github_login="sender")
        plugin = await _create_plugin(session, "plug-a", owner_id="owner")
        parent = await _add_comment(
            session, plugin.plugin_id, "u-parent", content="父评论"
        )
        reply = await _add_comment(
            session,
            plugin.plugin_id,
            "u-sender",
            content="感谢反馈",
            parent_id=parent.id,
        )

        service = InboxService(session)
        await service.fan_out_for_comment(reply, mentions=[])

        rows = list(
            (
                await session.scalars(
                    select(InboxMessageORM)
                    .where(InboxMessageORM.recipient_id == "u-parent")
                )
            ).all()
        )
        assert len(rows) == 1
        assert rows[0].type == "reply"
        assert rows[0].dedup_key == f"reply:{reply.id}:u-parent"


async def test_fan_out_for_comment_reply_over_mention_dedupes_recipient() -> None:
    """父评论作者同时被 @ 提及时，应只写入 reply 消息。

    对应需求 10.6 和属性 4：单条评论对每位接收者最多生成一条收件箱记录，
    且以 reply 作为最终类型。
    """
    async with session_scope() as session:
        await _ensure_author(session, "owner", github_login="owner")
        await _ensure_author(session, "u-parent", github_login="parent-user")
        await _ensure_author(session, "u-other", github_login="other-user")
        await _ensure_author(session, "u-sender", github_login="sender")

        plugin = await _create_plugin(session, "plug-a", owner_id="owner")
        parent = await _add_comment(
            session, plugin.plugin_id, "u-parent", content="父评论"
        )
        reply = await _add_comment(
            session,
            plugin.plugin_id,
            "u-sender",
            content="thanks @parent-user and @other-user",
            parent_id=parent.id,
        )

        service = InboxService(session)
        mentions = await service.parse_mentions(
            reply.content, sender_id=reply.author_id
        )
        await service.fan_out_for_comment(reply, mentions)

        # u-parent 应只收到回复消息，不应收到提及消息。
        parent_rows = list(
            (
                await session.scalars(
                    select(InboxMessageORM).where(
                        InboxMessageORM.recipient_id == "u-parent"
                    )
                )
            ).all()
        )
        assert [row.type for row in parent_rows] == ["reply"]

        # u-other 仍应收到提及消息。
        other_rows = list(
            (
                await session.scalars(
                    select(InboxMessageORM).where(
                        InboxMessageORM.recipient_id == "u-other"
                    )
                )
            ).all()
        )
        assert [row.type for row in other_rows] == ["mention"]

        # comment_mentions 仍应记录两次提及，以保留完整关系，
        # 而非只保留最终生成收件箱消息的那次提及。
        mention_rows = list(
            (
                await session.scalars(
                    select(CommentMentionORM).where(
                        CommentMentionORM.comment_id == reply.id
                    )
                )
            ).all()
        )
        assert {row.mentioned_author_id for row in mention_rows} == {
            "u-parent",
            "u-other",
        }


async def test_fan_out_for_comment_skips_self_replies() -> None:
    """回复自己的评论时，不应创建回复通知。"""
    async with session_scope() as session:
        await _ensure_author(session, "owner", github_login="owner")
        await _ensure_author(session, "u-sender", github_login="sender")
        plugin = await _create_plugin(session, "plug-a", owner_id="owner")
        parent = await _add_comment(
            session, plugin.plugin_id, "u-sender", content="我自己的评论串"
        )
        reply = await _add_comment(
            session,
            plugin.plugin_id,
            "u-sender",
            content="回复自己",
            parent_id=parent.id,
        )

        service = InboxService(session)
        await service.fan_out_for_comment(reply, mentions=[])

        rows = list(
            (
                await session.scalars(
                    select(InboxMessageORM).where(
                        InboxMessageORM.recipient_id == "u-sender"
                    )
                )
            ).all()
        )
        assert rows == []


async def test_fan_out_for_comment_skips_replies_to_deleted_parent() -> None:
    """回复已软删除的父评论时，不应通知任何人。"""
    async with session_scope() as session:
        await _ensure_author(session, "owner", github_login="owner")
        await _ensure_author(session, "u-parent", github_login="parent_user")
        await _ensure_author(session, "u-sender", github_login="sender")
        plugin = await _create_plugin(session, "plug-a", owner_id="owner")
        parent = await _add_comment(
            session, plugin.plugin_id, "u-parent", content="旧评论"
        )
        parent.is_deleted = True
        await session.flush()

        reply = await _add_comment(
            session,
            plugin.plugin_id,
            "u-sender",
            content="迟来的回复",
            parent_id=parent.id,
        )
        service = InboxService(session)
        await service.fan_out_for_comment(reply, mentions=[])

        rows = list(
            (
                await session.scalars(
                    select(InboxMessageORM).where(
                        InboxMessageORM.recipient_id == "u-parent"
                    )
                )
            ).all()
        )
        assert rows == []


# ---------------------------------------------------------------------------
# 治理事件触发的消息分发（fan_out_for_governance）。
# ---------------------------------------------------------------------------


async def test_fan_out_for_governance_notifies_owner_and_maintainers() -> None:
    """治理消息应分发给所有者及每位维护者（需求 11.4、11.5）。"""
    async with session_scope() as session:
        await _ensure_author(session, "owner", github_login="owner")
        await _ensure_author(session, "m1", github_login="maintainer-1")
        await _ensure_author(session, "m2", github_login="maintainer-2")
        await _ensure_author(session, "admin", github_login="admin")
        plugin = await _create_plugin(session, "plug-a", owner_id="owner")
        session.add_all(
            [
                PluginMaintainerORM(plugin_id="plug-a", author_id="m1"),
                PluginMaintainerORM(plugin_id="plug-a", author_id="m2"),
            ]
        )
        await session.flush()

        await InboxService(session).fan_out_for_governance(
            plugin,
            action="block_plugin",
            operator_id="admin",
            reason="违反规则",
        )

        rows = list(
            (
                await session.scalars(
                    select(InboxMessageORM).where(
                        InboxMessageORM.related_plugin_id == "plug-a"
                    )
                )
            ).all()
        )
        recipients = {row.recipient_id for row in rows}
        assert recipients == {"owner", "m1", "m2"}
        for row in rows:
            assert row.type == "governance"
            assert row.payload["action"] == "block_plugin"
            assert row.payload["reason"] == "违反规则"
            assert row.source_author_id == "admin"


async def test_fan_out_for_governance_dedupes_within_5s_window() -> None:
    """5 秒内的两次调用应为每位接收者合并成一条记录。"""
    async with session_scope() as session:
        await _ensure_author(session, "owner", github_login="owner")
        await _ensure_author(session, "admin", github_login="admin")
        plugin = await _create_plugin(session, "plug-a", owner_id="owner")

        service = InboxService(session)
        await service.fan_out_for_governance(
            plugin, action="block_plugin", operator_id="admin", reason="r1"
        )
        # 立即重复相同操作，应合并记录。
        await service.fan_out_for_governance(
            plugin, action="block_plugin", operator_id="admin", reason="r2"
        )

        rows = list(
            (
                await session.scalars(
                    select(InboxMessageORM).where(
                        InboxMessageORM.recipient_id == "owner",
                        InboxMessageORM.type == "governance",
                    )
                )
            ).all()
        )
        assert len(rows) == 1
        # 应保留最近一次分发的消息内容。
        assert rows[0].payload["reason"] == "r2"


async def test_fan_out_for_governance_creates_new_row_outside_window() -> None:
    """超出去重时间窗口后，应写入新记录。"""
    async with session_scope() as session:
        await _ensure_author(session, "owner", github_login="owner")
        await _ensure_author(session, "admin", github_login="admin")
        plugin = await _create_plugin(session, "plug-a", owner_id="owner")

        service = InboxService(session)
        await service.fan_out_for_governance(
            plugin, action="block_plugin", operator_id="admin", reason="首次处理理由"
        )
        # 将已有记录的时间调早至去重窗口之外，使下次调用必须插入新记录。
        existing = await session.scalar(
            select(InboxMessageORM).where(
                InboxMessageORM.recipient_id == "owner",
                InboxMessageORM.type == "governance",
            )
        )
        assert existing is not None
        existing.created_at = (
            existing.created_at - GOVERNANCE_DEDUPE_WINDOW - timedelta(seconds=1)
        )
        await session.flush()

        await service.fan_out_for_governance(
            plugin, action="block_plugin", operator_id="admin", reason="再次处理理由"
        )

        rows = list(
            (
                await session.scalars(
                    select(InboxMessageORM).where(
                        InboxMessageORM.recipient_id == "owner",
                        InboxMessageORM.type == "governance",
                    )
                )
            ).all()
        )
        assert len(rows) == 2
        reasons = {(row.payload or {}).get("reason") for row in rows}
        assert reasons == {"首次处理理由", "再次处理理由"}


async def test_fan_out_for_governance_distinct_actions_dont_dedupe() -> None:
    """同一插件上的不同操作应各自生成一条记录。"""
    async with session_scope() as session:
        await _ensure_author(session, "owner", github_login="owner")
        await _ensure_author(session, "admin", github_login="admin")
        plugin = await _create_plugin(session, "plug-a", owner_id="owner")

        service = InboxService(session)
        await service.fan_out_for_governance(
            plugin, action="block_plugin", operator_id="admin"
        )
        await service.fan_out_for_governance(
            plugin, action="set_trust_level", operator_id="admin"
        )

        rows = list(
            (
                await session.scalars(
                    select(InboxMessageORM).where(
                        InboxMessageORM.recipient_id == "owner",
                        InboxMessageORM.type == "governance",
                    )
                )
            ).all()
        )
        actions = {(row.payload or {}).get("action") for row in rows}
        assert actions == {"block_plugin", "set_trust_level"}


# ---------------------------------------------------------------------------
# 公告触发的消息分发（fan_out_for_announcement）。
# ---------------------------------------------------------------------------


async def test_fan_out_for_announcement_writes_inbox_rows_for_each_recipient() -> None:
    """emit_inbox=True 时，应为每位接收者写入一条收件箱记录。"""
    async with session_scope() as session:
        await _ensure_author(session, "admin", github_login="admin")
        await _ensure_author(session, "u1", github_login="u1")
        await _ensure_author(session, "u2", github_login="u2")
        announcement = AnnouncementORM(
            title="维护时段",
            body_markdown="服务将短暂中断",
            display_mode="banner",
            severity="info",
            dismissible=True,
            enabled=True,
            audience="all",
            emit_inbox=True,
            dismiss_token=0,
            created_by="admin",
        )
        session.add(announcement)
        await session.flush()

        count = await InboxService(session).fan_out_for_announcement(
            announcement, ["u1", "u2", "u1"]
        )
        assert count == 2

        rows = list(
            (
                await session.scalars(
                    select(InboxMessageORM).where(
                        InboxMessageORM.related_announcement_id == announcement.id
                    )
                )
            ).all()
        )
        assert {row.recipient_id for row in rows} == {"u1", "u2"}
        for row in rows:
            assert row.type == "announcement"
            assert row.payload["announcement_id"] == announcement.id
            assert row.payload["title"] == "维护时段"


async def test_fan_out_for_announcement_refuses_when_emit_inbox_false() -> None:
    """emit_inbox=False 时调用分发属于编程错误。"""
    async with session_scope() as session:
        await _ensure_author(session, "admin", github_login="admin")
        announcement = AnnouncementORM(
            title="静默通知",
            body_markdown="",
            display_mode="banner",
            severity="info",
            dismissible=True,
            enabled=True,
            audience="all",
            emit_inbox=False,
            dismiss_token=0,
            created_by="admin",
        )
        session.add(announcement)
        await session.flush()

        with pytest.raises(ValueError):
            await InboxService(session).fan_out_for_announcement(
                announcement, ["admin"]
            )


async def test_fan_out_for_announcement_dedupes_by_dismiss_token() -> None:
    """相同公告和标记的重复分发应复用记录，更新标记后应创建新记录。"""
    async with session_scope() as session:
        await _ensure_author(session, "admin", github_login="admin")
        await _ensure_author(session, "u1", github_login="u1")
        announcement = AnnouncementORM(
            title="通知",
            body_markdown="",
            display_mode="banner",
            severity="info",
            dismissible=True,
            enabled=True,
            audience="all",
            emit_inbox=True,
            dismiss_token=0,
            created_by="admin",
        )
        session.add(announcement)
        await session.flush()

        service = InboxService(session)
        await service.fan_out_for_announcement(announcement, ["u1"])
        await service.fan_out_for_announcement(announcement, ["u1"])  # 重复分发

        rows = list(
            (
                await session.scalars(
                    select(InboxMessageORM).where(
                        InboxMessageORM.recipient_id == "u1",
                        InboxMessageORM.related_announcement_id
                        == announcement.id,
                    )
                )
            ).all()
        )
        assert len(rows) == 1

        # 重新展示时递增 dismiss_token 会生成新的 dedup_key，
        # 因此应写入一条新的收件箱记录。
        announcement.dismiss_token = 1
        await session.flush()
        await service.fan_out_for_announcement(announcement, ["u1"])

        rows = list(
            (
                await session.scalars(
                    select(InboxMessageORM).where(
                        InboxMessageORM.recipient_id == "u1",
                        InboxMessageORM.related_announcement_id
                        == announcement.id,
                    )
                )
            ).all()
        )
        assert len(rows) == 2


# ---------------------------------------------------------------------------
# 撤销评论相关消息（revoke_messages_for_comment）。
# ---------------------------------------------------------------------------


async def test_revoke_messages_for_comment_marks_derived_rows_as_revoked() -> None:
    """删除评论时，应将所有派生收件箱记录标记为 revoked。"""
    async with session_scope() as session:
        await _ensure_author(session, "owner", github_login="owner")
        await _ensure_author(session, "u-alpha", github_login="alpha")
        await _ensure_author(session, "u-sender", github_login="sender")
        plugin = await _create_plugin(session, "plug-a", owner_id="owner")
        comment = await _add_comment(
            session,
            plugin.plugin_id,
            "u-sender",
            content="hi @alpha",
        )

        service = InboxService(session)
        mentions = await service.parse_mentions(
            comment.content, sender_id=comment.author_id
        )
        await service.fan_out_for_comment(comment, mentions)

        affected = await service.revoke_messages_for_comment(comment.id)
        assert affected == 1

        rows = list(
            (
                await session.scalars(
                    select(InboxMessageORM).where(
                        InboxMessageORM.related_comment_id == comment.id
                    )
                )
            ).all()
        )
        assert all(row.status == "revoked" for row in rows)

        # 再次调用应无变化，已撤销的记录不再修改。
        again = await service.revoke_messages_for_comment(comment.id)
        assert again == 0


# ---------------------------------------------------------------------------
# 列表、未读计数与已读标记（list/unread/mark_read/mark_all_read）。
# ---------------------------------------------------------------------------


async def test_list_messages_orders_newest_first_and_paginates() -> None:
    """列表应按时间从新到旧返回记录，并附带分页元数据。"""
    async with session_scope() as session:
        await _ensure_author(session, "viewer", github_login="viewer")
        # 手动插入时间戳确定的消息，避免排序断言仅依赖插入顺序。
        now = utc_now()
        for index in range(5):
            session.add(
                InboxMessageORM(
                    recipient_id="viewer",
                    type="system",
                    status="unread",
                    payload={"i": index},
                    dedup_key=f"system:viewer:{index}",
                    created_at=now - timedelta(minutes=5 - index),
                )
            )
        await session.flush()

        service = InboxService(session)
        page1, total = await service.list_messages("viewer", offset=0, limit=2)
        assert total == 5
        assert [int(msg.payload["i"]) for msg in page1] == [4, 3]

        page2, total2 = await service.list_messages("viewer", offset=2, limit=2)
        assert total2 == 5
        assert [int(msg.payload["i"]) for msg in page2] == [2, 1]


async def test_list_messages_filters_by_type() -> None:
    """类型筛选应仅返回匹配的记录。"""
    async with session_scope() as session:
        await _ensure_author(session, "viewer", github_login="viewer")
        session.add_all(
            [
                InboxMessageORM(
                    recipient_id="viewer",
                    type="mention",
                    status="unread",
                    payload={},
                    dedup_key="mention:viewer:1",
                ),
                InboxMessageORM(
                    recipient_id="viewer",
                    type="reply",
                    status="unread",
                    payload={},
                    dedup_key="reply:viewer:1",
                ),
                InboxMessageORM(
                    recipient_id="viewer",
                    type="system",
                    status="unread",
                    payload={},
                    dedup_key="system:viewer:1",
                ),
            ]
        )
        await session.flush()

        service = InboxService(session)
        mentions, total = await service.list_messages("viewer", type="mention")
        assert total == 1
        assert [m.type for m in mentions] == ["mention"]


async def test_list_messages_unknown_type_returns_empty() -> None:
    """未知筛选值应返回空页面，而不是报错。"""
    async with session_scope() as session:
        await _ensure_author(session, "viewer", github_login="viewer")
        service = InboxService(session)
        items, total = await service.list_messages("viewer", type="nonsense")
        assert items == []
        assert total == 0


async def test_list_messages_scope_to_recipient() -> None:
    """list_messages 不得泄露其他接收者的记录。"""
    async with session_scope() as session:
        await _ensure_author(session, "alice", github_login="alice")
        await _ensure_author(session, "bob", github_login="bob")
        session.add_all(
            [
                InboxMessageORM(
                    recipient_id="alice",
                    type="system",
                    status="unread",
                    payload={"who": "alice"},
                    dedup_key="system:alice:1",
                ),
                InboxMessageORM(
                    recipient_id="bob",
                    type="system",
                    status="unread",
                    payload={"who": "bob"},
                    dedup_key="system:bob:1",
                ),
            ]
        )
        await session.flush()

        service = InboxService(session)
        alice_items, _ = await service.list_messages("alice")
        assert {item.payload["who"] for item in alice_items} == {"alice"}


async def test_unread_count_only_counts_unread_rows() -> None:
    """已读和已撤销消息不应计入未读角标。"""
    async with session_scope() as session:
        await _ensure_author(session, "viewer", github_login="viewer")
        session.add_all(
            [
                InboxMessageORM(
                    recipient_id="viewer",
                    type="system",
                    status="unread",
                    payload={},
                    dedup_key="k1",
                ),
                InboxMessageORM(
                    recipient_id="viewer",
                    type="system",
                    status="unread",
                    payload={},
                    dedup_key="k2",
                ),
                InboxMessageORM(
                    recipient_id="viewer",
                    type="system",
                    status="read",
                    payload={},
                    dedup_key="k3",
                ),
                InboxMessageORM(
                    recipient_id="viewer",
                    type="system",
                    status="revoked",
                    payload={},
                    dedup_key="k4",
                ),
            ]
        )
        await session.flush()

        service = InboxService(session)
        assert await service.unread_count("viewer") == 2


async def test_mark_read_only_affects_recipient_unread_rows() -> None:
    """mark_read 应限定当前查看者，并忽略非未读记录。"""
    async with session_scope() as session:
        await _ensure_author(session, "alice", github_login="alice")
        await _ensure_author(session, "bob", github_login="bob")
        session.add_all(
            [
                InboxMessageORM(
                    recipient_id="alice",
                    type="system",
                    status="unread",
                    payload={},
                    dedup_key="alice-1",
                ),
                InboxMessageORM(
                    recipient_id="alice",
                    type="system",
                    status="unread",
                    payload={},
                    dedup_key="alice-2",
                ),
                InboxMessageORM(
                    recipient_id="bob",
                    type="system",
                    status="unread",
                    payload={},
                    dedup_key="bob-1",
                ),
            ]
        )
        await session.flush()

        alice_ids = list(
            (
                await session.scalars(
                    select(InboxMessageORM).where(
                        InboxMessageORM.recipient_id == "alice"
                    )
                )
            ).all()
        )
        bob_id = (
            await session.scalar(
                select(InboxMessageORM).where(
                    InboxMessageORM.recipient_id == "bob"
                )
            )
        ).id

        service = InboxService(session)
        # 尝试标记属于 bob 的记录时，应忽略该记录。
        affected = await service.mark_read(
            "alice", [row.id for row in alice_ids] + [bob_id]
        )
        assert affected == 2

        bob_row = await session.get(InboxMessageORM, bob_id)
        assert bob_row is not None
        assert bob_row.status == "unread"

        # 重复调用 mark_read 应无变化。
        again = await service.mark_read(
            "alice", [row.id for row in alice_ids]
        )
        assert again == 0
        assert await service.unread_count("alice") == 0


async def test_mark_all_read_marks_only_recipient_unread_rows() -> None:
    """mark_all_read 应仅清空当前查看者的未读队列。"""
    async with session_scope() as session:
        await _ensure_author(session, "alice", github_login="alice")
        await _ensure_author(session, "bob", github_login="bob")
        session.add_all(
            [
                InboxMessageORM(
                    recipient_id="alice",
                    type="system",
                    status="unread",
                    payload={},
                    dedup_key="alice-1",
                ),
                InboxMessageORM(
                    recipient_id="alice",
                    type="system",
                    status="read",
                    payload={},
                    dedup_key="alice-2",
                ),
                InboxMessageORM(
                    recipient_id="bob",
                    type="system",
                    status="unread",
                    payload={},
                    dedup_key="bob-1",
                ),
            ]
        )
        await session.flush()

        service = InboxService(session)
        affected = await service.mark_all_read("alice")
        assert affected == 1
        assert await service.unread_count("alice") == 0
        # bob 的未读记录应保持不变。
        assert await service.unread_count("bob") == 1
