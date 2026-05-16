"""Inline metadata edit service (display_name / icon / categories / tags).

Implements Requirement 5 / Property 5 — owner / maintainer / admin can patch
``display_name``, ``icon_url``, ``categories``, and ``tags`` of a plugin
without going through the full owner-update endpoint. Each patch:

* delegates the authorization check to
  :func:`plugin_market_backend.services._authz.assert_can_edit_plugin_metadata`
  so the property "metadata writes require ownership / maintainership / admin"
  has a single enforcement point,
* validates each field at both schema-level (Pydantic in
  :class:`plugin_market_backend.schemas.PluginMetadataPatch`) and
  business-level (categories ⊆ taxonomy, tag count and length, https-only icon
  URL),
* writes one row to ``plugin_metadata_changes`` capturing exactly the fields
  the operator supplied (Requirement 5.8 audit trail), and
* updates the plugin's ``updated_at`` timestamp (Requirement 5.7).

This service intentionally does **not** write a ``review_records`` row even
though the operation can affect a published plugin. Per the design's
"Inline Plugin Editing" decision, inline self-service edits live in their own
audit table to keep the governance trail focused on admin actions; the
optional ``ReviewAction.INLINE_EDIT_PLUGIN`` value is reserved for the
re-review path implemented in a later task.
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


# Editable fields exposed by the inline editor. Anything outside this set is a
# bug in the caller; we reject unknown keys defensively.
_PATCHABLE_FIELDS: frozenset[str] = frozenset(
    {"display_name", "icon_url", "categories", "tags"}
)

# Per-tag length cap kept in sync with PluginMetadataPatch / Requirement 5.5.
_MAX_TAGS = 10
_MIN_TAG_LENGTH = 1
_MAX_TAG_LENGTH = 40
_MAX_DISPLAY_NAME_LENGTH = 200


class InlineEditService:
    """Self-service plugin metadata edits backed by ``plugin_metadata_changes``."""

    def __init__(self, session: AsyncSession) -> None:
        """Bind the service to one transactional async session."""

        self.session = session

    async def patch_metadata(
        self,
        viewer_id: str,
        plugin_id: str,
        fields: dict[str, Any],
    ) -> PluginORM:
        """Apply an inline metadata patch and append an audit row.

        Args:
            viewer_id: The author requesting the edit. Must be the plugin's
                owner, a registered maintainer, or an admin.
            plugin_id: The plugin to patch.
            fields: Mapping of changed fields. Accepted keys are
                ``display_name``, ``icon_url``, ``categories`` and ``tags``.
                The mapping must contain at least one accepted key whose value
                is non-``None`` (otherwise nothing changes and we raise
                ``METADATA_NO_FIELDS``).

        Returns:
            The hydrated ``PluginORM`` row after the patch (caller is free to
            project it through :class:`plugin_market_backend.schemas.Plugin`).

        Raises:
            ApiError: with one of ``METADATA_FORBIDDEN`` (403),
                ``METADATA_NO_FIELDS`` / ``METADATA_INVALID_CATEGORY`` /
                ``METADATA_TAGS_TOO_MANY`` / ``METADATA_INVALID_ICON`` (422).
        """

        # 1. Authorization — single gate for Property 5.
        plugin = await assert_can_edit_plugin_metadata(
            self.session, plugin_id, viewer_id
        )

        # 2. Reject unsupported keys before any schema validation runs so
        #    callers get the deterministic ``METADATA_INVALID_FIELD`` code
        #    instead of a generic Pydantic envelope.
        unknown_keys = set(fields).difference(_PATCHABLE_FIELDS)
        if unknown_keys:
            raise ApiError(
                422,
                "METADATA_INVALID_FIELD",
                "Inline metadata patch received unsupported fields.",
                {"fields": sorted(unknown_keys)},
            )

        # 3. Business-level validation runs first against the raw field map
        #    so the task's required error codes
        #    (METADATA_TAGS_TOO_MANY / METADATA_INVALID_ICON / ...) surface
        #    instead of being masked by a Pydantic ValidationError.
        if "display_name" in fields:
            _validate_display_name(fields["display_name"])

        if "icon_url" in fields:
            _validate_icon_url(fields["icon_url"])

        if "tags" in fields:
            _validate_tags(fields["tags"])

        if "categories" in fields:
            await self._validate_categories(fields["categories"])

        # 4. Schema-level validation through Pydantic. With the business
        #    checks already done, this acts as a belt-and-suspenders pass
        #    that normalizes types (HttpUrl, list[str]) and rejects anything
        #    we missed.
        try:
            patch = PluginMetadataPatch.model_validate(
                {key: value for key, value in fields.items() if key in _PATCHABLE_FIELDS}
            )
        except ValueError as exc:  # pragma: no cover - defensive
            raise ApiError(
                422,
                "METADATA_INVALID_FIELD",
                "Inline metadata patch failed schema validation.",
                {"errors": str(exc)},
            ) from exc
        provided = patch.model_dump(exclude_unset=True)

        if not provided:
            raise ApiError(
                422,
                "METADATA_NO_FIELDS",
                "At least one editable field must be provided.",
                {"plugin_id": plugin_id},
            )

        # 4. Apply the patch. Coerce HttpUrl back to string for storage so the
        #    column matches the existing schema (``String(1000)`` nullable).
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

        # 5. Touch ``updated_at`` (Requirement 5.7) and write the audit row.
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
    # Internal helpers
    # ------------------------------------------------------------------

    async def _validate_categories(self, categories: Any) -> None:
        """Reject categories that are not part of the live taxonomy.

        The taxonomy is derived from the union of ``plugins.categories`` JSON
        arrays — this is the same source served by ``GET /api/v1/categories``.
        Using the live set rather than a static list keeps the editor in sync
        with the taxonomy without an extra config knob.
        """

        if categories is None:
            return
        if not isinstance(categories, list) or not all(
            isinstance(item, str) for item in categories
        ):
            raise ApiError(
                422,
                "METADATA_INVALID_CATEGORY",
                "Categories must be a list of strings.",
                {"received": categories},
            )

        if not categories:
            return

        # Reject duplicates up-front so the resulting plugin row is normalized.
        if len(set(categories)) != len(categories):
            raise ApiError(
                422,
                "METADATA_INVALID_CATEGORY",
                "Categories must not contain duplicates.",
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
                "Categories contain values that are not in the taxonomy.",
                {"invalid": invalid, "known": sorted(known)},
            )


def _validate_display_name(value: Any) -> None:
    """Reject empty / oversized display names early."""

    if value is None:
        return
    if not isinstance(value, str):
        raise ApiError(
            422,
            "METADATA_INVALID_FIELD",
            "display_name must be a string.",
            {"field": "display_name"},
        )
    stripped = value.strip()
    if not stripped:
        raise ApiError(
            422,
            "METADATA_INVALID_FIELD",
            "display_name must not be empty.",
            {"field": "display_name"},
        )
    if len(value) > _MAX_DISPLAY_NAME_LENGTH:
        raise ApiError(
            422,
            "METADATA_INVALID_FIELD",
            "display_name is too long.",
            {"max_length": _MAX_DISPLAY_NAME_LENGTH, "received": len(value)},
        )


def _validate_icon_url(value: Any) -> None:
    """Require https URLs for icon references, or an internal media path."""

    if value is None:
        return
    if not isinstance(value, str):
        try:
            value = str(value)
        except Exception as exc:
            raise ApiError(
                422,
                "METADATA_INVALID_ICON",
                "icon_url must be a string.",
                {"field": "icon_url"},
            ) from exc
    stripped = value.strip()
    # Accept three shapes:
    #   1) https URL (external icon)
    #   2) /plugin-media/... (uploaded icon hosted by this server)
    #   3) empty string (no icon) — caller will normalize to None
    if not stripped:
        return
    if stripped.startswith("/plugin-media/"):
        return
    lowered = stripped.lower()
    if not lowered.startswith("https://"):
        raise ApiError(
            422,
            "METADATA_INVALID_ICON",
            "icon_url must use the https scheme or be an internal /plugin-media/ path.",
            {"received": value},
        )


def _validate_tags(tags: Any) -> None:
    """Cap tag count and bound individual tag lengths.

    The ``PluginMetadataPatch`` schema also runs the same checks, but having
    the business rule here lets us surface the ``METADATA_TAGS_TOO_MANY``
    code expected by Requirement 5 before Pydantic raises a generic
    ``ValidationError``.
    """

    if not isinstance(tags, list):
        raise ApiError(
            422,
            "METADATA_INVALID_FIELD",
            "tags must be a list of strings.",
            {"field": "tags"},
        )
    if len(tags) > _MAX_TAGS:
        raise ApiError(
            422,
            "METADATA_TAGS_TOO_MANY",
            f"At most {_MAX_TAGS} tags are allowed.",
            {"limit": _MAX_TAGS, "received": len(tags)},
        )
    for tag in tags:
        if not isinstance(tag, str) or not (
            _MIN_TAG_LENGTH <= len(tag) <= _MAX_TAG_LENGTH
        ):
            raise ApiError(
                422,
                "METADATA_INVALID_FIELD",
                "Each tag must be 1-40 characters.",
                {"field": "tags", "value": tag},
            )
