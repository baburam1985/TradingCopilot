import asyncio
import yfinance as yf
from scrapers.base import FetchResult

async def fetch_yahoo(symbol: str) -> FetchResult:
    try:
        df = await asyncio.to_thread(
            lambda: yf.download(symbol, period="5d", interval="1d", progress=False)
        )
        if df.empty:
            return FetchResult(source="yahoo", open=0, high=0, low=0, close=0,
                               volume=0, success=False, error="Empty response")
        # yfinance 1.x returns MultiIndex columns — flatten to plain column names
        if hasattr(df.columns, "levels"):
            df.columns = df.columns.get_level_values(0)
        last = df.iloc[-1]
        return FetchResult(
            source="yahoo",
            open=float(last["Open"]),
            high=float(last["High"]),
            low=float(last["Low"]),
            close=float(last["Close"]),
            volume=int(last["Volume"]),
            success=True,
        )
    except Exception as e:
        return FetchResult(source="yahoo", open=0, high=0, low=0, close=0,
                           volume=0, success=False, error=str(e))
