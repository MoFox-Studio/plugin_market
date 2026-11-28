/**
 * PR 前端预览专用模拟数据。
 *
 * 只在 VITE_PREVIEW_MOCK=1 时由 main.ts 动态加载，生产构建不会执行这段代码。
 * 它拦截同源的 /api/v1 请求并返回一组稳定的演示数据，让预览页面能展示真实的
 * 布局与内容，而不需要连接后端。
 */
import type {
  Author,
  CurationEntry,
  MarketHome,
  MarketStats,
  Plugin,
  PluginVersion,
  Skill,
  SkillVersion,
  TrendingItem,
} from '@/types';
import type {
  RecommendationPreferences,
  RecommendationResponse,
} from '@/types/recommendations';

const daysAgo = (days: number) =>
  new Date(Date.now() - days * 86_400_000).toISOString();

function avatar(letter: string, background: string): string {
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="96" height="96"><rect width="96" height="96" rx="48" fill="${background}"/><text x="48" y="61" font-family="Georgia, serif" font-size="42" fill="#fff" text-anchor="middle">${letter}</text></svg>`;
  return `data:image/svg+xml;charset=utf-8,${encodeURIComponent(svg)}`;
}

const authors: Author[] = [
  {
    author_id: 'github:lumina',
    github_login: 'lumina',
    display_name: 'Lumina Wei',
    avatar_url: avatar('L', '#6b7f5e'),
    author_type: 'user',
    is_admin: false,
  },
  {
    author_id: 'github:keita',
    github_login: 'keita',
    display_name: 'Keita Tanaka',
    avatar_url: avatar('K', '#9a5b4f'),
    author_type: 'user',
    is_admin: false,
  },
  {
    author_id: 'github:marina',
    github_login: 'marina',
    display_name: 'Marina Liu',
    avatar_url: avatar('M', '#4f6d8a'),
    author_type: 'user',
    is_admin: false,
  },
  {
    author_id: 'github:haruki',
    github_login: 'haruki',
    display_name: 'Haruki Aoi',
    avatar_url: avatar('H', '#7a6a4f'),
    author_type: 'user',
    is_admin: false,
  },
];

interface PluginSeed {
  id: string;
  name: string;
  summary: string;
  category: string;
  tags: string[];
  trust: string;
  version: string;
  owner: number;
  downloads: number;
  likes: number;
  comments: number;
  rating: number;
  ratings: number;
  days: number;
}

const pluginSeeds: PluginSeed[] = [
  {
    id: 'smart_reply',
    name: 'SmartReply · 智能自动回复',
    summary: '自适应语境的自动回复管理器，支持关键词、LLM 兜底与冷却时间。',
    category: 'chat',
    tags: ['auto-reply', 'llm', 'moderation'],
    trust: 'official',
    version: '2.3.1',
    owner: 0,
    downloads: 128_400,
    likes: 2_360,
    comments: 48,
    rating: 4.8,
    ratings: 126,
    days: 1,
  },
  {
    id: 'sticker_studio',
    name: 'StickerStudio · 表情包工坊',
    summary: '管理、生成和分发自定义表情包，支持标签检索与批量导出。',
    category: 'fun',
    tags: ['sticker', 'media', 'community'],
    trust: 'verified',
    version: '1.2.0',
    owner: 1,
    downloads: 86_200,
    likes: 1_540,
    comments: 32,
    rating: 4.6,
    ratings: 88,
    days: 2,
  },
  {
    id: 'daily_news',
    name: 'DailyNews · 每日新闻简报',
    summary: '每天定时向频道投递新闻、天气和日历摘要。',
    category: 'information',
    tags: ['news', 'weather', 'schedule'],
    trust: 'verified',
    version: '0.9.4',
    owner: 2,
    downloads: 54_800,
    likes: 980,
    comments: 21,
    rating: 4.4,
    ratings: 64,
    days: 3,
  },
  {
    id: 'wardrobe_vision',
    name: 'Wardrobe Vision · 换装视觉',
    summary: '基于图像理解的角色造型与场景识别工具。',
    category: 'vision',
    tags: ['image', 'vision', 'character'],
    trust: 'community',
    version: '0.5.2',
    owner: 3,
    downloads: 31_600,
    likes: 640,
    comments: 17,
    rating: 4.2,
    ratings: 39,
    days: 4,
  },
  {
    id: 'memory_graph_pro',
    name: 'MemoryGraph Pro',
    summary: '对接 Neo-MoFox 记忆图谱的增强探索与可视化工具。',
    category: 'tool',
    tags: ['memory', 'graph', 'visualization'],
    trust: 'official',
    version: '1.0.0',
    owner: 0,
    downloads: 73_500,
    likes: 1_120,
    comments: 26,
    rating: 4.7,
    ratings: 71,
    days: 5,
  },
  {
    id: 'music_box',
    name: 'MusicBox · 点歌姬',
    summary: '在群聊中播放和分享音乐，支持多平台歌单。',
    category: 'fun',
    tags: ['music', 'media', 'playlist'],
    trust: 'community',
    version: '0.8.1',
    owner: 1,
    downloads: 66_900,
    likes: 890,
    comments: 29,
    rating: 4.3,
    ratings: 57,
    days: 6,
  },
  {
    id: 'translate_bridge',
    name: 'TranslateBridge · 翻译桥',
    summary: '多模型翻译聚合，自动检测语言并缓存结果。',
    category: 'tool',
    tags: ['translate', 'llm', 'cache'],
    trust: 'verified',
    version: '1.4.2',
    owner: 2,
    downloads: 47_300,
    likes: 760,
    comments: 14,
    rating: 4.5,
    ratings: 46,
    days: 7,
  },
  {
    id: 'security_guard',
    name: 'SecurityGuard · 安全守卫',
    summary: '消息反垃圾、反广告和敏感词检测工具链。',
    category: 'moderation',
    tags: ['security', 'spam', 'moderation'],
    trust: 'official',
    version: '3.0.0',
    owner: 3,
    downloads: 92_100,
    likes: 1_780,
    comments: 37,
    rating: 4.9,
    ratings: 103,
    days: 8,
  },
  {
    id: 'wiki_seeker',
    name: 'WikiSeeker · 百科搜索',
    summary: '集成维基、百度百科与自定义知识库的查询助手。',
    category: 'information',
    tags: ['wiki', 'search', 'knowledge'],
    trust: 'community',
    version: '0.6.0',
    owner: 0,
    downloads: 28_400,
    likes: 520,
    comments: 11,
    rating: 4.1,
    ratings: 33,
    days: 9,
  },
  {
    id: 'party_games',
    name: 'PartyGames · 群聊小游戏',
    summary: '狼人杀、成语接龙、猜数等多款小游戏集合。',
    category: 'fun',
    tags: ['game', 'community', 'party'],
    trust: 'community',
    version: '1.1.3',
    owner: 1,
    downloads: 41_700,
    likes: 690,
    comments: 19,
    rating: 4.0,
    ratings: 41,
    days: 10,
  },
];

const plugins: Plugin[] = pluginSeeds.map((seed) => {
  const owner = authors[seed.owner];
  return {
    plugin_id: seed.id,
    display_name: seed.name,
    summary: seed.summary,
    description: `${seed.summary}\n\n这是 PR 前端预览使用的模拟插件记录，内容仅用于展示页面结构。`,
    status: 'published',
    trust_level: seed.trust,
    latest_version: seed.version,
    latest_version_published_at: daysAgo(seed.days),
    owner_id: owner.author_id,
    owner_login: owner.github_login,
    owner_display_name: owner.display_name,
    owner_avatar_url: owner.avatar_url ?? undefined,
    repository_url: `https://github.com/MoFox-Studio/${seed.id}`,
    homepage: `https://example.com/${seed.id}`,
    license: 'MIT',
    categories: [seed.category],
    tags: seed.tags,
    maintainers: [owner.github_login],
    likes_count: seed.likes,
    downloads_count: seed.downloads,
    comments_count: seed.comments,
    rating_avg: seed.rating,
    rating_count: seed.ratings,
    viewer_has_liked: false,
    updated_at: daysAgo(seed.days),
    created_at: daysAgo(seed.days + 45),
  };
});

