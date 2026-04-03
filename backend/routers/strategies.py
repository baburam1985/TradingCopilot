from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from database import get_db
from models.aggregated_pnl import AggregatedPnl
from models.trading_session import TradingSession
from strategies.registry import STRATEGY_REGISTRY

router = APIRouter()


@router.get("")
async def list_strategies(db: AsyncSession = Depends(get_db)):
    # Compute avg win_rate per strategy from paper sessions
    result = await db.execute(
        select(TradingSession.strategy, func.avg(AggregatedPnl.win_rate).label("avg_win_rate"))
        .join(AggregatedPnl, AggregatedPnl.session_id == TradingSession.id)
        .where(TradingSession.mode == "paper")
        .group_by(TradingSession.strategy)
    )
    win_rates = {row.strategy: float(row.avg_win_rate) for row in result}

    return [
        {
            "name": cls.name,
            "description": cls.description,
            "parameters": cls.parameters,
            "avg_win_rate": win_rates.get(cls.name),
        }
        for cls in STRATEGY_REGISTRY.values()
    ]
