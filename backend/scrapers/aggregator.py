from scrapers.base import FetchResult, ConsensusBar

def aggregate(results: list[FetchResult]) -> ConsensusBar:
    successful = [r for r in results if r.success]
    if not successful:
        raise ValueError("All data sources failed — cannot form consensus")

    closes = [r.close for r in successful]
    consensus_close = sum(closes) / len(closes)

    outlier_flags = {}
    for r in successful:
        deviation = abs(r.close - consensus_close) / consensus_close
        if deviation > 0.01:
            outlier_flags[r.source] = {
                "close": r.close,
                "deviation_pct": round(deviation * 100, 2)
            }

    opens = [r.open for r in successful]
    highs = [r.high for r in successful]
    lows = [r.low for r in successful]
    volumes = [r.volume for r in successful]

    by_source = {r.source: r for r in results}

    return ConsensusBar(
        open=sum(opens) / len(opens),
        high=max(highs),
        low=min(lows),
        close=consensus_close,
        volume=int(sum(volumes) / len(volumes)),
        yahoo_close=by_source["yahoo"].close if by_source.get("yahoo") and by_source["yahoo"].success else None,
        alphavantage_close=by_source["alphavantage"].close if by_source.get("alphavantage") and by_source["alphavantage"].success else None,
        finnhub_close=by_source["finnhub"].close if by_source.get("finnhub") and by_source["finnhub"].success else None,
        outlier_flags=outlier_flags,
        sources_available=[r.source for r in successful],
    )
