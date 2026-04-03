import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import Watchlist from "./Watchlist";
import * as client from "../api/client";

vi.mock("../api/client");

const SESSIONS = [
  {
    id: "session-1",
    symbol: "AAPL",
    strategy: "momentum",
    mode: "paper",
    status: "active",
    starting_capital: 1000,
  },
  {
    id: "session-2",
    symbol: "TSLA",
    strategy: "mean_reversion",
    mode: "alpaca_live",
    status: "active",
    starting_capital: 500,
  },
];

const PNL_POSITIVE = { all_time: { total_pnl: 42.5, win_rate: 0.6 } };
const PNL_NEGATIVE = { all_time: { total_pnl: -18.3, win_rate: 0.3 } };

function renderWatchlist() {
  return render(
    <MemoryRouter>
      <Watchlist />
    </MemoryRouter>
  );
}

describe("Watchlist", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    client.getSessions.mockResolvedValue({ data: SESSIONS });
    client.getPnl.mockImplementation((id) =>
      id === "session-1"
        ? Promise.resolve({ data: PNL_POSITIVE })
        : Promise.resolve({ data: PNL_NEGATIVE })
    );
  });

  it("renders a card for each session", async () => {
    renderWatchlist();
    await waitFor(() => {
      const cards = screen.getAllByTestId("session-card");
      expect(cards).toHaveLength(SESSIONS.length);
    });
  });

  it("shows session symbols on the cards", async () => {
    renderWatchlist();
    await waitFor(() => {
      expect(screen.getByText("AAPL")).toBeInTheDocument();
      expect(screen.getByText("TSLA")).toBeInTheDocument();
    });
  });

  it("shows paper badge for paper mode sessions", async () => {
    renderWatchlist();
    await waitFor(() => {
      expect(screen.getByText("AAPL")).toBeInTheDocument();
    });
    expect(screen.getAllByText("Paper").length).toBeGreaterThan(0);
  });

  it("shows live badge for live mode sessions", async () => {
    renderWatchlist();
    await waitFor(() => {
      expect(screen.getByText("TSLA")).toBeInTheDocument();
    });
    expect(screen.getAllByText("Live").length).toBeGreaterThan(0);
  });

  it("renders positive P&L in green", async () => {
    renderWatchlist();
    await waitFor(() => {
      const pnlValues = screen.getAllByTestId("pnl-value");
      const positive = pnlValues.find((el) => el.textContent === "$42.50");
      expect(positive).toBeDefined();
      expect(positive.className).toContain("text-[#00e676]");
    });
  });

  it("renders negative P&L in red", async () => {
    renderWatchlist();
    await waitFor(() => {
      const pnlValues = screen.getAllByTestId("pnl-value");
      const negative = pnlValues.find((el) => el.textContent === "$-18.30");
      expect(negative).toBeDefined();
      expect(negative.className).toContain("text-[#ff4444]");
    });
  });

  it("shows a message when there are no sessions", async () => {
    client.getSessions.mockResolvedValue({ data: [] });
    renderWatchlist();
    await waitFor(() => {
      expect(
        screen.getByText(/no sessions found/i)
      ).toBeInTheDocument();
    });
  });
});