const stats: MarketStats = {
  published_plugins: plugins.length,
  plugins_total: plugins.length,
  versions_total: 38,
  authors_total: authors.length,
  comments_total: plugins.reduce((sum, item) => sum + item.comments_count, 0),
  ratings_total: plugins.reduce((sum, item) => sum + item.rating_count, 0),
  likes_total: plugins.reduce((sum, item) => sum + item.likes_count, 0),
  downloads_total: plugins.reduce((sum, item) => sum + item.downloads_count, 0),
  pending_plugins: 0,
  pending_versions: 0,
  webhooks_total: 0,
};

const showcase: CurationEntry[] = plugins.slice(0, 3).map((plugin, index) => {
  const author =
    authors.find((item) => item.author_id === plugin.owner_id) ?? authors[0];
  return {
    id: index + 1,
    slot_type: 'featured_plugin',
    target_type: 'plugin',
    target_id: plugin.plugin_id,
    signature_plugin_id: plugin.plugin_id,
    sort_order: index,
    enabled: true,
    audience: 'all',
    display_meta: {},
    plugin,
    author,
    signature_plugin: plugin,
    created_by: 'preview',
    created_at: daysAgo(30),
    updated_at: daysAgo(30),
  };
});

const trendingAuthors: TrendingItem[] = authors.map((author, index) => {
  const best = plugins[index] ?? plugins[0];
  return {
    author_id: author.author_id,
    github_login: author.github_login,
    display_name: author.display_name,
    avatar_url: author.avatar_url,
    bio: '在 MoFox 社区分享实用插件与自动化灵感。',
    plugins_count: 4 - index,
    likes_received: 1_860 - index * 240,
    downloads_total: 128_000 - index * 18_000,
    rating_avg: 4.8 - index * 0.1,
    rating_count: 96 - index * 12,
    best_plugin: {
      plugin_id: best.plugin_id,
      display_name: best.display_name,
      summary: best.summary,
      icon_url: null,
      latest_version: best.latest_version ?? null,
    },
  };
});

