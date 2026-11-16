"""独立推荐 API 的受限请求与响应契约。"""

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
    """分类匹配任意项，标签匹配所有项，独立于软性兴趣偏好。"""

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
            raise ValueError("版本必须使用数字版本号，例如 1.2.0。")
        try:
            Version(value)
        except InvalidVersion as exc:
            raise ValueError("版本无效。") from exc
        return value

    @field_validator("platform")
    @classmethod
    def platform_format(cls, value: str | None) -> str | None:
        if value is not None and not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9_.-]{0,39}", value):
            raise ValueError("平台标识无效。")
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
            raise ValueError("详情页推荐必须提供 context_plugin_id。")
        if self.placement == "home" and self.context_plugin_id:
            raise ValueError("仅详情页推荐接受 context_plugin_id。")
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
                raise ValueError("分类反馈必须且只能提供 category。")
            self.category = self.category.casefold()
        elif not self.plugin_id or self.category is not None:
            raise ValueError("插件反馈必须且只能提供 plugin_id。")
        return self


class RecommendationPreferencesUpdate(StrictModel):
    personalization_enabled: bool | None = Field(default=None, strict=True)
    interests: RecommendationInterests | None = None
    feedback: RecommendationFeedback | None = None
