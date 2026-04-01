from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from datetime import datetime
from database import get_db
from models.price_history import PriceHistory
from strategies.moving_average_crossover import MovingAverageCrossover
from backtester.runner import BacktestRunner
from pnl.aggregator import compute_period_summary

router = APIRouter()

class BacktestRequest(BaseModel):
    symbol: str
    strategy: str
    strategy_params: dict
    starting_capital: float
    from_dt: datetime
    to_dt: datetime

@router.post("")
async def run_backtest(req: BacktestRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(PriceHistory)
        .where(
            PriceHistory.symbol == req.symbol.upper(),
            PriceHistory.timestamp >= req.from_dt,
            PriceHistory.timestamp <= req.to_dt,
        )
        .order_by(PriceHistory.timestamp.asc())
    )
    bars = result.scalars().all()

    strategy = MovingAverageCrossover(**req.strategy_params)
    runner = BacktestRunner(strategy=strategy, starting_capital=req.starting_capital)
    trades = runner.run(bars)

    summary = compute_period_summary(trades, req.starting_capital)
    return {"trades": trades, "summary": summary}
