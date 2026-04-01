from fastapi import APIRouter
from strategies.moving_average_crossover import MovingAverageCrossover

router = APIRouter()

@router.get("")
async def list_strategies():
    return [
        {
            "name": MovingAverageCrossover.name,
            "description": MovingAverageCrossover.description,
            "parameters": {
                "short_window": {"type": "int", "default": 50, "description": "Short moving average window"},
                "long_window": {"type": "int", "default": 200, "description": "Long moving average window"},
            },
        }
    ]
