import os
import unittest.mock


def test_models_importable():
    env_vars = {
        "POSTGRES_HOST": "localhost",
        "POSTGRES_DB": "tradingcopilot",
        "POSTGRES_USER": "postgres",
        "POSTGRES_PASSWORD": "postgres",
    }
    with unittest.mock.patch.dict(os.environ, env_vars):
        from backend.models.price_history import PriceHistory
        from backend.models.trading_session import TradingSession
        from backend.models.paper_trade import PaperTrade
        from backend.models.aggregated_pnl import AggregatedPnl
        assert PriceHistory.__tablename__ == "price_history"
        assert TradingSession.__tablename__ == "sessions"
        assert PaperTrade.__tablename__ == "paper_trades"
        assert AggregatedPnl.__tablename__ == "aggregated_pnl"
