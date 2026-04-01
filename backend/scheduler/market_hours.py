from datetime import datetime, time, timezone
import zoneinfo

ET = zoneinfo.ZoneInfo("America/New_York")
MARKET_OPEN = time(9, 30)
MARKET_CLOSE = time(16, 0)

def is_market_open(dt: datetime | None = None) -> bool:
    if dt is None:
        dt = datetime.now(timezone.utc)
    et_dt = dt.astimezone(ET)
    if et_dt.weekday() >= 5:  # Saturday=5, Sunday=6
        return False
    return MARKET_OPEN <= et_dt.time() < MARKET_CLOSE
