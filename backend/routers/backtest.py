import asyncio
import itertools
import yfinance as yf
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel, Field
from database import get_db
from models.price_history import PriceHistory
from strategies.registry import STRATEGY_REGISTRY
from backtester.runner import BacktestRunner
from pnl.aggregator import compute_period_summary
from backtester.compare import run_comparison
from backtester.benchmark import BenchmarkCalculator
from backtester.walk_forward import WalkForwardEngine

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


_MAX_OPTIMIZE_COMBINATIONS = 100


class WalkForwardRequest(BaseModel):
    symbol: str
    strategy: str
    strategy_params: dict = Field(default_factory=dict)
    start_date: str
    end_date: str
    train_window_days: int = Field(ge=5, le=1825)
    test_window_days: int = Field(ge=1, le=365)
    step_days: int = Field(ge=1, le=365)
    starting_capital: float
    param_grid: dict[str, list] = Field(default_factory=dict)


class OptimizeRequest(BaseModel):
    symbol: str
    start_date: str
    end_date: str
    starting_capital: float
    strategy: str
    parameter_ranges: dict[str, list]


class OptimizeResultItem(BaseModel):
    parameters: dict
    sharpe_ratio: float | None
    total_pnl: float
    win_rate: float
    num_trades: int


class OptimizeResponse(BaseModel):
    combinations_tested: int
    results: list[OptimizeResultItem]


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


@router.post("/optimize", response_model=OptimizeResponse)
async def optimize_strategy(req: OptimizeRequest, db: AsyncSession = Depends(get_db)):
    if req.strategy not in STRATEGY_REGISTRY:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown strategy: '{req.strategy}'. Available: {list(STRATEGY_REGISTRY.keys())}",
        )

    # Build the full cartesian product of parameter values
    param_names = list(req.parameter_ranges.keys())
    param_values = [req.parameter_ranges[k] for k in param_names]
    all_combinations = list(itertools.product(*param_values))

    if len(all_combinations) > _MAX_OPTIMIZE_COMBINATIONS:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Too many parameter combinations: {len(all_combinations)}. "
                f"Maximum allowed is {_MAX_OPTIMIZE_COMBINATIONS}. "
                "Reduce the number of values in parameter_ranges."
            ),
        )

    from_dt = datetime.fromisoformat(req.start_date).replace(tzinfo=timezone.utc)
    to_dt = datetime.fromisoformat(req.end_date).replace(tzinfo=timezone.utc)

    result = await db.execute(
        select(PriceHistory)
        .where(
            PriceHistory.symbol == req.symbol.upper(),
            PriceHistory.timestamp >= from_dt,
            PriceHistory.timestamp <= to_dt,
        )
        .order_by(PriceHistory.timestamp.asc())
    )
    bars = result.scalars().all()

    strategy_cls = STRATEGY_REGISTRY[req.strategy]
    results: list[OptimizeResultItem] = []

    for combo in all_combinations:
        params = dict(zip(param_names, combo))
        try:
            strategy = strategy_cls(**params)
        except TypeError as exc:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid parameters for strategy '{req.strategy}': {exc}",
            )

        runner = BacktestRunner(strategy=strategy, starting_capital=req.starting_capital)
        trades = runner.run(bars)
        summary = compute_period_summary(trades, req.starting_capital)

        results.append(
            OptimizeResultItem(
                parameters=params,
                sharpe_ratio=summary["sharpe_ratio"],
                total_pnl=summary["total_pnl"],
                win_rate=summary["win_rate"],
                num_trades=summary["num_trades"],
            )
        )

    # Sort by sharpe_ratio descending; treat None as -infinity
    results.sort(key=lambda r: (r.sharpe_ratio is not None, r.sharpe_ratio or 0.0), reverse=True)

    return OptimizeResponse(combinations_tested=len(all_combinations), results=results)


@router.post("/walk-forward")
async def run_walk_forward(req: WalkForwardRequest, db: AsyncSession = Depends(get_db)):
    """Walk-forward backtesting: train on rolling windows, validate out-of-sample."""
    if req.strategy not in STRATEGY_REGISTRY:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown strategy: '{req.strategy}'. Available: {list(STRATEGY_REGISTRY.keys())}",
        )

    try:
        from_dt = datetime.fromisoformat(req.start_date).replace(tzinfo=timezone.utc)
        to_dt = datetime.fromisoformat(req.end_date).replace(tzinfo=timezone.utc)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD.")

    result = await db.execute(
        select(PriceHistory)
        .where(
            PriceHistory.symbol == req.symbol.upper(),
            PriceHistory.timestamp >= from_dt,
            PriceHistory.timestamp <= to_dt,
        )
        .order_by(PriceHistory.timestamp.asc())
    )
    bars = result.scalars().all()

    if not bars:
        raise HTTPException(
            status_code=422,
            detail=f"No price data found for {req.symbol.upper()} in the requested date range.",
        )

    try:
        engine = WalkForwardEngine(
            strategy_name=req.strategy,
            strategy_params=req.strategy_params,
            param_grid=req.param_grid,
            train_window_days=req.train_window_days,
            test_window_days=req.test_window_days,
            step_days=req.step_days,
            starting_capital=req.starting_capital,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    return engine.run(bars)


@router.get("/benchmark")
async def get_benchmark(
    symbol: str,
    start_date: str,
    end_date: str,
    capital: float = Query(gt=0),
    db: AsyncSession = Depends(get_db),
):
    """Standalone buy-and-hold benchmark for a symbol/date range."""
    try:
        from_dt = datetime.fromisoformat(start_date).replace(tzinfo=timezone.utc)
        to_dt = datetime.fromisoformat(end_date).replace(tzinfo=timezone.utc)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD.")

    result = await db.execute(
        select(PriceHistory)
        .where(
            PriceHistory.symbol == symbol.upper(),
            PriceHistory.timestamp >= from_dt,
            PriceHistory.timestamp <= to_dt,
        )
        .order_by(PriceHistory.timestamp.asc())
    )
    bars = result.scalars().all()

    if not bars:
        raise HTTPException(
            status_code=422,
            detail=f"No price data found for {symbol.upper()} in the requested date range.",
        )

    return {
        "symbol": symbol.upper(),
        "start_date": start_date,
        "end_date": end_date,
        "starting_capital": capital,
        **BenchmarkCalculator.compute(bars, capital),
    }
