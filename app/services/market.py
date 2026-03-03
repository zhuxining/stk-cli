"""Market service — indices, temperature, breadth."""

from app.models.market import IndexQuote, MarketBreadth, MarketTemperature


def get_indices() -> list[IndexQuote]:
    """Get major index quotes."""
    # TODO: implement akshare/longport index data
    raise NotImplementedError("Index service not yet implemented")


def get_temperature() -> MarketTemperature:
    """Calculate market temperature score (0-100)."""
    # TODO: implement weighted scoring from multiple akshare indicators
    raise NotImplementedError("Market temperature service not yet implemented")


def get_breadth() -> MarketBreadth:
    """Get market breadth (advance/decline stats)."""
    # TODO: implement akshare breadth data
    raise NotImplementedError("Market breadth service not yet implemented")
