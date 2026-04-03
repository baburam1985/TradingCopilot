import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import Reports from "./Reports";
import * as client from "../api/client";

vi.mock("../api/client");

// Silence Recharts ResizeObserver warnings in jsdom
vi.mock("recharts", async () => {
  const actual = await vi.importActual("recharts");
  return {
    ...actual,
    ResponsiveContainer: ({ children }) => (
      <div style={{ width: 500, height: 300 }}>{children}</div>
    ),
  };
});

// Mock sub-components that rely on complex DOM/canvas APIs
vi.mock("../components/EquityCurveChart", () => ({
  default: () => <div data-testid="equity-curve-chart" />,
}));
vi.mock("../components/PnLChart", () => ({
  default: () => <div data-testid="pnl-chart" />,
}));
vi.mock("../components/ComparisonView", () => ({
  default: () => <div data-testid="comparison-view" />,
}));
vi.mock("../components/TradeLog", () => ({
  default: () => <div data-testid="trade-log" />,
}));

const BACKTEST_META = {
  symbol: "AAPL",
  start_date: "2023-01-01",
  end_date: "2023-06-01",
  starting_capital: 1000,
};

const BACKTEST_RESULT = {
  trades: [
    {
      id: "t1",
      status: "closed",
      pnl: 50,
      timestamp_open: "2023-01-10T10:00:00Z",
      timestamp_close: "2023-01-15T10:00:00Z",
    },
  ],
  summary: {
    starting_capital: 1000,
    total_pnl: 50,
    win_rate: 1.0,
    sharpe_ratio: 1.5,
    num_trades: 1,
  },
};

const BENCHMARK_DATA = {
  symbol: "AAPL",
  start_date: "2023-01-01",
  end_date: "2023-06-01",
  starting_capital: 1000,
  bnh_return_pct: 0.12,
  bnh_final_value: 1120,
  bnh_equity_curve: [
    { timestamp: "2023-01-10T00:00:00Z", value: 1000 },
    { timestamp: "2023-06-01T00:00:00Z", value: 1120 },
  ],
};

function renderReportsWithBacktest(backtestMeta = BACKTEST_META) {
  return render(
    <MemoryRouter
      initialEntries={[
        { pathname: "/reports", state: { backtestResult: BACKTEST_RESULT, backtestMeta } },
      ]}
    >
      <Reports />
    </MemoryRouter>
  );
}

function renderReportsNormal() {
  client.getSessions.mockResolvedValue({ data: [] });
  return render(
    <MemoryRouter initialEntries={[{ pathname: "/reports", state: null }]}>
      <Reports />
    </MemoryRouter>
  );
}

describe("Reports — Backtest view with Benchmark panel", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    client.getBenchmark.mockResolvedValue({ data: BENCHMARK_DATA });
  });

  it("renders the backtest results heading", () => {
    renderReportsWithBacktest();
    expect(screen.getByText("Backtest Results")).toBeInTheDocument();
  });

  it("fetches the benchmark using backtestMeta fields", async () => {
    renderReportsWithBacktest();
    await waitFor(() => {
      expect(client.getBenchmark).toHaveBeenCalledWith(
        "AAPL",
        "2023-01-01",
        "2023-06-01",
        1000
      );
    });
  });

  it("renders the Buy & Hold Benchmark panel after data loads", async () => {
    renderReportsWithBacktest();
    await waitFor(() => {
      expect(screen.getByText("Buy & Hold Benchmark")).toBeInTheDocument();
    });
  });

  it("shows BnH return percentage", async () => {
    renderReportsWithBacktest();
    await waitFor(() => {
      // 0.12 * 100 = 12.00%
      expect(screen.getByText("+12.00%")).toBeInTheDocument();
    });
  });

  it("shows BnH final value", async () => {
    renderReportsWithBacktest();
    await waitFor(() => {
      expect(screen.getByText("$1120.00")).toBeInTheDocument();
    });
  });

  it("does not fetch benchmark when backtestMeta is missing", () => {
    render(
      <MemoryRouter
        initialEntries={[{ pathname: "/reports", state: { backtestResult: BACKTEST_RESULT } }]}
      >
        <Reports />
      </MemoryRouter>
    );
    expect(client.getBenchmark).not.toHaveBeenCalled();
  });

  it("does not show benchmark panel when getBenchmark fails", async () => {
    client.getBenchmark.mockRejectedValue(new Error("Network error"));
    renderReportsWithBacktest();
    // Panel should not appear
    await waitFor(() => {
      expect(screen.queryByText("Buy & Hold Benchmark")).not.toBeInTheDocument();
    });
  });
});

describe("Reports — Normal tabbed view", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    client.getSessions.mockResolvedValue({ data: [] });
  });

  it("renders the ANALYTICS and SESSION REPORT tabs", async () => {
    renderReportsNormal();
    await waitFor(() => {
      expect(screen.getByText("ANALYTICS")).toBeInTheDocument();
      expect(screen.getByText("SESSION REPORT")).toBeInTheDocument();
    });
  });
});
