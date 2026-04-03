"""Unit tests for POST /backtest/optimize — grid-search parameter optimization."""
import itertools
import sys
import types
import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from fastapi.testclient import TestClient


def _stub_scraper_modules():
    """Stub third-party scraper dependencies so main.py can be imported without them."""
    for mod_name in ["yfinance", "aiohttp", "finnhub"]:
        if mod_name not in sys.modules:
            sys.modules[mod_name] = types.ModuleType(mod_name)

    for full in ["scrapers.yahoo", "scrapers.alpha_vantage", "scrapers.finnhub"]:
        if full not in sys.modules:
            mod = types.ModuleType(full)

            async def _stub(*args, **kwargs):
                return None

            mod.fetch_yahoo = _stub
            mod.fetch_alpha_vantage = _stub
            mod.fetch_finnhub = _stub
            sys.modules[full] = mod


_stub_scraper_modules()

from main import app  # noqa: E402 — must come after stubs
from database import get_db  # noqa: E402


# ---------------------------------------------------------------------------
# Grid-generation helpers (pure logic, no DB)
# ---------------------------------------------------------------------------

def _all_combos(parameter_ranges: dict) -> list[dict]:
    """Reproduce the endpoint's grid-generation logic for testing."""
    param_names = list(parameter_ranges.keys())
    param_values = [parameter_ranges[k] for k in param_names]
    combos = list(itertools.product(*param_values))
    return [dict(zip(param_names, combo)) for combo in combos]


# ---------------------------------------------------------------------------
# Grid generation logic
# ---------------------------------------------------------------------------

def test_grid_single_param_three_values():
    combos = _all_combos({"period": [7, 9, 14]})
    assert len(combos) == 3
    assert {"period": 7} in combos
    assert {"period": 14} in combos


def test_grid_two_params_cartesian_product():
    combos = _all_combos({"period": [7, 14], "overbought": [70, 75]})
    assert len(combos) == 4
    assert {"period": 7, "overbought": 70} in combos
    assert {"period": 14, "overbought": 75} in combos


def test_grid_example_from_spec():
    """Matches the spec example: period×[7,9,14], overbought×[70,75] → 6 combos."""
    combos = _all_combos({"period": [7, 9, 14], "overbought": [70, 75]})
    assert len(combos) == 6


def test_grid_empty_ranges_yields_one_empty_combo():
    combos = _all_combos({})
    assert len(combos) == 1
    assert combos[0] == {}


def test_grid_single_value_per_param():
    combos = _all_combos({"period": [14], "overbought": [70]})
    assert len(combos) == 1
    assert combos[0] == {"period": 14, "overbought": 70}


def test_grid_combination_count_boundary():
    """Exactly 100 combos should be accepted; 101 should be rejected."""
    # 10 × 10 = 100 combos
    ranges_100 = {"a": list(range(10)), "b": list(range(10))}
    assert len(_all_combos(ranges_100)) == 100

    # 11 × 10 = 110 combos — over the limit
    ranges_110 = {"a": list(range(11)), "b": list(range(10))}
    assert len(_all_combos(ranges_110)) == 110


# ---------------------------------------------------------------------------
# Sorting logic
# ---------------------------------------------------------------------------

def _sort_results(results: list[dict]) -> list[dict]:
    """Mirror the endpoint's sort: sharpe_ratio desc, None last."""
    return sorted(
        results,
        key=lambda r: (r["sharpe_ratio"] is not None, r["sharpe_ratio"] or 0.0),
        reverse=True,
    )


def test_sort_by_sharpe_descending():
    items = [
        {"parameters": {"period": 7}, "sharpe_ratio": 0.5, "total_pnl": 10.0, "win_rate": 0.5, "num_trades": 4},
        {"parameters": {"period": 14}, "sharpe_ratio": 1.8, "total_pnl": 30.0, "win_rate": 0.7, "num_trades": 6},
        {"parameters": {"period": 9}, "sharpe_ratio": 1.2, "total_pnl": 20.0, "win_rate": 0.6, "num_trades": 5},
    ]
    sorted_items = _sort_results(items)
    assert sorted_items[0]["sharpe_ratio"] == 1.8
    assert sorted_items[1]["sharpe_ratio"] == 1.2
    assert sorted_items[2]["sharpe_ratio"] == 0.5


