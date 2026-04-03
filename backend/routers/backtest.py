import asyncio
import yfinance as yf
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from database import get_db
from models.price_history import PriceHistory
from strategies.registry import STRATEGY_REGISTRY
from backtester.runner import BacktestRunner
from pnl.aggregator import compute_period_summary
from backtester.compare import run_comparison

router = APIRouter()


class BacktestRequest(BaseModel):
    symbol: str
    strategy: str
    strategy_params: dict
    starting_capital: float
    from_dt: datetime
    to_dt: datetime


class StrategySpec(BaseModel):
    name: str
    params: dict = {}


class CompareRequest(BaseModel):
    symbol: str
    strategies: list[StrategySpec]
    starting_capital: float
    from_dt: datetime
    to_dt: datetime


@router.post("/seed/{symbol}")
async def seed_price_history(
    symbol: str,
    days: int = Query(default=365, ge=1, le=1825),
    db: AsyncSession = Depends(get_db),
):
    end = datetime.now(timezone.utc)
    start = end - timedelta(days=days)

    df = await asyncio.to_thread(
        lambda: yf.download(symbol.upper(), start=start.date(), end=end.date(), progress=False)
    )
    if df.empty:
        raise HTTPException(status_code=422, detail=f"Yahoo Finance returned no data for {symbol}")

    if hasattr(df.columns, "levels"):
        df.columns = df.columns.get_level_values(0)

    existing = await db.execute(
        select(PriceHistory.timestamp).where(PriceHistory.symbol == symbol.upper())
    )
    existing_timestamps = {row[0].replace(tzinfo=timezone.utc) for row in existing.fetchall()}

    inserted = 0
    skipped = 0
    for ts, row in df.iterrows():
        ts_utc = ts.to_pydatetime().replace(tzinfo=timezone.utc)
        if ts_utc in existing_timestamps:
            skipped += 1
            continue
        db.add(PriceHistory(
            symbol=symbol.upper(),
            timestamp=ts_utc,
            open=float(row["Open"]),
            high=float(row["High"]),
            low=float(row["Low"]),
            close=float(row["Close"]),
            volume=int(row["Volume"]),
            yahoo_close=float(row["Close"]),
            alphavantage_close=None,
            finnhub_close=None,
            outlier_flags={},
            sources_available=["yahoo"],
        ))
        inserted += 1

    await db.commit()
    return {"symbol": symbol.upper(), "inserted": inserted, "skipped": skipped}


@router.post("")
async def run_backtest(req: BacktestRequest, db: AsyncSession = Depends(get_db)):
    if req.strategy not in STRATEGY_REGISTRY:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown strategy: '{req.strategy}'. Available: {list(STRATEGY_REGISTRY.keys())}",
        )

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

    strategy_cls = STRATEGY_REGISTRY[req.strategy]
    strategy = strategy_cls(**req.strategy_params)
    runner = BacktestRunner(strategy=strategy, starting_capital=req.starting_capital)
    trades = runner.run(bars)

    summary = compute_period_summary(trades, req.starting_capital)
    return {"trades": trades, "summary": summary}


@router.post("/compare")
async def run_backtest_compare(req: CompareRequest, db: AsyncSession = Depends(get_db)):
    for spec in req.strategies:
        if spec.name not in STRATEGY_REGISTRY:
            raise HTTPException(
                status_code=400,
                detail=f"Unknown strategy: '{spec.name}'. Available: {list(STRATEGY_REGISTRY.keys())}",
            )

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

    specs = [{"name": s.name, "params": s.params} for s in req.strategies]
    return run_comparison(bars, strategy_specs=specs, starting_capital=req.starting_capital)
