import uuid
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from database import get_db
from models.paper_trade import PaperTrade
from models.trading_session import TradingSession
from pnl.aggregator import compute_period_summary, compute_equity_curve
from strategies.reasoning import to_english

router = APIRouter()

@router.get("/{session_id}/trades")
async def get_trades(session_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(PaperTrade)
        .where(PaperTrade.session_id == session_id)
        .order_by(PaperTrade.timestamp_open.asc())
    )
    trades = result.scalars().all()
    _TRADE_FIELDS = (
        "id", "session_id", "action", "signal_reason",
        "price_at_signal", "quantity", "timestamp_open",
        "timestamp_close", "price_at_close", "pnl", "status",
        "alpaca_order_id", "reasoning",
    )
    return [
        {
            **{f: getattr(t, f) for f in _TRADE_FIELDS},
            "reasoning_text": to_english(t.reasoning) if t.reasoning else t.signal_reason,
        }
        for t in trades
    ]

@router.get("/{session_id}/equity-curve")
async def get_equity_curve(session_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    session = await db.get(TradingSession, session_id)
    result = await db.execute(
        select(PaperTrade)
        .where(PaperTrade.session_id == session_id)
        .where(PaperTrade.status == "closed")
        .order_by(PaperTrade.timestamp_close.asc())
    )
    trades = [
        {
            "pnl": float(t.pnl) if t.pnl is not None else None,
            "status": t.status,
            "timestamp_close": t.timestamp_close.isoformat() if t.timestamp_close else None,
        }
        for t in result.scalars().all()
    ]
    return compute_equity_curve(
        trades,
        float(session.starting_capital),
        session.created_at.isoformat(),
    )


@router.get("/{session_id}/pnl")
async def get_pnl(session_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    session = await db.get(TradingSession, session_id)
    trades_result = await db.execute(
        select(PaperTrade).where(PaperTrade.session_id == session_id)
    )
    trades = [
        {"pnl": float(t.pnl) if t.pnl else None, "status": t.status}
        for t in trades_result.scalars().all()
    ]
    return {
        "all_time": compute_period_summary(trades, float(session.starting_capital)),
    }
