# Plugin Market Backend API 文档

本文档基于当前仓库中的 FastAPI 实现整理，覆盖后端对外暴露的主要 HTTP 接口、认证方式、常见请求体、返回结构和部署联调注意事项。

适用代码入口：

- 服务入口：src/plugin_market_backend/app.py
- 请求/响应模型：src/plugin_market_backend/schemas.py
- Bearer 认证：src/plugin_market_backend/auth.py
- 浏览器会话认证：src/plugin_market_backend/session_auth.py
- 统一错误：src/plugin_market_backend/errors.py

## 1. 概览

- Base URL：部署域名根路径，例如 https://market.example.com
- API 前缀：/api/v1
- 内容类型：JSON 为主，图片上传使用 multipart/form-data
- 鉴权模式：公开、浏览器 GitHub 登录、作者 Bearer Token、管理员 Bearer Token / 浏览器管理员会话
- Cookie 会话名：默认 plugin_market_session，可由环境变量调整
- 静态资源：/assets、/plugin-media

## 2. 认证方式

### 2.1 公开接口

无需任何认证，适合市场浏览、插件详情、分类标签、公共作者资料、Webhook 外部投递等。

### 2.2 浏览器登录会话

用于前端页面中的“我 / Inbox / 评论 / 点赞 / 评分 / 管理后台”等能力。

- 登录入口：GET /api/v1/auth/github/login
- 登录完成：GET /api/v1/auth/github/callback
- 当前登录态：GET /api/v1/me
- 登出：POST /api/v1/auth/logout

需要登录的浏览器接口通常依赖 require_browser_author。

### 2.3 作者 Bearer Token

用于 CLI 或自动化发布流程，依赖 require_author_token。

Header 格式：

```http
Authorization: Bearer <token>
```

支持两种来源：

- 固定作者 token：PLUGIN_MARKET_AUTHOR_TOKEN
- GitHub Bearer Token：服务端会调用 GitHub 用户信息接口并自动映射作者身份

### 2.4 管理员认证

管理接口依赖 require_admin_operator，接受两种来源：

- 固定管理员 token：Authorization: Bearer <admin-token>
- 已登录且 is_admin=true 的浏览器管理员会话

## 3. 浏览器写操作的同源限制

大多数浏览器写接口在登录校验之外，还会调用 ensure_same_origin_browser_write。也就是说使用 Cookie 会话进行 POST / PUT / PATCH / DELETE 时，请求的 Origin / Referer 必须与服务端允许的来源一致。

## 4. 统一错误格式

所有业务错误和校验错误都会返回统一 JSON 包装：

```json
{
  "error": {
    "code": "ERROR_CODE",
    "message": "Human readable message",
    "details": {}
  }
}
```

常见状态码：

- 400：参数或状态不合法
- 401：未认证
- 403：认证通过但无权限
- 404：资源不存在
- 409：冲突
- 422：请求体验证失败
- 500：服务端错误

422 的 details.errors 来自 FastAPI / Pydantic 校验结果。

## 5. 常见响应包装

### 5.1 列表分页包装

```json
{
  "items": [],
  "total": 0
}
```

用于：

- PluginListResponse
- VersionListResponse
- CommentListResponse
- InboxMessageListResponse
- AnnouncementListResponse
- CurationEntryListResponse

### 5.2 轻量操作结果

```json
{ "ok": true }
```

或：

```json
{ "updated": 3 }
```

### 5.3 204 No Content

删除类接口部分直接返回 204，无响应体。

## 6. 核心模型摘要

以下仅列出联调时最常用字段。

### 6.1 Plugin

- plugin_id：插件唯一标识
- display_name：展示名称
- summary / description：简介与详情
- icon_url：图标地址
- homepage / repository_url / license：外部链接与许可证
- categories / tags：分类与标签
- status：插件状态
- trust_level：信任等级
- owner_id / owner_login / owner_display_name：作者信息
- maintainers：维护者 author_id 列表
- likes_count / rating_avg / rating_count / comments_count / downloads_count：统计信息
- latest_version / latest_version_published_at：最新版本信息
- viewer_has_liked / viewer_rating：当前用户视角的互动信息

### 6.2 PluginVersion

- plugin_id / version
- release_tag / release_title / release_url
- asset_name / asset_download_url / checksum_sha256
- file_size / published_at
- is_prerelease / is_yanked / status
- plugin_api_version / min_host_version / max_host_version
- supported_platforms
- last_sync_status / last_sync_error
- download_count

