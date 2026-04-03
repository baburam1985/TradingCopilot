"""Evening close summary generator.

Called by the 4:15 PM ET scheduler job. For each active TradingSession it:
  1. Computes the day's P&L summary (total P&L, trade count, win rate, max drawdown).
  2. Produces a pattern analysis comparing signals fired vs outcomes.
  3. Generates a "tomorrow preview" of the top 3 expected signals from the pattern archive.
  4. Persists a CloseSummary record.
  5. Updates (or creates) the singleton UserStreak record.
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database import AsyncSessionLocal
from models.close_summary import CloseSummary
from models.paper_trade import PaperTrade
from models.trading_session import TradingSession
from models.user_streak import UserStreak
from pnl.aggregator import compute_period_summary
from close_summary.streak import _is_market_day, update_streak

logger = logging.getLogger(__name__)

# ---- pattern analysis helpers ------------------------------------------------


def _build_pattern_analysis(trades: list) -> list[dict]:
    """Summarise which signal patterns fired and what their outcomes were.

    Groups trades by signal_reason, counts how many were profitable vs not.
    """
    from collections import defaultdict

    groups: dict[str, dict] = defaultdict(lambda: {"fired": 0, "wins": 0, "losses": 0})
    for t in trades:
        if t.status != "closed" or t.pnl is None:
            continue
        reason = t.signal_reason or "unknown"
        groups[reason]["fired"] += 1
        if float(t.pnl) > 0:
            groups[reason]["wins"] += 1
        else:
            groups[reason]["losses"] += 1

    result = []
    for pattern, stats in groups.items():
        fired = stats["fired"]
        wins = stats["wins"]
        result.append({
            "pattern": pattern,
            "fired": fired,
            "wins": wins,
            "losses": stats["losses"],
            "win_rate": round(wins / fired, 4) if fired else 0.0,
        })
    return result


def _build_tomorrow_preview(session: TradingSession, pattern_analysis: list[dict]) -> list[dict]:
    """Return top 3 signals expected tomorrow based on past pattern win rates.

    Falls back to the session's strategy name if no pattern history exists.
    """
    sorted_patterns = sorted(
        [p for p in pattern_analysis if p["fired"] >= 1],
        key=lambda p: p["win_rate"],
        reverse=True,
    )
    preview = []
    for p in sorted_patterns[:3]:
        preview.append({
            "signal": p["pattern"],
            "strategy": session.strategy,
            "confidence": p["win_rate"],
        })

    # If fewer than 3 patterns available, pad with generic entry
    if not preview:
        preview.append({
            "signal": "market_open_signal",
            "strategy": session.strategy,
            "confidence": 0.5,
        })

    return preview


# ---- main entry point --------------------------------------------------------


async def generate_close_summaries() -> None:
    """Generate close summaries for all active sessions. Called at 4:15 PM ET."""
    today = date.today()

    if not _is_market_day(today):
        logger.info("close_summary: skipping non-trading day %s", today)
        return

    today_str = today.isoformat()
    now = datetime.now(timezone.utc)

    async with AsyncSessionLocal() as db:
        # Load all active sessions
        result = await db.execute(
            select(TradingSession).where(TradingSession.status == "active")
        )
        sessions = result.scalars().all()

        if not sessions:
            logger.info("close_summary: no active sessions on %s", today_str)
        else:
            for session in sessions:
                await _process_session(db, session, today_str, now)

        # Update the global streak regardless of whether sessions exist
        # (streak counts days with *at least one* active session)
        if sessions:
            await _update_global_streak(db, today)

        await db.commit()

    logger.info("close_summary: completed for %s (%d sessions)", today_str, len(sessions))


async def _process_session(
    db: AsyncSession,
    session: TradingSession,
    today_str: str,
    now: datetime,
) -> None:
    # Skip if a summary already exists for this session+date (idempotent)
    existing = await db.execute(
        select(CloseSummary).where(
            CloseSummary.session_id == session.id,
            CloseSummary.trading_date == today_str,
        )
    )
    if existing.scalars().first():
        logger.debug("close_summary: summary already exists for session %s on %s", session.id, today_str)
        return

    # Fetch all trades for this session
    trades_result = await db.execute(
        select(PaperTrade).where(PaperTrade.session_id == session.id)
    )
    trades = trades_result.scalars().all()

    # Compute summary metrics
    trade_dicts = [
        {"pnl": float(t.pnl) if t.pnl is not None else None, "status": t.status}
        for t in trades
    ]
    summary = compute_period_summary(trade_dicts, float(session.starting_capital))

    # Build pattern analysis and tomorrow preview
    pattern_analysis = _build_pattern_analysis(trades)
    tomorrow_preview = _build_tomorrow_preview(session, pattern_analysis)

    close_summary = CloseSummary(
        session_id=session.id,
        generated_at=now,
        trading_date=today_str,
        total_pnl=float(summary["total_pnl"]),
        trade_count=int(summary["num_trades"]),
        win_rate=float(summary["win_rate"]),
        max_drawdown_pct=float(summary["max_drawdown_pct"]),
        pattern_analysis=pattern_analysis,
        tomorrow_preview=tomorrow_preview,
    )
    db.add(close_summary)
    logger.info("close_summary: created summary for session %s on %s", session.id, today_str)


async def _update_global_streak(db: AsyncSession, today: date) -> None:
    """Fetch or create the singleton UserStreak record and update it."""
    result = await db.execute(select(UserStreak).limit(1))
    streak_record = result.scalars().first()

    if streak_record is None:
        # Create the singleton record
        new_state = update_streak(
            current_streak=0,
            longest_streak=0,
            last_trading_date=None,
            milestone_badges=None,
            today=today,
        )
        streak_record = UserStreak(
            current_streak=new_state["current_streak"],
            longest_streak=new_state["longest_streak"],
            last_trading_date=new_state["last_trading_date"],
            milestone_badges=new_state["milestone_badges"],
            updated_at=datetime.now(timezone.utc),
        )
        db.add(streak_record)
    else:
        new_state = update_streak(
            current_streak=streak_record.current_streak,
            longest_streak=streak_record.longest_streak,
            last_trading_date=streak_record.last_trading_date,
            milestone_badges=streak_record.milestone_badges or [],
            today=today,
        )
        streak_record.current_streak = new_state["current_streak"]
        streak_record.longest_streak = new_state["longest_streak"]
        streak_record.last_trading_date = new_state["last_trading_date"]
        streak_record.milestone_badges = new_state["milestone_badges"]
        streak_record.updated_at = datetime.now(timezone.utc)

    if new_state["new_badges"]:
        logger.info(
            "close_summary: milestone badges earned: %s",
            [b["badge"] for b in new_state["new_badges"]],
        )
