"""
Risk engine — stateless guardrail checks for trading sessions.

All pct parameters are expressed as whole-number percentages (e.g. 5 = 5%).
"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class RiskParams:
    stop_loss_pct: Optional[float] = None       # exit if unrealised loss >= this %
    take_profit_pct: Optional[float] = None     # exit if unrealised gain >= this %
    max_position_pct: Optional[float] = None    # max position size as % of capital
    daily_max_loss_pct: Optional[float] = None  # circuit breaker: pause if daily loss >= this %


def should_stop_loss(
    entry_price: float,
    current_price: float,
    action: str,
    stop_loss_pct: Optional[float],
) -> bool:
    """Return True if the open trade has hit its stop-loss threshold."""
    if stop_loss_pct is None or stop_loss_pct <= 0:
        return False
    threshold = stop_loss_pct / 100.0
    if action == "buy":
        return current_price <= entry_price * (1 - threshold)
    if action == "sell":
        return current_price >= entry_price * (1 + threshold)
    return False


def should_take_profit(
    entry_price: float,
    current_price: float,
    action: str,
    take_profit_pct: Optional[float],
) -> bool:
    """Return True if the open trade has hit its take-profit threshold."""
    if take_profit_pct is None or take_profit_pct <= 0:
        return False
    threshold = take_profit_pct / 100.0
    if action == "buy":
        return current_price >= entry_price * (1 + threshold)
    if action == "sell":
        return current_price <= entry_price * (1 - threshold)
    return False


def exceeds_max_position(
    quantity: float,
    current_price: float,
    capital: float,
    max_position_pct: Optional[float],
) -> bool:
    """Return True if the intended position size exceeds the configured limit."""
    if max_position_pct is None or max_position_pct <= 0:
        return False
    position_value = quantity * current_price
    limit = (max_position_pct / 100.0) * capital
    return position_value > limit


def daily_loss_limit_breached(
    daily_realised_pnl: float,
    capital: float,
    daily_max_loss_pct: Optional[float],
) -> bool:
    """Return True if cumulative today's P&L has exceeded the daily max loss."""
    if daily_max_loss_pct is None or daily_max_loss_pct <= 0:
        return False
    limit = -(daily_max_loss_pct / 100.0) * capital
    return daily_realised_pnl <= limit
