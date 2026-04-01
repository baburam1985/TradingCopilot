import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from database import get_db
from models.trading_session import TradingSession
from scheduler.scraper_job import register_symbol, unregister_symbol

router = APIRouter()

class CreateSessionRequest(BaseModel):
    symbol: str
    strategy: str
    strategy_params: dict
    starting_capital: float
    mode: str  # "paper" or "live"

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
