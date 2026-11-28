"""提供收件箱消息生成、分发和查询服务。

本模块管理系统中派生生成的 ``inbox_messages`` 记录，接口对应设计文档中的职责：

* ``InboxService.parse_mentions`` 扫描内容，将 ``@<github_login>`` 标记解析为
  已有作者（需求 9.1 至 9.3、性质 10）。
* ``InboxService.fan_out_for_comment`` 写入 ``comment_mentions``，
  按回复优先于提及的规则生成 ``mention`` 或 ``reply`` 消息
  （需求 10.6、性质 4）。
* ``InboxService.fan_out_for_governance`` 在管理员治理插件时，向所有者和维护者
  生成 ``governance`` 消息；通过 5 秒滑动窗口去重，避免管理页面的重复操作
  刷满收件箱（需求 11.4 至 11.7）。
* ``InboxService.fan_out_for_announcement`` 向指定收件人生成 ``announcement``
  消息；调用方根据 ``announcement.emit_inbox`` 决定是否调用。
* ``InboxService.revoke_messages_for_comment`` 在评论删除后，将派生消息标记为
  ``revoked``，保留审计记录但不再作为有效消息处理（需求 9.6）。
* ``InboxService.list_messages``、``unread_count``、``mark_read`` 和
  ``mark_all_read`` 提供按访问者隔离的查询和写入接口，服务于
  ``GET /api/v1/inbox/*``（需求 11.1 至 11.8）。

消息分发利用 ``plugin_market_backend.orm.InboxMessageORM`` 上的唯一约束
``unique_inbox_dedup(recipient_id, dedup_key)``，对重复事件更新而非重复插入。
去重键格式在各次调用间保持稳定，便于外部调用方（例如管理员重试）使用：

* 提及：``mention:{comment_id}:{recipient_id}``。
* 回复：``reply:{comment_id}:{recipient_id}``。
* 治理：``governance:{plugin_id}:{action}:{ts_micros}``，时间戳后缀为
  记录首次创建时的微秒级纪元时间。代码通过查找最近 5 秒内相同收件人、插件和
  操作的消息实现滑动窗口去重，找到后刷新 ``created_at`` 而非插入。
  微秒精度用于降低不同分发事件的去重键冲突风险。
* 公告：``announcement:{announcement_id}:{recipient_id}:{dismiss_token}``，
  管理员重新展示公告时递增 ``dismiss_token``，从而生成新消息，避免与旧消息冲突。
"""

from __future__ import annotations

import re
from datetime import timedelta
from typing import Any, Iterable

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from plugin_market_backend.orm import (
    AnnouncementORM,
    AuthorFollowORM,
    AuthorORM,
    CommentMentionORM,
    InboxMessageORM,
    PluginCommentORM,
    PluginMaintainerORM,
    PluginORM,
    PluginSubscriptionORM,
    utc_now,
)
from plugin_market_backend.schemas import (
    InboxMessage,
    InboxMessageLink,
    InboxMessageSource,
)


# ---------------------------------------------------------------------------
# 模块级常量
# ---------------------------------------------------------------------------


MENTION_RE = re.compile(
    r"@([A-Za-z0-9](?:[A-Za-z0-9-]{0,38}))(?![A-Za-z0-9-])"
)
"""匹配基于 GitHub 登录名的提及标记。

匹配 ``@<login>``，其中 ``<login>`` 长度为 1 至 39 个字符，
以字母或数字开头，仅包含字母、数字和连字符，后面不能紧接字母、数字或连字符。
例如 ``@foo-bar`` 只匹配一次，不会拆成 ``foo`` 和 ``bar``。
"""


GOVERNANCE_DEDUPE_WINDOW = timedelta(seconds=5)
"""抑制重复治理消息分发的滑动时间窗口。"""


PREVIEW_MAX_LENGTH = 200
"""收件箱载荷预览保留的最大字符数。"""


_VALID_TYPES: frozenset[str] = frozenset(
    {"mention", "reply", "governance", "announcement", "author_activity", "plugin_activity", "system"}
)


# ---------------------------------------------------------------------------
# 服务
# ---------------------------------------------------------------------------


