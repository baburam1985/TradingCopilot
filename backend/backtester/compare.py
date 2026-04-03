from backtester.runner import BacktestRunner
from pnl.aggregator import compute_period_summary
from strategies.registry import STRATEGY_REGISTRY


def run_comparison(
    bars: list,
    strategy_specs: list[dict],
    starting_capital: float,
) -> list[dict]:
    """Run multiple strategies over the same bar data and return comparative results.

    Args:
        bars: Price history bars (same list passed to each strategy).
        strategy_specs: List of {"name": str, "params": dict} dicts.
        starting_capital: Starting capital for each strategy run.

    Returns:
        List of {"strategy": str, "trades": list, "summary": dict} — one per spec.

    Raises:
        ValueError: If a strategy name is not in STRATEGY_REGISTRY.
    """
    results = []
    for spec in strategy_specs:
        name = spec["name"]
        params = spec.get("params", {})
        if name not in STRATEGY_REGISTRY:
            raise ValueError(f"Unknown strategy: '{name}'. Available: {list(STRATEGY_REGISTRY.keys())}")
        strategy = STRATEGY_REGISTRY[name](**params)
        runner = BacktestRunner(strategy=strategy, starting_capital=starting_capital)
        trades = runner.run(bars)
        summary = compute_period_summary(trades, starting_capital)
        results.append({"strategy": name, "trades": trades, "summary": summary})
    return results
