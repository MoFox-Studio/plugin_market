"""Domain service layer for the plugin market backend.

Each module in this package owns a single bounded responsibility and follows
the same shape: a service class taking an ``AsyncSession`` in its constructor
and exposing async methods. This package will be populated by tasks 4 through
9; the current commit only ships the skeleton, the shared authorization gate
``assert_can_edit_plugin_metadata``, and the pure ``audience_matches``
predicate.

Importing from this package never triggers a circular import with
``plugin_market_backend.service`` (the legacy module), and ``service.py``
re-exports ``MarketService`` so existing call sites stay valid.
"""

from __future__ import annotations

from plugin_market_backend.services._audience import (
    AUDIENCE_VALUES,
    audience_matches,
)
from plugin_market_backend.services._authz import assert_can_edit_plugin_metadata
from plugin_market_backend.services.announcements_service import AnnouncementsService
from plugin_market_backend.services.bulk_ops_service import BulkOpsService
from plugin_market_backend.services.curation_service import CurationService
from plugin_market_backend.services.inbox_service import InboxService
from plugin_market_backend.services.inline_edit_service import InlineEditService
from plugin_market_backend.services.profile_service import ProfileService
from plugin_market_backend.services.skill_service import SkillService

__all__ = [
    "AUDIENCE_VALUES",
    "AnnouncementsService",
    "BulkOpsService",
    "CurationService",
    "InboxService",
    "InlineEditService",
    "ProfileService",
    "SkillService",
    "assert_can_edit_plugin_metadata",
    "audience_matches",
]
