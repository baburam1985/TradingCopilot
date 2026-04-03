import uuid
from collections import defaultdict
from datetime import datetime, timezone
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from database import get_db
from models.trading_session import TradingSession
from models.paper_trade import PaperTrade
from models.trade_note import TradeNote
from scheduler.scraper_job import register_symbol, unregister_symbol
from journal import build_journal_csv

router = APIRouter()

class CreateSessionRequest(BaseModel):
    symbol: str
    strategy: str
    strategy_params: dict
    starting_capital: float
    mode: str  # "paper" or "live"
    broker: Optional[str] = None  # "alpaca" | "ibkr" | None (uses paper executor for "paper" mode)
    # Risk management (all optional)
    stop_loss_pct: Optional[float] = None
    take_profit_pct: Optional[float] = None
    max_position_pct: Optional[float] = None
    daily_max_loss_pct: Optional[float] = None
    # Notification preferences
    notify_email: bool = False
    email_address: Optional[str] = None

class UpdateSessionRequest(BaseModel):
    notify_email: Optional[bool] = None
    email_address: Optional[str] = None

@router.post("")
async def create_session(req: CreateSessionRequest, db: AsyncSession = Depends(get_db)):
    session = TradingSession(
        symbol=req.symbol.upper(),
        strategy=req.strategy,
        strategy_params=req.strategy_params,
        starting_capital=req.starting_capital,
        mode=req.mode,
        status="active",
        created_at=datetime.now(timezone.utc),
        stop_loss_pct=req.stop_loss_pct,
        take_profit_pct=req.take_profit_pct,
        max_position_pct=req.max_position_pct,
        daily_max_loss_pct=req.daily_max_loss_pct,
        notify_email=req.notify_email,
        email_address=req.email_address,
    )
    db.add(session)
    await db.commit()
    await db.refresh(session)
    register_symbol(session.symbol)
    return session

@router.get("")
async def list_sessions(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(TradingSession).order_by(TradingSession.created_at.desc()))
    return result.scalars().all()

@router.get("/{session_id}")
async def get_session(session_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    session = await db.get(TradingSession, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return session

@router.patch("/{session_id}")
async def update_session(session_id: uuid.UUID, req: UpdateSessionRequest, db: AsyncSession = Depends(get_db)):
    session = await db.get(TradingSession, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    if req.notify_email is not None:
        session.notify_email = req.notify_email
    if req.email_address is not None:
        session.email_address = req.email_address
    await db.commit()
    await db.refresh(session)
    return session

@router.patch("/{session_id}/stop")
async def stop_session(session_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    session = await db.get(TradingSession, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    session.status = "closed"
    session.closed_at = datetime.now(timezone.utc)
    await db.commit()
    unregister_symbol(session.symbol)
    return session


@router.get("/{session_id}/journal")
async def export_journal(
    session_id: uuid.UUID,
    format: str = Query(default="csv"),
    db: AsyncSession = Depends(get_db),
):
    if format != "csv":
        raise HTTPException(status_code=400, detail="Only csv format supported")

    session = await db.get(TradingSession, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    trades_result = await db.execute(
        select(PaperTrade)
        .where(PaperTrade.session_id == session_id)
        .order_by(PaperTrade.timestamp_open.asc())
    )
    trades = trades_result.scalars().all()

    # Fetch all notes for these trades in one query
    trade_ids = [t.id for t in trades]
    notes_by_trade: dict = defaultdict(list)
    if trade_ids:
        notes_result = await db.execute(
            select(TradeNote)
            .where(TradeNote.trade_id.in_(trade_ids))
            .order_by(TradeNote.created_at.asc())
        )
        for note in notes_result.scalars().all():
            notes_by_trade[note.trade_id].append(note)

    csv_content = build_journal_csv(trades, notes_by_trade)
    return StreamingResponse(
        iter([csv_content]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=journal_{session_id}.csv"},
    )
