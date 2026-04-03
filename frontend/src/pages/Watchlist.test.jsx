import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import Watchlist from "./Watchlist";
import * as client from "../api/client";

vi.mock("../api/client");

// Provide a no-op NotificationContext so Watchlist can render in tests
vi.mock("../context/NotificationContext", () => ({
  useNotifications: () => ({ addNotification: vi.fn() }),
  NotificationProvider: ({ children }) => children,
}));

const WATCHLIST_ITEMS = [
  {
    id: "item-1",
    symbol: "AAPL",
    strategy: "momentum",
    last_signal: "buy",
    last_price: 150.25,
    alert_threshold: 145.0,
    created_at: "2023-01-10T00:00:00Z",
  },
  {
    id: "item-2",
    symbol: "TSLA",
    strategy: "mean_reversion",
    last_signal: "sell",
    last_price: 220.5,
    alert_threshold: null,
    created_at: "2023-02-01T00:00:00Z",
  },
];

const MOCK_WS = { close: vi.fn(), onmessage: null };

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
    client.getWatchlist.mockResolvedValue({ data: WATCHLIST_ITEMS });
    client.createWatchlistSocket.mockReturnValue(MOCK_WS);
    client.deleteWatchlistItem.mockResolvedValue({});
    client.createWatchlistItem.mockResolvedValue({ data: {} });
  });

  it("renders a row for each watchlist item", async () => {
    renderWatchlist();
    await waitFor(() => {
      expect(screen.getByText("AAPL")).toBeInTheDocument();
      expect(screen.getByText("TSLA")).toBeInTheDocument();
    });
  });

  it("shows the strategy for each item", async () => {
    renderWatchlist();
    await waitFor(() => {
      expect(screen.getByText("momentum")).toBeInTheDocument();
      expect(screen.getByText("mean_reversion")).toBeInTheDocument();
    });
  });

  it("renders buy and sell signal badges", async () => {
    renderWatchlist();
    await waitFor(() => {
      expect(screen.getByText("buy")).toBeInTheDocument();
      expect(screen.getByText("sell")).toBeInTheDocument();
    });
  });

  it("displays last price when available", async () => {
    renderWatchlist();
    await waitFor(() => {
      expect(screen.getByText("$150.25")).toBeInTheDocument();
      expect(screen.getByText("$220.50")).toBeInTheDocument();
    });
  });

  it("shows a message when the watchlist is empty", async () => {
    client.getWatchlist.mockResolvedValue({ data: [] });
    renderWatchlist();
    await waitFor(() => {
      expect(screen.getByText(/No symbols on your watchlist/i)).toBeInTheDocument();
    });
  });

  it("renders Remove buttons for each item", async () => {
    renderWatchlist();
    await waitFor(() => {
      const removeButtons = screen.getAllByText("Remove");
      expect(removeButtons).toHaveLength(WATCHLIST_ITEMS.length);
    });
  });

  it("shows page heading", async () => {
    renderWatchlist();
    expect(screen.getByText("Watchlist")).toBeInTheDocument();
  });
});