const categoryPreview = (category: string) => {
  const items = plugins.filter((plugin) => plugin.categories?.includes(category));
  return { items, total: items.length };
};

const home: MarketHome = {
  showcase,
  featured_plugins: plugins.slice(0, 6),
  trending_authors: trendingAuthors,
  latest: [...plugins]
    .sort(
      (a, b) =>
        new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime(),
    )
    .slice(0, 5),
  top_rated: [...plugins]
    .sort((a, b) => b.rating_avg - a.rating_avg)
    .slice(0, 6),
  categories_preview: {
    chat: categoryPreview('chat'),
    fun: categoryPreview('fun'),
    information: categoryPreview('information'),
    tool: categoryPreview('tool'),
  },
  stats,
  active_announcements: [],
};

interface SkillSeed {
  id: string;
  name: string;
  description: string;
  category: string;
  tags: string[];
  owner: number;
  downloads: number;
  likes: number;
  comments: number;
  rating: number;
  ratings: number;
  days: number;
}

const skillSeeds: SkillSeed[] = [
  {
    id: 'gazette_writer',
    name: 'GazetteWriter · 公报撰稿',
    description: '把零散素材整理成有版面感的社区公报，支持 Markdown 与栏目编排。',
    category: 'productivity',
    tags: ['writing', 'markdown', 'editorial'],
    owner: 0,
    downloads: 12_600,
    likes: 320,
    comments: 9,
    rating: 4.7,
    ratings: 28,
    days: 2,
  },
  {
    id: 'memory_curator',
    name: 'MemoryCurator · 记忆整理',
    description: '从对话中提炼可复用的长期记忆，并按主题归档。',
    category: 'ai',
    tags: ['memory', 'knowledge', 'ai'],
    owner: 1,
    downloads: 9_800,
    likes: 260,
    comments: 7,
    rating: 4.5,
    ratings: 21,
    days: 4,
  },
  {
    id: 'release_notes',
    name: 'ReleaseNotes · 版本手记',
    description: '根据提交记录生成结构化的版本说明与升级提示。',
    category: 'devtools',
    tags: ['release', 'changelog', 'automation'],
    owner: 2,
    downloads: 7_400,
    likes: 180,
    comments: 5,
    rating: 4.3,
    ratings: 16,
    days: 6,
  },
  {
    id: 'poster_design',
    name: 'PosterDesign · 海报设计',
    description: '为活动、专栏和推荐位生成风格统一的海报草图。',
    category: 'media',
    tags: ['design', 'image', 'layout'],
    owner: 3,
    downloads: 5_900,
    likes: 150,
    comments: 4,
    rating: 4.1,
    ratings: 12,
    days: 8,
  },
];

