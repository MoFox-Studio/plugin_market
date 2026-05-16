"""Author profile, background, and pinned plugin service.

This module implements the personal-space backend (Requirements 3 and 4):

* :class:`ProfileService.get_profile` / :meth:`update_profile` read and write
  the ``author_profiles`` row for one author. Profiles are lazily created on
  first write so existing accounts do not need a backfill.
* :class:`ProfileService.list_pins` / :meth:`add_pin` /
  :meth:`update_pin_reason` / :meth:`remove_pin` manage the
  ``pinned_plugins`` table while preserving Property 6 invariants:
    - at most 6 active pins per author,
    - every pin points at a plugin owned or maintained by the author,
    - render order is ``pinned_at`` descending.

All methods raise :class:`plugin_market_backend.errors.ApiError` on failure;
callers are expected to wrap them in ``session_scope`` so the transaction is
committed on success and rolled back on failure.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from plugin_market_backend.errors import ApiError
from plugin_market_backend.orm import (
    AuthorProfileORM,
    PinnedPluginORM,
    PluginMaintainerORM,
    PluginORM,
    utc_now,
)
from plugin_market_backend.schemas import (
    AuthorProfile,
    PinnedPluginItem,
    Plugin,
)


MAX_BIO_LENGTH = 2000
MAX_PIN_REASON_LENGTH = 200
MAX_ACTIVE_PINS = 6


class ProfileService:
    """Manage ``author_profiles`` and ``pinned_plugins`` rows.

    The service keeps the personal-space writes in a single bounded module so
    Property 6 (pinned invariants) can be enforced in exactly one place.
    """

    def __init__(self, session: AsyncSession) -> None:
        """Create a service bound to one transactional session."""

        self.session = session

    # ------------------------------------------------------------------
    # Profile (bio / background)
    # ------------------------------------------------------------------

    async def get_profile(self, author_id: str) -> AuthorProfile:
        """Return the profile row for ``author_id``.

        If the author has never updated their profile we synthesize a default
        ``AuthorProfile`` instance with an empty bio and no background image.
        The row is not created until the author saves a change.
        """

        record = await self.session.get(AuthorProfileORM, author_id)
        if record is None:
            return AuthorProfile(author_id=author_id, bio="", background_image_url=None)
        return _profile_to_schema(record)

    async def update_profile(
        self,
        author_id: str,
        *,
        bio: str | None = None,
        background_image_url: str | None = None,
    ) -> AuthorProfile:
        """Update the bio and/or background image for ``author_id``.

        Args:
            author_id: The owner of the profile row.
            bio: New bio text. ``None`` means "do not change". Empty string
                clears the bio. Length is capped at 2000 characters
                (Requirement 3.2).
            background_image_url: New background image URL. ``None`` means
                "do not change". An empty string clears the background.
                Non-https URLs are rejected (Requirement 3.5 / design's
                ``PROFILE_BACKGROUND_INVALID_URL``).

        Returns:
            The updated profile schema.
        """

        if bio is not None and len(bio) > MAX_BIO_LENGTH:
            raise ApiError(
                422,
                "PROFILE_BIO_TOO_LONG",
                f"Bio must be at most {MAX_BIO_LENGTH} characters.",
                {"max_length": MAX_BIO_LENGTH, "received": len(bio)},
            )
        if background_image_url is not None and background_image_url:
            _assert_https_url(background_image_url)

        record = await self.session.get(AuthorProfileORM, author_id)
        if record is None:
            record = AuthorProfileORM(
                author_id=author_id,
                bio=bio if bio is not None else "",
                background_image_url=background_image_url or None,
                background_image_kind="url",
            )
            self.session.add(record)
        else:
            if bio is not None:
                record.bio = bio
            if background_image_url is not None:
                # If the previous background was an upload and we are about to
                # replace or clear it, delete the orphan file on disk.
                from plugin_market_backend.content import delete_profile_background_url

                if record.background_image_kind == "upload" and record.background_image_url:
                    if record.background_image_url != background_image_url:
                        delete_profile_background_url(record.background_image_url)
                record.background_image_url = background_image_url or None
                record.background_image_kind = "url"
        record.updated_at = utc_now()
        await self.session.flush()
        return _profile_to_schema(record)

    async def set_background_from_upload(
        self,
        author_id: str,
        raw_bytes: bytes,
    ) -> AuthorProfile:
        """Persist an uploaded background image and update the profile."""

        from plugin_market_backend.content import (
            delete_profile_background_url,
            store_profile_background,
        )

        new_url = store_profile_background(author_id, raw_bytes)

        record = await self.session.get(AuthorProfileORM, author_id)
        if record is None:
            record = AuthorProfileORM(
                author_id=author_id,
                bio="",
                background_image_url=new_url,
                background_image_kind="upload",
            )
            self.session.add(record)
        else:
            # Best-effort cleanup of the previous upload to avoid orphan files.
            if record.background_image_kind == "upload":
                delete_profile_background_url(record.background_image_url)
            record.background_image_url = new_url
            record.background_image_kind = "upload"
        record.updated_at = utc_now()
        await self.session.flush()
        return _profile_to_schema(record)

    # ------------------------------------------------------------------
    # Pinned plugins
    # ------------------------------------------------------------------

    async def list_pins(self, author_id: str) -> list[PinnedPluginItem]:
        """Return the active pin slots for ``author_id`` ordered by pinned_at desc."""

        stmt = (
            select(PinnedPluginORM)
            .where(PinnedPluginORM.author_id == author_id)
            .order_by(PinnedPluginORM.pinned_at.desc(), PinnedPluginORM.id.desc())
        )
        rows = list((await self.session.scalars(stmt)).all())
        if not rows:
            return []

        plugin_ids = [row.plugin_id for row in rows]
        plugin_stmt = (
            select(PluginORM)
            .options(
                selectinload(PluginORM.maintainers),
                selectinload(PluginORM.owner),
                selectinload(PluginORM.versions),
            )
            .where(PluginORM.plugin_id.in_(plugin_ids))
        )
        plugin_map: dict[str, PluginORM] = {
            plugin.plugin_id: plugin
            for plugin in (await self.session.scalars(plugin_stmt)).all()
        }

        return [
            PinnedPluginItem(
                plugin_id=row.plugin_id,
                pinned_reason=row.pinned_reason,
                pinned_at=row.pinned_at,
                plugin=_plugin_to_schema(plugin_map.get(row.plugin_id)),
            )
            for row in rows
        ]

    async def add_pin(
        self,
        author_id: str,
        plugin_id: str,
        reason: str | None = None,
    ) -> PinnedPluginItem:
        """Add a new pin for ``author_id``.

        Enforces:

        * the plugin must exist (``PIN_PLUGIN_NOT_FOUND``),
        * the author must own or maintain it (``PIN_PLUGIN_NOT_OWNED``),
        * the reason length cap of 200 characters,
        * no duplicate pin for the same ``(author_id, plugin_id)`` pair
          (``PIN_ALREADY_EXISTS``),
        * at most 6 active pins per author (``PIN_LIMIT_EXCEEDED``).

        The ``pinned_at`` timestamp is set to ``utc_now`` so the personal
        space renders the most recently added pin first (Requirement 4.8 /
        Property 6).
        """

        _assert_reason_length(reason)
        await self._assert_can_pin(author_id, plugin_id)

        existing = await self.session.scalar(
            select(PinnedPluginORM).where(
                PinnedPluginORM.author_id == author_id,
                PinnedPluginORM.plugin_id == plugin_id,
            )
        )
        if existing is not None:
            raise ApiError(
                409,
                "PIN_ALREADY_EXISTS",
                "This plugin is already pinned.",
                {"author_id": author_id, "plugin_id": plugin_id},
            )

        active_count = await self._count_active_pins(author_id)
        if active_count >= MAX_ACTIVE_PINS:
            raise ApiError(
                409,
                "PIN_LIMIT_EXCEEDED",
                f"At most {MAX_ACTIVE_PINS} pinned plugins are allowed.",
                {"limit": MAX_ACTIVE_PINS, "current": active_count},
            )

        pin = PinnedPluginORM(
            author_id=author_id,
            plugin_id=plugin_id,
            pinned_reason=reason,
            pinned_at=utc_now(),
        )
        self.session.add(pin)
        await self.session.flush()

        plugin_row = await self._load_plugin_for_schema(plugin_id)
        return PinnedPluginItem(
            plugin_id=pin.plugin_id,
            pinned_reason=pin.pinned_reason,
            pinned_at=pin.pinned_at,
            plugin=_plugin_to_schema(plugin_row),
        )

    async def update_pin_reason(
        self,
        author_id: str,
        plugin_id: str,
        reason: str | None,
    ) -> PinnedPluginItem:
        """Replace the ``pinned_reason`` of an existing pin without touching ``pinned_at``."""

        _assert_reason_length(reason)
        pin = await self.session.scalar(
            select(PinnedPluginORM).where(
                PinnedPluginORM.author_id == author_id,
                PinnedPluginORM.plugin_id == plugin_id,
            )
        )
        if pin is None:
            raise ApiError(
                404,
                "PIN_NOT_FOUND",
                "Pinned plugin not found.",
                {"author_id": author_id, "plugin_id": plugin_id},
            )

        pin.pinned_reason = reason
        await self.session.flush()

        plugin_row = await self._load_plugin_for_schema(plugin_id)
        return PinnedPluginItem(
            plugin_id=pin.plugin_id,
            pinned_reason=pin.pinned_reason,
            pinned_at=pin.pinned_at,
            plugin=_plugin_to_schema(plugin_row),
        )

    async def remove_pin(self, author_id: str, plugin_id: str) -> None:
        """Remove the pin record for ``(author_id, plugin_id)``.

        Raises ``PIN_NOT_FOUND`` if there is no matching pin so the caller can
        surface a deterministic error to the client.
        """

        pin = await self.session.scalar(
            select(PinnedPluginORM).where(
                PinnedPluginORM.author_id == author_id,
                PinnedPluginORM.plugin_id == plugin_id,
            )
        )
        if pin is None:
            raise ApiError(
                404,
                "PIN_NOT_FOUND",
                "Pinned plugin not found.",
                {"author_id": author_id, "plugin_id": plugin_id},
            )
        await self.session.delete(pin)
        await self.session.flush()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _assert_can_pin(self, author_id: str, plugin_id: str) -> None:
        """Verify the plugin exists and is owned or maintained by ``author_id``."""

        plugin = await self.session.get(PluginORM, plugin_id)
        if plugin is None:
            raise ApiError(
                404,
                "PIN_PLUGIN_NOT_FOUND",
                "Plugin not found.",
                {"plugin_id": plugin_id},
            )
        if plugin.owner_id == author_id:
            return

        maintainer_stmt = select(PluginMaintainerORM.id).where(
            PluginMaintainerORM.plugin_id == plugin_id,
            PluginMaintainerORM.author_id == author_id,
        )
        if (await self.session.execute(maintainer_stmt)).first() is not None:
            return

        raise ApiError(
            403,
            "PIN_PLUGIN_NOT_OWNED",
            "You do not own or maintain this plugin.",
            {"author_id": author_id, "plugin_id": plugin_id},
        )

    async def _count_active_pins(self, author_id: str) -> int:
        """Return how many pins ``author_id`` currently has."""

        from sqlalchemy import func

        stmt = (
            select(func.count())
            .select_from(PinnedPluginORM)
            .where(PinnedPluginORM.author_id == author_id)
        )
        return int((await self.session.scalar(stmt)) or 0)

    async def _load_plugin_for_schema(self, plugin_id: str) -> PluginORM | None:
        """Load a plugin with the relations the ``Plugin`` schema needs."""

        stmt = (
            select(PluginORM)
            .options(
                selectinload(PluginORM.maintainers),
                selectinload(PluginORM.owner),
                selectinload(PluginORM.versions),
            )
            .where(PluginORM.plugin_id == plugin_id)
        )
        return await self.session.scalar(stmt)


# ----------------------------------------------------------------------
# Module-level helpers (kept private)
# ----------------------------------------------------------------------


def _profile_to_schema(record: AuthorProfileORM) -> AuthorProfile:
    """Convert an ``AuthorProfileORM`` row into the API schema."""

    kind = record.background_image_kind if record.background_image_kind in {"url", "upload"} else "url"
    return AuthorProfile(
        author_id=record.author_id,
        bio=record.bio or "",
        background_image_url=record.background_image_url,
        background_image_kind=kind,  # type: ignore[arg-type]
        updated_at=record.updated_at,
    )


def _plugin_to_schema(plugin: PluginORM | None) -> Plugin | None:
    """Project a ``PluginORM`` row into the lightweight ``Plugin`` schema.

    Pinned-plugin payloads do not need community stats (likes / ratings /
    downloads), so we keep this projection self-contained instead of taking
    a dependency on :class:`MarketService`.
    """

    if plugin is None:
        return None

    from plugin_market_backend.content import normalize_readme_markdown
    from plugin_market_backend.enums import VersionStatus

    versions = list(plugin.versions or [])
    published = [
        item
        for item in versions
        if item.status == VersionStatus.PUBLISHED and not item.is_yanked
    ]
    latest = max(published, key=lambda item: item.published_at) if published else None
    owner = plugin.owner if getattr(plugin, "owner", None) is not None else None
    return Plugin(
        plugin_id=plugin.plugin_id,
        display_name=plugin.display_name,
        summary=plugin.summary,
        description=plugin.description,
        icon_url=plugin.icon_url,
        has_readme=bool(normalize_readme_markdown(plugin.readme_markdown)),
        homepage=plugin.homepage,
        repository_url=plugin.repository_url,
        license=plugin.license,
        categories=plugin.categories or [],
        tags=plugin.tags or [],
        status=plugin.status,
        owner_id=plugin.owner_id,
        owner_login=owner.github_login if owner is not None else None,
        owner_display_name=owner.display_name if owner is not None else None,
        owner_avatar_url=owner.avatar_url if owner is not None else None,
        maintainers=[item.author_id for item in plugin.maintainers],
        trust_level=plugin.trust_level,
        risk_notice=plugin.risk_notice,
        created_at=plugin.created_at,
        updated_at=plugin.updated_at,
        latest_version=latest.version if latest else None,
        latest_version_published_at=latest.published_at if latest else None,
        downloads_count=sum(int(item.download_count or 0) for item in versions),
    )


def _assert_reason_length(reason: str | None) -> None:
    """Reject pin reasons longer than 200 characters."""

    if reason is None:
        return
    if len(reason) > MAX_PIN_REASON_LENGTH:
        raise ApiError(
            422,
            "PIN_REASON_TOO_LONG",
            f"Pinned reason must be at most {MAX_PIN_REASON_LENGTH} characters.",
            {"max_length": MAX_PIN_REASON_LENGTH, "received": len(reason)},
        )


def _assert_https_url(url: str) -> None:
    """Reject background URLs that are neither https nor an internal media path."""

    stripped = url.strip()
    if not stripped:
        return
    if stripped.startswith("/plugin-media/"):
        return
    lowered = stripped.lower()
    if not lowered.startswith("https://"):
        raise ApiError(
            422,
            "PROFILE_BACKGROUND_INVALID_URL",
            "Background image URL must use the https scheme or be an internal /plugin-media/ path.",
            {"received": url},
        )
