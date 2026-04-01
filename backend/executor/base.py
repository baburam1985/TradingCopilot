from abc import ABC, abstractmethod
from strategies.base import Signal


class ExecutorBase(ABC):
    @abstractmethod
    async def execute(self, session, signal: Signal, current_price: float, db):
        ...
