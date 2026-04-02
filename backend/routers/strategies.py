from fastapi import APIRouter
from strategies.registry import STRATEGY_REGISTRY

router = APIRouter()


@router.get("")
async def list_strategies():
    return [
        {
            "name": cls.name,
            "description": cls.description,
            "parameters": cls.parameters,
        }
        for cls in STRATEGY_REGISTRY.values()
    ]
