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

当前仓库内置的 `docker-compose.yml` 适合以下生产拓扑：

- `postgres` 仅在 Docker 网络内暴露，不直接开放到公网。
- `api` 仅绑定宿主机 `127.0.0.1:8787`，用于给 Nginx、Caddy 等反向代理转发。
- 反向代理再把公网域名，例如 `https://market.mofox-sama.com`，转发到 `http://127.0.0.1:8787`。

建议部署步骤：

```bash
cp .env.example .env
# 编辑 .env，替换数据库、OAuth、session secret、token 等配置
docker compose up -d --build
docker compose logs -f api
```

如果你要通过域名访问服务，至少需要：

- 将 `market.mofox-sama.com` 的 DNS A 记录指向部署服务器公网 IP。
- 将 `PLUGIN_MARKET_GITHUB_OAUTH_REDIRECT_URI` 改为 `https://market.mofox-sama.com/api/v1/auth/github/callback`。
- 在反向代理中把域名转发到 `127.0.0.1:8787`。

Nginx 反代示例：

```nginx
server {
	listen 80;
	server_name market.mofox-sama.com;
	return 301 https://$host$request_uri;
}

server {
	listen 443 ssl http2;
	server_name market.mofox-sama.com;

	ssl_certificate /etc/letsencrypt/live/market.mofox-sama.com/fullchain.pem;
	ssl_certificate_key /etc/letsencrypt/live/market.mofox-sama.com/privkey.pem;

	location / {
		proxy_pass http://127.0.0.1:8787;
		proxy_set_header Host $host;
		proxy_set_header X-Real-IP $remote_addr;
		proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
		proxy_set_header X-Forwarded-Proto https;
	}
}
```

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

## 前端

前端使用 Vue 3 + TypeScript + Vite 构建，源码位于 `frontend/` 目录。

### 技术栈

- Vue 3 (Composition API + `<script setup lang="ts">`)
- Vue Router 4 (History mode)
- Pinia (状态管理)
- TypeScript 5
- Vite 6

### 目录结构

```text
frontend/
├── src/
│   ├── api/          # fetch 封装
│   ├── assets/       # 全局 CSS
│   ├── components/   # 通用组件
│   ├── router/       # 路由定义
│   ├── stores/       # Pinia stores (auth, taxonomy, toast)
│   ├── types/        # TypeScript 接口定义
│   ├── utils/        # 工具函数
│   └── views/        # 页面视图
├── public/           # 静态资源
├── index.html
├── tsconfig.json
├── vite.config.js
└── package.json
```

### 前端开发

```bash
cd frontend
npm install
npm run dev          # 启动开发服务器，API 代理到 http://127.0.0.1:8000
npm run build        # 构建产物输出到 src/plugin_market_backend/static/
npm run typecheck    # TypeScript 类型检查
```

开发模式下 Vite 会将 `/api` 请求代理到后端，无需额外配置。

### 构建部署

`npm run build` 会将产物直接输出到后端的 `src/plugin_market_backend/static/` 目录，FastAPI 直接 serve 该目录，无需额外部署步骤。

### 前端功能

插件市场 `/` 包含：

- 排行榜：按版本活跃度和更新时间排序。
- 最新插件：最近更新的已发布插件。
- 分类/标签筛选：侧边栏快速导航。
- 搜索：支持关键字、分类、标签和信任等级组合筛选。
- 网格/列表视图切换。

个人工作台 `/me` 包含：

- 插件列表与版本管理。
- 一键下架版本。
- 删除插件。
- 查看治理记录。

管理后台 `/admin` 包含：

- 插件治理：上架、退回、封禁、下架、删除。
- 版本治理：恢复、退回、下架、封禁。
- 社区标识切换：官方、认证、社区。
- 7 天活动图表与状态分布。
- 热门插件观察与审核流。

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

## API 路由清单

以下为当前后端对外暴露的主要接口，路由来源于 [src/plugin_market_backend/app.py](src/plugin_market_backend/app.py)。

### 健康检查与站点信息

```text
GET    /health
GET    /ready
GET    /api/v1/brand
```

### 公共插件市场接口

```text
GET    /api/v1/plugins
GET    /api/v1/market/featured
GET    /api/v1/market/trending-authors
GET    /api/v1/market/stats
GET    /api/v1/plugins/{plugin_id}
GET    /api/v1/plugins/{plugin_id}/community
GET    /api/v1/plugins/{plugin_id}/rating
POST   /api/v1/plugins/{plugin_id}/rating
DELETE /api/v1/plugins/{plugin_id}/rating
POST   /api/v1/plugins/{plugin_id}/like
GET    /api/v1/plugins/{plugin_id}/comments
POST   /api/v1/plugins/{plugin_id}/comments
DELETE /api/v1/plugins/{plugin_id}/comments/{comment_id}
POST   /api/v1/plugins/{plugin_id}/install-record
GET    /api/v1/plugins/{plugin_id}/versions
GET    /api/v1/plugins/{plugin_id}/versions/{version}
GET    /api/v1/plugins/{plugin_id}/recommended-version
GET    /api/v1/plugins/{plugin_id}/install
GET    /api/v1/categories
GET    /api/v1/tags
```

### GitHub 登录与当前用户接口

```text
GET    /api/v1/auth/github/login
GET    /api/v1/auth/github/callback
POST   /api/v1/auth/logout
GET    /api/v1/me
GET    /api/v1/me/plugins
GET    /api/v1/me/plugins/{plugin_id}
POST   /api/v1/me/plugins/{plugin_id}/versions/{version}/yank
DELETE /api/v1/me/plugins/{plugin_id}
```

### 作者发布接口

```text
POST   /api/v1/plugins
PUT    /api/v1/plugins/{plugin_id}
POST   /api/v1/plugins/{plugin_id}/versions
POST   /api/v1/plugins/{plugin_id}/sync
POST   /api/v1/plugins/{plugin_id}/versions/{version}/yank
GET    /api/v1/plugins/{plugin_id}/status
```

### 管理后台接口

```text
GET    /api/v1/admin/reviews
GET    /api/v1/admin/plugins
GET    /api/v1/admin/plugins/{plugin_id}
GET    /api/v1/admin/dashboard
GET    /api/v1/admin/system
GET    /api/v1/admin/stats
POST   /api/v1/admin/plugins/{plugin_id}/reject
POST   /api/v1/admin/plugins/{plugin_id}/publish
POST   /api/v1/admin/plugins/{plugin_id}/trust-level/{trust_level}
POST   /api/v1/admin/plugins/{plugin_id}/block
POST   /api/v1/admin/plugins/{plugin_id}/deprecate
DELETE /api/v1/admin/plugins/{plugin_id}
POST   /api/v1/admin/plugins/{plugin_id}/versions/{version}/reject
POST   /api/v1/admin/plugins/{plugin_id}/versions/{version}/publish
POST   /api/v1/admin/plugins/{plugin_id}/versions/{version}/yank
POST   /api/v1/admin/plugins/{plugin_id}/versions/{version}/block
```

### GitHub Webhook 接口

```text
POST   /api/v1/github/webhooks
```

### 前端页面路由

这些路由由同一个 FastAPI 服务直接托管静态前端：

```text
GET /               # 插件市场首页
GET /admin          # 管理后台
GET /me             # 当前用户插件管理页
GET /plugin/{plugin_id}
GET /author/{author_id}
```

## 测试

```bash
uv run pytest
```