class InboxService:
    """为每位收件人生成并提供收件箱消息。"""

    def __init__(self, session: AsyncSession) -> None:
        """将服务绑定到单个异步事务会话。"""
        self.session = session

    # ------------------------------------------------------------------
    # 提及解析（性质 10、需求 9.1 至 9.3）
    # ------------------------------------------------------------------

    async def parse_mentions(
        self, content: str, sender_id: str
    ) -> list[AuthorORM]:
        """将 ``content`` 中的 ``@<login>`` 标记解析为已有作者。

        不匹配已有作者的标记会被忽略（需求 9.3）。结果排除发送者本人，
        避免向收件箱写入自我提及消息（需求 9.4、性质 4），并按 ``author_id`` 去重。

        Args:
            content: 原始评论内容。
            sender_id: 提交评论的作者 ID，用于过滤自我提及。

        Returns:
            解析出的 ``AuthorORM`` 记录列表，按对应 ``@<login>`` 首次出现的顺序排列。
        """
        if not content:
            return []

        # 保留首次出现的顺序，使结果列表保持稳定。
        ordered_logins: list[str] = []
        seen_logins: set[str] = set()
        for match in MENTION_RE.finditer(content):
            login = match.group(1)
            if login in seen_logins:
                continue
            seen_logins.add(login)
            ordered_logins.append(login)

        if not ordered_logins:
            return []

        rows = list(
            (
                await self.session.scalars(
                    select(AuthorORM).where(
                        AuthorORM.github_login.in_(ordered_logins)
                    )
                )
            ).all()
        )
        by_login: dict[str, AuthorORM] = {row.github_login: row for row in rows}

        result: list[AuthorORM] = []
        seen_ids: set[str] = set()
        for login in ordered_logins:
            author = by_login.get(login)
            if author is None:
                continue
            if author.author_id == sender_id:
                continue
            if author.author_id in seen_ids:
                continue
            seen_ids.add(author.author_id)
            result.append(author)
        return result

    # ------------------------------------------------------------------
    # 评论消息分发（需求 9.4、10.5、10.6）
    # ------------------------------------------------------------------

    async def fan_out_for_comment(
        self,
        comment: PluginCommentORM,
        mentions: Iterable[AuthorORM],
    ) -> None:
        """持久化 ``comment_mentions`` 记录并生成提及或回复消息。

        分发遵循性质 4 的回复优先规则：同一评论同时回复并提及同一收件人时，
        仅发送 ``reply`` 消息，不再发送提及消息；其他被提及作者仍收到 ``mention``。

        Args:
            comment: 已刷入数据库的评论 ORM 记录，必须已分配 ``id``。
            mentions: 所有已解析提及对应的作者记录。调用方通常通过
                ``parse_mentions`` 预先排除自我提及。

        Raises:
            ValueError: 评论尚未分配 ``id``。
        """
        if comment.id is None:  # pragma: no cover - 防御性处理
            raise ValueError(
                "fan_out_for_comment 要求评论已刷入数据库并具有 ID"
            )

        sender_id = comment.author_id
        mention_authors: list[AuthorORM] = [
            author
            for author in mentions
            if author.author_id != sender_id
        ]

        # 为每个已解析提及持久化规范化的 comment_mentions 记录，
        # 包括因回复优先规则而不发送提及消息的作者，
        # 使下游查询和性质测试获得完整的关联关系。
        for author in mention_authors:
            already = await self.session.scalar(
                select(CommentMentionORM.id).where(
                    CommentMentionORM.comment_id == comment.id,
                    CommentMentionORM.mentioned_author_id == author.author_id,
                )
            )
            if already is None:
                self.session.add(
                    CommentMentionORM(
                        comment_id=comment.id,
                        mentioned_author_id=author.author_id,
                        created_at=utc_now(),
                    )
                )

        # 若存在回复目标，则解析其收件人。
        reply_recipient_id: str | None = None
        if comment.parent_id is not None:
            parent = await self.session.get(
                PluginCommentORM, comment.parent_id
            )
            if (
                parent is not None
                and not parent.is_deleted
                and parent.author_id != sender_id
            ):
                reply_recipient_id = parent.author_id

        # 分发提及消息时，跳过将收到回复消息的作者（需求 10.6）。
        for author in mention_authors:
            if author.author_id == reply_recipient_id:
                continue
            await self._upsert_message(
                recipient_id=author.author_id,
                type="mention",
                dedup_key=f"mention:{comment.id}:{author.author_id}",
                payload=self._comment_payload(comment, kind="mention"),
                related_comment_id=comment.id,
                related_plugin_id=comment.plugin_id,
                source_author_id=sender_id,
            )

        if reply_recipient_id is not None:
            await self._upsert_message(
                recipient_id=reply_recipient_id,
                type="reply",
                dedup_key=f"reply:{comment.id}:{reply_recipient_id}",
                payload=self._comment_payload(comment, kind="reply"),
                related_comment_id=comment.id,
                related_plugin_id=comment.plugin_id,
                source_author_id=sender_id,
            )

        await self.session.flush()

    # ------------------------------------------------------------------
    # 治理消息分发（需求 11.4、11.5、11.7）
    # ------------------------------------------------------------------

    async def fan_out_for_governance(
        self,
        plugin: PluginORM,
        action: str,
        operator_id: str,
        reason: str | None = None,
    ) -> None:
        """为插件所有者和维护者生成治理消息。

        在 5 秒滑动窗口内，对相同 ``(recipient, plugin_id, action)`` 的重复调用
        进行合并：刷新已有消息的 ``created_at`` 而非插入新记录，
        使收件人在一轮密集操作中只收到一条通知（需求 11.7）。
        唯一约束 ``unique_inbox_dedup`` 为去重键冲突提供额外保护。

        Args:
            plugin: 目标插件的 ORM 记录。
            action: 治理操作的简短标识，例如 ``"block_plugin"`` 或
                ``"set_trust_level"``。
            operator_id: 执行操作的管理员 ID，记录为 ``source_author_id``，
                供界面展示操作来源。
            reason: 操作者提供的可选自由文本理由。
        """
        recipients = await self._collect_governance_recipients(plugin)
        if not recipients:
            return

        now = utc_now()
        window_start = now - GOVERNANCE_DEDUPE_WINDOW
        payload_template = {
            "action": action,
            "reason": reason,
            "plugin_id": plugin.plugin_id,
            "plugin_display_name": plugin.display_name,
            "operator_id": operator_id,
        }

        for recipient_id in recipients:
            # 查找去重窗口内该收件人和插件对应的治理消息，
            # 后续匹配操作后刷新已有消息，而非重复插入。
            recent_rows = list(
                (
                    await self.session.scalars(
                        select(InboxMessageORM)
                        .where(
                            InboxMessageORM.recipient_id == recipient_id,
                            InboxMessageORM.type == "governance",
                            InboxMessageORM.related_plugin_id
                            == plugin.plugin_id,
                            InboxMessageORM.created_at >= window_start,
                        )
                        .order_by(InboxMessageORM.created_at.desc())
                    )
                ).all()
            )
            existing = next(
                (
                    row
                    for row in recent_rows
                    if (row.payload or {}).get("action") == action
                ),
                None,
            )
            if existing is not None:
                existing.created_at = now
                existing.payload = payload_template
                if existing.status == "revoked":
                    existing.status = "unread"
                continue

            dedup_key = (
                f"governance:{plugin.plugin_id}:{action}"
                f":{int(now.timestamp() * 1_000_000)}"
            )
            await self._upsert_message(
                recipient_id=recipient_id,
                type="governance",
                dedup_key=dedup_key,
                payload=payload_template,
                related_plugin_id=plugin.plugin_id,
                source_author_id=operator_id,
                created_at=now,
            )

        await self.session.flush()

    # ------------------------------------------------------------------
    # 公告消息分发（需求 11.3）
    # ------------------------------------------------------------------

    async def fan_out_for_announcement(
        self,
        announcement: AnnouncementORM,
        recipients_iter: Iterable[str | AuthorORM],
    ) -> int:
        """为指定收件人生成公告消息。

        调用方负责遵守 ``announcement.emit_inbox``：调用本方法意味着管理员
        已选择分发到收件箱。若 ``emit_inbox=False``，立即报错以暴露误调用。

        Args:
            announcement: 待广播的公告。
            recipients_iter: 作者 ID 字符串或 ``AuthorORM`` 记录的可迭代对象，
                按 ID 去重。

        Returns:
            新写入或刷新的收件箱消息数量。

        Raises:
            ValueError: 公告的 ``emit_inbox`` 为 ``False``。
        """
        if not announcement.emit_inbox:
            raise ValueError(
                "fan_out_for_announcement 收到的公告设置了 "
                "emit_inbox=False；调用方必须预先检查。"
            )

        recipient_ids: list[str] = []
        seen: set[str] = set()
        for entry in recipients_iter:
            recipient_id = (
                entry.author_id if isinstance(entry, AuthorORM) else entry
            )
            if not recipient_id or recipient_id in seen:
                continue
            seen.add(recipient_id)
            recipient_ids.append(recipient_id)

        if not recipient_ids:
            return 0

        payload = {
            "announcement_id": announcement.id,
            "title": announcement.title,
            "severity": announcement.severity,
            "display_mode": announcement.display_mode,
            "preview": (announcement.body_markdown or "")[:PREVIEW_MAX_LENGTH],
        }

        count = 0
        for recipient_id in recipient_ids:
            dedup_key = (
                f"announcement:{announcement.id}:{recipient_id}"
                f":{announcement.dismiss_token}"
            )
            await self._upsert_message(
                recipient_id=recipient_id,
                type="announcement",
                dedup_key=dedup_key,
                payload=payload,
                related_announcement_id=announcement.id,
                source_author_id=None,
            )
            count += 1
        await self.session.flush()
        return count

    async def fan_out_for_author_activity(
        self,
        *,
        author_id: str,
        source_author_id: str,
        dedup_key: str,
        payload: dict[str, Any],
        related_plugin_id: str | None = None,
    ) -> int:
        """为指定作者的关注者生成作者动态消息。"""
        follower_ids = list(
            (
                await self.session.scalars(
                    select(AuthorFollowORM.follower_id).where(
                        AuthorFollowORM.author_id == author_id
                    )
                )
            ).all()
        )
        count = 0
        for follower_id in dict.fromkeys(follower_ids):
            if not follower_id or follower_id == source_author_id:
                continue
            await self._upsert_message(
                recipient_id=follower_id,
                type="author_activity",
                dedup_key=f"{dedup_key}:{follower_id}",
                payload=payload,
                related_plugin_id=related_plugin_id,
                source_author_id=source_author_id,
            )
            count += 1
        if count:
            await self.session.flush()
        return count

    async def fan_out_for_plugin_activity(
        self,
        *,
        plugin_id: str,
        source_author_id: str,
        dedup_key: str,
        payload: dict[str, Any],
    ) -> int:
        """为插件订阅者生成插件动态消息。"""
        subscriber_ids = list(
            (
                await self.session.scalars(
                    select(PluginSubscriptionORM.author_id).where(
                        PluginSubscriptionORM.plugin_id == plugin_id
                    )
                )
            ).all()
        )
        count = 0
        for subscriber_id in dict.fromkeys(subscriber_ids):
            if not subscriber_id or subscriber_id == source_author_id:
                continue
            await self._upsert_message(
                recipient_id=subscriber_id,
                type="plugin_activity",
                dedup_key=f"{dedup_key}:{subscriber_id}",
                payload=payload,
                related_plugin_id=plugin_id,
                source_author_id=source_author_id,
            )
            count += 1
        if count:
            await self.session.flush()
        return count

    # ------------------------------------------------------------------
    # 撤销消息（需求 9.6）
    # ------------------------------------------------------------------

    async def revoke_messages_for_comment(self, comment_id: int) -> int:
        """将 ``comment_id`` 派生的所有收件箱消息标记为 ``revoked``。

        已撤销的记录保持不变。

        Args:
            comment_id: 作为消息来源的评论 ID。

        Returns:
            本次修改的消息记录数。
        """
        rows = list(
            (
                await self.session.scalars(
                    select(InboxMessageORM).where(
                        InboxMessageORM.related_comment_id == comment_id,
                        InboxMessageORM.status != "revoked",
                    )
                )
            ).all()
        )
        for row in rows:
            row.status = "revoked"
        if rows:
            await self.session.flush()
        return len(rows)

    # ------------------------------------------------------------------
    # 消息读取接口（需求 11.1、11.2、11.6、11.7、11.8）
    # ------------------------------------------------------------------

    async def list_messages(
        self,
        viewer_id: str,
        *,
        type: str | None = None,
        offset: int = 0,
        limit: int = 50,
    ) -> tuple[list[InboxMessage], int]:
        """按时间从新到旧分页返回 ``viewer_id`` 的收件箱消息。

        Args:
            viewer_id: 当前查看消息的作者 ID。仅返回 ``recipient_id`` 匹配的消息，
                在路由层权限检查之外进一步隔离不同收件人的数据。
            type: 可选的消息类型过滤条件，支持 ``_VALID_TYPES`` 中的值。
                未知值返回空结果，不抛出异常，避免客户端配置错误导致端点失败。
            offset: 分页偏移量，小于 0 时按 0 处理。
            limit: 单页条目数，小于或等于 0 时返回空结果。

        Returns:
            ``(messages, total)`` 元组；``messages`` 为转换成 ``InboxMessage``
            的当前页消息，``total`` 为相同过滤条件下未分页的总数。
        """
        if limit <= 0:
            return [], 0

        base_filters = [InboxMessageORM.recipient_id == viewer_id]
        if type is not None:
            if type not in _VALID_TYPES:
                return [], 0
            base_filters.append(InboxMessageORM.type == type)

        total_stmt = (
            select(func.count())
            .select_from(InboxMessageORM)
            .where(*base_filters)
        )
        total = int((await self.session.scalar(total_stmt)) or 0)
        if total == 0:
            return [], 0

        page_stmt = (
            select(InboxMessageORM)
            .where(*base_filters)
            .order_by(
                InboxMessageORM.created_at.desc(),
                InboxMessageORM.id.desc(),
            )
            .offset(max(offset, 0))
            .limit(limit)
        )
        rows = list((await self.session.scalars(page_stmt)).all())
        return await self._project_messages(rows), total

    async def unread_count(self, viewer_id: str) -> int:
        """返回 ``viewer_id`` 的 ``unread`` 消息数量。

        排除已撤销和已读消息，使导航栏通知图标仅反映待处理事项。
        """
        stmt = (
            select(func.count())
            .select_from(InboxMessageORM)
            .where(
                InboxMessageORM.recipient_id == viewer_id,
                InboxMessageORM.status == "unread",
            )
        )
        return int((await self.session.scalar(stmt)) or 0)

    async def mark_read(
        self, viewer_id: str, ids: Iterable[int]
    ) -> int:
        """将指定收件箱消息标记为已读。

        仅修改满足 ``recipient_id == viewer_id`` 且 ``status='unread'`` 的记录。
        ``revoked`` 消息保持不变，避免误恢复已软删除的会话；已读消息也不再修改。

        Args:
            viewer_id: 当前查看消息的作者 ID。
            ids: 待标记为已读的消息 ID。

        Returns:
            实际转换为 ``read`` 状态的记录数。
        """
        ids_list = [int(i) for i in ids if i is not None]
        if not ids_list:
            return 0

        rows = list(
            (
                await self.session.scalars(
                    select(InboxMessageORM).where(
                        InboxMessageORM.recipient_id == viewer_id,
                        InboxMessageORM.id.in_(ids_list),
                        InboxMessageORM.status == "unread",
                    )
                )
            ).all()
        )
        now = utc_now()
        for row in rows:
            row.status = "read"
            row.read_at = now
        if rows:
            await self.session.flush()
        return len(rows)

    async def mark_all_read(self, viewer_id: str) -> int:
        """将 ``viewer_id`` 的所有未读消息标记为已读。"""
        result = await self.session.execute(
            update(InboxMessageORM)
            .where(
                InboxMessageORM.recipient_id == viewer_id,
                InboxMessageORM.status == "unread",
            )
            .values(status="read", read_at=utc_now())
        )
        await self.session.flush()
        return int(result.rowcount or 0)

    # ------------------------------------------------------------------
    # 内部辅助函数
    # ------------------------------------------------------------------

    async def _collect_governance_recipients(
        self, plugin: PluginORM
    ) -> list[str]:
        """返回 ``plugin`` 的所有者和维护者 ID，并去除重复项。"""
        recipients: list[str] = []
        seen: set[str] = set()
        if plugin.owner_id:
            recipients.append(plugin.owner_id)
            seen.add(plugin.owner_id)

        maintainer_ids = list(
            (
                await self.session.scalars(
                    select(PluginMaintainerORM.author_id).where(
                        PluginMaintainerORM.plugin_id == plugin.plugin_id
                    )
                )
            ).all()
        )
        for maintainer_id in maintainer_ids:
            if maintainer_id and maintainer_id not in seen:
                recipients.append(maintainer_id)
                seen.add(maintainer_id)
        return recipients

    async def _upsert_message(
        self,
        *,
        recipient_id: str,
        type: str,
        dedup_key: str,
        payload: dict[str, Any],
        related_comment_id: int | None = None,
        related_plugin_id: str | None = None,
        related_announcement_id: int | None = None,
        source_author_id: str | None = None,
        created_at: Any | None = None,
    ) -> InboxMessageORM:
        """按 ``(recipient, dedup_key)`` 插入或刷新收件箱消息。

        相同收件人和去重键的记录已存在时，更新载荷及关联字段、刷新 ``created_at``，
        并将 ``revoked`` 状态恢复为 ``unread``，遵循以唯一约束保证分发幂等性的设计。
        """
        existing = await self.session.scalar(
            select(InboxMessageORM).where(
                InboxMessageORM.recipient_id == recipient_id,
                InboxMessageORM.dedup_key == dedup_key,
            )
        )
        when = created_at or utc_now()
        if existing is not None:
            existing.payload = payload
            existing.created_at = when
            existing.related_comment_id = related_comment_id
            existing.related_plugin_id = related_plugin_id
            existing.related_announcement_id = related_announcement_id
            existing.source_author_id = source_author_id
            if existing.status == "revoked":
                existing.status = "unread"
            return existing

        message = InboxMessageORM(
            recipient_id=recipient_id,
            type=type,
            status="unread",
            payload=payload,
            dedup_key=dedup_key,
            related_comment_id=related_comment_id,
            related_plugin_id=related_plugin_id,
            related_announcement_id=related_announcement_id,
            source_author_id=source_author_id,
            created_at=when,
        )
        self.session.add(message)
        return message

    @staticmethod
    def _comment_payload(
        comment: PluginCommentORM, *, kind: str
    ) -> dict[str, Any]:
        """构建随提及或回复消息保存的 JSON 载荷。"""
        text = (comment.content or "").strip()
        return {
            "kind": kind,
            "comment_id": comment.id,
            "plugin_id": comment.plugin_id,
            "preview": text[:PREVIEW_MAX_LENGTH],
        }

    async def _project_messages(
        self, rows: list[InboxMessageORM]
    ) -> list[InboxMessage]:
        """将 ORM 记录转换为 ``InboxMessage`` 数据模型。"""
        if not rows:
            return []

        source_ids = {
            row.source_author_id
            for row in rows
            if row.source_author_id is not None
        }
        sources: dict[str, AuthorORM] = {}
        if source_ids:
            source_rows = list(
                (
                    await self.session.scalars(
                        select(AuthorORM).where(
                            AuthorORM.author_id.in_(source_ids)
                        )
                    )
                ).all()
            )
            sources = {row.author_id: row for row in source_rows}

        out: list[InboxMessage] = []
        for row in rows:
            payload = dict(row.payload or {})
            preview_value = payload.get("preview", "")
            preview = (
                str(preview_value) if preview_value is not None else ""
            )

            source: InboxMessageSource | None = None
            if row.source_author_id is not None:
                source_row = sources.get(row.source_author_id)
                if source_row is not None:
                    source = InboxMessageSource(
                        author_id=source_row.author_id,
                        github_login=source_row.github_login,
                        display_name=source_row.display_name,
                        avatar_url=source_row.avatar_url,
                    )

            out.append(
                InboxMessage(
                    id=row.id,
                    type=row.type,  # type: ignore[arg-type]
                    status=row.status,  # type: ignore[arg-type]
                    preview=preview,
                    payload=payload,
                    source=source,
                    link=_build_link(row),
                    related_plugin_id=row.related_plugin_id,
                    related_comment_id=row.related_comment_id,
                    related_announcement_id=row.related_announcement_id,
                    created_at=row.created_at,
                    read_at=row.read_at,
                )
            )
        return out


# ---------------------------------------------------------------------------
# 模块级辅助函数
# ---------------------------------------------------------------------------


def _build_link(row: InboxMessageORM) -> InboxMessageLink:
    """为收件箱消息构建导航目标。

    前端据此将提及和回复定位到评论锚点，将治理消息链接到插件页面，
    并将公告消息定位到对应弹窗。
    """
    if row.related_comment_id is not None:
        return InboxMessageLink(
            kind="comment",
            plugin_id=row.related_plugin_id,
            comment_id=row.related_comment_id,
        )
    if row.related_announcement_id is not None:
        return InboxMessageLink(
            kind="announcement",
            announcement_id=row.related_announcement_id,
        )
    if row.related_plugin_id is not None:
        return InboxMessageLink(kind="plugin", plugin_id=row.related_plugin_id)
    return InboxMessageLink(kind="system")
