from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional

@dataclass
class Signal:
    action: str  # "buy" | "sell" | "hold"
    reason: str
    confidence: float
    reasoning: Optional[dict] = field(default=None)

class StrategyBase(ABC):
    name: str
    description: str

    @abstractmethod
    def analyze(self, closes: list[float]) -> Signal:
        ...
