"""Unit tests for POST /sessions/{session_id}/optimize (session-scoped grid search)."""
import sys
import types
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

# Stub third-party dependencies before importing main
for _mod in ["yfinance", "aiohttp", "finnhub"]:
    if _mod not in sys.modules:
        sys.modules[_mod] = types.ModuleType(_mod)

for _full in ["scrapers.yahoo", "scrapers.alpha_vantage", "scrapers.finnhub"]:
    if _full not in sys.modules:
        _m = types.ModuleType(_full)

        async def _stub(*a, **kw):
            return None

        _m.fetch_yahoo = _stub
        _m.fetch_alpha_vantage = _stub
        _m.fetch_finnhub = _stub
        sys.modules[_full] = _m

from main import app  # noqa: E402
from database import get_db  # noqa: E402


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_session(
    symbol="AAPL",
    strategy="rsi",
    starting_capital=1000.0,
    created_at=None,
    closed_at=None,
):
    s = MagicMock()
    s.id = uuid.uuid4()
    s.symbol = symbol
    s.strategy = strategy
    s.strategy_params = {"period": 14, "overbought": 70, "oversold": 30}
    s.starting_capital = starting_capital
    s.created_at = created_at or datetime(2024, 1, 1, tzinfo=timezone.utc)
    s.closed_at = closed_at
    return s


def _make_bars(n: int = 50):
    bars = []
    for i in range(n):
        b = MagicMock()
        b.close = 100.0 + i * 0.1
        b.timestamp = f"2024-01-{(i % 28) + 1:02d}"
        bars.append(b)
    return bars


def _make_summary(sharpe=1.0, total_pnl=80.0, win_rate=0.6, num_trades=5):
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
def client_with_session(request):
    """Client fixture that accepts a session mock (or None for 404)."""
    session_mock = getattr(request, "param", _make_session())
    bars = _make_bars(50)

    async def override_get_db():
        mock_db = AsyncMock()

        def execute_side_effect(stmt):
            result = MagicMock()
            # First call → session lookup, second call → price history
            if not hasattr(execute_side_effect, "_count"):
                execute_side_effect._count = 0
            execute_side_effect._count += 1

            if execute_side_effect._count == 1:
                # Session query
                scalar_result = MagicMock()
                scalar_result.first.return_value = session_mock
                result.scalars.return_value = scalar_result
            else:
                # Price history query
                scalars_result = MagicMock()
                scalars_result.all.return_value = bars
                result.scalars.return_value = scalars_result
            return result

        mock_db.execute = AsyncMock(side_effect=execute_side_effect)
        yield mock_db

    app.dependency_overrides[get_db] = override_get_db
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture()
def client():
    """Client with a valid RSI session."""
    session = _make_session()
    bars = _make_bars(50)

    async def override_get_db():
        mock_db = AsyncMock()
        call_count = [0]

        async def execute_side_effect(stmt):
            call_count[0] += 1
            result = MagicMock()
            if call_count[0] == 1:
                scalar_result = MagicMock()
                scalar_result.first.return_value = session
                result.scalars.return_value = scalar_result
            else:
                scalars_result = MagicMock()
                scalars_result.all.return_value = bars
                result.scalars.return_value = scalars_result
            return result

        mock_db.execute = execute_side_effect
        yield mock_db

    app.dependency_overrides[get_db] = override_get_db
    yield TestClient(app)
    app.dependency_overrides.clear()


SESSION_ID = str(uuid.uuid4())
OPTIMIZE_URL = f"/sessions/{SESSION_ID}/optimize"


# ---------------------------------------------------------------------------
# 404 — session not found
# ---------------------------------------------------------------------------

def test_optimize_returns_404_for_unknown_session():
    async def override_get_db():
        mock_db = AsyncMock()

        async def execute_side_effect(stmt):
            result = MagicMock()
            scalar_result = MagicMock()
            scalar_result.first.return_value = None
            result.scalars.return_value = scalar_result
            return result

        mock_db.execute = execute_side_effect
        yield mock_db

    app.dependency_overrides[get_db] = override_get_db
    c = TestClient(app)
    resp = c.post(OPTIMIZE_URL, json={"param_grid": {"period": [7, 14]}, "metric": "sharpe"})
    app.dependency_overrides.clear()
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# 400 — too many combinations
# ---------------------------------------------------------------------------

