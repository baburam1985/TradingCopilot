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


def compute_period_summary(trades: list[dict], starting_capital: float) -> dict:
    closed = [t for t in trades if t.get("status") == "closed" and t.get("pnl") is not None]
    total_pnl = sum(t["pnl"] for t in closed)
    num_wins = sum(1 for t in closed if t["pnl"] > 0)
    num_losses = sum(1 for t in closed if t["pnl"] <= 0)
    num_trades = len(closed)
    win_rate = (num_wins / num_trades) if num_trades > 0 else 0.0

    return {
        "total_pnl": total_pnl,
        "num_trades": num_trades,
        "num_wins": num_wins,
        "num_losses": num_losses,
        "win_rate": win_rate,
        "starting_capital": starting_capital,
        "ending_capital": starting_capital + total_pnl,
    }
