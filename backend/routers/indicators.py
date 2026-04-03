import math
import uuid
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from database import get_db
from models.trading_session import TradingSession
from models.price_history import PriceHistory
from strategies.rsi import _compute_rsi
from strategies.bollinger_bands import _compute_bollinger_bands
from strategies.macd import _compute_macd

router = APIRouter()

ALL_INDICATORS = {"sma", "ema", "bollinger", "rsi", "macd"}

# Default parameters
SMA_PERIOD = 20
EMA_PERIOD = 20
BB_PERIOD = 20
BB_MULTIPLIER = 2.0
RSI_PERIOD = 14
MACD_FAST = 12
MACD_SLOW = 26
MACD_SIGNAL = 9


def _compute_sma_series(closes: list[float], period: int) -> list[Optional[float]]:
    result = []
    for i in range(len(closes)):
        if i + 1 < period:
            result.append(None)
        else:
            result.append(sum(closes[i - period + 1 : i + 1]) / period)
    return result


def _compute_ema_series(closes: list[float], period: int) -> list[Optional[float]]:
    result = []
    k = 2.0 / (period + 1)
    ema = None
    for i, price in enumerate(closes):
        if i == 0:
            ema = price
        else:
            ema = price * k + ema * (1 - k)
        # Only emit values once we have enough data to be meaningful
        if i + 1 < period:
            result.append(None)
        else:
            result.append(ema)
    return result


def _compute_bollinger_series(
    closes: list[float], period: int, multiplier: float
) -> list[Optional[dict]]:
    result = []
    for i in range(len(closes)):
        if i + 1 < period:
            result.append(None)
        else:
            window = closes[i - period + 1 : i + 1]
            middle = sum(window) / period
            variance = sum((p - middle) ** 2 for p in window) / period
            std = math.sqrt(variance)
            result.append({
                "upper": middle + multiplier * std,
                "middle": middle,
                "lower": middle - multiplier * std,
            })
    return result


def _compute_rsi_series(closes: list[float], period: int) -> list[Optional[float]]:
    result = []
    # Need at least period+1 values to compute RSI
    for i in range(len(closes)):
        if i + 1 < period + 1:
            result.append(None)
        else:
            result.append(_compute_rsi(closes[: i + 1], period))
    return result


def _compute_macd_series(
    closes: list[float], fast: int, slow: int, signal: int
) -> list[Optional[dict]]:
    result = []
    min_bars = slow + signal
    for i in range(len(closes)):
        if i + 1 < min_bars:
            result.append(None)
        else:
            macd_line, signal_line = _compute_macd(closes[: i + 1], fast, slow, signal)
            result.append({
                "macd": macd_line,
                "signal": signal_line,
                "histogram": macd_line - signal_line,
            })
    return result


@router.get("/{session_id}/indicators")
async def get_indicators(
    session_id: uuid.UUID,
    indicators: Optional[str] = Query(default=None, description="Comma-separated list of indicators (sma,ema,bollinger,rsi,macd). Defaults to all."),
    db: AsyncSession = Depends(get_db),
):
    session = await db.get(TradingSession, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    # Parse requested indicators
    if indicators:
        requested = {ind.strip().lower() for ind in indicators.split(",") if ind.strip()}
        unknown = requested - ALL_INDICATORS
        if unknown:
            raise HTTPException(
                status_code=400,
                detail=f"Unknown indicators: {', '.join(sorted(unknown))}. Valid: {', '.join(sorted(ALL_INDICATORS))}",
            )
    else:
        requested = ALL_INDICATORS

    # Fetch price history for this session's symbol, ordered by time
    result = await db.execute(
        select(PriceHistory)
        .where(PriceHistory.symbol == session.symbol)
        .order_by(PriceHistory.timestamp.asc())
    )
    rows = result.scalars().all()

    if not rows:
        return {ind: [] for ind in requested}

    timestamps = [row.timestamp.isoformat() for row in rows]
    closes = [float(row.close) for row in rows]

    response: dict = {}

    if "sma" in requested:
        sma_vals = _compute_sma_series(closes, SMA_PERIOD)
        response["sma"] = [
            {"time": t, "value": v}
            for t, v in zip(timestamps, sma_vals)
            if v is not None
        ]

    if "ema" in requested:
        ema_vals = _compute_ema_series(closes, EMA_PERIOD)
        response["ema"] = [
            {"time": t, "value": v}
            for t, v in zip(timestamps, ema_vals)
            if v is not None
        ]

    if "bollinger" in requested:
        bb_vals = _compute_bollinger_series(closes, BB_PERIOD, BB_MULTIPLIER)
        response["bollinger"] = [
            {"time": t, "upper": b["upper"], "middle": b["middle"], "lower": b["lower"]}
            for t, b in zip(timestamps, bb_vals)
            if b is not None
        ]

    if "rsi" in requested:
        rsi_vals = _compute_rsi_series(closes, RSI_PERIOD)
        response["rsi"] = [
            {"time": t, "value": v}
            for t, v in zip(timestamps, rsi_vals)
            if v is not None
        ]

    if "macd" in requested:
        macd_vals = _compute_macd_series(closes, MACD_FAST, MACD_SLOW, MACD_SIGNAL)
        response["macd"] = [
            {"time": t, "macd": m["macd"], "signal": m["signal"], "histogram": m["histogram"]}
            for t, m in zip(timestamps, macd_vals)
            if m is not None
        ]

    return response