const skills: Skill[] = skillSeeds.map((seed) => {
  const owner = authors[seed.owner];
  return {
    skill_id: seed.id,
    display_name: seed.name,
    description: seed.description,
    readme_markdown: `## ${seed.name}\n\n${seed.description}\n\n### 使用方法\n\n在技能市场安装后，于对话中引用对应技能即可。\n\n- 支持自定义模板\n- 可与其他技能组合使用\n`,
    owner_id: owner.author_id,
    owner_login: owner.github_login,
    owner_display_name: owner.display_name,
    owner_avatar_url: owner.avatar_url ?? null,
    icon_url: null,
    categories: [seed.category],
    tags: seed.tags,
    status: 'published',
    trust_level: 'community',
    latest_version: '1.0.0',
    download_count: seed.downloads,
    likes_count: seed.likes,
    comments_count: seed.comments,
    rating_avg: seed.rating,
    rating_count: seed.ratings,
    viewer_has_liked: false,
    created_at: daysAgo(seed.days + 30),
    updated_at: daysAgo(seed.days),
  };
});

const categories = ['tool', 'chat', 'fun', 'information', 'vision', 'moderation'];
const tags = [
  'auto-reply',
  'llm',
  'music',
  'news',
  'translation',
  'sticker',
  'memory',
  'automation',
];
const skillCategories = ['productivity', 'ai', 'devtools', 'media'];
const skillTags = ['writing', 'markdown', 'memory', 'release', 'design', 'layout'];

const ratingDistribution = { '5': 18, '4': 6, '3': 2, '2': 1, '1': 0 };

function pluginVersions(plugin: Plugin): PluginVersion[] {
  const latest = plugin.latest_version ?? '1.0.0';
  return [latest, '1.0.0', '0.9.0'].map((version, index) => ({
    version,
    status: 'published',
    release_title: index === 0 ? '稳定版' : `历史版本 ${version}`,
    published_at: daysAgo(index * 9 + 2),
    file_size: 1_048_576 + index * 26_214,
    download_count: Math.max(120, plugin.downloads_count - index * 4_200),
    plugin_api_version: '1.0',
    min_host_version: '0.1.0',
    supported_platforms: ['windows', 'linux', 'macos'],
    is_prerelease: false,
    is_yanked: false,
    release_url: `${plugin.repository_url}/releases/tag/v${version}`,
    asset_download_url: plugin.repository_url,
  }));
}

function skillVersions(): SkillVersion[] {
  return ['1.0.0', '0.9.0'].map((version, index) => ({
    version,
    package_size: 148_000 + index * 12_000,
    checksum_sha256: 'preview-checksum',
    release_notes: index === 0 ? '首个稳定版本。' : '预览版本。',
    min_mofox_version: '0.1.0',
    download_count: 1_200 - index * 300,
    created_at: daysAgo(index * 12 + 3),
  }));
}

