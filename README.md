# Plugin Market Backend

Neo-MoFox 插件市场中心后端，用于保存插件元数据、版本索引、审核状态、兼容性信息和治理审计记录。服务不托管插件包，插件包仍通过 GitHub Release 分发。

## 能力范围

- 公共查询 API：搜索、详情、版本列表、推荐安装版本、分类和标签。
- 作者 API：插件注册、元数据更新、版本提交、版本同步、作者撤回版本。
- 管理 API：审核、拒绝、下架、弃用、封禁、审计记录和统计。
- 前端页面：插件市场、个人插件页、管理后台由同一个 FastAPI 服务托管。
- 数据库持久化：SQLAlchemy async，开发默认 SQLite，生产建议 PostgreSQL。
- GitHub OAuth：用户只能通过 GitHub 登录，MPDT 发布时可用 GitHub token 自动关联作者账户。
- GitHub webhook：支持 `X-Hub-Signature-256` 验签和事件持久化审计。
- 兼容性决策：按宿主版本、插件 API 版本、平台和预发布策略选择推荐版本。

## 本地启动

```bash
uv sync
uv run uvicorn plugin_market_backend.app:app --host 127.0.0.1 --port 8787
```

兼容旧入口仍可用：

```bash
uv run uvicorn plugin_market_mock.app:app --host 127.0.0.1 --port 8787
```

默认开发配置会使用 `./data/plugin_market.db`，启动时自动建表并写入 demo 数据。

前端入口：

```text
http://127.0.0.1:8787/       # 插件市场
http://127.0.0.1:8787/me     # 当前 GitHub 用户发布的插件
http://127.0.0.1:8787/admin  # 管理后台
```

## Docker 启动

```bash
docker compose up --build
```

生产部署前应复制 `.env.example` 并替换所有 token 和 webhook secret。

## 配置

环境变量前缀为 `PLUGIN_MARKET_`：

```text
PLUGIN_MARKET_DATABASE_URL=sqlite+aiosqlite:///./data/plugin_market.db
PLUGIN_MARKET_ADMIN_TOKEN=admin-token
PLUGIN_MARKET_AUTHOR_TOKEN=dev-token
PLUGIN_MARKET_GITHUB_WEBHOOK_SECRET=
PLUGIN_MARKET_GITHUB_OAUTH_CLIENT_ID=
PLUGIN_MARKET_GITHUB_OAUTH_CLIENT_SECRET=
PLUGIN_MARKET_GITHUB_OAUTH_REDIRECT_URI=http://127.0.0.1:8787/api/v1/auth/github/callback
PLUGIN_MARKET_SESSION_SECRET=change-me
PLUGIN_MARKET_ADMIN_GITHUB_LOGINS=["your-github-login"]
PLUGIN_MARKET_SEED_DEMO_DATA=true
PLUGIN_MARKET_CREATE_TABLES_ON_STARTUP=true
```

生产 PostgreSQL 示例：

```text
PLUGIN_MARKET_DATABASE_URL=postgresql+asyncpg://plugin_market:plugin_market@postgres:5432/plugin_market
```

## 认证

公共查询接口不需要认证。

浏览器用户只能通过 GitHub OAuth 登录。创建 GitHub OAuth App 时，callback URL 设置为：

```text
http://127.0.0.1:8787/api/v1/auth/github/callback
```

生产环境应改成你的公网域名，并把管理员 GitHub 登录名写入 `PLUGIN_MARKET_ADMIN_GITHUB_LOGINS`。

作者侧接口使用：

```text
Authorization: Bearer dev-token
```

也可以直接使用 GitHub OAuth/PAT token：

```text
Authorization: Bearer ghp_or_github_token
```

服务会调用 GitHub `/user` 获取真实身份，并把插件 owner 写为 `github:<login>`。`mpdt market publish` 在未显式传入市场 token 时会复用 GitHub token，因此发布记录会自动关联到 GitHub 账户。

管理侧接口使用：

```text
Authorization: Bearer admin-token
```

固定 token 仍保留给自动化和兼容测试使用；面向用户的网页登录与发布归属应使用 GitHub 身份。

## 前端功能

插件市场 `/` 包含：

- 排行榜：按版本活跃度和更新时间排序。
- 最新插件：最近更新的已发布插件。
- 随机推荐：从已发布插件中轮换展示。
- 查看全部：展开完整插件列表并支持搜索。

管理后台 `/admin` 包含：

- 插件列表：查看状态、owner、摘要并执行通过、退回、封禁。
- 审核记录：查看治理审计事件。
- 服务监控：数据库、OAuth、webhook、待审核数量、用户数和最新审核时间。

## 推荐版本接口

```text
GET /api/v1/plugins/{plugin_id}/recommended-version?host_version=1.2.0&plugin_api_version=1.0&platform=windows&include_prerelease=false
```

默认返回最新兼容稳定版，并排除 blocked、yanked、未发布和预发布版本。

## GitHub Webhook

```text
POST /api/v1/github/webhooks
X-GitHub-Event: release
X-GitHub-Delivery: <delivery-id>
X-Hub-Signature-256: sha256=<signature>
```

设置 `PLUGIN_MARKET_GITHUB_WEBHOOK_SECRET` 后会强制验签。当前 webhook 先做事件持久化和审计，为后续 GitHub Release 复核任务提供输入。

## 测试

```bash
uv run pytest
```
