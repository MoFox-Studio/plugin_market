"""Seed data for local development and tests."""

from __future__ import annotations

import random
from datetime import timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from plugin_market_backend.enums import AuthorType, TrustLevel
from plugin_market_backend.orm import (
    AuthorORM,
    PluginCommentORM,
    PluginLikeORM,
    PluginORM,
    PluginRatingORM,
    PluginVersionORM,
    utc_now,
)
from plugin_market_backend.schemas import PluginCreate, PluginVersionCreate
from plugin_market_backend.service import MarketService


DEMO_PLUGIN = {
    "plugin_id": "demo_plugin",
    "display_name": "Demo Plugin",
    "summary": "A mock plugin used for market API development.",
    "description": (
        "This seeded plugin lets CLI and frontend prototypes query a realistic market record.\n\n"
        "- 提供基础 API 交互示例\n- 演示命令注册流程\n- 附带完整的审核链路样例"
    ),
    "repository_url": "https://github.com/MoFox-Studio/demo_plugin",
    "homepage": "https://example.com/demo_plugin",
    "license": "MIT",
    "categories": ["tool"],
    "tags": ["demo", "utility"],
    "maintainers": ["mock-author"],
}


EXTRA_PLUGINS: list[dict] = [
    {
        "plugin_id": "smart_reply",
        "display_name": "SmartReply · 智能自动回复",
        "summary": "自适应语境的自动回复管理器，支持关键词、LLM 兜底与冷却时间。",
        "description": (
            "SmartReply 通过层级规则匹配为群聊与私聊提供即时响应。\n\n"
            "特性：\n- 基于正则与关键字的快速匹配\n- 命中失败时回退到 LLM\n- 支持每用户冷却时间与回复模板\n- 统计面板记录命中率"
        ),
        "repository_url": "https://github.com/MoFox-Studio/smart_reply",
        "homepage": "https://plugins.mofox.dev/smart_reply",
        "license": "Apache-2.0",
        "categories": ["chat"],
        "tags": ["auto-reply", "llm", "moderation"],
        "trust_level": TrustLevel.OFFICIAL,
        "version": "2.3.1",
    },
    {
        "plugin_id": "sticker_studio",
        "display_name": "StickerStudio · 表情包工坊",
        "summary": "管理、生成和分发自定义表情包。",
        "description": (
            "内置表情包画布、文本合成与批量导入工具。\n\n"
            "- 支持 GIF/静态图/WebP\n- 带预览和搜索\n- 基于关键词触发发送"
        ),
        "repository_url": "https://github.com/MoFox-Studio/sticker_studio",
        "license": "MIT",
        "categories": ["fun"],
        "tags": ["sticker", "media", "entertainment"],
        "trust_level": TrustLevel.VERIFIED,
        "version": "1.2.0",
    },
    {
        "plugin_id": "daily_news",
        "display_name": "DailyNews · 每日新闻简报",
        "summary": "每天定时向频道投递新闻、天气和日历摘要。",
        "description": (
            "聚合 RSS 与 API 源，生成可配置的早间简报。\n\n"
            "- 支持自定义模板\n- 节假日日历\n- 分组推送"
        ),
        "repository_url": "https://github.com/MoFox-Studio/daily_news",
        "license": "MIT",
        "categories": ["information"],
        "tags": ["news", "schedule", "digest"],
        "trust_level": TrustLevel.VERIFIED,
        "version": "0.9.4",
    },
    {
        "plugin_id": "wardrobe_vision",
        "display_name": "Wardrobe Vision · 换装视觉",
        "summary": "基于图像理解的角色造型与场景识别工具。",
        "description": (
            "与视觉模型联动，对头像、服饰进行检测与记忆。\n\n"
            "- 支持多角色档案\n- 场景与情绪分析\n- 与记忆图谱集成"
        ),
        "repository_url": "https://github.com/MoFox-Studio/wardrobe_vision",
        "license": "AGPL-3.0",
        "categories": ["vision"],
        "tags": ["vision", "memory", "persona"],
        "trust_level": TrustLevel.COMMUNITY,
        "version": "0.5.2",
    },
    {
        "plugin_id": "memory_graph_pro",
        "display_name": "MemoryGraph Pro",
        "summary": "对接 Neo-MoFox 记忆图谱的增强探索与可视化工具。",
        "description": (
            "提供图可视化面板、向量检索和关系追踪。\n\n"
            "- ForceGraph 可视化\n- 批量导入/导出\n- 相似度重排"
        ),
        "repository_url": "https://github.com/MoFox-Studio/memory_graph_pro",
        "license": "MIT",
        "categories": ["tool"],
        "tags": ["memory", "graph", "visualization"],
        "trust_level": TrustLevel.OFFICIAL,
        "version": "1.0.0",
    },
    {
        "plugin_id": "music_box",
        "display_name": "MusicBox · 点歌姬",
        "summary": "在群聊中播放和分享音乐,支持多平台歌单。",
        "description": "支持网易云、QQ、Spotify 元数据搜索,并可以生成歌单海报。",
        "repository_url": "https://github.com/MoFox-Studio/music_box",
        "license": "MIT",
        "categories": ["fun"],
        "tags": ["music", "entertainment"],
        "trust_level": TrustLevel.COMMUNITY,
        "version": "0.8.1",
    },
    {
        "plugin_id": "translate_bridge",
        "display_name": "TranslateBridge · 翻译桥",
        "summary": "多模型翻译聚合,自动检测语言并缓存结果。",
        "description": (
            "将 DeepL、Google、LLM 翻译组合起来,提供一致接口和命中缓存。\n\n"
            "- 100+ 语种\n- 可选润色\n- 流量控制"
        ),
        "repository_url": "https://github.com/MoFox-Studio/translate_bridge",
        "license": "MIT",
        "categories": ["tool"],
        "tags": ["translation", "i18n"],
        "trust_level": TrustLevel.VERIFIED,
        "version": "1.4.2",
    },
    {
        "plugin_id": "gacha_sim",
        "display_name": "GachaSim · 抽卡模拟器",
        "summary": "多种游戏的抽卡概率模拟,支持自定义卡池与历史统计。",
        "description": "覆盖常见游戏的抽卡概率,提供历史记录、概率图与运势分析。",
        "repository_url": "https://github.com/MoFox-Studio/gacha_sim",
        "license": "MIT",
        "categories": ["fun"],
        "tags": ["game", "entertainment", "probability"],
        "trust_level": TrustLevel.COMMUNITY,
        "version": "0.3.7",
    },
    {
        "plugin_id": "security_guard",
        "display_name": "SecurityGuard · 安全守卫",
        "summary": "消息反垃圾、反广告和敏感词检测工具链。",
        "description": "提供可配置的规则、模型打分与管理员工作流,保护社区秩序。",
        "repository_url": "https://github.com/MoFox-Studio/security_guard",
        "license": "Apache-2.0",
        "categories": ["moderation"],
        "tags": ["security", "moderation", "filter"],
        "trust_level": TrustLevel.OFFICIAL,
        "version": "3.0.0",
    },
    {
        "plugin_id": "wiki_seeker",
        "display_name": "WikiSeeker · 百科搜索",
        "summary": "集成维基、百度百科与自定义知识库的查询助手。",
        "description": "支持多知识源、结果摘要与自定义检索优先级。",
        "repository_url": "https://github.com/MoFox-Studio/wiki_seeker",
        "license": "MIT",
        "categories": ["information"],
        "tags": ["search", "knowledge"],
        "trust_level": TrustLevel.COMMUNITY,
        "version": "0.6.0",
    },
    {
        "plugin_id": "party_games",
        "display_name": "PartyGames · 群聊小游戏",
        "summary": "狼人杀、成语接龙、猜数等多款小游戏集合。",
        "description": "提供房间管理、积分榜和丰富的游戏事件。",
        "repository_url": "https://github.com/MoFox-Studio/party_games",
        "license": "MIT",
        "categories": ["fun"],
        "tags": ["game", "multiplayer", "entertainment"],
        "trust_level": TrustLevel.COMMUNITY,
        "version": "1.1.3",
    },
]


