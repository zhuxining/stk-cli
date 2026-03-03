"""Application settings via pydantic-settings."""

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Longport credentials
    longport_app_key: str = ""
    longport_app_secret: str = ""
    longport_access_token: str = ""

    # Local storage
    data_dir: Path = Path.home() / ".stk"

    # Output
    default_format: str = "json"

    # Logging
    log_level: str = "WARNING"


settings = Settings()
