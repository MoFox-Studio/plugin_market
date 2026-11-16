"""提供插件市场后端的领域服务层。

本包各模块分别承担边界明确的职责。服务类在构造时接收 ``AsyncSession``，
并提供异步方法；共享授权检查 ``assert_can_edit_plugin_metadata`` 和
纯函数 ``audience_matches`` 则用于复用权限与受众判断。

本包可与旧模块 ``plugin_market_backend.service`` 配合使用，
现有调用方仍可通过 ``service.py`` 导入 ``MarketService``。
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
from plugin_market_backend.services.skill_service import SkillService, synchronize_skill_storage

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
    "synchronize_skill_storage",
]