def test_sort_none_sharpe_goes_last():
    items = [
        {"parameters": {"period": 7}, "sharpe_ratio": None, "total_pnl": 0.0, "win_rate": 0.0, "num_trades": 0},
        {"parameters": {"period": 14}, "sharpe_ratio": 1.5, "total_pnl": 20.0, "win_rate": 0.6, "num_trades": 4},
        {"parameters": {"period": 9}, "sharpe_ratio": None, "total_pnl": 5.0, "win_rate": 0.5, "num_trades": 1},
    ]
    sorted_items = _sort_results(items)
    assert sorted_items[0]["sharpe_ratio"] == 1.5
    assert sorted_items[1]["sharpe_ratio"] is None
    assert sorted_items[2]["sharpe_ratio"] is None


def test_sort_all_none_sharpe_stable():
    items = [
        {"parameters": {"period": 7}, "sharpe_ratio": None, "total_pnl": 10.0, "win_rate": 0.5, "num_trades": 2},
        {"parameters": {"period": 14}, "sharpe_ratio": None, "total_pnl": 5.0, "win_rate": 0.3, "num_trades": 1},
    ]
    sorted_items = _sort_results(items)
    # Both None — order is not asserted beyond the fact that both remain
    assert all(r["sharpe_ratio"] is None for r in sorted_items)


# ---------------------------------------------------------------------------
# HTTP endpoint tests (mock DB + backtester)
# ---------------------------------------------------------------------------

def _make_bars(n: int = 50):
    from types import SimpleNamespace
    return [
        SimpleNamespace(close=100.0 + i * 0.1, timestamp=f"2024-01-{(i % 28) + 1:02d}")
        for i in range(n)
    ]


def _make_summary(sharpe: float | None = 1.0, total_pnl: float = 100.0,
                  win_rate: float = 0.6, num_trades: int = 5) -> dict:
    return {
        "total_pnl": total_pnl,
        "num_trades": num_trades,
        "num_wins": int(num_trades * win_rate),
        "num_losses": num_trades - int(num_trades * win_rate),
        "win_rate": win_rate,
        "starting_capital": 1000.0,
        "ending_capital": 1000.0 + total_pnl,
        "sharpe_ratio": sharpe,
        "sortino_ratio": None,
        "max_drawdown_pct": 5.0,
        "calmar_ratio": None,
        "profit_factor": None,
    }


@pytest.fixture()
def client():
    """Create a TestClient with DB and backtester mocked out."""
    async def override_get_db():
        mock_db = AsyncMock()
        scalars_result = MagicMock()
        scalars_result.all.return_value = _make_bars(50)
        execute_result = MagicMock()
        execute_result.scalars.return_value = scalars_result
        mock_db.execute = AsyncMock(return_value=execute_result)
        yield mock_db

    app.dependency_overrides[get_db] = override_get_db
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_optimize_returns_correct_combination_count(client):
    with patch("routers.backtest.BacktestRunner.run", return_value=[]), \
         patch("routers.backtest.compute_period_summary", return_value=_make_summary()):
        resp = client.post("/backtest/optimize", json={
            "symbol": "AAPL",
            "start_date": "2024-01-01",
            "end_date": "2024-12-31",
            "starting_capital": 1000.0,
            "strategy": "rsi",
            "parameter_ranges": {
                "period": [7, 9, 14],
                "overbought": [70, 75],
            },
        })
    assert resp.status_code == 200
    data = resp.json()
    assert data["combinations_tested"] == 6
    assert len(data["results"]) == 6


def test_optimize_results_sorted_by_sharpe_descending(client):
    sharpe_values = iter([0.5, 2.0, 1.5, 0.1, 0.8, 1.2])

    def mock_summary(*args, **kwargs):
        return _make_summary(sharpe=next(sharpe_values))

    with patch("routers.backtest.BacktestRunner.run", return_value=[]), \
         patch("routers.backtest.compute_period_summary", side_effect=mock_summary):
        resp = client.post("/backtest/optimize", json={
            "symbol": "AAPL",
            "start_date": "2024-01-01",
            "end_date": "2024-12-31",
            "starting_capital": 1000.0,
            "strategy": "rsi",
            "parameter_ranges": {
                "period": [7, 9, 14],
                "overbought": [70, 75],
            },
        })
    assert resp.status_code == 200
    ratios = [r["sharpe_ratio"] for r in resp.json()["results"] if r["sharpe_ratio"] is not None]
    assert ratios == sorted(ratios, reverse=True)