### 6.3 Comment

- id / plugin_id / parent_id
- content
- created_at / updated_at / is_deleted
- author：CommentAuthor
- mentions：MentionCandidate[]

### 6.4 RatingSummary

- plugin_id
- rating_avg
- rating_count
- distribution：各分值票数，例如 {"5": 10, "4": 2}
- viewer_rating：当前用户评分

### 6.5 AuthorProfile

- author_id
- bio
- background_image_url
- background_image_kind：url 或 upload
- updated_at

### 6.6 MarketHome

- showcase：精选编排位
- featured_plugins：推荐插件
- trending_authors：热门作者
- latest：最新插件
- top_rated：高评分插件
- categories_preview：分类预览
- stats：市场统计
- active_announcements：可见公告

## 7. 关键请求体示例

### 7.1 PluginCreate

```json
{
  "plugin_id": "example_plugin",
  "display_name": "Example Plugin",
  "summary": "一句话介绍",
  "description": "完整描述",
  "repository_url": "https://github.com/example/repo",
  "license": "MIT",
  "categories": ["tool"],
  "tags": ["utility", "chat"],
  "maintainers": ["github:alice"],
  "plugin_dependencies": ["base_plugin>=1.0.0"],
  "readme_markdown": "# README"
}
```

### 7.2 PluginVersionCreate

```json
{
  "version": "1.0.0",
  "release_tag": "v1.0.0",
  "release_title": "Initial Release",
  "release_url": "https://github.com/example/repo/releases/tag/v1.0.0",
  "asset_name": "example-plugin.zip",
  "asset_download_url": "https://github.com/example/repo/releases/download/v1.0.0/example-plugin.zip",
  "checksum_sha256": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
  "file_size": 102400,
  "is_prerelease": false,
  "plugin_api_version": "1.0",
  "min_host_version": "1.0.0",
  "supported_platforms": ["windows", "linux"]
}
```

### 7.3 CommentCreate

```json
{
  "content": "很好用，@alice 能否支持更多参数？",
  "parent_id": null
}
```

### 7.4 RatingRequest

```json
{
  "score": 5
}
```

### 7.5 AuthorProfileUpdate

```json
{
  "bio": "这里是作者简介",
  "background_image_url": "https://example.com/background.webp"
}
```

也可使用内部上传后的路径：

```json
{
  "background_image_url": "/plugin-media/profile_backgrounds/github_alice.webp"
}
```

### 7.6 PluginMetadataPatch

```json
{
  "display_name": "新的显示名",
  "icon_url": "/plugin-media/icons/example_plugin.png",
  "categories": ["tool"],
  "tags": ["assistant", "workflow"]
}
```

### 7.7 AnnouncementCreate

```json
{
  "title": "维护通知",
  "body_markdown": "今晚 23:00 短暂维护",
  "display_mode": "banner",
  "severity": "warning",
  "dismissible": true,
  "enabled": true,
  "audience": "all",
  "emit_inbox": false
}
```

### 7.8 CurationEntryCreate

```json
{
  "slot_type": "featured_plugin",
  "target_type": "plugin",
  "target_id": "example_plugin",
  "signature_plugin_id": null,
  "sort_order": 0,
  "enabled": true,
  "audience": "all",
  "display_meta": {}
}
```

### 7.9 BulkActionRequest

```json
{
  "plugin_ids": ["plugin_a", "plugin_b"],
  "action": "publish",
  "params": {}
}
```

## 8. 接口清单

### 8.1 SPA 与静态入口

