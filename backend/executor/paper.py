from datetime import datetime, timezone
from executor.base import ExecutorBase
from models.paper_trade import PaperTrade
from strategies.base import Signal


class PaperExecutor(ExecutorBase):
    async def execute(self, session, signal: Signal, current_price: float, db=None):
        quantity = float(session.starting_capital) / current_price
        trade = PaperTrade(
            session_id=session.id,
            action=signal.action,
            signal_reason=signal.reason,
            price_at_signal=current_price,
            quantity=quantity,
            timestamp_open=datetime.now(timezone.utc),
            status="open",
            reasoning=signal.reasoning,
        )
        if db:
            db.add(trade)
            await db.commit()
        return trade

    async def close_trade(self, trade: PaperTrade, current_price: float, db=None):
        trade.timestamp_close = datetime.now(timezone.utc)
        trade.price_at_close = current_price
        trade.pnl = (current_price - float(trade.price_at_signal)) * float(trade.quantity)
        trade.status = "closed"
        if db:
            await db.commit()
        return trade
