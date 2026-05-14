"""Runtime configuration for the plugin market backend."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Environment-driven service settings."""

    model_config = SettingsConfigDict(env_prefix="PLUGIN_MARKET_", env_file=".env", extra="ignore")

    env: str = "development"
    database_url: str = "sqlite+aiosqlite:///./data/plugin_market.db"
    cors_origins: list[str] = Field(default_factory=list)
    admin_token: str = "admin-token"
    author_token: str = "dev-token"
    github_webhook_secret: str = ""
    github_oauth_client_id: str = ""
    github_oauth_client_secret: str = ""
    github_oauth_redirect_uri: str = ""
    github_api_base_url: str = "https://api.github.com"
    github_login_base_url: str = "https://github.com/login/oauth"
    session_secret: str = "change-me-in-production"
    session_cookie_name: str = "plugin_market_session"
    admin_github_logins: list[str] = Field(default_factory=list)
    require_review: bool = False
    seed_demo_data: bool = True
    create_tables_on_startup: bool = True

    @property
    def database_path(self) -> Path | None:
        """Return the SQLite file path when the database URL points to a local SQLite database."""

        prefix = "sqlite+aiosqlite:///"
        if not self.database_url.startswith(prefix):
            return None
        raw_path = self.database_url[len(prefix) :]
        if raw_path == ":memory:":
            return None
        return Path(raw_path)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return cached runtime settings."""

    return Settings()


def reset_settings_cache() -> None:
    """Clear cached settings for tests."""

    get_settings.cache_clear()
