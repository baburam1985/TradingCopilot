from abc import ABC, abstractmethod
from dataclasses import dataclass

@dataclass
class Signal:
    action: str  # "buy" | "sell" | "hold"
    reason: str
    confidence: float

class StrategyBase(ABC):
    name: str
    description: str

    @abstractmethod
    def analyze(self, closes: list[float]) -> Signal:
        ...
