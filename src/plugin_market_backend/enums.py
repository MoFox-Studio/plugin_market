"""Shared lifecycle and permission enums for the plugin market backend."""

from __future__ import annotations

from enum import StrEnum


class PluginStatus(StrEnum):
    """Plugin lifecycle states."""

    DRAFT = "draft"
    PENDING_REVIEW = "pending_review"
    PUBLISHED = "published"
    DEPRECATED = "deprecated"
    BLOCKED = "blocked"
    ARCHIVED = "archived"


class VersionStatus(StrEnum):
    """Plugin version lifecycle states."""

    SUBMITTED = "submitted"
    PENDING_REVIEW = "pending_review"
    PUBLISHED = "published"
    YANKED = "yanked"
    BLOCKED = "blocked"


class SyncStatus(StrEnum):
    """Release metadata synchronization states."""

    NONE = "none"
    SUCCESS = "success"
    FAILED = "failed"


class TrustLevel(StrEnum):
    """Plugin trust levels shown by clients."""

    OFFICIAL = "official"
    VERIFIED = "verified"
    COMMUNITY = "community"


class AuthorType(StrEnum):
    """Author account types."""

    USER = "user"
    ORGANIZATION = "organization"


class ReviewAction(StrEnum):
    """Audited market actions."""

    REGISTER_PLUGIN = "register_plugin"
    UPDATE_PLUGIN = "update_plugin"
    SUBMIT_VERSION = "submit_version"
    APPROVE_PLUGIN = "approve_plugin"
    REJECT_PLUGIN = "reject_plugin"
    BLOCK_PLUGIN = "block_plugin"
    DEPRECATE_PLUGIN = "deprecate_plugin"
    ARCHIVE_PLUGIN = "archive_plugin"
    SET_TRUST_LEVEL = "set_trust_level"
    APPROVE_VERSION = "approve_version"
    REJECT_VERSION = "reject_version"
    YANK_VERSION = "yank_version"
    BLOCK_VERSION = "block_version"
    SYNC_VERSION = "sync_version"
    WEBHOOK_RECEIVED = "webhook_received"
    MAINTAINER_ADD = "maintainer_add"
    MAINTAINER_REMOVE = "maintainer_remove"
