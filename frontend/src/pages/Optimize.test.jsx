import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import userEvent from "@testing-library/user-event";
import Optimize from "./Optimize";
import * as client from "../api/client";

vi.mock("../api/client");
vi.mock("../components/OptimizeHeatmap", () => ({
  default: () => <div data-testid="optimize-heatmap" />,
}));

const STRATEGIES = [
  {
    name: "momentum",
    parameters: {
      short_window: { type: "int", default: 10, description: "Short window" },
      long_window: { type: "int", default: 50, description: "Long window" },
    },
  },
  {
    name: "mean_reversion",
    parameters: {
      window: { type: "int", default: 20, description: "Lookback window" },
    },
  },
];

function renderOptimize() {
  return render(
    <MemoryRouter>
      <Optimize />
    </MemoryRouter>
  );
}

describe("Optimize page", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    client.getStrategies.mockResolvedValue({ data: STRATEGIES });
  });

  it("renders the OPTIMIZE and WALK-FORWARD tabs", async () => {
    renderOptimize();
    await waitFor(() => {
      expect(screen.getByText("OPTIMIZE")).toBeInTheDocument();
      expect(screen.getByText("WALK-FORWARD")).toBeInTheDocument();
    });
  });

  it("shows the optimizer form by default", async () => {
    renderOptimize();
    await waitFor(() => {
      expect(screen.getByText("Run Optimization")).toBeInTheDocument();
    });
  });

  it("switches to walk-forward form when tab is clicked", async () => {
    renderOptimize();
    await waitFor(() => screen.getByText("WALK-FORWARD"));
    fireEvent.click(screen.getByText("WALK-FORWARD"));
    expect(screen.getByText("Run Walk-Forward Analysis")).toBeInTheDocument();
  });

  it("walk-forward form renders window configuration fields", async () => {
    renderOptimize();
    await waitFor(() => screen.getByText("WALK-FORWARD"));
    fireEvent.click(screen.getByText("WALK-FORWARD"));
    expect(screen.getByText("Window Configuration")).toBeInTheDocument();
    // Labels appear as text within the DOM
    expect(screen.getAllByText(/Train Window/i).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/Test Window/i).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/Step Size/i).length).toBeGreaterThan(0);
  });

  it("walk-forward shows parameter grid section for strategy with params", async () => {
    renderOptimize();
    await waitFor(() => screen.getByText("WALK-FORWARD"));
    fireEvent.click(screen.getByText("WALK-FORWARD"));
    expect(screen.getByText(/Parameter Grid/i)).toBeInTheDocument();
  });

  it("calls runWalkForward with correct payload on submit", async () => {
    const WALK_FORWARD_RESULT = {
      windows: [
        {
          window_index: 0,
          train_start: "2023-01-01",
          train_end: "2023-03-01",
          test_start: "2023-03-01",
          test_end: "2023-04-01",
          best_params: { short_window: 10, long_window: 50 },
          train_sharpe: 1.2,
          test_sharpe: 0.9,
          test_pnl: 45.0,
          test_win_rate: 0.55,
          test_num_trades: 8,
          test_max_drawdown_pct: 5.2,
        },
      ],
      aggregate: {
        num_windows: 1,
        avg_test_sharpe: 0.9,
        avg_test_pnl: 45.0,
        avg_test_win_rate: 0.55,
        consistency_score: 1.0,
        avg_train_sharpe: 1.2,
      },
    };
    client.runWalkForward.mockResolvedValue({ data: WALK_FORWARD_RESULT });

    renderOptimize();
    await waitFor(() => screen.getByText("WALK-FORWARD"));
    fireEvent.click(screen.getByText("WALK-FORWARD"));

    // Fill in required fields using placeholders
    fireEvent.change(screen.getByPlaceholderText("e.g. AAPL"), {
      target: { value: "AAPL" },
    });
    const dateInputs = screen
      .getAllByDisplayValue("")
      .filter((el) => el.type === "date");
    fireEvent.change(dateInputs[0], { target: { value: "2023-01-01" } });
    fireEvent.change(dateInputs[1], { target: { value: "2023-06-01" } });

    fireEvent.click(screen.getByText("Run Walk-Forward Analysis"));

    await waitFor(() => {
      expect(client.runWalkForward).toHaveBeenCalledOnce();
      const call = client.runWalkForward.mock.calls[0][0];
      expect(call.symbol).toBe("AAPL");
      expect(call.strategy).toBe("momentum");
    });
  });

  it("displays per-window table after successful walk-forward run", async () => {
    const WALK_FORWARD_RESULT = {
      windows: [
        {
          window_index: 0,
          train_start: "2023-01-01",
          train_end: "2023-03-01",
          test_start: "2023-03-01",
          test_end: "2023-04-01",
          best_params: { short_window: 10 },
          train_sharpe: 1.1,
          test_sharpe: 0.8,
          test_pnl: 30.0,
          test_win_rate: 0.5,
          test_num_trades: 6,
          test_max_drawdown_pct: 4.0,
        },
      ],
      aggregate: {
        num_windows: 1,
        avg_test_sharpe: 0.8,
        avg_test_pnl: 30.0,
        avg_test_win_rate: 0.5,
        consistency_score: 1.0,
        avg_train_sharpe: 1.1,
      },
    };
    client.runWalkForward.mockResolvedValue({ data: WALK_FORWARD_RESULT });

    renderOptimize();
    await waitFor(() => screen.getByText("WALK-FORWARD"));
    fireEvent.click(screen.getByText("WALK-FORWARD"));

    const symbolInput = screen.getByPlaceholderText("e.g. AAPL");
    fireEvent.change(symbolInput, { target: { value: "TSLA" } });
    const dateInputs = screen
      .getAllByDisplayValue("")
      .filter((el) => el.type === "date");
    fireEvent.change(dateInputs[0], { target: { value: "2023-01-01" } });
    fireEvent.change(dateInputs[1], { target: { value: "2023-06-01" } });

    fireEvent.click(screen.getByText("Run Walk-Forward Analysis"));

    await waitFor(() => {
      expect(screen.getByText("Per-Window Results")).toBeInTheDocument();
      expect(screen.getByText("Out-of-Sample Aggregate")).toBeInTheDocument();
    });
  });

  it("shows error message on walk-forward failure", async () => {
    client.runWalkForward.mockRejectedValue({
      response: { data: { detail: "No price data found for TEST." } },
    });

    renderOptimize();
    await waitFor(() => screen.getByText("WALK-FORWARD"));
    fireEvent.click(screen.getByText("WALK-FORWARD"));

    const symbolInput = screen.getByPlaceholderText("e.g. AAPL");
    fireEvent.change(symbolInput, { target: { value: "TEST" } });
    const dateInputs = screen
      .getAllByDisplayValue("")
      .filter((el) => el.type === "date");
    fireEvent.change(dateInputs[0], { target: { value: "2023-01-01" } });
    fireEvent.change(dateInputs[1], { target: { value: "2023-06-01" } });

    fireEvent.click(screen.getByText("Run Walk-Forward Analysis"));

    await waitFor(() => {
      expect(screen.getByText("No price data found for TEST.")).toBeInTheDocument();
    });
  });
});
