from strategies.moving_average_crossover import MovingAverageCrossover
from strategies.rsi import RSIStrategy

STRATEGY_REGISTRY: dict[str, type] = {
    "moving_average_crossover": MovingAverageCrossover,
    "rsi": RSIStrategy,
}
