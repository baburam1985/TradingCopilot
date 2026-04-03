from strategies.moving_average_crossover import MovingAverageCrossover
from strategies.rsi import RSIStrategy
from strategies.macd import MACDStrategy
from strategies.bollinger_bands import BollingerBandsStrategy
from strategies.vwap import VWAPStrategy
from strategies.breakout import BreakoutStrategy
from strategies.mean_reversion import MeanReversionStrategy

STRATEGY_REGISTRY: dict[str, type] = {
    "moving_average_crossover": MovingAverageCrossover,
    "rsi": RSIStrategy,
    "macd": MACDStrategy,
    "bollinger_bands": BollingerBandsStrategy,
    "vwap": VWAPStrategy,
    "breakout": BreakoutStrategy,
    "mean_reversion": MeanReversionStrategy,
}
