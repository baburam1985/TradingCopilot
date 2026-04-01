import logging
from executor.base import ExecutorBase
from strategies.base import Signal

logger = logging.getLogger(__name__)


class LiveExecutorStub(ExecutorBase):
    async def execute(self, session, signal: Signal, current_price: float, db=None):
        logger.info(
            "[LIVE STUB] Would execute %s for %s at $%.4f (session %s)",
            signal.action, session.symbol, current_price, session.id
        )
        return None
