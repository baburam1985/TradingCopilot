import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import OptimizeHeatmap from "./OptimizeHeatmap";

// 2x2 grid: short_window (10, 20) x long_window (50, 100)
const RESULTS = [
  { parameters: { short_window: 10, long_window: 50 }, sharpe_ratio: 1.5, total_pnl: 200, win_rate: 0.6, num_trades: 10 },
  { parameters: { short_window: 10, long_window: 100 }, sharpe_ratio: 0.5, total_pnl: 50, win_rate: 0.4, num_trades: 8 },
  { parameters: { short_window: 20, long_window: 50 }, sharpe_ratio: -0.2, total_pnl: -30, win_rate: 0.3, num_trades: 6 },
  { parameters: { short_window: 20, long_window: 100 }, sharpe_ratio: 0.8, total_pnl: 80, win_rate: 0.5, num_trades: 12 },
];

// Single combination — no meaningful heatmap axes
const SINGLE_RESULT = [
  { parameters: { short_window: 10, long_window: 50 }, sharpe_ratio: 1.2, total_pnl: 100, win_rate: 0.6, num_trades: 5 },
];

describe("OptimizeHeatmap", () => {
  it("renders the heatmap container", () => {
    render(<OptimizeHeatmap results={RESULTS} />);
    expect(screen.getByTestId("optimize-heatmap")).toBeInTheDocument();
  });

  it("renders a heatmap grid when two multi-value params exist", () => {
    render(<OptimizeHeatmap results={RESULTS} />);
    expect(screen.getByTestId("heatmap-grid")).toBeInTheDocument();
  });

  it("renders the correct number of cells", () => {
    render(<OptimizeHeatmap results={RESULTS} />);
    // 2 x_vals × 2 y_vals = 4 cells
    expect(screen.getAllByTestId(/heatmap-cell-/).length).toBe(4);
  });

  it("renders the best parameters card", () => {
    render(<OptimizeHeatmap results={RESULTS} />);
    expect(screen.getByTestId("best-params-card")).toBeInTheDocument();
  });

  it("best params card shows highest sharpe parameters", () => {
    render(<OptimizeHeatmap results={RESULTS} />);
    // Best is short_window=10, long_window=50 (sharpe=1.5)
    const card = screen.getByTestId("best-params-card");
    expect(card.textContent).toContain("10");
    expect(card.textContent).toContain("50");
  });

  it("the best cell has a star indicator", () => {
    render(<OptimizeHeatmap results={RESULTS} />);
    // Best cell: short_window x=10, long_window y=50
    const bestCell = screen.getByTestId("heatmap-cell-10-50");
    expect(bestCell.textContent).toContain("★");
  });

  it("heatmap cell for worst result has lowest normalized value", () => {
    render(<OptimizeHeatmap results={RESULTS} />);
    const worstCell = screen.getByTestId("heatmap-cell-20-50"); // sharpe=-0.2, lowest
    const norm = parseFloat(worstCell.getAttribute("data-norm"));
    expect(norm).toBeLessThan(0.1); // normalized to near 0 (red end)
  });

  it("heatmap cell for best result has highest normalized value", () => {
    render(<OptimizeHeatmap results={RESULTS} />);
    const bestCell = screen.getByTestId("heatmap-cell-10-50"); // sharpe=1.5, highest
    const norm = parseFloat(bestCell.getAttribute("data-norm"));
    expect(norm).toBeGreaterThan(0.9); // normalized to near 1 (green end)
  });

  it("shows no-data message when results is empty", () => {
    render(<OptimizeHeatmap results={[]} />);
    expect(screen.getByTestId("optimize-heatmap")).toBeInTheDocument();
    expect(screen.queryByTestId("heatmap-grid")).not.toBeInTheDocument();
  });

  it("falls back gracefully with a single result (no heatmap grid possible)", () => {
    render(<OptimizeHeatmap results={SINGLE_RESULT} />);
    expect(screen.getByTestId("optimize-heatmap")).toBeInTheDocument();
    expect(screen.getByTestId("best-params-card")).toBeInTheDocument();
  });
});