def test_optimize_rejects_over_100_combinations(client):
    with patch("routers.optimizer.BacktestRunner.run", return_value=[]), \
         patch("routers.optimizer.compute_period_summary", return_value=_make_summary()):
        resp = client.post(OPTIMIZE_URL, json={
            "param_grid": {
                "period": list(range(11)),     # 11 values
                "overbought": list(range(10)), # 10 values → 110 combos
            },
            "metric": "sharpe",
        })
    assert resp.status_code == 400
    assert "100" in resp.json()["detail"]


def test_optimize_accepts_exactly_100_combinations(client):
    with patch("routers.optimizer.BacktestRunner.run", return_value=[]), \
         patch("routers.optimizer.compute_period_summary", return_value=_make_summary()):
        resp = client.post(OPTIMIZE_URL, json={
            "param_grid": {
                "period": list(range(10)),     # 10 × 10 = 100
                "overbought": list(range(10)),
            },
            "metric": "sharpe",
        })
    assert resp.status_code == 200
    assert resp.json()["iterations_run"] == 100


# ---------------------------------------------------------------------------
# Response shape
# ---------------------------------------------------------------------------

def test_optimize_response_contains_required_top_level_fields(client):
    with patch("routers.optimizer.BacktestRunner.run", return_value=[]), \
         patch("routers.optimizer.compute_period_summary", return_value=_make_summary(sharpe=1.5)):
        resp = client.post(OPTIMIZE_URL, json={
            "param_grid": {"period": [7, 14]},
            "metric": "sharpe",
        })
    assert resp.status_code == 200
    data = resp.json()
    assert "results" in data
    assert "best_params" in data
    assert "iterations_run" in data


def test_optimize_result_items_have_correct_fields(client):
    with patch("routers.optimizer.BacktestRunner.run", return_value=[]), \
         patch("routers.optimizer.compute_period_summary", return_value=_make_summary(sharpe=1.5)):
        resp = client.post(OPTIMIZE_URL, json={
            "param_grid": {"period": [14]},
            "metric": "sharpe",
        })
    assert resp.status_code == 200
    item = resp.json()["results"][0]
    assert "params" in item
    assert "sharpe" in item
    assert "total_return" in item
    assert "win_rate" in item


def test_optimize_iterations_run_matches_grid_size(client):
    with patch("routers.optimizer.BacktestRunner.run", return_value=[]), \
         patch("routers.optimizer.compute_period_summary", return_value=_make_summary()):
        resp = client.post(OPTIMIZE_URL, json={
            "param_grid": {"period": [7, 9, 14], "overbought": [70, 75]},
            "metric": "sharpe",
        })
    assert resp.status_code == 200
    assert resp.json()["iterations_run"] == 6


def test_optimize_params_reflected_in_results(client):
    with patch("routers.optimizer.BacktestRunner.run", return_value=[]), \
         patch("routers.optimizer.compute_period_summary", return_value=_make_summary()):
        resp = client.post(OPTIMIZE_URL, json={
            "param_grid": {"period": [7, 14]},
            "metric": "sharpe",
        })
    assert resp.status_code == 200
    periods = {r["params"]["period"] for r in resp.json()["results"]}
    assert periods == {7, 14}


# ---------------------------------------------------------------------------
# Metric sorting
# ---------------------------------------------------------------------------

def test_optimize_sorts_by_sharpe_descending(client):
    sharpe_values = iter([0.5, 2.0, 1.5])

    def mock_summary(*args, **kwargs):
        return _make_summary(sharpe=next(sharpe_values))

    with patch("routers.optimizer.BacktestRunner.run", return_value=[]), \
         patch("routers.optimizer.compute_period_summary", side_effect=mock_summary):
        resp = client.post(OPTIMIZE_URL, json={
            "param_grid": {"period": [7, 9, 14]},
            "metric": "sharpe",
        })
    assert resp.status_code == 200
    ratios = [r["sharpe"] for r in resp.json()["results"] if r["sharpe"] is not None]
    assert ratios == sorted(ratios, reverse=True)