| 方法 | 路径 | 认证 | 用途 | 返回 |
| --- | --- | --- | --- | --- |
| GET | / | 公开 | 返回前端首页 SPA | index.html |
| GET | /admin | 公开 | 返回后台 SPA | index.html |
| GET | /me | 公开 | 返回个人工作台 SPA | index.html |
| GET | /plugin/{plugin_id} | 公开 | 插件详情页直达入口 | index.html |
| GET | /author/{author_id} | 公开 | 作者页直达入口 | index.html |
| GET | /logo.png | 公开 | 站点 logo | 图片文件 |
| GET | /assets/* | 公开 | 前端静态资源 | 静态文件 |
| GET | /plugin-media/* | 公开 | 上传后的图标与背景图 | 静态文件 |

### 8.2 健康检查与品牌信息

| 方法 | 路径 | 认证 | 说明 | 返回 |
| --- | --- | --- | --- | --- |
| GET | /health | 公开 | 进程健康检查 | {status, service} |
| GET | /ready | 公开 | 数据库 readiness 检查 | {status, database} |
| GET | /api/v1/brand | 公开 | 前端品牌资源地址 | {logo_url} |

### 8.3 公共市场接口

| 方法 | 路径 | 认证 | 说明 | 请求参数 | 返回 |
| --- | --- | --- | --- | --- | --- |
| GET | /api/v1/plugins | 公开，可感知当前 viewer | 搜索 / 筛选插件列表 | q, status, category, tag, trust_level, sort, offset, limit | PluginListResponse |
| GET | /api/v1/market/featured | 公开 | 首页推荐分组 | limit | {ranking, latest, top_rated} |
| GET | /api/v1/market/trending-authors | 公开 | 热门作者榜 | limit | TrendingItem[] |
| GET | /api/v1/market/stats | 公开 | 市场统计 | 无 | MarketStats |
| GET | /api/v1/market/home | 公开，可感知当前 viewer | 首页聚合接口，支持 ETag | 无 | MarketHome |
| GET | /api/v1/plugins/{plugin_id} | 公开 | 插件详情 | 无 | Plugin |
| GET | /api/v1/plugins/{plugin_id}/readme | 公开 | 渲染后的 README | 无 | PluginReadmeResponse |
| GET | /api/v1/plugins/{plugin_id}/dependencies | 公开 | 依赖解析结果 | 无 | PluginDependenciesResponse |
| GET | /api/v1/plugins/{plugin_id}/community | 公开，可感知当前 viewer | 详情页聚合快照 | 无 | CommunitySnapshot |
| GET | /api/v1/plugins/{plugin_id}/rating | 公开，可感知当前 viewer | 评分聚合 | 无 | RatingSummary |
| GET | /api/v1/plugins/{plugin_id}/comments | 公开 | 评论列表 | offset, limit | CommentListResponse |
| POST | /api/v1/plugins/{plugin_id}/install-record | 公开 | 安装/下载计数 | version | PluginVersion |
| GET | /api/v1/plugins/{plugin_id}/versions | 公开 | 版本列表 | 无 | VersionListResponse |
| GET | /api/v1/plugins/{plugin_id}/versions/{version} | 公开 | 单版本详情 | 无 | PluginVersion |
| GET | /api/v1/plugins/{plugin_id}/recommended-version | 公开 | 推荐安装版本 | host_version, plugin_api_version, platform, include_prerelease | PluginVersion |
| GET | /api/v1/plugins/{plugin_id}/install | 公开 | 安装信息聚合 | host_version, plugin_api_version, platform | InstallInfo |
| GET | /api/v1/categories | 公开 | 分类列表 | 无 | TaxonomyResponse |
| GET | /api/v1/tags | 公开 | 标签列表 | 无 | TaxonomyResponse |

### 8.4 社区互动接口

| 方法 | 路径 | 认证 | 说明 | 请求体 | 返回 |
| --- | --- | --- | --- | --- | --- |
| POST | /api/v1/plugins/{plugin_id}/rating | 浏览器登录 | 创建或更新评分 | RatingRequest | RatingSummary |
| DELETE | /api/v1/plugins/{plugin_id}/rating | 浏览器登录 | 清除评分 | 无 | RatingSummary |
| POST | /api/v1/plugins/{plugin_id}/like | 浏览器登录 | 点赞切换 | 无 | LikeResponse |
| POST | /api/v1/plugins/{plugin_id}/comments | 浏览器登录 | 新建评论 | CommentCreate | Comment |
| DELETE | /api/v1/plugins/{plugin_id}/comments/{comment_id} | 浏览器登录 | 删除自己的评论，管理员可删任意评论 | 无 | {ok:true} |

说明：浏览器写操作附带同源校验。

### 8.5 GitHub OAuth 与当前登录态

| 方法 | 路径 | 认证 | 说明 | 返回 |
| --- | --- | --- | --- | --- |
| GET | /api/v1/auth/github/login | 公开 | 发起 GitHub OAuth 登录 | 302 跳转 |
| GET | /api/v1/auth/github/callback | GitHub OAuth 回调 | 换取 GitHub 用户信息并写入 Cookie | 302 跳转 |
| POST | /api/v1/auth/logout | 浏览器登录 | 清除当前浏览器会话 | {ok:true} |
| GET | /api/v1/me | 公开 | 返回当前 Cookie 登录状态 | AuthStatus |

### 8.6 作者公开资料与提及搜索

| 方法 | 路径 | 认证 | 说明 | 返回 |
| --- | --- | --- | --- | --- |
| GET | /api/v1/authors/{author_id}/profile | 公开 | 作者公开资料 | AuthorProfile |
| GET | /api/v1/authors/{author_id}/pins | 公开 | 作者公开置顶插件 | PinnedPluginItem[] |
| GET | /api/v1/authors/search | 公开 | @ 提及候选搜索 | MentionCandidate[] |

author_search 查询参数：

- prefix：1 到 39 字符
- limit：1 到 20，默认 8

### 8.7 当前登录用户个人空间与工作台

| 方法 | 路径 | 认证 | 说明 | 请求体 / 参数 | 返回 |
| --- | --- | --- | --- | --- | --- |
| GET | /api/v1/me/profile | 浏览器登录 | 获取自己的个人空间资料 | 无 | AuthorProfile |
| PUT | /api/v1/me/profile | 浏览器登录 | 更新自己的 Bio 与背景 | AuthorProfileUpdate | AuthorProfile |
| POST | /api/v1/me/profile/background | 浏览器登录 | 上传背景图 | multipart/form-data: file | AuthorProfile |
| POST | /api/v1/me/plugins/{plugin_id}/icon | 浏览器登录 | 上传插件图标 | multipart/form-data: file | Plugin |
| GET | /api/v1/me/pins | 浏览器登录 | 获取自己的置顶插件 | 无 | PinnedPluginItem[] |
| POST | /api/v1/me/pins | 浏览器登录 | 新增置顶插件 | PinCreate | PinnedPluginItem |
| PUT | /api/v1/me/pins/{plugin_id} | 浏览器登录 | 更新置顶原因 | PinUpdate | PinnedPluginItem |
| DELETE | /api/v1/me/pins/{plugin_id} | 浏览器登录 | 删除置顶插件 | 无 | 204 |
| GET | /api/v1/me/plugins | 浏览器登录 | 获取自己拥有或维护的插件列表 | 无 | PluginListResponse |
| GET | /api/v1/me/plugins/{plugin_id} | 浏览器登录 | 获取单个插件治理快照 | 无 | PluginGovernanceSnapshot |
| POST | /api/v1/me/plugins/{plugin_id}/versions/{version}/yank | 浏览器登录 | 下架自己的某个版本 | ReviewDecision | PluginVersion |
| DELETE | /api/v1/me/plugins/{plugin_id} | 浏览器登录 | 删除自己的插件 | 无 | 204 |
| PATCH | /api/v1/me/plugins/{plugin_id}/metadata | 浏览器登录 | 更新前台展示元数据 | PluginMetadataPatch | Plugin |

### 8.8 Inbox

| 方法 | 路径 | 认证 | 说明 | 请求参数 / 体 | 返回 |
| --- | --- | --- | --- | --- | --- |
| GET | /api/v1/inbox/messages | 浏览器登录 | 获取当前用户 Inbox 列表 | type, offset, limit | InboxMessageListResponse |
| GET | /api/v1/inbox/unread-count | 浏览器登录 | 获取未读数 | 无 | InboxUnreadCount |
| POST | /api/v1/inbox/messages/{message_id}/read | 浏览器登录 | 标记单条为已读 | 无 | {updated:n} |
| POST | /api/v1/inbox/read-all | 浏览器登录 | 全部标记已读 | 无 | {updated:n} |

### 8.9 公告接口

| 方法 | 路径 | 认证 | 说明 | 返回 |
| --- | --- | --- | --- | --- |
| GET | /api/v1/announcements/active | 公开，可感知当前 viewer | 获取当前可见公告 | AnnouncementDTO[] |
| POST | /api/v1/announcements/{announcement_id}/dismiss | 浏览器登录 | 忽略单条公告 | AnnouncementDismissResponse |

### 8.10 管理员公告接口

| 方法 | 路径 | 认证 | 说明 | 请求体 | 返回 |
| --- | --- | --- | --- | --- | --- |
| GET | /api/v1/admin/announcements | 管理员 | 公告列表 | offset, limit | AnnouncementListResponse |
| POST | /api/v1/admin/announcements | 管理员 | 创建公告 | AnnouncementCreate | AnnouncementDTO |
| PUT | /api/v1/admin/announcements/{announcement_id} | 管理员 | 更新公告 | AnnouncementUpdate | AnnouncementDTO |
| POST | /api/v1/admin/announcements/{announcement_id}/disable | 管理员 | 关闭公告 | 无 | AnnouncementDTO |
| POST | /api/v1/admin/announcements/{announcement_id}/resurface | 管理员 | 重发公告，提高 dismiss_token | 无 | AnnouncementDTO |

### 8.11 管理员精选编排接口

| 方法 | 路径 | 认证 | 说明 | 请求体 | 返回 |
| --- | --- | --- | --- | --- | --- |
| GET | /api/v1/admin/curation/entries | 管理员 | 获取全部精选条目 | 无 | CurationEntryListResponse |
| POST | /api/v1/admin/curation/entries | 管理员 | 创建精选条目 | CurationEntryCreate | CurationEntryDTO |
| PUT | /api/v1/admin/curation/entries/{entry_id} | 管理员 | 更新精选条目 | CurationEntryUpdate | CurationEntryDTO |
| POST | /api/v1/admin/curation/entries/{entry_id}/disable | 管理员 | 禁用精选条目 | 无 | CurationEntryDTO |
| PUT | /api/v1/admin/curation/order | 管理员 | 批量调整排序 | CurationOrderUpdate | CurationEntryDTO[] |

### 8.12 管理员批量治理接口

| 方法 | 路径 | 认证 | 说明 | 请求体 | 返回 |
| --- | --- | --- | --- | --- | --- |
| POST | /api/v1/admin/plugins/bulk | 管理员 | 对多个插件执行批量治理 | BulkActionRequest | BulkActionResult，HTTP 207 |

action 可选值：

- publish
- reject
- block
- deprecate
- set_trust_level
- delete

### 8.13 作者 / CLI 接口

| 方法 | 路径 | 认证 | 说明 | 请求体 | 返回 |
| --- | --- | --- | --- | --- | --- |
| POST | /api/v1/plugins | 作者 Bearer | 注册插件 | PluginCreate | Plugin |
| PUT | /api/v1/plugins/{plugin_id} | 作者 Bearer | 更新插件元数据 | PluginUpdate | Plugin |
| POST | /api/v1/plugins/{plugin_id}/versions | 作者 Bearer | 提交新版本 | PluginVersionCreate | PluginVersion |
| POST | /api/v1/plugins/{plugin_id}/sync | 作者 Bearer | 同步版本元数据 | VersionSyncRequest | PluginVersion |
| POST | /api/v1/plugins/{plugin_id}/versions/{version}/yank | 作者 Bearer | 作者下架版本 | ReviewDecision | PluginVersion |
| GET | /api/v1/plugins/{plugin_id}/status | 作者 Bearer | 查询插件状态、审核状态与同步状态 | 无 | 自由 JSON 状态对象 |

### 8.14 管理员治理与系统接口

| 方法 | 路径 | 认证 | 说明 | 请求体 | 返回 |
| --- | --- | --- | --- | --- | --- |
| GET | /api/v1/admin/reviews | 管理员 | 审核记录列表 | 无 | ReviewRecord[] |
| GET | /api/v1/admin/plugins | 管理员 | 全量插件列表 | offset, limit | PluginListResponse |
| GET | /api/v1/admin/plugins/{plugin_id} | 管理员 | 单插件治理快照 | 无 | PluginGovernanceSnapshot |
| GET | /api/v1/admin/dashboard | 管理员 | 后台首页聚合数据 | 无 | AdminDashboard |
| GET | /api/v1/admin/system | 管理员 | 系统运行状态 | 无 | 自由 JSON |
| GET | /api/v1/admin/stats | 管理员 | 市场统计 | 无 | MarketStats |
| POST | /api/v1/admin/plugins/{plugin_id}/reject | 管理员 | 退回插件到 draft | ReviewDecision | Plugin |
| POST | /api/v1/admin/plugins/{plugin_id}/publish | 管理员 | 发布 / 重新上架插件 | ReviewDecision | Plugin |
| POST | /api/v1/admin/plugins/{plugin_id}/trust-level/{trust_level} | 管理员 | 设置 trust badge | ReviewDecision | Plugin |
| POST | /api/v1/admin/plugins/{plugin_id}/block | 管理员 | 封禁插件 | ReviewDecision | Plugin |
| POST | /api/v1/admin/plugins/{plugin_id}/deprecate | 管理员 | 下架 / 弃用插件 | ReviewDecision | Plugin |
| DELETE | /api/v1/admin/plugins/{plugin_id} | 管理员 | 删除插件及关联数据 | 无 | 204 |
| POST | /api/v1/admin/plugins/{plugin_id}/versions/{version}/reject | 管理员 | 退回版本到 submitted | ReviewDecision | PluginVersion |
| POST | /api/v1/admin/plugins/{plugin_id}/versions/{version}/publish | 管理员 | 发布 / 恢复版本 | ReviewDecision | PluginVersion |
| POST | /api/v1/admin/plugins/{plugin_id}/versions/{version}/yank | 管理员 | 下架版本 | ReviewDecision | PluginVersion |
| POST | /api/v1/admin/plugins/{plugin_id}/versions/{version}/block | 管理员 | 封禁版本 | ReviewDecision | PluginVersion |

admin/system 返回字段包括：

- status
- environment
- database
- database_path
- github_oauth_configured
- github_webhook_configured
- review_required
- started_at
- uptime_seconds
- stats

### 8.15 GitHub Webhook

| 方法 | 路径 | 认证 | 说明 | Header / Body | 返回 |
| --- | --- | --- | --- | --- | --- |
| POST | /api/v1/github/webhooks | GitHub Webhook 签名 | 接收并审计 GitHub 事件 | X-GitHub-Event, X-GitHub-Delivery, X-Hub-Signature-256 | WebhookResponse |

说明：

- 如果配置了 PLUGIN_MARKET_GITHUB_WEBHOOK_SECRET，会强制校验 X-Hub-Signature-256
- 事件正文会被记录到数据库中，用于审计与后续处理

## 9. 认证与前端联动说明

### 9.1 前端当前实际使用的接口

前端客户端封装位于 frontend/src/api/index.ts，当前主要覆盖：

- 市场首页：/api/v1/market/home
- Inbox：/api/v1/inbox/messages、/api/v1/inbox/unread-count、标记已读接口
- 公告：/api/v1/announcements/active、dismiss
- 我的资料：/api/v1/me/profile、/api/v1/me/profile/background
- 我的 pins：/api/v1/me/pins
- 我的插件：metadata patch、icon upload
- 管理公告：/api/v1/admin/announcements/*
- 管理精选：/api/v1/admin/curation/*
- 作者搜索：/api/v1/authors/search

### 9.2 登录态读取

前端通过 GET /api/v1/me 判断当前是否已登录，并据此决定：

- 是否允许评论 / 点赞 / 评分
- 是否进入 /me 页面
- 是否允许进入 /admin 页面

### 9.3 管理后台路由保护

前端路由中 /admin 会先触发 loadViewer，再判断 is_admin，未通过则跳转到市场页。后端仍然是最终权限边界。

## 10. 建议联调顺序

### 10.1 公开浏览链路

1. GET /health
2. GET /api/v1/market/home
3. GET /api/v1/plugins
4. GET /api/v1/plugins/{plugin_id}
5. GET /api/v1/plugins/{plugin_id}/community

### 10.2 登录互动链路

1. GET /api/v1/auth/github/login
2. GET /api/v1/me
3. POST /api/v1/plugins/{plugin_id}/like
4. POST /api/v1/plugins/{plugin_id}/rating
5. POST /api/v1/plugins/{plugin_id}/comments
6. GET /api/v1/inbox/messages

### 10.3 作者发布链路

1. POST /api/v1/plugins
2. PUT /api/v1/plugins/{plugin_id}
3. POST /api/v1/plugins/{plugin_id}/versions
4. POST /api/v1/plugins/{plugin_id}/sync
5. GET /api/v1/plugins/{plugin_id}/status

### 10.4 管理治理链路

1. GET /api/v1/admin/dashboard
2. GET /api/v1/admin/plugins
3. POST /api/v1/admin/plugins/{plugin_id}/publish
4. POST /api/v1/admin/plugins/{plugin_id}/versions/{version}/publish
5. GET /api/v1/admin/reviews

## 11. 维护建议

- 新增或删除 API 时，优先同步更新本文件与 src/plugin_market_backend/app.py 中的路由定义。
- 新增请求体或响应模型时，优先同步更新 schemas.py 对应章节。
- 若前端实际依赖发生变化，可同时检查 frontend/src/api/index.ts 是否需要补充封装。
- 生产部署建议始终通过数据库引导脚本和 Alembic 管理 schema，不要再依赖历史 create_tables_on_startup 作为唯一迁移方式。