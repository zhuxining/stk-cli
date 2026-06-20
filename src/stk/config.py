"""Application settings via pydantic-settings."""

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from .env file."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Longport credentials
    longport_app_key: str = ""
    longport_app_secret: str = ""
    longport_access_token: str = ""

    # Local storage
    data_dir: Path = Path.home() / ".stk"

    # Cache
    cache_enabled: bool = True
    cache_dir: Path = Path.home() / ".stk" / "cache"

    # THS (同花顺) sync
    ths_username: str = ""
    """同花顺账号（手机号）"""
    ths_password: str = ""
    """同花顺密码"""

    # Logging
    log_level: str = "WARNING"


settings = Settings()