function pluginReadme(plugin: Plugin): string {
  return [
    `<h2>${plugin.display_name}</h2>`,
    `<p>${plugin.summary}</p>`,
    '<h3>功能特性</h3>',
    '<ul><li>开箱即用的默认配置</li><li>可在插件设置中调整行为</li><li>与社区插件组合使用</li></ul>',
    '<h3>安装</h3>',
    '<pre><code>mpdt plugin install ' + plugin.plugin_id + '</code></pre>',
    '<p>以上内容来自 PR 预览的模拟数据，仅用于展示阅读版式。</p>',
  ].join('');
}

const recommendationPreferences: RecommendationPreferences = {
  personalization_enabled: false,
  interests: { categories: [], tags: [] },
  ignored_plugins: [],
  reduced_categories: [],
  revision: 1,
  updated_at: daysAgo(1),
  feedback_retention_days: 30,
};

const recommendationResponse: RecommendationResponse = {
  recommendation_id: 'preview',
  algorithm_version: 'preview',
  mode: 'popular',
  generated_at: daysAgo(0),
  items: plugins.slice(0, 6).map((plugin) => ({
    plugin,
    recommended_version: plugin.latest_version ?? '1.0.0',
    compatibility: 'compatible',
    reasons: [{ code: 'popular', label: '社区热门' }],
  })),
  next_cursor: null,
};

function json(data: unknown, status = 200): Response {
  return new Response(JSON.stringify(data), {
    status,
    headers: {
      'Content-Type': 'application/json; charset=utf-8',
      'X-Preview-Mock': '1',
    },
  });
}

function listPlugins(params: URLSearchParams) {
  const query = (params.get('q') ?? '').trim().toLowerCase();
  const category = params.get('category') ?? '';
  const tag = params.get('tag') ?? '';
  const trust = params.get('trust_level') ?? '';
  const authorId = params.get('author_id') ?? '';
  const sort = params.get('sort') ?? '';

  let items = plugins.filter((plugin) => {
    const haystack = `${plugin.display_name} ${plugin.summary} ${plugin.owner_login ?? ''}`.toLowerCase();
    return (
      (!query || haystack.includes(query)) &&
      (!category || plugin.categories?.includes(category)) &&
      (!tag || plugin.tags?.includes(tag)) &&
      (!trust || plugin.trust_level === trust) &&
      (!authorId || plugin.owner_id === authorId)
    );
  });

  if (sort === 'popular' || sort === 'likes') {
    items = [...items].sort((a, b) => b.likes_count - a.likes_count);
  } else if (sort === 'downloads') {
    items = [...items].sort((a, b) => b.downloads_count - a.downloads_count);
  } else if (sort === 'rating') {
    items = [...items].sort((a, b) => b.rating_avg - a.rating_avg);
  }

  const offset = Number(params.get('offset') ?? 0);
  const limit = Number(params.get('limit') ?? items.length);
  return { items: items.slice(offset, offset + limit), total: items.length };
}

function listSkills(params: URLSearchParams) {
  const query = (params.get('search') ?? params.get('q') ?? '')
    .trim()
    .toLowerCase();
  const category = params.get('category') ?? '';
  const tag = params.get('tag') ?? '';
  const sort = params.get('sort') ?? '';

  let items = skills.filter((skill) => {
    const haystack = `${skill.display_name} ${skill.description} ${skill.owner_login ?? ''}`.toLowerCase();
    return (
      (!query || haystack.includes(query)) &&
      (!category || skill.categories.includes(category)) &&
      (!tag || skill.tags.includes(tag))
    );
  });

  if (sort === 'downloads') {
    items = [...items].sort((a, b) => b.download_count - a.download_count);
  } else if (sort === 'name') {
    items = [...items].sort((a, b) =>
      a.display_name.localeCompare(b.display_name, 'zh-CN'),
    );
  } else if (sort === 'created') {
    items = [...items].sort(
      (a, b) =>
        new Date(b.created_at).getTime() - new Date(a.created_at).getTime(),
    );
  }

  const page = Math.max(1, Number(params.get('page') ?? 1));
  const pageSize = Math.max(1, Number(params.get('page_size') ?? items.length));
  const start = (page - 1) * pageSize;
  return { items: items.slice(start, start + pageSize), total: items.length };
}

