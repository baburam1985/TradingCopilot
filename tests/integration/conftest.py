import asyncio
import os
import pytest
import httpx
from dotenv import dotenv_values
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy import text

# Read credentials from .env — override host to localhost since tests run on the host machine
_env = dotenv_values(os.path.join(os.path.dirname(__file__), "..", "..", ".env"))

INTEGRATION_DB_URL = (
    f"postgresql+asyncpg://{_env['POSTGRES_USER']}:{_env['POSTGRES_PASSWORD']}"
    f"@localhost:{_env.get('POSTGRES_PORT', '5432')}/{_env['POSTGRES_DB']}"
)
BASE_URL = "http://localhost:8000"

_engine = create_async_engine(INTEGRATION_DB_URL, echo=False)
_session_factory = async_sessionmaker(_engine, expire_on_commit=False)


@pytest.fixture(scope="session")
def base_url():
    return BASE_URL


@pytest.fixture(scope="session")
async def client():
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=20.0) as c:
        yield c


@pytest.fixture(scope="session")
async def db_session():
    async with _session_factory() as session:
        yield session


@pytest.fixture
async def clean_db(db_session):
    yield
    # Rollback any aborted transaction before truncating
    await db_session.rollback()
    await db_session.execute(
        text("TRUNCATE TABLE paper_trades, aggregated_pnl, sessions, price_history RESTART IDENTITY CASCADE")
    )
    await db_session.commit()


@pytest.fixture
def scrape_symbol(client):
    """Returns an async callable that POSTs /symbols/{symbol}/scrape with retries."""
    async def _scrape(symbol: str, retries: int = 3, delay: float = 2.0):
        last_error = None
        for attempt in range(retries):
            try:
                resp = await client.post(f"/symbols/{symbol}/scrape")
                if resp.status_code == 200:
                    return resp.json()
                last_error = f"HTTP {resp.status_code}: {resp.text}"
            except Exception as exc:
                last_error = str(exc)
            if attempt < retries - 1:
                await asyncio.sleep(delay)
        pytest.skip(f"Yahoo Finance unreachable after {retries} attempts: {last_error}")
    return _scrape
