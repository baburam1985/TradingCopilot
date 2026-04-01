import uuid
import pytest
import yfinance as yf
from datetime import datetime, timezone, timedelta
from sqlalchemy import text

pytestmark = pytest.mark.integration


async def _seed_price_history(db_session, symbol: str, days: int = 90):
    """Fetch real historical daily bars from Yahoo Finance and insert into price_history."""
    end = datetime.now(timezone.utc)
    start = end - timedelta(days=days)

    df = await __import__("asyncio").to_thread(
        lambda: yf.download(symbol, start=start.date(), end=end.date(), progress=False)
    )
    if df.empty:
        pytest.skip(f"Yahoo Finance returned no historical data for {symbol}")

    # Flatten MultiIndex columns if present (yfinance >= 0.2.38 returns MultiIndex)
    if hasattr(df.columns, "levels"):
        df.columns = df.columns.get_level_values(0)

    rows = []
    for ts, row in df.iterrows():
        rows.append({
            "id": str(uuid.uuid4()),
            "symbol": symbol,
            "timestamp": ts.to_pydatetime().replace(tzinfo=timezone.utc),
            "open": float(row["Open"]),
            "high": float(row["High"]),
            "low": float(row["Low"]),
            "close": float(row["Close"]),
            "volume": int(row["Volume"]),
            "yahoo_close": float(row["Close"]),
            "alphavantage_close": None,
            "finnhub_close": None,
            "outlier_flags": "{}",
            "sources_available": "{yahoo}",
        })

    if not rows:
        pytest.skip("No rows to insert after parsing Yahoo Finance data")

    await db_session.execute(
        text("""
            INSERT INTO price_history
              (id, symbol, timestamp, open, high, low, close, volume,
               yahoo_close, alphavantage_close, finnhub_close, outlier_flags, sources_available)
            VALUES
              (:id, :symbol, :timestamp, :open, :high, :low, :close, :volume,
               :yahoo_close, :alphavantage_close, :finnhub_close, :outlier_flags::jsonb, :sources_available::text[])
        """),
        rows,
    )
    await db_session.commit()
    return rows


async def test_backtest_returns_valid_structure(client, db_session, clean_db):
    symbol = "AAPL"
    rows = await _seed_price_history(db_session, symbol, days=90)
    timestamps = [r["timestamp"] for r in rows]
    from_dt = min(timestamps).isoformat()
    to_dt = max(timestamps).isoformat()

    resp = await client.post("/backtest", json={
        "symbol": symbol,
        "strategy": "moving_average_crossover",
        "strategy_params": {"short_window": 10, "long_window": 20},
        "starting_capital": 1000.0,
        "from_dt": from_dt,
        "to_dt": to_dt,
    })
    assert resp.status_code == 200
    data = resp.json()
    assert "trades" in data
    assert "summary" in data
    assert isinstance(data["trades"], list)


async def test_backtest_summary_has_required_keys(client, db_session, clean_db):
    symbol = "AAPL"
    rows = await _seed_price_history(db_session, symbol, days=90)
    timestamps = [r["timestamp"] for r in rows]

    resp = await client.post("/backtest", json={
        "symbol": symbol,
        "strategy": "moving_average_crossover",
        "strategy_params": {"short_window": 10, "long_window": 20},
        "starting_capital": 1000.0,
        "from_dt": min(timestamps).isoformat(),
        "to_dt": max(timestamps).isoformat(),
    })
    summary = resp.json()["summary"]
    for key in ("total_pnl", "num_trades", "num_wins", "num_losses", "win_rate", "starting_capital", "ending_capital"):
        assert key in summary, f"Missing key in summary: {key}"


async def test_backtest_summary_values_are_valid_types(client, db_session, clean_db):
    symbol = "AAPL"
    rows = await _seed_price_history(db_session, symbol, days=90)
    timestamps = [r["timestamp"] for r in rows]

    resp = await client.post("/backtest", json={
        "symbol": symbol,
        "strategy": "moving_average_crossover",
        "strategy_params": {"short_window": 10, "long_window": 20},
        "starting_capital": 1000.0,
        "from_dt": min(timestamps).isoformat(),
        "to_dt": max(timestamps).isoformat(),
    })
    summary = resp.json()["summary"]
    assert summary["num_trades"] >= 0
    assert 0.0 <= summary["win_rate"] <= 1.0
    assert summary["ending_capital"] > 0
    assert isinstance(summary["total_pnl"], (int, float))


async def test_backtest_trades_have_required_fields(client, db_session, clean_db):
    symbol = "AAPL"
    rows = await _seed_price_history(db_session, symbol, days=90)
    timestamps = [r["timestamp"] for r in rows]

    resp = await client.post("/backtest", json={
        "symbol": symbol,
        "strategy": "moving_average_crossover",
        "strategy_params": {"short_window": 10, "long_window": 20},
        "starting_capital": 1000.0,
        "from_dt": min(timestamps).isoformat(),
        "to_dt": max(timestamps).isoformat(),
    })
    trades = resp.json()["trades"]
    for trade in trades:
        assert "action" in trade
        assert "price_at_signal" in trade
        assert "status" in trade
        assert trade["action"] in ("buy", "sell")
        assert float(trade["price_at_signal"]) > 0
