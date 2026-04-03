"""Session-scoped strategy parameter optimizer.

POST /sessions/{session_id}/optimize — runs a grid search over strategy
parameter combinations using the session's symbol, date range, and
starting capital, then returns a heatmap-compatible response.
"""
import itertools
import uuid
from datetime import datetime, timezone
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backtester.runner import BacktestRunner
from database import get_db
from models.price_history import PriceHistory
from models.trading_session import TradingSession
from pnl.aggregator import compute_period_summary
from strategies.registry import STRATEGY_REGISTRY

router = APIRouter()

_MAX_COMBINATIONS = 100


class OptimizeRequest(BaseModel):
    param_grid: dict[str, list]
    metric: Literal["sharpe", "total_return", "win_rate"] = "sharpe"


class OptimizeResultItem(BaseModel):
    params: dict
    sharpe: Optional[float]
    total_return: float
    win_rate: float


class OptimizeResponse(BaseModel):
    results: list[OptimizeResultItem]
    best_params: dict
    iterations_run: int


@router.post("/{session_id}/optimize", response_model=OptimizeResponse)
async def optimize_session(
    session_id: uuid.UUID,
    req: OptimizeRequest,
    db: AsyncSession = Depends(get_db),
):
    # Load session
    result = await db.execute(
        select(TradingSession).where(TradingSession.id == session_id)
    )
    session = result.scalars().first()
    if session is None:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found.")

    # Validate strategy is known
    if session.strategy not in STRATEGY_REGISTRY:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown strategy '{session.strategy}' on session. Available: {list(STRATEGY_REGISTRY.keys())}",
        )

    # Build cartesian product and enforce cap
    param_names = list(req.param_grid.keys())
    param_values = [req.param_grid[k] for k in param_names]
    all_combinations = list(itertools.product(*param_values))

    if len(all_combinations) > _MAX_COMBINATIONS:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Too many parameter combinations: {len(all_combinations)}. "
                f"Maximum allowed is {_MAX_COMBINATIONS}. "
                "Reduce the number of values in param_grid."
            ),
        )

    # Date range: session.created_at → session.closed_at (or now)
    from_dt = session.created_at
    to_dt = session.closed_at or datetime.now(timezone.utc)

    # Fetch price history for this session's symbol
    ph_result = await db.execute(
        select(PriceHistory)
        .where(
            PriceHistory.symbol == session.symbol,
            PriceHistory.timestamp >= from_dt,
            PriceHistory.timestamp <= to_dt,
        )
        .order_by(PriceHistory.timestamp.asc())
    )
    bars = ph_result.scalars().all()

    strategy_cls = STRATEGY_REGISTRY[session.strategy]
    results: list[OptimizeResultItem] = []

    for combo in all_combinations:
        params = dict(zip(param_names, combo))
        try:
            strategy = strategy_cls(**params)
        except TypeError as exc:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid parameters for strategy '{session.strategy}': {exc}",
            )

        runner = BacktestRunner(strategy=strategy, starting_capital=float(session.starting_capital))
        trades = runner.run(bars)
        summary = compute_period_summary(trades, float(session.starting_capital))

        results.append(
            OptimizeResultItem(
                params=params,
                sharpe=summary["sharpe_ratio"],
                total_return=summary["total_pnl"] / float(session.starting_capital),
                win_rate=summary["win_rate"],
            )
        )

    # Sort by the requested metric (descending); treat None as -infinity for sharpe
    if req.metric == "sharpe":
        results.sort(
            key=lambda r: (r.sharpe is not None, r.sharpe or 0.0),
            reverse=True,
        )
    elif req.metric == "total_return":
        results.sort(key=lambda r: r.total_return, reverse=True)
    else:  # win_rate
        results.sort(key=lambda r: r.win_rate, reverse=True)

    best_params = results[0].params if results else {}

    return OptimizeResponse(
        results=results,
        best_params=best_params,
        iterations_run=len(all_combinations),
    )