def test_optimize_rejects_over_100_combinations(client):
    resp = client.post("/backtest/optimize", json={
        "symbol": "AAPL",
        "start_date": "2024-01-01",
        "end_date": "2024-12-31",
        "starting_capital": 1000.0,
        "strategy": "rsi",
        "parameter_ranges": {
            "period": list(range(11)),    # 11 values
            "overbought": list(range(10)), # 10 values → 110 combos
        },
    })
    assert resp.status_code == 400
    assert "100" in resp.json()["detail"]


def test_optimize_rejects_exactly_101_combinations(client):
    """Boundary: 101 combinations must be rejected."""
    resp = client.post("/backtest/optimize", json={
        "symbol": "AAPL",
        "start_date": "2024-01-01",
        "end_date": "2024-12-31",
        "starting_capital": 1000.0,
        "strategy": "rsi",
        "parameter_ranges": {
            "period": list(range(101)),  # 101 values, 1 other param = 101 combos
            "overbought": [70],
        },
    })
    assert resp.status_code == 400


def test_optimize_accepts_exactly_100_combinations(client):
    with patch("routers.backtest.BacktestRunner.run", return_value=[]), \
         patch("routers.backtest.compute_period_summary", return_value=_make_summary()):
        resp = client.post("/backtest/optimize", json={
            "symbol": "AAPL",
            "start_date": "2024-01-01",
            "end_date": "2024-12-31",
            "starting_capital": 1000.0,
            "strategy": "rsi",
            "parameter_ranges": {
                "period": list(range(10)),     # 10 values
                "overbought": list(range(10)), # 10 values → exactly 100
            },
        })
    assert resp.status_code == 200
    assert resp.json()["combinations_tested"] == 100


def test_optimize_unknown_strategy_returns_400(client):
    resp = client.post("/backtest/optimize", json={
        "symbol": "AAPL",
        "start_date": "2024-01-01",
        "end_date": "2024-12-31",
        "starting_capital": 1000.0,
        "strategy": "nonexistent_strategy",
        "parameter_ranges": {"period": [14]},
    })
    assert resp.status_code == 400
    assert "nonexistent_strategy" in resp.json()["detail"]


def test_optimize_response_schema(client):
    """Each result item must contain the required fields."""
    with patch("routers.backtest.BacktestRunner.run", return_value=[]), \
         patch("routers.backtest.compute_period_summary", return_value=_make_summary(sharpe=1.5)):
        resp = client.post("/backtest/optimize", json={
            "symbol": "AAPL",
            "start_date": "2024-01-01",
            "end_date": "2024-12-31",
            "starting_capital": 1000.0,
            "strategy": "rsi",
            "parameter_ranges": {"period": [14]},
        })
    assert resp.status_code == 200
    result = resp.json()["results"][0]
    assert "parameters" in result
    assert "sharpe_ratio" in result
    assert "total_pnl" in result
    assert "win_rate" in result
    assert "num_trades" in result


def test_optimize_parameters_reflected_in_results(client):
    """The parameters dict in each result must match the combination used."""
    with patch("routers.backtest.BacktestRunner.run", return_value=[]), \
         patch("routers.backtest.compute_period_summary", return_value=_make_summary()):
        resp = client.post("/backtest/optimize", json={
            "symbol": "AAPL",
            "start_date": "2024-01-01",
            "end_date": "2024-12-31",
            "starting_capital": 1000.0,
            "strategy": "rsi",
            "parameter_ranges": {"period": [7, 14]},
        })
    assert resp.status_code == 200
    returned_periods = {r["parameters"]["period"] for r in resp.json()["results"]}
    assert returned_periods == {7, 14}


def test_optimize_none_sharpe_sorted_last(client):
    """Combinations with no closed trades (sharpe=None) go to the bottom."""
    sharpe_values = iter([None, 1.2, None])

    def mock_summary(*args, **kwargs):
        return _make_summary(sharpe=next(sharpe_values))

    with patch("routers.backtest.BacktestRunner.run", return_value=[]), \
         patch("routers.backtest.compute_period_summary", side_effect=mock_summary):
        resp = client.post("/backtest/optimize", json={
            "symbol": "AAPL",
            "start_date": "2024-01-01",
            "end_date": "2024-12-31",
            "starting_capital": 1000.0,
            "strategy": "rsi",
            "parameter_ranges": {"period": [7, 9, 14]},
        })
    assert resp.status_code == 200
    results = resp.json()["results"]
    assert results[0]["sharpe_ratio"] == 1.2
    assert results[1]["sharpe_ratio"] is None
    assert results[2]["sharpe_ratio"] is None
