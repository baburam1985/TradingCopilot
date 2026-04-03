import os
import unittest.mock


def test_models_importable():
    # conftest.py already sets these env vars; the patch is kept for explicitness.
    # Imports use the short (runtime) path so they resolve to the same sys.modules
    # entries as other backend modules, preventing SQLAlchemy metadata conflicts.
    env_vars = {
        "POSTGRES_HOST": "localhost",
        "POSTGRES_DB": "tradingcopilot",
        "POSTGRES_USER": "postgres",
        "POSTGRES_PASSWORD": "postgres",
    }
    with unittest.mock.patch.dict(os.environ, env_vars):
        from models.price_history import PriceHistory
        from models.trading_session import TradingSession
        from models.paper_trade import PaperTrade
        from models.aggregated_pnl import AggregatedPnl
        assert PriceHistory.__tablename__ == "price_history"
        assert TradingSession.__tablename__ == "sessions"
        assert PaperTrade.__tablename__ == "paper_trades"
        assert AggregatedPnl.__tablename__ == "aggregated_pnl"

