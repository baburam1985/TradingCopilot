"""
Analysis router — GET /analysis/regime?symbol=AAPL
"""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from models.price_history import PriceHistory
from analysis.regime import Bar, RegimeDetector, STRATEGIES

logger = logging.getLogger(__name__)
router = APIRouter()

_detector = RegimeDetector()

# Minimum bars before we attempt yfinance fallback
_FALLBACK_THRESHOLD = 30
# How many bars to request from DB
_DB_LIMIT = 60


@router.get("/regime")
async def get_regime(
    symbol: str = Query(..., min_length=1, max_length=20),
    db: AsyncSession = Depends(get_db),
):
    """
    Return the current market regime and per-strategy fitness scores.

    Data source: last 60 bars from price_history.
    Fallback: yfinance if DB has fewer than 30 bars.
    """
    symbol = symbol.upper().strip()

    rows = await _fetch_bars_from_db(symbol, db)

    if len(rows) < _FALLBACK_THRESHOLD:
        rows = await _fetch_bars_from_yfinance(symbol, existing=rows)

    bars = [Bar(high=float(r.high), low=float(r.low), close=float(r.close)) for r in rows]

    try:
        result = _detector.detect(bars)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    return {
        "symbol": symbol,
        "regime": result.regime,
        "adx": result.adx,
        "atr_pct": result.atr_pct,
        "confidence": result.confidence,
        "fitness_scores": result.fitness_scores,
    }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _fetch_bars_from_db(symbol: str, db: AsyncSession) -> list:
    stmt = (
        select(PriceHistory)
        .where(PriceHistory.symbol == symbol)
        .order_by(desc(PriceHistory.timestamp))
        .limit(_DB_LIMIT)
    )
    result = await db.execute(stmt)
    rows = result.scalars().all()
    # Return in chronological order (oldest first)
    return list(reversed(rows))


async def _fetch_bars_from_yfinance(symbol: str, existing: list) -> list:
    """Attempt to pull 60 bars from yfinance; return existing on failure."""
    try:
        import yfinance as yf  # optional dependency

        ticker = yf.Ticker(symbol)
        hist = ticker.history(period="90d", interval="1d", auto_adjust=True)
        if hist.empty:
            return existing

        # Build lightweight objects compatible with _fetch_bars_from_db
        class _Row:
            __slots__ = ("high", "low", "close")

            def __init__(self, high, low, close):
                self.high = high
                self.low = low
                self.close = close

        rows = [
            _Row(high=row["High"], low=row["Low"], close=row["Close"])
            for _, row in hist.tail(_DB_LIMIT).iterrows()
        ]
        return rows
    except Exception as exc:  # noqa: BLE001
        logger.warning("yfinance fallback failed for %s: %s", symbol, exc)
        raise HTTPException(
            status_code=503,
            detail=(
                f"Insufficient price history for {symbol} in the database "
                "and the yfinance fallback failed. Retry in a few seconds."
            ),
        ) from exc
