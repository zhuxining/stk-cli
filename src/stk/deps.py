"""Lazy singletons for external dependencies."""

from functools import lru_cache

from stk.config import settings
from stk.errors import ConfigError


@lru_cache(maxsize=1)
def get_longport_ctx():
    """Lazily initialize and return longport QuoteContext."""
    if not all([
        settings.longport_app_key,
        settings.longport_app_secret,
        settings.longport_access_token,
    ]):
        raise ConfigError(
            "Longport credentials not configured. "
            "Set LONGPORT_APP_KEY, LONGPORT_APP_SECRET, LONGPORT_ACCESS_TOKEN in .env"
        )

    from longport.openapi import Config, Language, QuoteContext

    config = Config(
        app_key=settings.longport_app_key,
        app_secret=settings.longport_app_secret,
        access_token=settings.longport_access_token,
        language=Language.ZH_CN,
        enable_print_quote_packages=False,
    )
    return QuoteContext(config)
