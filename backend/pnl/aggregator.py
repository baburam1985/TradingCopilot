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