FAKE_USERS: list[dict[str, str]] = [
    {"author_id": "github:octocat", "github_login": "octocat", "display_name": "Octocat"},
    {"author_id": "github:lumina", "github_login": "lumina", "display_name": "Lumina Wei"},
    {"author_id": "github:keita", "github_login": "keita", "display_name": "Keita Tanaka"},
    {"author_id": "github:marina", "github_login": "marina", "display_name": "Marina Liu"},
    {"author_id": "github:haruki", "github_login": "haruki", "display_name": "Haruki Aoi"},
    {"author_id": "github:nova", "github_login": "nova", "display_name": "Nova Chen"},
]


SAMPLE_COMMENTS: list[str] = [
    "装好之后聊天氛围立刻热闹了不少，支持！",
    "和 Neo-MoFox 1.4 配合使用没有问题,配置非常顺手。",
    "希望下个版本可以加一个自定义冷却时间的选项～",
    "作者响应速度很快,issue 很快就被处理了。",
    "这个功能我期待了好久,终于正式上线🎉",
    "建议增加一个英文示例,方便海外用户学习。",
    "在 NapCat 平台下运行稳定,已经连续运行两周。",
    "文档写得清楚,二次开发很容易。",
]


async def seed_database(session: AsyncSession) -> None:
    """Populate the database with the minimal demo plugin when empty."""

    count = await session.scalar(select(func.count()).select_from(PluginORM))
    if count:
        return
    service = MarketService(session)
    await _seed_demo_plugin(service)