function pluginComments(plugin: Plugin) {
  return [
    {
      id: 'preview-comment-1',
      plugin_id: plugin.plugin_id,
      parent_id: null,
      content: `在预览里看到 ${plugin.display_name} 的版面效果，很清晰。`,
      created_at: daysAgo(2),
      is_deleted: false,
      author: {
        author_id: authors[1].author_id,
        github_login: authors[1].github_login,
        display_name: authors[1].display_name,
        avatar_url: authors[1].avatar_url ?? undefined,
      },
    },
    {
      id: 'preview-comment-2',
      plugin_id: plugin.plugin_id,
      parent_id: null,
      content: '安装流程的说明也可以在这里展示。',
      created_at: daysAgo(1),
      is_deleted: false,
      author: {
        author_id: authors[2].author_id,
        github_login: authors[2].github_login,
        display_name: authors[2].display_name,
        avatar_url: authors[2].avatar_url ?? undefined,
      },
    },
  ];
}

function skillComments() {
  return [
    {
      id: 1,
      skill_id: skills[0].skill_id,
      parent_id: null,
      content: '预览数据里也能看到讨论区的排版。',
      created_at: daysAgo(1),
      is_deleted: false,
      author: {
        author_id: authors[0].author_id,
        github_login: authors[0].github_login,
        display_name: authors[0].display_name,
        avatar_url: authors[0].avatar_url ?? undefined,
      },
    },
  ];
}

function respond(
  apiPath: string,
  method: string,
  params: URLSearchParams,
): Response | null {
  if (method !== 'GET') {
    if (apiPath === '/recommendations') return json(recommendationResponse);
    if (apiPath === '/auth/logout') return new Response(null, { status: 204 });
    if (apiPath.endsWith('/dismiss')) return json({ dismissed: true });
    if (apiPath.endsWith('/install-record')) {
      return json({ asset_download_url: null });
    }
    return json({ ok: true });
  }

  if (apiPath === '/me') return json({ authenticated: false });
  if (apiPath === '/me/recommendation-preferences') {
    return json(recommendationPreferences);
  }
  if (apiPath === '/inbox/unread-count') return json({ count: 0 });
  if (apiPath === '/inbox/messages') return json({ items: [], total: 0 });
  if (apiPath === '/market/home') return json(home);
  if (apiPath === '/market/stats') return json(stats);
  if (apiPath === '/categories') return json({ items: categories });
  if (apiPath === '/tags') return json({ items: tags });
  if (apiPath === '/announcements/active') return json([]);
  if (apiPath === '/plugins') return json(listPlugins(params));
  if (apiPath === '/skills') return json(listSkills(params));
  if (apiPath === '/skills/categories') return json({ items: skillCategories });
  if (apiPath === '/skills/tags') return json({ items: skillTags });
  if (apiPath === '/authors/search') {
    return json(
      authors.slice(0, 4).map((author) => ({
        author_id: author.author_id,
        github_login: author.github_login,
        display_name: author.display_name,
        avatar_url: author.avatar_url ?? null,
      })),
    );
  }

  const pluginMatch = apiPath.match(/^\/plugins\/([^/]+)(\/.*)?$/);
  if (pluginMatch) {
    const plugin = plugins.find(
      (item) => item.plugin_id === decodeURIComponent(pluginMatch[1]),
    );
    if (!plugin) return json({ detail: 'Plugin not found' }, 404);
    const rest = pluginMatch[2] ?? '';
    if (!rest) return json(plugin);
    if (rest === '/community') {
      return json({
        plugin,
        rating: { distribution: ratingDistribution },
      });
    }
    if (rest === '/versions') {
      const items = pluginVersions(plugin);
      return json({ items, total: items.length });
    }
    if (rest === '/readme') {
      return json({ exists: true, html: pluginReadme(plugin) });
    }
    if (rest === '/dependencies') return json({ items: [] });
    if (rest === '/comments') {
      const items = pluginComments(plugin);
      return json({ items, total: items.length });
    }
    if (rest === '/rating') {
      return json({ distribution: ratingDistribution });
    }
  }

  const skillMatch = apiPath.match(/^\/skills\/([^/]+)(\/.*)?$/);
  if (skillMatch) {
    const skill = skills.find(
      (item) => item.skill_id === decodeURIComponent(skillMatch[1]),
    );
    if (!skill) return json({ detail: 'Skill not found' }, 404);
    const rest = skillMatch[2] ?? '';
    if (!rest) return json(skill);
    if (rest === '/versions') {
      const items = skillVersions();
      return json({ items, total: items.length });
    }
    if (rest === '/comments') {
      const items = skillComments();
      return json({ items, total: items.length });
    }
    if (rest === '/rating') {
      return json({ distribution: ratingDistribution });
    }
  }

  const authorMatch = apiPath.match(/^\/authors\/([^/]+)\/(profile|pins|follow)$/);
  if (authorMatch) {
    const authorId = decodeURIComponent(authorMatch[1]);
    const author = authors.find((item) => item.author_id === authorId);
    if (authorMatch[2] === 'profile') {
      return json({
        author_id: authorId,
        bio: author ? `${author.display_name} 的模拟作者简介。` : '模拟作者简介。',
        background_image_url: null,
        background_image_kind: 'url',
        updated_at: daysAgo(5),
      });
    }
    if (authorMatch[2] === 'pins') return json([]);
    return json({ author_id: authorId, following: false, followers_count: 42 });
  }

  if (apiPath.startsWith('/me/')) return json({ items: [], total: 0 });

  console.debug('[preview] 未匹配的模拟接口', apiPath, method);
  return json({ items: [], total: 0 });
}

