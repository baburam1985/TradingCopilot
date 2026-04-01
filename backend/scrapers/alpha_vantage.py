import httpx
from config import ALPHA_VANTAGE_API_KEY
from scrapers.base import FetchResult

AV_BASE = "https://www.alphavantage.co/query"

async def fetch_alpha_vantage(symbol: str) -> FetchResult:
    if not ALPHA_VANTAGE_API_KEY:
        return FetchResult(source="alphavantage", open=0, high=0, low=0, close=0,
                           volume=0, success=False, error="No API key configured")
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(AV_BASE, params={
                "function": "TIME_SERIES_INTRADAY",
                "symbol": symbol,
                "interval": "1min",
                "outputsize": "compact",
                "apikey": ALPHA_VANTAGE_API_KEY,
            })
            data = resp.json()
            ts = data.get("Time Series (1min)", {})
            if not ts:
                return FetchResult(source="alphavantage", open=0, high=0, low=0, close=0,
                                   volume=0, success=False, error="No time series in response")
            latest_key = sorted(ts.keys())[-1]
            bar = ts[latest_key]
            return FetchResult(
                source="alphavantage",
                open=float(bar["1. open"]),
                high=float(bar["2. high"]),
                low=float(bar["3. low"]),
                close=float(bar["4. close"]),
                volume=int(bar["5. volume"]),
                success=True,
            )
    except Exception as e:
        return FetchResult(source="alphavantage", open=0, high=0, low=0, close=0,
                           volume=0, success=False, error=str(e))
