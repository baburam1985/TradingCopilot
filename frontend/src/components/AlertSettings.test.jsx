import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import AlertSettings from "./AlertSettings";
import * as client from "../api/client";

vi.mock("../api/client");

const SESSION = {
  id: "session-abc",
  symbol: "AAPL",
  strategy: "momentum",
  mode: "paper",
  status: "active",
  starting_capital: 1000,
  notify_email: true,
  email_address: "trader@example.com",
};

const SESSION_NO_EMAIL = {
  ...SESSION,
  notify_email: false,
  email_address: null,
};

describe("AlertSettings", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    client.updateSession.mockResolvedValue({ data: SESSION });
  });

  it("renders with existing alert data", () => {
    render(<AlertSettings session={SESSION} />);
    expect(screen.getByTestId("alert-settings")).toBeInTheDocument();
    expect(screen.getByTestId("email-toggle")).toBeChecked();
    expect(screen.getByTestId("email-input")).toHaveValue("trader@example.com");
  });

  it("renders with no email pre-filled when session has no email", () => {
    render(<AlertSettings session={SESSION_NO_EMAIL} />);
    expect(screen.getByTestId("email-toggle")).not.toBeChecked();
    expect(screen.queryByTestId("email-input")).not.toBeInTheDocument();
  });

  it("shows email input when email toggle is checked", () => {
    render(<AlertSettings session={SESSION_NO_EMAIL} />);
    fireEvent.click(screen.getByTestId("email-toggle"));
    expect(screen.getByTestId("email-input")).toBeInTheDocument();
  });

  it("hides email input when email toggle is unchecked", () => {
    render(<AlertSettings session={SESSION} />);
    expect(screen.getByTestId("email-input")).toBeInTheDocument();
    fireEvent.click(screen.getByTestId("email-toggle"));
    expect(screen.queryByTestId("email-input")).not.toBeInTheDocument();
  });

  it("renders price above/below toggles", () => {
    render(<AlertSettings session={SESSION} />);
    expect(screen.getByTestId("price-above-toggle")).toBeInTheDocument();
    expect(screen.getByTestId("price-below-toggle")).toBeInTheDocument();
  });

  it("shows price-above input when toggle is checked", () => {
    render(<AlertSettings session={SESSION} />);
    expect(screen.queryByTestId("price-above-input")).not.toBeInTheDocument();
    fireEvent.click(screen.getByTestId("price-above-toggle"));
    expect(screen.getByTestId("price-above-input")).toBeInTheDocument();
  });

  it("shows price-below input when toggle is checked", () => {
    render(<AlertSettings session={SESSION} />);
    expect(screen.queryByTestId("price-below-input")).not.toBeInTheDocument();
    fireEvent.click(screen.getByTestId("price-below-toggle"));
    expect(screen.getByTestId("price-below-input")).toBeInTheDocument();
  });

  it("renders signal alerts toggle", () => {
    render(<AlertSettings session={SESSION} />);
    expect(screen.getByTestId("signal-alerts-toggle")).toBeInTheDocument();
    expect(screen.getByTestId("signal-alerts-toggle")).not.toBeChecked();
  });

  it("calls updateSession with correct data on save", async () => {
    render(<AlertSettings session={SESSION} />);
    fireEvent.click(screen.getByTestId("save-btn"));
    await waitFor(() => {
      expect(client.updateSession).toHaveBeenCalledWith(SESSION.id, {
        notify_email: true,
        email_address: "trader@example.com",
      });
    });
  });

  it("shows Saved message after successful save", async () => {
    render(<AlertSettings session={SESSION} />);
    fireEvent.click(screen.getByTestId("save-btn"));
    await waitFor(() => {
      expect(screen.getByTestId("save-msg")).toHaveTextContent("Saved");
    });
  });

  it("shows push enable button when Notification permission is default", () => {
    Object.defineProperty(window, "Notification", {
      value: { permission: "default", requestPermission: vi.fn() },
      writable: true,
      configurable: true,
    });
    render(<AlertSettings session={SESSION} />);
    expect(screen.getByTestId("push-enable-btn")).toBeInTheDocument();
  });

  it("shows push active status when Notification permission is granted", () => {
    Object.defineProperty(window, "Notification", {
      value: { permission: "granted", requestPermission: vi.fn() },
      writable: true,
      configurable: true,
    });
    render(<AlertSettings session={SESSION} />);
    expect(screen.getByTestId("push-status-active")).toBeInTheDocument();
  });

  it("shows push denied message when permission is denied", () => {
    Object.defineProperty(window, "Notification", {
      value: { permission: "denied", requestPermission: vi.fn() },
      writable: true,
      configurable: true,
    });
    render(<AlertSettings session={SESSION} />);
    expect(screen.getByTestId("push-status-denied")).toBeInTheDocument();
  });
});
