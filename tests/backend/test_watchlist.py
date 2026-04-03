import uuid
import pytest
from datetime import datetime, timezone
from models.watchlist_item import WatchlistItem


def test_watchlist_item_attributes():
    item = WatchlistItem(
        symbol="AAPL",
        strategy="rsi",
        strategy_params={"period": 14, "oversold": 30, "overbought": 70},
        alert_threshold=180.0,
        notify_email=True,
        email_address="trader@example.com",
        created_at=datetime.now(timezone.utc),
    )
    assert item.symbol == "AAPL"
    assert item.strategy == "rsi"
    assert item.strategy_params["period"] == 14
    assert item.alert_threshold == 180.0
    assert item.notify_email is True
    assert item.email_address == "trader@example.com"
    assert item.last_signal is None
    assert item.last_price is None
    assert item.last_evaluated_at is None
