"""插件市场后端的运行时配置。"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """由环境变量驱动的服务配置。"""

    model_config = SettingsConfigDict(env_prefix="PLUGIN_MARKET_", env_file=".env", extra="ignore")

    env: str = "development"
    database_url: str = "sqlite+aiosqlite:///./data/plugin_market.db"
    storage_dir: str = "./data"
    cors_origins: list[str] = Field(default_factory=list)
    admin_token: str = "admin-token"
    author_token: str = "dev-token"
    github_webhook_secret: str = ""
    github_oauth_client_id: str = ""
    github_oauth_client_secret: str = ""
    github_oauth_redirect_uri: str = ""
    github_api_base_url: str = "https://api.github.com"
    github_login_base_url: str = "https://github.com/login/oauth"
    github_trust_env: bool = True
    session_secret: str = "change-me-in-production"
    session_cookie_name: str = "plugin_market_session"
    admin_github_logins: list[str] = Field(default_factory=list)
    require_review: bool = False
    seed_demo_data: bool = True
    create_tables_on_startup: bool = True

    @property
    def database_path(self) -> Path | None:
        """当数据库 URL 指向本地 SQLite 数据库时返回文件路径。"""
        prefix = "sqlite+aiosqlite:///"
        if not self.database_url.startswith(prefix):
            return None
        raw_path = self.database_url[len(prefix) :]
        if raw_path == ":memory:":
            return None
        return Path(raw_path)

    @property
    def storage_path(self) -> Path:
        """返回上传包与媒体资源的绝对存储根目录。"""
        return Path(self.storage_dir).expanduser().resolve()


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """返回缓存的运行时配置。"""
    return Settings()


def reset_settings_cache() -> None:
    """清除配置缓存，供测试使用。"""
    get_settings.cache_clear()
