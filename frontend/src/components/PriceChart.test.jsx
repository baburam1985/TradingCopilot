import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import PriceChart from "./PriceChart";

// recharts uses ResizeObserver internally — polyfill for jsdom
global.ResizeObserver = class ResizeObserver {
  observe() {}
  unobserve() {}
  disconnect() {}
};

const BARS = [
  { timestamp: "2024-01-01T09:30:00Z", close: "150.00" },
  { timestamp: "2024-01-01T09:31:00Z", close: "151.00" },
  { timestamp: "2024-01-01T09:32:00Z", close: "152.00" },
];

const TRADES = [
  { action: "buy", timestamp_open: "2024-01-01T09:30:00Z" },
  { action: "sell", timestamp_open: "2024-01-01T09:32:00Z" },
];

const INDICATORS = {
  sma: [149.5, 150.5, 151.5],
  ema: [149.8, 150.8, 151.8],
  bollinger: {
    upper: [152, 153, 154],
    lower: [147, 148, 149],
    middle: [149.5, 150.5, 151.5],
  },
  rsi: [55, 58, 62],
  macd: {
    macd: [0.1, 0.15, 0.2],
    signal: [0.08, 0.12, 0.18],
    histogram: [0.02, 0.03, 0.02],
  },
};

describe("PriceChart", () => {
  it("renders without crashing with no indicator props", () => {
    render(<PriceChart bars={BARS} trades={TRADES} />);
    expect(screen.getByTestId("price-chart")).toBeInTheDocument();
  });

  it("renders without crashing with full indicator props", () => {
    render(
      <PriceChart
        bars={BARS}
        trades={TRADES}
        indicators={INDICATORS}
        activeIndicators={new Set(["sma", "ema", "bollinger", "rsi", "macd"])}
      />
    );
    expect(screen.getByTestId("price-chart")).toBeInTheDocument();
  });

  it("renders without crashing with empty bars and trades", () => {
    render(<PriceChart bars={[]} trades={[]} />);
    expect(screen.getByTestId("price-chart")).toBeInTheDocument();
  });

  it("shows all indicator toggle buttons", () => {
    render(<PriceChart bars={BARS} trades={TRADES} />);
    expect(screen.getByTestId("toggle-sma")).toBeInTheDocument();
    expect(screen.getByTestId("toggle-ema")).toBeInTheDocument();
    expect(screen.getByTestId("toggle-bollinger")).toBeInTheDocument();
    expect(screen.getByTestId("toggle-rsi")).toBeInTheDocument();
    expect(screen.getByTestId("toggle-macd")).toBeInTheDocument();
  });

  it("RSI panel is hidden when rsi is not active", () => {
    render(
      <PriceChart
        bars={BARS}
        trades={TRADES}
        indicators={INDICATORS}
        activeIndicators={new Set()}
      />
    );
    expect(screen.queryByTestId("rsi-panel")).not.toBeInTheDocument();
  });

  it("RSI panel is visible when rsi is active", () => {
    render(
      <PriceChart
        bars={BARS}
        trades={TRADES}
        indicators={INDICATORS}
        activeIndicators={new Set(["rsi"])}
      />
    );
    expect(screen.getByTestId("rsi-panel")).toBeInTheDocument();
  });

  it("MACD panel is hidden when macd is not active", () => {
    render(
      <PriceChart
        bars={BARS}
        trades={TRADES}
        indicators={INDICATORS}
        activeIndicators={new Set()}
      />
    );
    expect(screen.queryByTestId("macd-panel")).not.toBeInTheDocument();
  });

  it("MACD panel is visible when macd is active", () => {
    render(
      <PriceChart
        bars={BARS}
        trades={TRADES}
        indicators={INDICATORS}
        activeIndicators={new Set(["macd"])}
      />
    );
    expect(screen.getByTestId("macd-panel")).toBeInTheDocument();
  });

  it("calls onToggleIndicator when a toggle button is clicked", () => {
    const onToggle = vi.fn();
    render(
      <PriceChart
        bars={BARS}
        trades={TRADES}
        indicators={INDICATORS}
        activeIndicators={new Set()}
        onToggleIndicator={onToggle}
      />
    );
    fireEvent.click(screen.getByTestId("toggle-sma"));
    expect(onToggle).toHaveBeenCalledWith("sma");
  });

  it("manages toggle state locally when no onToggleIndicator is provided", () => {
    render(<PriceChart bars={BARS} trades={TRADES} indicators={INDICATORS} />);

    // RSI panel should not be visible initially
    expect(screen.queryByTestId("rsi-panel")).not.toBeInTheDocument();

    // Click RSI toggle to activate
    fireEvent.click(screen.getByTestId("toggle-rsi"));
    expect(screen.getByTestId("rsi-panel")).toBeInTheDocument();

    // Click again to deactivate
    fireEvent.click(screen.getByTestId("toggle-rsi"));
    expect(screen.queryByTestId("rsi-panel")).not.toBeInTheDocument();
  });

  it("MACD panel toggles on/off via local state", () => {
    render(<PriceChart bars={BARS} trades={TRADES} indicators={INDICATORS} />);

    expect(screen.queryByTestId("macd-panel")).not.toBeInTheDocument();
    fireEvent.click(screen.getByTestId("toggle-macd"));
    expect(screen.getByTestId("macd-panel")).toBeInTheDocument();
  });
});
