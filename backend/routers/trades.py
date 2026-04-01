import uuid
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from database import get_db
from models.paper_trade import PaperTrade
from models.trading_session import TradingSession
from pnl.aggregator import compute_period_summary

router = APIRouter()

@router.get("/{session_id}/trades")
async def get_trades(session_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(PaperTrade)
        .where(PaperTrade.session_id == session_id)
        .order_by(PaperTrade.timestamp_open.asc())
    )
    return result.scalars().all()

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
