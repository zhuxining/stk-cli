"""Custom exceptions for stk-cli."""


class StkError(Exception):
    """Base exception for all stk-cli errors."""

    def __init__(self, message: str):
        """Initialize exception with message."""
        self.message = message
        super().__init__(message)


class ConfigError(StkError):
    """Configuration missing or invalid."""


class SourceError(StkError):
    """Data source API call failed."""


class SymbolNotFoundError(StkError):
    """Symbol does not exist."""


class IndicatorError(StkError):
    """Technical indicator calculation failed."""


class DataNotFoundError(StkError):
    """Requested data not available."""