function installBadge(): void {
  if (document.getElementById('pr-preview-badge')) return;
  const badge = document.createElement('a');
  badge.id = 'pr-preview-badge';
  badge.textContent = import.meta.env.VITE_PR_NUMBER
    ? `PR #${import.meta.env.VITE_PR_NUMBER} · 前端预览 · 模拟数据`
    : '前端预览 · 模拟数据';
  const href = import.meta.env.VITE_PR_URL;
  if (href) {
    badge.href = href;
    badge.target = '_blank';
    badge.rel = 'noopener noreferrer';
  }
  badge.style.cssText = [
    'position:fixed',
    'right:14px',
    'bottom:14px',
    'z-index:2147483647',
    'display:inline-flex',
    'align-items:center',
    'gap:6px',
    'padding:8px 13px',
    'border-radius:999px',
    'background:#1f1d1a',
    'color:#f4efe6',
    'font:600 12px/1.4 ui-sans-serif,system-ui,-apple-system,sans-serif',
    'text-decoration:none',
    'letter-spacing:.02em',
    'box-shadow:0 8px 24px rgba(0,0,0,.28)',
    'opacity:.92',
  ].join(';');
  document.body.appendChild(badge);
}

export function installPreviewMock(): void {
  const nativeFetch = window.fetch.bind(window);

  window.fetch = (async (
    input: RequestInfo | URL,
    init?: RequestInit,
  ): Promise<Response> => {
    const request = input instanceof Request ? input : null;
    const rawUrl = request ? request.url : String(input);
    const url = new URL(rawUrl, window.location.href);
    const method = (init?.method ?? request?.method ?? 'GET').toUpperCase();

    if (url.origin !== window.location.origin) {
      return nativeFetch(input, init);
    }

    if (url.pathname.endsWith('/health')) {
      return json({ status: 'ok' });
    }
    if (url.pathname.endsWith('/ready')) {
      return json({ status: 'ready', database: 'ok' });
    }

    const apiIndex = url.pathname.indexOf('/api/v1');
    if (apiIndex < 0) {
      return nativeFetch(input, init);
    }

    const apiPath = url.pathname.slice(apiIndex + '/api/v1'.length) || '/';
    await new Promise((resolve) => setTimeout(resolve, 120));
    return respond(apiPath, method, url.searchParams) ?? json(null, 404);
  }) as typeof window.fetch;

  installBadge();
}
