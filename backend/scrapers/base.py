from dataclasses import dataclass, field
from typing import Optional

@dataclass
class FetchResult:
    source: str
    open: float
    high: float
    low: float
    close: float
    volume: int
    success: bool
    error: Optional[str] = None

@dataclass
class ConsensusBar:
    open: float
    high: float
    low: float
    close: float
    volume: int
    yahoo_close: Optional[float]
    alphavantage_close: Optional[float]
    finnhub_close: Optional[float]
    outlier_flags: dict
    sources_available: list[str]