async def seed_rich_demo(session: AsyncSession) -> None:
    """Populate the database with the full rich demo dataset when empty."""

    count = await session.scalar(select(func.count()).select_from(PluginORM))
    if count:
        return
    service = MarketService(session)
    await _seed_demo_plugin(service)
    await _seed_extra_plugins(service, session)


async def _seed_demo_plugin(service: MarketService) -> None:
    """Preserve the original demo plugin expected by tests."""

    plugin = await service.register_plugin(
        PluginCreate(
            plugin_id=DEMO_PLUGIN["plugin_id"],
            display_name=DEMO_PLUGIN["display_name"],
            summary=DEMO_PLUGIN["summary"],
            description=DEMO_PLUGIN["description"],
            homepage=DEMO_PLUGIN["homepage"],
            repository_url=DEMO_PLUGIN["repository_url"],
            license=DEMO_PLUGIN["license"],
            categories=DEMO_PLUGIN["categories"],
            tags=DEMO_PLUGIN["tags"],
            maintainers=DEMO_PLUGIN["maintainers"],
        ),
        owner_id="mock-author",
    )
    await service.submit_version(
        plugin.plugin_id,
        PluginVersionCreate(
            version="1.0.0",
            release_tag="v1.0.0",
            release_title="Demo Plugin 1.0.0",
            release_url="https://github.com/MoFox-Studio/demo_plugin/releases/tag/v1.0.0",
            asset_name="demo_plugin-1.0.0.mfp",
            asset_download_url="https://github.com/MoFox-Studio/demo_plugin/releases/download/v1.0.0/demo_plugin-1.0.0.mfp",
            checksum_sha256="a" * 64,
            file_size=12345,
            is_prerelease=False,
            plugin_api_version="1.0",
            min_host_version="1.0.0",
            max_host_version=None,
            supported_platforms=["all"],
        ),
        operator_id="mock-author",
    )