def test_optimize_sorts_by_total_return_descending(client):
    pnl_values = iter([50.0, 200.0, 100.0])

    def mock_summary(*args, **kwargs):
        return _make_summary(total_pnl=next(pnl_values))

    with patch("routers.optimizer.BacktestRunner.run", return_value=[]), \
         patch("routers.optimizer.compute_period_summary", side_effect=mock_summary):
        resp = client.post(OPTIMIZE_URL, json={
            "param_grid": {"period": [7, 9, 14]},
            "metric": "total_return",
        })
    assert resp.status_code == 200
    returns = [r["total_return"] for r in resp.json()["results"]]
    assert returns == sorted(returns, reverse=True)


def test_optimize_sorts_by_win_rate_descending(client):
    wr_values = iter([0.4, 0.7, 0.55])

    def mock_summary(*args, **kwargs):
        return _make_summary(win_rate=next(wr_values))

    with patch("routers.optimizer.BacktestRunner.run", return_value=[]), \
         patch("routers.optimizer.compute_period_summary", side_effect=mock_summary):
        resp = client.post(OPTIMIZE_URL, json={
            "param_grid": {"period": [7, 9, 14]},
            "metric": "win_rate",
        })
    assert resp.status_code == 200
    rates = [r["win_rate"] for r in resp.json()["results"]]
    assert rates == sorted(rates, reverse=True)


# ---------------------------------------------------------------------------
# best_params
# ---------------------------------------------------------------------------

def test_optimize_best_params_matches_top_result_by_sharpe(client):
    sharpe_values = iter([0.5, 2.0, 1.5])

    def mock_summary(*args, **kwargs):
        return _make_summary(sharpe=next(sharpe_values))

    with patch("routers.optimizer.BacktestRunner.run", return_value=[]), \
         patch("routers.optimizer.compute_period_summary", side_effect=mock_summary):
        resp = client.post(OPTIMIZE_URL, json={
            "param_grid": {"period": [7, 9, 14]},
            "metric": "sharpe",
        })
    assert resp.status_code == 200
    data = resp.json()
    assert data["best_params"] == data["results"][0]["params"]


# ---------------------------------------------------------------------------
# total_return is a ratio, not absolute PnL
# ---------------------------------------------------------------------------

def test_optimize_total_return_is_ratio_not_absolute(client):
    """total_return must equal total_pnl / starting_capital."""
    with patch("routers.optimizer.BacktestRunner.run", return_value=[]), \
         patch("routers.optimizer.compute_period_summary", return_value=_make_summary(total_pnl=100.0)):
        resp = client.post(OPTIMIZE_URL, json={
            "param_grid": {"period": [14]},
            "metric": "sharpe",
        })
    assert resp.status_code == 200
    item = resp.json()["results"][0]
    # starting_capital=1000, total_pnl=100 → total_return=0.1
    assert abs(item["total_return"] - 0.1) < 1e-6


# ---------------------------------------------------------------------------
# Default metric (sharpe when not specified)
# ---------------------------------------------------------------------------

def test_optimize_defaults_to_sharpe_when_metric_omitted(client):
    sharpe_values = iter([0.5, 2.0])

    def mock_summary(*args, **kwargs):
        return _make_summary(sharpe=next(sharpe_values))

    with patch("routers.optimizer.BacktestRunner.run", return_value=[]), \
         patch("routers.optimizer.compute_period_summary", side_effect=mock_summary):
        # No "metric" field → defaults to sharpe
        resp = client.post(OPTIMIZE_URL, json={
            "param_grid": {"period": [7, 14]},
        })
    assert resp.status_code == 200
    # Best result should be the one with sharpe=2.0
    assert resp.json()["results"][0]["sharpe"] == 2.0


# ---------------------------------------------------------------------------
# None sharpe sorted last
# ---------------------------------------------------------------------------

def test_optimize_none_sharpe_sorted_last_when_metric_sharpe(client):
    sharpe_values = iter([None, 1.5, None])

    def mock_summary(*args, **kwargs):
        return _make_summary(sharpe=next(sharpe_values))

    with patch("routers.optimizer.BacktestRunner.run", return_value=[]), \
         patch("routers.optimizer.compute_period_summary", side_effect=mock_summary):
        resp = client.post(OPTIMIZE_URL, json={
            "param_grid": {"period": [7, 9, 14]},
            "metric": "sharpe",
        })
    assert resp.status_code == 200
    results = resp.json()["results"]
    assert results[0]["sharpe"] == 1.5
    assert results[1]["sharpe"] is None
    assert results[2]["sharpe"] is None
