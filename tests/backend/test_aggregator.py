import pytest
from backend.scrapers.base import FetchResult
from backend.scrapers.aggregator import aggregate

def make_result(source, close, open_=100.0, high=105.0, low=99.0, volume=1000000):
    return FetchResult(source=source, open=open_, high=high, low=low,
                       close=close, volume=volume, success=True)

def test_consensus_is_average_of_closes():
    results = [
        make_result("yahoo", close=150.0),
        make_result("alphavantage", close=150.6),
        make_result("finnhub", close=149.4),
    ]
    bar = aggregate(results)
    assert bar.close == pytest.approx(150.0, abs=0.01)

def test_outlier_flagged_when_deviation_over_1_percent():
    results = [
        make_result("yahoo", close=150.0),
        make_result("alphavantage", close=150.0),
        make_result("finnhub", close=160.0),  # >1% deviation
    ]
    bar = aggregate(results)
    assert "finnhub" in bar.outlier_flags

def test_consensus_works_with_two_sources():
    results = [
        make_result("yahoo", close=100.0),
        FetchResult(source="alphavantage", open=0, high=0, low=0, close=0, volume=0, success=False),
        make_result("finnhub", close=102.0),
    ]
    bar = aggregate(results)
    assert bar.close == pytest.approx(101.0, abs=0.01)
    assert "alphavantage" not in bar.sources_available

def test_sources_available_lists_successful_sources():
    results = [
        make_result("yahoo", close=100.0),
        make_result("alphavantage", close=100.0),
        FetchResult(source="finnhub", open=0, high=0, low=0, close=0, volume=0, success=False),
    ]
    bar = aggregate(results)
    assert set(bar.sources_available) == {"yahoo", "alphavantage"}
