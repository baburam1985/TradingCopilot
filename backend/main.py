from contextlib import asynccontextmanager
from fastapi import FastAPI
from scheduler.scraper_job import start_scheduler, stop_scheduler
from routers import sessions, market_data, strategies, trades, backtest, websocket

@asynccontextmanager
async def lifespan(app: FastAPI):
    start_scheduler()
    yield
    stop_scheduler()

app = FastAPI(title="TradingCopilot", lifespan=lifespan)

app.include_router(sessions.router, prefix="/sessions", tags=["sessions"])
app.include_router(market_data.router, prefix="/symbols", tags=["market-data"])
app.include_router(strategies.router, prefix="/strategies", tags=["strategies"])
app.include_router(trades.router, prefix="/sessions", tags=["trades"])
app.include_router(backtest.router, prefix="/backtest", tags=["backtest"])
app.include_router(websocket.router, tags=["websocket"])
