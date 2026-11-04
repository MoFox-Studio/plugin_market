"""Bounded request/response contracts for the independent recommendation API."""

from __future__ import annotations

from datetime import datetime
import re
from typing import Annotated, Literal

from packaging.version import InvalidVersion, Version
from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator, model_validator

from plugin_market_backend.enums import TrustLevel
from plugin_market_backend.schemas import Plugin

Label = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=40)]
PluginId = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class RecommendationInterests(StrictModel):
    categories: list[Label] = Field(default_factory=list, max_length=3)
    tags: list[Label] = Field(default_factory=list, max_length=10)

    @field_validator("categories", "tags")
    @classmethod
    def unique(cls, values: list[str]) -> list[str]:
        return sorted(set(value.casefold() for value in values))


class RecommendationFilters(StrictModel):
    """Categories match any; tags match all; separate from soft interests."""

    categories: list[Label] = Field(default_factory=list, max_length=10)
    tags: list[Label] = Field(default_factory=list, max_length=10)
    trust_levels: list[TrustLevel] = Field(default_factory=list, max_length=3)

    @field_validator("categories", "tags")
    @classmethod
    def unique(cls, values: list[str]) -> list[str]:
        return sorted(set(value.casefold() for value in values))


class RecommendationEnvironment(StrictModel):
    host_version: str | None = Field(default=None, min_length=1, max_length=80)
    plugin_api_version: str | None = Field(default=None, min_length=1, max_length=80)
    platform: str | None = Field(default=None, min_length=1, max_length=40)

    @field_validator("host_version", "plugin_api_version")
    @classmethod
    def version_format(cls, value: str | None) -> str | None:
        if value is None:
            return None
        if not re.fullmatch(r"v?\d+(?:\.\d+){0,3}(?:(?:a|b|rc)\d+|-(?:alpha|beta|rc)[.-]?\d+)?(?:\+[a-zA-Z0-9]+(?:[.-][a-zA-Z0-9]+)*)?", value):
            raise ValueError("Version must be a numeric release, for example 1.2.0.")
        try:
            Version(value)
        except InvalidVersion as exc:
            raise ValueError("Invalid version.") from exc
        return value

    @field_validator("platform")
    @classmethod
    def platform_format(cls, value: str | None) -> str | None:
        if value is not None and not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9_.-]{0,39}", value):
            raise ValueError("Invalid platform identifier.")
        return value.lower() if value else value


class RecommendationRequest(StrictModel):
    placement: Literal["home", "detail"] = "home"
    context_plugin_id: PluginId | None = None
    limit: int = Field(default=6, ge=1, le=6, strict=True)
    interests: RecommendationInterests = Field(default_factory=RecommendationInterests)
    filters: RecommendationFilters = Field(default_factory=RecommendationFilters)
    exclude_ids: list[PluginId] = Field(default_factory=list, max_length=100)
    reduced_categories: list[Label] = Field(default_factory=list, max_length=50)
    environment: RecommendationEnvironment = Field(default_factory=RecommendationEnvironment)
    cursor: str | None = Field(default=None, min_length=1, max_length=24000)

    @model_validator(mode="after")
    def validate_placement(self) -> RecommendationRequest:
        if self.placement == "detail" and not self.context_plugin_id:
            raise ValueError("Detail recommendations require context_plugin_id.")
        if self.placement == "home" and self.context_plugin_id:
            raise ValueError("context_plugin_id is only accepted for detail recommendations.")
        return self


class RecommendationReason(StrictModel):
    code: str
    label: str


class RecommendationItem(StrictModel):
    plugin: Plugin
    recommended_version: str
    compatibility: Literal["compatible", "unknown"]
    reasons: list[RecommendationReason] = Field(max_length=2)


class RecommendationResponse(StrictModel):
    recommendation_id: str
    algorithm_version: Literal["rules-v1"] = "rules-v1"
    mode: Literal["personalized", "contextual", "popular"]
    generated_at: datetime
    items: list[RecommendationItem]
    next_cursor: str | None = None


class IgnoredRecommendation(StrictModel):
    plugin_id: str
    reason: Literal["not_interested", "already_have"]
    expires_at: datetime


class ReducedRecommendationCategory(StrictModel):
    category: str
    expires_at: datetime


class RecommendationPreferences(StrictModel):
    personalization_enabled: bool = False
    interests: RecommendationInterests = Field(default_factory=RecommendationInterests)
    ignored_plugins: list[IgnoredRecommendation] = Field(default_factory=list)
    reduced_categories: list[ReducedRecommendationCategory] = Field(default_factory=list)
    revision: int = 0
    updated_at: datetime | None = None
    feedback_retention_days: Literal[90] = 90


class RecommendationFeedback(StrictModel):
    type: Literal["not_interested", "already_have", "restore_plugin", "reduce_category", "restore_category"]
    plugin_id: PluginId | None = None
    category: Label | None = None

    @model_validator(mode="after")
    def validate_target(self) -> RecommendationFeedback:
        category_action = self.type in {"reduce_category", "restore_category"}
        if category_action:
            if not self.category or self.plugin_id is not None:
                raise ValueError("Category feedback requires category only.")
            self.category = self.category.casefold()
        elif not self.plugin_id or self.category is not None:
            raise ValueError("Plugin feedback requires plugin_id only.")
        return self


class RecommendationPreferencesUpdate(StrictModel):
    personalization_enabled: bool | None = Field(default=None, strict=True)
    interests: RecommendationInterests | None = None
    feedback: RecommendationFeedback | None = None
