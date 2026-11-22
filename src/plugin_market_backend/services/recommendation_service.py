"""Opt-in, explainable content recommendations without browsing history.

There is deliberately no result cache: every request rechecks publication,
version eligibility and account preferences. Signed cursors bind a stable
ranking timestamp, account, conditions and data revision, never a user ID
supplied by the browser. Public catalogue changes invalidate old cursors.
"""

from __future__ import annotations

import base64
from collections import Counter, deque
from datetime import datetime, timedelta, timezone
import hashlib
import hmac
import json
import math
import secrets
from typing import Any
from urllib.parse import urlsplit

from packaging.version import InvalidVersion, Version
from sqlalchemy import delete, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from plugin_market_backend.config import get_settings
from plugin_market_backend.enums import PluginStatus, VersionStatus
from plugin_market_backend.errors import ApiError
from plugin_market_backend.orm import (
    AuthorFollowORM, PluginORM, PluginRatingORM, PluginSubscriptionORM,
    PluginVersionORM, RecommendationFeedbackORM, RecommendationPreferenceORM,
    utc_now,
)
from plugin_market_backend.recommendation_schemas import (
    IgnoredRecommendation, RecommendationEnvironment, RecommendationInterests,
    RecommendationItem, RecommendationPreferences, RecommendationPreferencesUpdate,
    RecommendationReason, RecommendationRequest, RecommendationResponse,
    ReducedRecommendationCategory,
)
from plugin_market_backend.service import MarketService

ALGORITHM = "rules-v1"
FEEDBACK_DAYS = 90
CURSOR_TTL_SECONDS = 1800
_DEVELOPMENT_CURSOR_KEY = secrets.token_bytes(32)


def aware(value: datetime) -> datetime:
    return value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)


def digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()).hexdigest()


def cursor_key() -> bytes:
    value = get_settings().session_secret
    if value == "change-me-in-production" or len(value) < 32:
        return _DEVELOPMENT_CURSOR_KEY
    return hashlib.sha256(("recommendations:" + value).encode()).digest()


def encode_cursor(payload: dict[str, Any]) -> str:
    body = base64.urlsafe_b64encode(json.dumps(payload, separators=(",", ":")).encode()).decode().rstrip("=")
    signature = hmac.new(cursor_key(), body.encode(), hashlib.sha256).hexdigest()
    return f"{body}.{signature}"


