"""提供插件批量治理服务。

实现任务 9：将管理员治理操作应用于一批插件，并通过保存点隔离各条记录的失败。
"""

from __future__ import annotations

from typing import Any, Iterable

from plugin_market_backend.enums import PluginStatus, ReviewAction, TrustLevel
from plugin_market_backend.errors import ApiError
from plugin_market_backend.orm import utc_now
from plugin_market_backend.schemas import BulkActionItemError, BulkActionItemResult, BulkActionResult
from sqlalchemy.ext.asyncio import AsyncSession


MAX_BULK_TARGETS = 100


class BulkOpsService:
    """批量执行插件治理操作，并保证每条记录的操作具有原子性。"""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def bulk_apply(
        self,
        operator_id: str,
        plugin_ids: Iterable[str],
        action: str,
        params: dict[str, Any] | None = None,
    ) -> BulkActionResult:
        ids = [str(plugin_id).strip() for plugin_id in plugin_ids if str(plugin_id).strip()]
        if len(ids) > MAX_BULK_TARGETS:
            raise ApiError(
                422,
                "BULK_TOO_MANY_TARGETS",
                f"批量操作最多接受 {MAX_BULK_TARGETS} 个插件。",
                {"limit": MAX_BULK_TARGETS, "received": len(ids)},
            )
        if not ids:
            raise ApiError(
                422,
                "BULK_NO_TARGETS",
                "至少需要一个插件 ID。",
            )

        normalized_action = str(action or "").strip()
        normalized_params = dict(params or {})
        reason = normalized_params.get("reason")
        trust_level = self._parse_trust_level(normalized_action, normalized_params)
        if normalized_action == "delete" and not reason:
            raise ApiError(
                422,
                "BULK_MISSING_REASON",
                "执行 delete 操作时必须提供 params.reason。",
            )

        results: list[BulkActionItemResult] = []
        for plugin_id in ids:
            try:
                async with self.session.begin_nested():
                    item = await self._apply_one(
                        operator_id=operator_id,
                        plugin_id=plugin_id,
                        action=normalized_action,
                        reason=reason,
                        trust_level=trust_level,
                    )
                results.append(item)
            except ApiError as exc:
                results.append(
                    BulkActionItemResult(
                        plugin_id=plugin_id,
                        ok=False,
                        error=BulkActionItemError(code=exc.code, message=exc.message),
                    )
                )
            except Exception as exc:  # pragma: no cover - 防御性处理
                results.append(
                    BulkActionItemResult(
                        plugin_id=plugin_id,
                        ok=False,
                        error=BulkActionItemError(
                            code="BULK_OPERATION_FAILED",
                            message=str(exc) or "批量操作失败。",
                        ),
                    )
                )

        await self.session.flush()
        return BulkActionResult(results=results)

    async def _apply_one(
        self,
        *,
        operator_id: str,
        plugin_id: str,
        action: str,
        reason: str | None,
        trust_level: TrustLevel | None,
    ) -> BulkActionItemResult:
        from plugin_market_backend.service import MarketService

        market = MarketService(self.session)

        if action == "delete":
            await market._get_plugin_orm(plugin_id)
            await market.delete_plugin(plugin_id)
            await market._record(
                "plugin",
                plugin_id,
                ReviewAction.BULK_DELETE,
                None,
                None,
                operator_id,
                reason,
            )
            await self.session.flush()
            return BulkActionItemResult(plugin_id=plugin_id, ok=True, after=None)

        plugin = await market._get_plugin_orm(plugin_id)
        if action == "publish":
            before = plugin.status
            plugin.status = PluginStatus.PUBLISHED
            audit_action = ReviewAction.BULK_PUBLISH
            after_value = plugin.status
        elif action == "reject":
            before = plugin.status
            plugin.status = PluginStatus.DRAFT
            audit_action = ReviewAction.BULK_REJECT
            after_value = plugin.status
        elif action == "block":
            before = plugin.status
            plugin.status = PluginStatus.BLOCKED
            audit_action = ReviewAction.BULK_BLOCK
            after_value = plugin.status
        elif action == "deprecate":
            before = plugin.status
            plugin.status = PluginStatus.DEPRECATED
            audit_action = ReviewAction.BULK_DEPRECATE
            after_value = plugin.status
        elif action == "set_trust_level":
            if trust_level is None:
                raise ApiError(
                    422,
                    "BULK_MISSING_TRUST_LEVEL",
                    "执行 set_trust_level 操作时必须提供 params.trust_level。",
                )
            before = plugin.trust_level
            plugin.trust_level = trust_level
            audit_action = ReviewAction.BULK_SET_TRUST_LEVEL
            after_value = plugin.trust_level
        else:
            raise ApiError(
                422,
                "BULK_UNKNOWN_ACTION",
                "不支持的批量操作。",
                {"action": action},
            )

        plugin.updated_at = utc_now()
        await market._record(
            "plugin",
            plugin_id,
            audit_action,
            before,
            after_value,
            operator_id,
            reason,
        )
        await self.session.flush()
        after = await market.get_plugin(plugin_id)
        return BulkActionItemResult(plugin_id=plugin_id, ok=True, after=after)

    def _parse_trust_level(
        self,
        action: str,
        params: dict[str, Any],
    ) -> TrustLevel | None:
        if action != "set_trust_level":
            return None
        raw = params.get("trust_level")
        if raw in (None, ""):
            raise ApiError(
                422,
                "BULK_MISSING_TRUST_LEVEL",
                "执行 set_trust_level 操作时必须提供 params.trust_level。",
            )
        try:
            return raw if isinstance(raw, TrustLevel) else TrustLevel(str(raw))
        except ValueError as exc:
            raise ApiError(
                422,
                "BULK_INVALID_TRUST_LEVEL",
                "params.trust_level 无效。",
                {"trust_level": raw},
            ) from exc
