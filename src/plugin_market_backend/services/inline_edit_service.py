"""提供插件名称、图标、分类和标签的行内元数据编辑服务。

实现需求 5 和性质 5：所有者、维护者或管理员无需调用完整的所有者更新端点，
即可修改插件的 ``display_name``、``icon_url``、``categories`` 和 ``tags``。
每次局部更新都会：

* 委托 ``plugin_market_backend.services._authz.assert_can_edit_plugin_metadata``
  检查权限，统一保证元数据写入仅限所有者、维护者或管理员；
* 在数据模型层（Pydantic 的 ``PluginMetadataPatch``）和业务层校验各字段，
  包括分类归属、标签数量与长度，以及图标 URL 的 HTTPS 或内部媒体路径要求；
* 向 ``plugin_metadata_changes`` 写入一条记录，准确记录操作者提交的字段
  （需求 5.8 的审计轨迹）；
* 更新插件的 ``updated_at`` 时间戳（需求 5.7）。

即使操作影响已发布插件，本服务也刻意不写入 ``review_records``。
按照行内插件编辑的设计决策，自助编辑使用独立审计表，
使治理记录专注于管理员操作；可选值 ``ReviewAction.INLINE_EDIT_PLUGIN``
预留给后续任务实现的重新审核流程。
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from plugin_market_backend.errors import ApiError
from plugin_market_backend.orm import (
    PluginMetadataChangeORM,
    PluginORM,
    utc_now,
)
from plugin_market_backend.schemas import PluginMetadataPatch
from plugin_market_backend.services._authz import assert_can_edit_plugin_metadata


# 行内编辑器公开的可编辑字段。集合外的字段表示调用方有误，
# 因此防御性地拒绝未知字段。
_PATCHABLE_FIELDS: frozenset[str] = frozenset(
    {"display_name", "icon_url", "categories", "tags"}
)

# 单个标签的长度限制与 PluginMetadataPatch 及需求 5.5 保持一致。
_MAX_TAGS = 10
_MIN_TAG_LENGTH = 1
_MAX_TAG_LENGTH = 40
_MAX_DISPLAY_NAME_LENGTH = 200


class InlineEditService:
    """提供自助插件元数据编辑，并通过 ``plugin_metadata_changes`` 记录变更。"""

    def __init__(self, session: AsyncSession) -> None:
        """将服务绑定到单个异步事务会话。"""
        self.session = session

    async def patch_metadata(
        self,
        viewer_id: str,
        plugin_id: str,
        fields: dict[str, Any],
    ) -> PluginORM:
        """应用行内元数据局部更新并追加审计记录。

        Args:
            viewer_id: 请求编辑的作者 ID；必须是插件所有者、已登记维护者或管理员。
            plugin_id: 待更新插件的 ID。
            fields: 待修改字段的映射。支持 ``display_name``、``icon_url``、
                ``categories`` 和 ``tags``；校验后必须至少包含一个已提供的字段，
                否则抛出 ``METADATA_NO_FIELDS``。

        Returns:
            更新后已加载的 ``PluginORM`` 记录，调用方可转换为
            ``plugin_market_backend.schemas.Plugin``。

        Raises:
            ApiError: 无编辑权限时返回 ``METADATA_FORBIDDEN``（403）；
                字段缺失、字段不受支持或值不合法时返回对应的元数据错误码（422）。
        """
        # 1. 权限检查：性质 5 的统一检查入口。
        plugin = await assert_can_edit_plugin_metadata(
            self.session, plugin_id, viewer_id
        )

        # 2. 在数据模型校验前拒绝不支持的字段，使调用方得到明确的
        #    ``METADATA_INVALID_FIELD`` 错误码，而不是通用的 Pydantic 错误。
        unknown_keys = set(fields).difference(_PATCHABLE_FIELDS)
        if unknown_keys:
            raise ApiError(
                422,
                "METADATA_INVALID_FIELD",
                "行内元数据更新包含不支持的字段。",
                {"fields": sorted(unknown_keys)},
            )

        # 3. 先对原始字段映射执行业务校验，以返回任务要求的错误码
        #    （METADATA_TAGS_TOO_MANY / METADATA_INVALID_ICON 等），
        #    避免被 Pydantic 的 ValidationError 覆盖。
        if "display_name" in fields:
            _validate_display_name(fields["display_name"])

        if "icon_url" in fields:
            _validate_icon_url(fields["icon_url"])

        if "tags" in fields:
            _validate_tags(fields["tags"])

        if "categories" in fields:
            await self._validate_categories(fields["categories"])

        # 4. 通过 Pydantic 执行数据模型校验。在业务检查之后进行二次防护，
        #    规范化 HttpUrl、list[str] 等类型，并拒绝遗漏的无效输入。
        try:
            patch = PluginMetadataPatch.model_validate(
                {key: value for key, value in fields.items() if key in _PATCHABLE_FIELDS}
            )
        except ValueError as exc:  # pragma: no cover - 防御性处理
            raise ApiError(
                422,
                "METADATA_INVALID_FIELD",
                "行内元数据更新未通过数据模型校验。",
                {"errors": str(exc)},
            ) from exc
        provided = patch.model_dump(exclude_unset=True)

        if not provided:
            raise ApiError(
                422,
                "METADATA_NO_FIELDS",
                "至少需要提供一个可编辑字段。",
                {"plugin_id": plugin_id},
            )

        # 5. 应用局部更新，将 HttpUrl 转回字符串存储，
        #    以匹配现有的可空 ``String(1000)`` 字段。
        changed_fields: dict[str, Any] = {}
        if "display_name" in provided:
            plugin.display_name = provided["display_name"]
            changed_fields["display_name"] = provided["display_name"]
        if "icon_url" in provided:
            icon_value = provided["icon_url"]
            icon_str = str(icon_value) if icon_value is not None else None
            plugin.icon_url = icon_str
            changed_fields["icon_url"] = icon_str
        if "categories" in provided:
            categories = list(provided["categories"])
            plugin.categories = categories
            changed_fields["categories"] = categories
        if "tags" in provided:
            tags = list(provided["tags"])
            plugin.tags = tags
            changed_fields["tags"] = tags

        # 6. 更新 ``updated_at``（需求 5.7）并写入审计记录。
        now = utc_now()
        plugin.updated_at = now
        self.session.add(
            PluginMetadataChangeORM(
                plugin_id=plugin_id,
                operator_id=viewer_id,
                changed_fields=changed_fields,
                created_at=now,
            )
        )

        await self.session.flush()
        return plugin

    # ------------------------------------------------------------------
    # 内部辅助函数
    # ------------------------------------------------------------------

    async def _validate_categories(self, categories: Any) -> None:
        """拒绝不属于当前分类体系的分类。

        分类集合取自 ``plugins.categories`` JSON 数组的并集，
        与 ``GET /api/v1/categories`` 使用相同数据来源。
        使用实时集合而非静态列表，无需额外配置即可使编辑器与分类体系保持同步。

        Args:
            categories: 待校验的分类列表；``None`` 或空列表无需进一步校验。

        Raises:
            ApiError: 分类不是字符串列表、包含重复项或含有未知分类。
        """
        if categories is None:
            return
        if not isinstance(categories, list) or not all(
            isinstance(item, str) for item in categories
        ):
            raise ApiError(
                422,
                "METADATA_INVALID_CATEGORY",
                "分类必须是字符串列表。",
                {"received": categories},
            )

        if not categories:
            return

        # 提前拒绝重复项，保证写入插件记录的分类已规范化。
        if len(set(categories)) != len(categories):
            raise ApiError(
                422,
                "METADATA_INVALID_CATEGORY",
                "分类不能包含重复项。",
                {"received": categories},
            )

        rows = await self.session.scalars(select(PluginORM.categories))
        known: set[str] = set()
        for row in rows:
            for value in row or []:
                if isinstance(value, str):
                    known.add(value)

        invalid = sorted({value for value in categories if value not in known})
        if invalid:
            raise ApiError(
                422,
                "METADATA_INVALID_CATEGORY",
                "分类中包含不属于分类体系的值。",
                {"invalid": invalid, "known": sorted(known)},
            )


def _validate_display_name(value: Any) -> None:
    """提前拒绝为空或过长的显示名称。"""
    if value is None:
        return
    if not isinstance(value, str):
        raise ApiError(
            422,
            "METADATA_INVALID_FIELD",
            "display_name 必须是字符串。",
            {"field": "display_name"},
        )
    stripped = value.strip()
    if not stripped:
        raise ApiError(
            422,
            "METADATA_INVALID_FIELD",
            "display_name 不能为空。",
            {"field": "display_name"},
        )
    if len(value) > _MAX_DISPLAY_NAME_LENGTH:
        raise ApiError(
            422,
            "METADATA_INVALID_FIELD",
            "display_name 过长。",
            {"max_length": _MAX_DISPLAY_NAME_LENGTH, "received": len(value)},
        )


def _validate_icon_url(value: Any) -> None:
    """要求图标使用 HTTPS URL 或内部媒体路径。"""
    if value is None:
        return
    if not isinstance(value, str):
        try:
            value = str(value)
        except Exception as exc:
            raise ApiError(
                422,
                "METADATA_INVALID_ICON",
                "icon_url 必须是字符串。",
                {"field": "icon_url"},
            ) from exc
    stripped = value.strip()
    # 接受三种形式：
    #   1) HTTPS URL（外部图标）
    #   2) /plugin-media/...（由本服务器托管的上传图标）
    #   3) 空字符串（无图标），由调用方规范化为 None
    if not stripped:
        return
    if stripped.startswith("/plugin-media/"):
        return
    lowered = stripped.lower()
    if not lowered.startswith("https://"):
        raise ApiError(
            422,
            "METADATA_INVALID_ICON",
            "icon_url 必须使用 HTTPS 协议或内部 /plugin-media/ 路径。",
            {"received": value},
        )


def _validate_tags(tags: Any) -> None:
    """限制标签数量及单个标签长度。

    ``PluginMetadataPatch`` 数据模型也执行相同检查；在此处保留业务规则，
    可在 Pydantic 抛出通用 ``ValidationError`` 前，返回需求 5 要求的
    ``METADATA_TAGS_TOO_MANY`` 错误码。

    Args:
        tags: 待校验的标签列表。

    Raises:
        ApiError: 标签不是列表、数量超限，或标签不是长度为 1 至 40 的字符串。
    """
    if not isinstance(tags, list):
        raise ApiError(
            422,
            "METADATA_INVALID_FIELD",
            "tags 必须是字符串列表。",
            {"field": "tags"},
        )
    if len(tags) > _MAX_TAGS:
        raise ApiError(
            422,
            "METADATA_TAGS_TOO_MANY",
            f"最多允许 {_MAX_TAGS} 个标签。",
            {"limit": _MAX_TAGS, "received": len(tags)},
        )
    for tag in tags:
        if not isinstance(tag, str) or not (
            _MIN_TAG_LENGTH <= len(tag) <= _MAX_TAG_LENGTH
        ):
            raise ApiError(
                422,
                "METADATA_INVALID_FIELD",
                "每个标签必须为 1 至 40 个字符。",
                {"field": "tags", "value": tag},
            )
