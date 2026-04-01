import asyncio
import finnhub
from config import FINNHUB_API_KEY
from scrapers.base import FetchResult

async def fetch_finnhub(symbol: str) -> FetchResult:
    if not FINNHUB_API_KEY:
        return FetchResult(source="finnhub", open=0, high=0, low=0, close=0,
                           volume=0, success=False, error="No API key configured")
    try:
        client = finnhub.Client(api_key=FINNHUB_API_KEY)
        quote = await asyncio.to_thread(client.quote, symbol)
        if not quote or quote.get("c") == 0:
            return FetchResult(source="finnhub", open=0, high=0, low=0, close=0,
                               volume=0, success=False, error="Empty quote")
        return FetchResult(
            source="finnhub",
            open=float(quote["o"]),
            high=float(quote["h"]),
            low=float(quote["l"]),
            close=float(quote["c"]),
            volume=0,
            success=True,
        )
    except Exception as e:
        return FetchResult(source="finnhub", open=0, high=0, low=0, close=0,
                           volume=0, success=False, error=str(e))
