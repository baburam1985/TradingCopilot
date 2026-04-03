import uuid
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from database import get_db
from models.trading_session import TradingSession
from models.paper_trade import PaperTrade
from models.price_history import PriceHistory
from strategies.reasoning import to_english

router = APIRouter()


@router.get("/{session_id}/chart-data")
async def get_chart_data(session_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """Return OHLC candles + signal markers for the session time window.

    Candle timestamps are Unix epoch seconds (as expected by lightweight-charts).
    """
    session = await db.get(TradingSession, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    # Fetch OHLCV bars scoped to session time window
    query = (
        select(PriceHistory)
        .where(PriceHistory.symbol == session.symbol)
        .where(PriceHistory.timestamp >= session.created_at)
        .order_by(PriceHistory.timestamp.asc())
    )
    if session.closed_at:
        query = query.where(PriceHistory.timestamp <= session.closed_at)

    price_result = await db.execute(query)
    price_rows = price_result.scalars().all()

    # Fetch trades for signal markers
    trades_result = await db.execute(
        select(PaperTrade)
        .where(PaperTrade.session_id == session_id)
        .order_by(PaperTrade.timestamp_open.asc())
    )
    trades = trades_result.scalars().all()

    candles = [
        {
            "time": int(row.timestamp.timestamp()),
            "open": float(row.open),
            "high": float(row.high),
            "low": float(row.low),
            "close": float(row.close),
            "volume": int(row.volume) if row.volume else 0,
        }
        for row in price_rows
    ]

    signals = []
    for t in trades:
        reasoning_text = to_english(t.reasoning) if t.reasoning else (t.signal_reason or "")
        pnl_pct = None
        if t.pnl is not None and t.price_at_signal and t.quantity:
            cost_basis = float(t.price_at_signal) * float(t.quantity)
            if cost_basis > 0:
                pnl_pct = round(float(t.pnl) / cost_basis * 100, 2)
        signals.append(
            {
                "time": int(t.timestamp_open.timestamp()),
                "action": t.action,
                "price": float(t.price_at_signal),
                "reasoning_text": reasoning_text,
                "pnl_pct": pnl_pct,
            }
        )

    return {
        "symbol": session.symbol,
        "strategy": session.strategy,
        "session_start": session.created_at.isoformat(),
        "session_end": session.closed_at.isoformat() if session.closed_at else None,
        "candles": candles,
        "signals": signals,
    }