def decode_cursor(token: str, now: datetime) -> dict[str, Any]:
    try:
        body, signature = token.split(".", 1)
        expected = hmac.new(cursor_key(), body.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(signature, expected):
            raise ValueError("signature")
        value = json.loads(base64.urlsafe_b64decode(body + "=" * (-len(body) % 4)))
        if (
            not isinstance(value, dict) or value.get("v") != ALGORITHM
            or type(value.get("at")) is not int or type(value.get("offset")) is not int
            or value["offset"] < 0 or not isinstance(value.get("excluded"), list)
            or len(value["excluded"]) > 100
            or any(not isinstance(item, str) or len(item) > 120 for item in value["excluded"])
        ):
            raise ValueError("payload")
    except (ValueError, TypeError, UnicodeError, KeyError) as exc:
        raise ApiError(422, "INVALID_RECOMMENDATION_CURSOR", "推荐批次无效，请重新加载。") from exc
    age = now.timestamp() - value["at"]
    if age > CURSOR_TTL_SECONDS or age < -60:
        raise ApiError(409, "STALE_RECOMMENDATION_CURSOR", "推荐批次已过期，请重新加载。")
    return value


def features(categories: list[str], tags: list[str]) -> dict[str, float]:
    values = {f"category:{s.strip().casefold()}": 2.0 for s in categories if s.strip()}
    values.update({f"tag:{s.strip().casefold()}": 1.0 for s in tags if s.strip()})
    return normalized(values)


def normalized(values: dict[str, float]) -> dict[str, float]:
    norm = math.sqrt(sum(value * value for value in values.values()))
    return {key: value / norm for key, value in values.items()} if norm else {}


def similarity(left: dict[str, float], right: dict[str, float]) -> float:
    return max(0.0, min(1.0, sum(value * right.get(key, 0) for key, value in left.items())))


async def purge_expired_recommendation_feedback(session: AsyncSession) -> None:
    """Also called hourly by the application; expired feedback is never applied."""
    await session.execute(delete(RecommendationFeedbackORM).where(RecommendationFeedbackORM.expires_at <= utc_now()))


class RecommendationService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.market = MarketService(session)

    async def preferences(self, author_id: str) -> RecommendationPreferences:
        await purge_expired_recommendation_feedback(self.session)
        row = await self.session.get(RecommendationPreferenceORM, author_id)
        feedback = list((await self.session.scalars(
            select(RecommendationFeedbackORM).where(RecommendationFeedbackORM.author_id == author_id)
            .order_by(RecommendationFeedbackORM.kind, RecommendationFeedbackORM.target)
        )).all())
        return RecommendationPreferences(
            personalization_enabled=bool(row and row.personalization_enabled),
            interests=RecommendationInterests(categories=row.categories, tags=row.tags) if row else RecommendationInterests(),
            revision=row.revision if row else 0,
            updated_at=aware(row.updated_at) if row else None,
            ignored_plugins=[IgnoredRecommendation(plugin_id=f.target, reason=f.reason, expires_at=aware(f.expires_at))
                             for f in feedback if f.kind == "plugin"],
            reduced_categories=[ReducedRecommendationCategory(category=f.target, expires_at=aware(f.expires_at))
                                for f in feedback if f.kind == "category"],
        )

    async def update_preferences(
        self, author_id: str, payload: RecommendationPreferencesUpdate, *, reset: bool = False,
    ) -> RecommendationPreferences:
        current = await self.preferences(author_id)
        row = await self.session.get(RecommendationPreferenceORM, author_id)
        now = utc_now()
        enabled = False if reset else (
            current.personalization_enabled if payload.personalization_enabled is None else payload.personalization_enabled
        )
        interests = RecommendationInterests() if reset else (payload.interests or current.interests)
        changed = reset or enabled != current.personalization_enabled or interests != current.interests
        action = payload.feedback
        feedback_row = None
        kind = target = ""
        restoring = False
        if action:
            kind = "category" if action.type in {"reduce_category", "restore_category"} else "plugin"
            target = (action.category if kind == "category" else action.plugin_id) or ""
            restoring = action.type in {"restore_plugin", "restore_category"}
            feedback_row = await self.session.get(RecommendationFeedbackORM, (author_id, kind, target))
            if kind == "plugin" and not restoring and await self.session.get(PluginORM, target) is None:
                raise ApiError(404, "PLUGIN_NOT_FOUND", "插件不存在。")
            changed |= (feedback_row is not None) if restoring else (feedback_row is None or feedback_row.reason != action.type)
            if feedback_row is None and not restoring:
                count = len(current.ignored_plugins) if kind == "plugin" else len(current.reduced_categories)
                if count >= (200 if kind == "plugin" else 50):
                    raise ApiError(422, "RECOMMENDATION_PREFERENCES_LIMIT", "偏好条目已达上限，请先恢复部分条目。")
        if not changed:
            return current
        if row is None:
            self.session.add(RecommendationPreferenceORM(
                author_id=author_id, personalization_enabled=enabled, categories=interests.categories,
                tags=interests.tags, revision=1, updated_at=now,
            ))
            try:
                await self.session.flush()
            except IntegrityError as exc:
                raise ApiError(409, "PREFERENCES_CHANGED", "偏好已被另一个请求更新，请重新读取。") from exc
        else:
            result = await self.session.execute(
                update(RecommendationPreferenceORM)
                .where(RecommendationPreferenceORM.author_id == author_id,
                       RecommendationPreferenceORM.revision == current.revision)
                .values(personalization_enabled=enabled, categories=interests.categories, tags=interests.tags,
                        revision=current.revision + 1, updated_at=now)
                .execution_options(synchronize_session=False)
            )
            if result.rowcount != 1:
                raise ApiError(409, "PREFERENCES_CHANGED", "偏好已被另一个请求更新，请重新读取。")
            await self.session.refresh(row)
        if reset:
            await self.session.execute(delete(RecommendationFeedbackORM).where(RecommendationFeedbackORM.author_id == author_id))
        elif action:
            if restoring and feedback_row:
                await self.session.delete(feedback_row)
            elif not restoring:
                if feedback_row is None:
                    self.session.add(RecommendationFeedbackORM(
                        author_id=author_id, kind=kind, target=target, reason=action.type,
                        created_at=now, expires_at=now + timedelta(days=FEEDBACK_DAYS),
                    ))
                else:
                    feedback_row.reason = action.type
                    feedback_row.created_at = now
                    feedback_row.expires_at = now + timedelta(days=FEEDBACK_DAYS)
        await self.session.flush()
        return await self.preferences(author_id)

    def eligible_version(self, plugin: PluginORM, environment: RecommendationEnvironment) -> PluginVersionORM | None:
        candidates: list[tuple[Version, PluginVersionORM]] = []
        for version in plugin.versions:
            if version.status != VersionStatus.PUBLISHED or version.is_yanked or version.is_prerelease:
                continue
            try:
                release = Version(version.version)
                asset = urlsplit(version.asset_download_url)
                if release.is_prerelease or release.is_devrelease or asset.scheme not in {"http", "https"} or not asset.netloc:
                    continue
                if environment.host_version:
                    minimum = Version(version.min_host_version)
                    maximum = Version(version.max_host_version) if version.max_host_version else None
                    if maximum is not None and maximum < minimum:
                        continue
                if environment.plugin_api_version:
                    Version(version.plugin_api_version)
            except (InvalidVersion, TypeError, ValueError):
                continue
            if not (
                self.market._matches_host(version, environment.host_version)
                and self.market._matches_api(version, environment.plugin_api_version)
                and self.market._matches_platform(version, environment.platform)
            ):
                continue
            candidates.append((release, version))
        return max(candidates, key=lambda pair: (pair[0], aware(pair[1].published_at)), default=(None, None))[1]

    async def recommend(self, request: RecommendationRequest, viewer_id: str | None) -> RecommendationResponse:
        now = utc_now()
        cursor = decode_cursor(request.cursor, now) if request.cursor else None
        subject = hmac.new(cursor_key(), (viewer_id or "anonymous").encode(), hashlib.sha256).hexdigest()
        if cursor and cursor.get("subject") != subject:
            raise ApiError(409, "STALE_RECOMMENDATION_CURSOR", "登录身份已变化，请重新加载推荐。")
        prefs = await self.preferences(viewer_id) if viewer_id else RecommendationPreferences()
        interests = prefs.interests if viewer_id and prefs.personalization_enabled else (
            RecommendationInterests() if viewer_id else request.interests
        )
        reduced = {entry.category for entry in prefs.reduced_categories} if viewer_id else {
            value.casefold() for value in request.reduced_categories
        }
        query_key = digest({
            **request.model_dump(mode="json", exclude={"cursor", "exclude_ids", "interests", "reduced_categories"}),
            "interests": interests.model_dump(), "reduced": sorted(reduced),
            "enabled": prefs.personalization_enabled, "revision": prefs.revision,
        })
        if cursor and (cursor.get("query") != query_key or not set(cursor["excluded"]).issubset(request.exclude_ids)):
            raise ApiError(409, "STALE_RECOMMENDATION_CURSOR", "推荐条件已变化，请重新加载。")
        initial_excludes = set(cursor["excluded"] if cursor else request.exclude_ids)
        plugins = list((await self.session.scalars(
            select(PluginORM).where(PluginORM.status == PluginStatus.PUBLISHED)
            .options(selectinload(PluginORM.owner), selectinload(PluginORM.maintainers), selectinload(PluginORM.versions))
            .order_by(PluginORM.plugin_id)
        )).all())
        by_id = {plugin.plugin_id: plugin for plugin in plugins}
        context = by_id.get(request.context_plugin_id or "")
        if request.placement == "detail" and context is None:
            raise ApiError(404, "PLUGIN_NOT_FOUND", "当前插件不存在或未公开。")
        subscriptions: set[str] = set()
        ratings: dict[str, int] = {}
        followed: set[str] = set()
        if viewer_id:
            subscriptions = set((await self.session.scalars(
                select(PluginSubscriptionORM.plugin_id).where(PluginSubscriptionORM.author_id == viewer_id)
            )).all())
            ratings = dict((await self.session.execute(
                select(PluginRatingORM.plugin_id, PluginRatingORM.score).where(PluginRatingORM.author_id == viewer_id)
            )).all())
            if prefs.personalization_enabled:
                followed = set((await self.session.scalars(
                    select(AuthorFollowORM.author_id).where(AuthorFollowORM.follower_id == viewer_id)
                )).all())
        excluded = initial_excludes | subscriptions | set(ratings) | {entry.plugin_id for entry in prefs.ignored_plugins}
        if context:
            excluded.add(context.plugin_id)
        vectors = {plugin.plugin_id: features(plugin.categories or [], plugin.tags or []) for plugin in plugins}
        profile: dict[str, float] = {}
        sources: list[tuple[str, dict[str, float]]] = []

        def add_source(code: str, vector: dict[str, float], weight: float) -> None:
            if vector:
                sources.append((code, vector))
                for key, value in vector.items():
                    profile[key] = profile.get(key, 0) + value * weight

        add_source("chosen_interests", features(interests.categories, interests.tags), 5)
        if viewer_id and prefs.personalization_enabled:
            for plugin_id in sorted(subscriptions | set(ratings)):
                # A subscription and the legacy likes fields are the same action.
                weight = max(4 if plugin_id in subscriptions else 0, {4: 3, 5: 4}.get(ratings.get(plugin_id), 0))
                if weight:
                    add_source("subscription_similarity" if plugin_id in subscriptions else "rating_similarity",
                               vectors.get(plugin_id, {}), weight)
        has_personal = any(code in {"subscription_similarity", "rating_similarity"} for code, _ in sources) or bool(followed)
        if context:
            add_source("similar_to_current", vectors[context.plugin_id], 3)
        profile = normalized(profile)
        mode = "personalized" if has_personal else "contextual" if profile else "popular"
        stats = await self.market._community_stats_for(list(by_id), viewer_id)
        candidates: list[dict[str, Any]] = []
        filter_categories = set(request.filters.categories)
        filter_tags = set(request.filters.tags)
        for plugin in plugins:
            if plugin.plugin_id in excluded or (viewer_id and (plugin.owner_id == viewer_id or any(m.author_id == viewer_id for m in plugin.maintainers))):
                continue
            categories = {s.casefold() for s in (plugin.categories or [])}
            tags = {s.casefold() for s in (plugin.tags or [])}
            if filter_categories and not categories.intersection(filter_categories):
                continue
            if not filter_tags.issubset(tags):
                continue
            if request.filters.trust_levels and plugin.trust_level not in request.filters.trust_levels:
                continue
            version = self.eligible_version(plugin, request.environment)
            if version is not None:
                candidates.append({"plugin": plugin, "version": version, "stats": stats[plugin.plugin_id],
                                   "vector": vectors[plugin.plugin_id], "categories": categories,
                                   "primary_category": (plugin.categories[0].strip().casefold() if plugin.categories else "")})
        # Bind both eligibility and ranking inputs. No process cache can retain
        # a revoked plugin, a changed rating or another account's preferences.
        state = digest({
            "candidates": [{
                "id": c["plugin"].plugin_id, "owner": c["plugin"].owner_id,
                "version": c["version"].version, "published": aware(c["version"].published_at).isoformat(),
                "asset": c["version"].asset_download_url, "stats": c["stats"], "vector": c["vector"],
            } for c in candidates],
            "sources": sources, "followed": sorted(followed),
            "subscriptions": sorted(subscriptions), "ratings": ratings,
            "rating_prior": {plugin_id: [values["rating_count"], values["rating_avg"]]
                             for plugin_id, values in stats.items()},
            "feedback": prefs.model_dump(mode="json"),
        })
        if cursor and cursor.get("state") != state:
            raise ApiError(409, "STALE_RECOMMENDATION_CURSOR", "目录或偏好已更新，请重新加载推荐。")
        at = cursor["at"] if cursor else int(now.timestamp()) // 60 * 60
        as_of = datetime.fromtimestamp(at, timezone.utc)
        self._score(candidates, stats, profile, sources, followed, reduced, as_of)
        ordered = self._diverse_order(candidates, request.limit, bool(profile or followed))
        offset = cursor["offset"] if cursor else 0
        if offset > len(ordered):
            raise ApiError(422, "INVALID_RECOMMENDATION_CURSOR", "推荐批次无效。")
        batch: list[dict[str, Any]] = []
        # Keeping boundaries preserves diversity and stable pagination even
        # when the browser adds recently displayed IDs to its exclusions.
        while offset < len(ordered) and not batch:
            batch = [c for c in ordered[offset:offset + request.limit] if c["plugin"].plugin_id not in request.exclude_ids]
            offset += request.limit
        offset = min(offset, len(ordered))
        more = any(c["plugin"].plugin_id not in request.exclude_ids for c in ordered[offset:])
        token_data = {"v": ALGORITHM, "subject": subject, "query": query_key, "state": state,
                      "at": at, "offset": offset, "excluded": sorted(initial_excludes)}
        known_environment = any(request.environment.model_dump().values())
        items = []
        for candidate in batch:
            plugin = self.market._plugin_schema(candidate["plugin"], candidate["stats"])
            # Cards must advertise the eligible stable version, not a newer
            # pre-release returned by the general catalogue serializer.
            plugin.latest_version = candidate["version"].version
            plugin.latest_version_published_at = candidate["version"].published_at
            items.append(RecommendationItem(
                plugin=plugin, recommended_version=candidate["version"].version,
                compatibility="compatible" if known_environment else "unknown",
                reasons=candidate["reasons"],
            ))
        return RecommendationResponse(
            recommendation_id=digest({**token_data, "items": [item.plugin.plugin_id for item in items]})[:24],
            mode=mode, generated_at=as_of, items=items,
            next_cursor=encode_cursor(token_data) if more else None,
        )

    @staticmethod
    def _score(candidates, all_stats, profile, sources, followed, reduced, as_of):
        total_ratings = sum(s["rating_count"] for s in all_stats.values())
        mean = sum(s["rating_avg"] * s["rating_count"] for s in all_stats.values()) / total_ratings if total_ratings else 3.0
        # Capped logarithmic counters limit the influence of cumulative,
        # unauthenticated install counters; they do not prove installation.
        def heat(stats):
            return min(1.0, math.log1p(max(0, stats["downloads_count"])) / math.log1p(10000)) * 0.7 + min(
                1.0, math.log1p(max(0, stats["likes_count"])) / math.log1p(1000)
            ) * 0.3

        labels = {
            "chosen_interests": "符合你选择的兴趣",
            "subscription_similarity": "与你订阅的插件用途相关",
            "rating_similarity": "与你高评分的插件用途相关",
            "similar_to_current": "与当前插件用途相关",
        }
        for item in candidates:
            p, stats = item["plugin"], item["stats"]
            interest = similarity(profile, item["vector"])
            author = float(p.owner_id in followed)
            quality = (stats["rating_count"] * stats["rating_avg"] + 5 * mean) / (stats["rating_count"] + 5) / 5
            days = (as_of - aware(item["version"].published_at)).total_seconds() / 86400
            fresh = math.exp(-max(0, days) / 30)
            popularity = heat(stats)
            item["score"] = (
                0.5 * interest + 0.15 * author + 0.15 * quality + 0.1 * popularity + 0.1 * fresh
                if profile or followed else 0.45 * quality + 0.30 * popularity + 0.25 * fresh
            )
            if reduced.intersection(item["categories"]):
                item["score"] *= 0.35
            item["exploration"] = bool(profile or followed) and interest == 0 and not author
            reasons = []
            matches = [(similarity(vector, item["vector"]), code) for code, vector in sources]
            best = max(matches, default=(0, ""))
            if best[0] > 0:
                reasons.append(RecommendationReason(code=best[1], label=labels[best[1]]))
            if author:
                reasons.append(RecommendationReason(code="followed_author", label="来自你关注的作者"))
            if 0 <= days <= 30:
                reasons.append(RecommendationReason(code="recent_release", label="最近发布了稳定版本"))
            if stats["rating_count"] >= 3 and stats["rating_avg"] >= 4:
                reasons.append(RecommendationReason(code="well_rated", label="获得多位用户好评"))
            if not reasons:
                reasons.append(RecommendationReason(code="explore" if item["exploration"] else "public_discovery",
                                                    label="探索不同用途的插件" if item["exploration"] else "发现更多公开插件"))
            item["reasons"] = reasons[:2]

    @staticmethod
    def _diverse_order(candidates, limit: int, has_interests: bool):
        remaining = sorted(candidates, key=lambda c: (-c["score"], c["plugin"].plugin_id))
        ordered = []

        def category(item):
            return item["primary_category"]

        def select_batch(seed, target_categories):
            """Small min-cost flow can reassign early choices to respect caps.

            Greedy selection can consume the only author/category slot needed
            by another candidate even when a valid full batch exists. At most
            six augmentations select the best feasible batch. Coverage rewards
            stop after the required three categories, then ranking scores win.
            """
            selected = [seed] if seed else []
            authors = Counter(item["plugin"].owner_id for item in selected)
            categories = Counter(category(item) for item in selected)
            graph: list[list[list]] = []

            def node():
                graph.append([])
                return len(graph) - 1

            def edge(start, end, capacity, cost):
                forward = [end, len(graph[end]), capacity, cost]
                reverse = [start, len(graph[start]), 0, -cost]
                graph[start].append(forward)
                graph[end].append(reverse)
                return forward

            source, sink, coverage = node(), node(), node()
            edge(coverage, sink, max(0, target_categories - len({c for c in categories if c})), 0)
            owner_nodes, category_nodes, candidate_edges = {}, {}, []
            for item in remaining:
                if item is seed:
                    continue
                owner, primary = item["plugin"].owner_id, category(item)
                if owner not in owner_nodes:
                    owner_nodes[owner] = node()
                    edge(source, owner_nodes[owner], 2 - authors[owner], 0)
                if primary not in category_nodes:
                    category_nodes[primary] = node()
                    gate = node()
                    edge(category_nodes[primary], gate, 3 - categories[primary], 0)
                    edge(gate, sink, 3 - categories[primary], 0)
                    if primary and not categories[primary]:
                        edge(gate, coverage, 1, -10)
                candidate_edges.append((item, edge(owner_nodes[owner], category_nodes[primary], 1, -item["score"])))

            for _ in range(limit - len(selected)):
                distances, previous = [math.inf] * len(graph), [None] * len(graph)
                distances[source] = 0
                queue, queued = deque([source]), {source}
                while queue:
                    start = queue.popleft()
                    queued.remove(start)
                    for index, connection in enumerate(graph[start]):
                        end, _, capacity, cost = connection
                        if capacity and distances[start] + cost < distances[end] - 1e-12:
                            distances[end] = distances[start] + cost
                            previous[end] = (start, index)
                            if end not in queued:
                                queue.append(end)
                                queued.add(end)
                if previous[sink] is None:
                    break
                end = sink
                while end != source:
                    start, index = previous[end]
                    connection = graph[start][index]
                    connection[2] -= 1
                    graph[end][connection[1]][2] += 1
                    end = start
            return selected + [item for item, connection in candidate_edges if connection[2] == 0]

        while remaining:
            target_categories = min(3, limit, len({category(item) for item in remaining if category(item)}))
            # Prefer the highest scoring exploration item that permits a full,
            # diverse batch. Same author/category options are interchangeable.
            seeds = []
            groups = set()
            if has_interests and limit >= 2:
                for item in remaining:
                    group = (item["plugin"].owner_id, category(item))
                    if item["exploration"] and group not in groups:
                        groups.add(group)
                        seeds.append(item)
            batch, best = [], (-1, -1, -1.0)
            for seed in seeds or [None]:
                attempt = select_batch(seed, target_categories)
                coverage = min(target_categories, len({category(item) for item in attempt if category(item)}))
                quality = (len(attempt), coverage, sum(item["score"] for item in attempt))
                if quality > best:
                    batch, best = attempt, quality
                if len(attempt) == min(limit, len(remaining)) and coverage == target_categories:
                    break
            chosen_ids = {item["plugin"].plugin_id for item in batch}
            remaining = [item for item in remaining if item["plugin"].plugin_id not in chosen_ids]
            # Only impossible diversity constraints relax; eligibility and hard
            # filters were already applied before entering this function.
            while remaining and len(batch) < limit:
                batch.append(remaining.pop(0))
            ordered.extend(sorted(batch, key=lambda c: (-c["score"], c["plugin"].plugin_id)))
        return ordered
