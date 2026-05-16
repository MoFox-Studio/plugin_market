"""Operations console curation service.

Implements Requirement 2 and the service-layer portion of Requirement 1:

* :func:`is_visible` is a pure function over one ``CurationEntryORM`` row,
  the current viewer, and the evaluation time. It covers only predicates that
  are intrinsic to the curation row itself: ``enabled``, schedule window, and
  ``audience``.
* :meth:`validate_entry` enforces Property 7: when an author-targeted curation
  entry carries ``signature_plugin_id``, that plugin must be owned or
  maintained by the referenced author.
* Every write path appends an audit row to ``review_records`` using the
  dedicated curation ``ReviewAction`` values.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any, Iterable, Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from plugin_market_backend.enums import ReviewAction
from plugin_market_backend.errors import ApiError
from plugin_market_backend.orm import (
    AuthorORM,
    CurationEntryORM,
    PluginMaintainerORM,
    PluginORM,
    ReviewRecordORM,
    utc_now,
)
from plugin_market_backend.schemas import CurationEntryDTO
from plugin_market_backend.services._audience import audience_matches

if TYPE_CHECKING:
    pass


def _strip_tz(dt: datetime) -> datetime:
    """Normalize SQLite-returned datetimes for safe comparison."""

    if dt.tzinfo is not None:
        return dt.replace(tzinfo=None)
    return dt


def is_visible(
    entry: "CurationEntryORM",
    viewer: "AuthorORM | None",
    now: datetime,
    *,
    viewer_has_plugin: bool = False,
) -> bool:
    """Return whether ``entry`` should be shown to ``viewer`` at ``now``.

    This predicate is intentionally pure. Target resource visibility
    (for example, whether the referenced plugin is publicly visible) is
    evaluated by the caller that already has those rows loaded.
    """

    if not entry.enabled:
        return False

    now_naive = _strip_tz(now)
    if entry.starts_at is not None and _strip_tz(entry.starts_at) > now_naive:
        return False
    if entry.ends_at is not None and now_naive > _strip_tz(entry.ends_at):
        return False
    return audience_matches(
        entry.audience,
        viewer,
        viewer_has_plugin=viewer_has_plugin,
    )


class CurationService:
    """Curate ``curation_entries`` rows used by the home page showcase."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def validate_entry(self, entry: Any) -> None:
        data = _payload_data(entry)
        target_type = data.get("target_type")
        target_id = data.get("target_id")
        signature_plugin_id = data.get("signature_plugin_id")
        starts_at = data.get("starts_at")
        ends_at = data.get("ends_at")

        if starts_at is not None and ends_at is not None:
            if _strip_tz(starts_at) > _strip_tz(ends_at):
                raise ApiError(
                    422,
                    "CURATION_INVALID_SCHEDULE",
                    "starts_at must be earlier than or equal to ends_at.",
                    {"starts_at": starts_at.isoformat(), "ends_at": ends_at.isoformat()},
                )

        if target_type == "plugin":
            plugin = await self.session.get(PluginORM, target_id)
            if plugin is None:
                raise ApiError(
                    404,
                    "CURATION_TARGET_NOT_FOUND",
                    "Referenced plugin was not found.",
                    {"target_type": target_type, "target_id": target_id},
                )

        if target_type == "author":
            author = await self.session.get(AuthorORM, target_id)
            if author is None:
                raise ApiError(
                    404,
                    "CURATION_TARGET_NOT_FOUND",
                    "Referenced author was not found.",
                    {"target_type": target_type, "target_id": target_id},
                )

        if signature_plugin_id and target_type != "author":
            raise ApiError(
                422,
                "CURATION_SIGNATURE_INVALID_TARGET",
                "signature_plugin_id is only allowed for author-targeted entries.",
                {"target_type": target_type, "signature_plugin_id": signature_plugin_id},
            )

        if target_type == "author" and signature_plugin_id:
            plugin = await self.session.scalar(
                select(PluginORM).where(PluginORM.plugin_id == signature_plugin_id)
            )
            if plugin is None:
                raise ApiError(
                    404,
                    "CURATION_SIGNATURE_PLUGIN_NOT_FOUND",
                    "Signature plugin was not found.",
                    {"plugin_id": signature_plugin_id},
                )

            maintainer_ids = set(
                (
                    await self.session.scalars(
                        select(PluginMaintainerORM.author_id).where(
                            PluginMaintainerORM.plugin_id == signature_plugin_id
                        )
                    )
                ).all()
            )
            if plugin.owner_id != target_id and target_id not in maintainer_ids:
                raise ApiError(
                    422,
                    "CURATION_SIGNATURE_NOT_OWNED",
                    "Signature plugin must be owned or maintained by the referenced author.",
                    {
                        "target_id": target_id,
                        "signature_plugin_id": signature_plugin_id,
                    },
                )

    async def list_entries(self) -> list[CurationEntryDTO]:
        stmt = select(CurationEntryORM).order_by(
            CurationEntryORM.sort_order.asc(),
            CurationEntryORM.created_at.asc(),
            CurationEntryORM.id.asc(),
        )
        rows: Sequence[CurationEntryORM] = list((await self.session.scalars(stmt)).all())
        return [_orm_to_dto(item) for item in rows]

    async def create(self, payload: Any, operator_id: str) -> CurationEntryDTO:
        await self.validate_entry(payload)
        now = utc_now()
        data = _payload_data(payload)

        record = CurationEntryORM(
            slot_type=data["slot_type"],
            target_type=data["target_type"],
            target_id=data["target_id"],
            signature_plugin_id=data.get("signature_plugin_id"),
            sort_order=int(data.get("sort_order", 0) or 0),
            enabled=bool(data.get("enabled", True)),
            starts_at=data.get("starts_at"),
            ends_at=data.get("ends_at"),
            audience=data.get("audience", "all"),
            display_meta=dict(data.get("display_meta") or {}),
            created_by=operator_id,
            created_at=now,
            updated_at=now,
        )
        self.session.add(record)
        await self.session.flush()

        self._audit(
            action=ReviewAction.CREATE_CURATION,
            target_id=str(record.id),
            operator_id=operator_id,
        )
        await self.session.flush()
        return _orm_to_dto(record)

    async def update(
        self,
        entry_id: int,
        payload: Any,
        operator_id: str,
    ) -> CurationEntryDTO:
        record = await self._get_or_404(entry_id)
        update_data = _payload_data(payload, exclude_unset=True)

        candidate = {
            "slot_type": record.slot_type,
            "target_type": record.target_type,
            "target_id": record.target_id,
            "signature_plugin_id": record.signature_plugin_id,
            "sort_order": record.sort_order,
            "enabled": record.enabled,
            "starts_at": record.starts_at,
            "ends_at": record.ends_at,
            "audience": record.audience,
            "display_meta": record.display_meta,
        }
        candidate.update(update_data)
        await self.validate_entry(candidate)

        for field, value in update_data.items():
            setattr(record, field, value)
        record.updated_at = utc_now()

        self._audit(
            action=ReviewAction.UPDATE_CURATION,
            target_id=str(record.id),
            operator_id=operator_id,
        )
        await self.session.flush()
        return _orm_to_dto(record)

    async def disable(self, entry_id: int, operator_id: str) -> CurationEntryDTO:
        record = await self._get_or_404(entry_id)
        record.enabled = False
        record.updated_at = utc_now()
        self._audit(
            action=ReviewAction.DISABLE_CURATION,
            target_id=str(record.id),
            operator_id=operator_id,
        )
        await self.session.flush()
        return _orm_to_dto(record)

    async def reorder(
        self,
        ids_in_order: Iterable[int],
        operator_id: str,
    ) -> list[CurationEntryDTO]:
        ids = list(ids_in_order)
        if not ids:
            raise ApiError(
                422,
                "CURATION_REORDER_EMPTY",
                "ids_in_order must not be empty.",
            )

        if len(set(ids)) != len(ids):
            raise ApiError(
                422,
                "CURATION_REORDER_DUPLICATE_IDS",
                "ids_in_order must not contain duplicates.",
                {"ids_in_order": ids},
            )

        stmt = select(CurationEntryORM).where(CurationEntryORM.id.in_(ids))
        rows = list((await self.session.scalars(stmt)).all())
        row_map = {row.id: row for row in rows}
        missing = [entry_id for entry_id in ids if entry_id not in row_map]
        if missing:
            raise ApiError(
                404,
                "CURATION_NOT_FOUND",
                "One or more curation entries were not found.",
                {"missing_ids": missing},
            )

        now = utc_now()
        for index, entry_id in enumerate(ids):
            row = row_map[entry_id]
            row.sort_order = index
            row.updated_at = now
            self._audit(
                action=ReviewAction.UPDATE_CURATION,
                target_id=str(row.id),
                operator_id=operator_id,
            )

        await self.session.flush()
        return [_orm_to_dto(row_map[entry_id]) for entry_id in ids]

    async def _get_or_404(self, entry_id: int) -> CurationEntryORM:
        record = await self.session.get(CurationEntryORM, entry_id)
        if record is None:
            raise ApiError(
                404,
                "CURATION_NOT_FOUND",
                "Curation entry not found.",
                {"entry_id": entry_id},
            )
        return record

    def _audit(
        self,
        *,
        action: ReviewAction,
        target_id: str,
        operator_id: str,
        reason: str | None = None,
    ) -> None:
        self.session.add(
            ReviewRecordORM(
                target_type="curation",
                target_id=target_id,
                action=action,
                status_before=None,
                status_after=None,
                reason=reason,
                operator_id=operator_id,
            )
        )


def _payload_data(payload: Any, *, exclude_unset: bool = False) -> dict[str, Any]:
    if hasattr(payload, "model_dump"):
        return dict(payload.model_dump(exclude_unset=exclude_unset))
    if isinstance(payload, dict):
        return dict(payload)
    return {
        key: value
        for key, value in vars(payload).items()
        if not key.startswith("_") and (not exclude_unset or value is not None)
    }


def _orm_to_dto(record: CurationEntryORM) -> CurationEntryDTO:
    return CurationEntryDTO(
        id=record.id,
        slot_type=record.slot_type,  # type: ignore[arg-type]
        target_type=record.target_type,  # type: ignore[arg-type]
        target_id=record.target_id,
        signature_plugin_id=record.signature_plugin_id,
        sort_order=record.sort_order,
        enabled=record.enabled,
        starts_at=record.starts_at,
        ends_at=record.ends_at,
        audience=record.audience,  # type: ignore[arg-type]
        display_meta=dict(record.display_meta or {}),
        created_by=record.created_by,
        created_at=record.created_at,
        updated_at=record.updated_at,
    )