async def _seed_extra_plugins(service: MarketService, session: AsyncSession) -> None:
    """Seed a realistic set of extra plugins with engagement data."""

    rng = random.Random(42)

    for user in FAKE_USERS:
        existing = await session.get(AuthorORM, user["author_id"])
        if existing is not None:
            continue
        session.add(
            AuthorORM(
                author_id=user["author_id"],
                github_user_id=f"id-{user['github_login']}",
                github_login=user["github_login"],
                display_name=user["display_name"],
                avatar_url=f"https://avatars.githubusercontent.com/u/{abs(hash(user['github_login'])) % 99999}?v=4",
                author_type=AuthorType.USER,
                verified_at=utc_now(),
                is_admin=False,
            )
        )
    await session.flush()

    owner_pool = [user["author_id"] for user in FAKE_USERS]

    for index, entry in enumerate(EXTRA_PLUGINS):
        owner_id = owner_pool[index % len(owner_pool)]
        plugin = await service.register_plugin(
            PluginCreate(
                plugin_id=entry["plugin_id"],
                display_name=entry["display_name"],
                summary=entry["summary"],
                description=entry["description"],
                repository_url=entry["repository_url"],
                homepage=entry.get("homepage"),
                license=entry["license"],
                categories=entry["categories"],
                tags=entry["tags"],
                maintainers=[owner_id],
            ),
            owner_id=owner_id,
        )
        trust = entry.get("trust_level", TrustLevel.COMMUNITY)
        plugin_row = await session.get(PluginORM, plugin.plugin_id)
        if plugin_row is not None:
            plugin_row.trust_level = trust

        version = entry["version"]
        await service.submit_version(
            plugin.plugin_id,
            PluginVersionCreate(
                version=version,
                release_tag=f"v{version}",
                release_title=f"{entry['display_name']} {version}",
                release_url=f"{entry['repository_url']}/releases/tag/v{version}",
                asset_name=f"{entry['plugin_id']}-{version}.mfp",
                asset_download_url=f"{entry['repository_url']}/releases/download/v{version}/{entry['plugin_id']}-{version}.mfp",
                checksum_sha256=(hex(abs(hash(entry["plugin_id"] + version)))[2:] + "0" * 64)[:64],
                file_size=rng.randint(20_000, 800_000),
                is_prerelease=False,
                plugin_api_version="1.0",
                min_host_version="1.0.0",
                max_host_version=None,
                supported_platforms=["all"],
            ),
            operator_id=owner_id,
        )
        version_row = await session.scalar(
            select(PluginVersionORM).where(
                PluginVersionORM.plugin_id == plugin.plugin_id,
                PluginVersionORM.version == version,
            )
        )
        if version_row is not None:
            version_row.download_count = rng.randint(120, 9800)
            version_row.published_at = utc_now() - timedelta(days=rng.randint(1, 90))

        # Likes
        for liker_idx in range(rng.randint(3, len(owner_pool))):
            liker_id = owner_pool[(index + liker_idx) % len(owner_pool)]
            if liker_id == owner_id and rng.random() < 0.5:
                continue
            existing_like = await session.scalar(
                select(PluginLikeORM).where(
                    PluginLikeORM.plugin_id == plugin.plugin_id,
                    PluginLikeORM.author_id == liker_id,
                )
            )
            if existing_like is None:
                session.add(PluginLikeORM(plugin_id=plugin.plugin_id, author_id=liker_id))

        # Ratings
        for rater_idx in range(rng.randint(2, len(owner_pool))):
            rater_id = owner_pool[(index * 3 + rater_idx) % len(owner_pool)]
            score = rng.choices([3, 4, 4, 5, 5, 5], k=1)[0]
            existing_rating = await session.scalar(
                select(PluginRatingORM).where(
                    PluginRatingORM.plugin_id == plugin.plugin_id,
                    PluginRatingORM.author_id == rater_id,
                )
            )
            if existing_rating is None:
                session.add(
                    PluginRatingORM(
                        plugin_id=plugin.plugin_id,
                        author_id=rater_id,
                        score=score,
                    )
                )

        # Comments
        comment_count = rng.randint(1, 4)
        for comment_idx in range(comment_count):
            commenter_id = owner_pool[(index + comment_idx * 2) % len(owner_pool)]
            session.add(
                PluginCommentORM(
                    plugin_id=plugin.plugin_id,
                    author_id=commenter_id,
                    parent_id=None,
                    content=rng.choice(SAMPLE_COMMENTS),
                    is_deleted=False,
                    created_at=utc_now() - timedelta(days=rng.randint(0, 30), hours=rng.randint(0, 23)),
                )
            )
        await session.flush()
