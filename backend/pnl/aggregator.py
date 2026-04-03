import math
import statistics


def compute_equity_curve(trades: list[dict], starting_capital: float, session_start: str) -> list[dict]:
    """Return cumulative portfolio value at each closed trade event.

    Each point: {"timestamp": ISO string, "portfolio_value": float}.
    The first point anchors the curve at session start with starting_capital.
    """
    closed = [
        t for t in trades
        if t.get("status") == "closed" and t.get("pnl") is not None and t.get("timestamp_close") is not None
    ]
    closed.sort(key=lambda t: t["timestamp_close"])

    points = [{"timestamp": session_start, "portfolio_value": round(starting_capital, 4)}]
    cumulative = starting_capital
    for t in closed:
        cumulative += float(t["pnl"])
        points.append({
            "timestamp": t["timestamp_close"],
            "portfolio_value": round(cumulative, 4),
        })
    return points


def _max_drawdown_pct(pnl_values: list[float], starting_capital: float) -> float:
    """Return max peak-to-trough drawdown as a percentage (0–100)."""
    peak = starting_capital
    max_dd = 0.0
    equity = starting_capital
    for pnl in pnl_values:
        equity += pnl
        if equity > peak:
            peak = equity
        if peak > 0:
            dd = (peak - equity) / peak * 100
            if dd > max_dd:
                max_dd = dd
    return max_dd


def compute_period_summary(trades: list[dict], starting_capital: float) -> dict:
    closed = [t for t in trades if t.get("status") == "closed" and t.get("pnl") is not None]
    pnl_values = [float(t["pnl"]) for t in closed]

    total_pnl = sum(pnl_values)
    num_wins = sum(1 for p in pnl_values if p > 0)
    num_losses = sum(1 for p in pnl_values if p <= 0)
    num_trades = len(pnl_values)
    win_rate = (num_wins / num_trades) if num_trades > 0 else 0.0

    # Sharpe ratio (sample std, risk-free rate = 0)
    sharpe_ratio = None
    if num_trades >= 2:
        std = statistics.stdev(pnl_values)
        if std > 0:
            sharpe_ratio = statistics.mean(pnl_values) / std

    # Sortino ratio (downside deviation using population std of negative returns)
    sortino_ratio = None
    if num_trades >= 1:
        downside = [p for p in pnl_values if p < 0]
        if downside:
            downside_std = math.sqrt(sum(p ** 2 for p in downside) / len(downside))
            if downside_std > 0:
                sortino_ratio = statistics.mean(pnl_values) / downside_std

    # Max drawdown
    max_dd_pct = _max_drawdown_pct(pnl_values, starting_capital)

    # Calmar ratio: total_return_pct / max_drawdown_pct
    calmar_ratio = None
    if max_dd_pct > 0:
        total_return_pct = total_pnl / starting_capital * 100
        calmar_ratio = total_return_pct / max_dd_pct

    # Profit factor: gross profit / gross loss
    profit_factor = None
    gross_profit = sum(p for p in pnl_values if p > 0)
    gross_loss = abs(sum(p for p in pnl_values if p < 0))
    if gross_loss > 0:
        profit_factor = gross_profit / gross_loss

    return {
        "total_pnl": total_pnl,
        "num_trades": num_trades,
        "num_wins": num_wins,
        "num_losses": num_losses,
        "win_rate": win_rate,
        "starting_capital": starting_capital,
        "ending_capital": starting_capital + total_pnl,
        "sharpe_ratio": sharpe_ratio,
        "sortino_ratio": sortino_ratio,
        "max_drawdown_pct": max_dd_pct,
        "calmar_ratio": calmar_ratio,
        "profit_factor": profit_factor,
    }
