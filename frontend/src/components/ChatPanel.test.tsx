import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ChatPanel } from "@/components/ChatPanel";
import { chatHistoryFixture, portfolioFixture, watchlistFixture } from "@/test/fixtures";
import { renderWithProviders } from "@/test/harness";
import type { ChatEntry } from "@/state/ChatProvider";

const mocks = vi.hoisted(() => ({
  sendChat: vi.fn(),
  getPortfolio: vi.fn(),
  getWatchlist: vi.fn(),
  getPortfolioHistory: vi.fn(),
}));

vi.mock("@/lib/api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/api")>();
  return { ...actual, api: { ...actual.api, ...mocks } };
});

const historyEntries: ChatEntry[] = chatHistoryFixture.messages.map((message) => ({ ...message }));

beforeEach(() => {
  Object.values(mocks).forEach((mock) => mock.mockReset());
  mocks.getPortfolio.mockResolvedValue(portfolioFixture);
  mocks.getWatchlist.mockResolvedValue({ tickers: watchlistFixture });
  mocks.getPortfolioHistory.mockResolvedValue({ snapshots: [] });
});

describe("ChatPanel", () => {
  it("renders stored history with both roles", () => {
    renderWithProviders(<ChatPanel />, { chatEntries: historyEntries });

    expect(screen.getByText("buy me 10 apple shares")).toBeInTheDocument();
    expect(
      screen.getByText("Bought 10 AAPL at $192.50. That's 19% of your portfolio."),
    ).toBeInTheDocument();
  });

  it("renders executed actions inline as confirmations", () => {
    renderWithProviders(<ChatPanel />, { chatEntries: historyEntries });

    expect(screen.getByText("Bought 10 AAPL at $192.50")).toBeInTheDocument();
    expect(screen.getByText("Added PYPL to the watchlist")).toBeInTheDocument();
  });

  it("renders a failed action with its reason instead of hiding it", () => {
    renderWithProviders(<ChatPanel />, { chatEntries: historyEntries });

    const failure = screen.getByText("Buy 100 TSLA rejected");
    expect(failure).toBeInTheDocument();
    expect(failure.closest("li")).toHaveAttribute("data-status", "failed");
    expect(screen.getByText("Need $24500.00, have $8075.00")).toBeInTheDocument();
  });

  it("offers an opening move when there is no conversation yet", () => {
    renderWithProviders(<ChatPanel />, { chatEntries: [] });
    expect(screen.getByText("Ask about your book")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Buy 10 shares of NVDA" })).toBeInTheDocument();
  });

  it("shows the thinking indicator for the whole round trip", async () => {
    const user = userEvent.setup();
    let resolve: (value: unknown) => void = () => {};
    mocks.sendChat.mockImplementation(
      () =>
        new Promise((r) => {
          resolve = r;
        }),
    );

    renderWithProviders(<ChatPanel />, { chatEntries: [] });

    await user.type(screen.getByLabelText("Message FinAlly"), "how am I doing?");
    await user.click(screen.getByRole("button", { name: "Send" }));

    expect(await screen.findByText("Thinking…")).toBeInTheDocument();
    expect(screen.getByText("how am I doing?")).toBeInTheDocument();

    resolve({
      id: "m9",
      message: "Up 1.2% on the day.",
      actions: { trades: [], watchlist_changes: [] },
      created_at: "2026-10-01T14:40:00.000Z",
    });

    expect(await screen.findByText("Up 1.2% on the day.")).toBeInTheDocument();
    await waitFor(() => expect(screen.queryByText("Thinking…")).not.toBeInTheDocument());
  });

  it("re-reads portfolio state after the assistant executes a trade", async () => {
    const user = userEvent.setup();
    mocks.sendChat.mockResolvedValue({
      id: "m10",
      message: "Bought 2 NVDA.",
      actions: {
        trades: [
          { ticker: "NVDA", side: "buy", quantity: 2, status: "executed", price: 121.4, error: null },
        ],
        watchlist_changes: [],
      },
      created_at: "2026-10-01T14:41:00.000Z",
    });

    renderWithProviders(<ChatPanel />, { chatEntries: [] });

    await user.type(screen.getByLabelText("Message FinAlly"), "buy 2 nvda");
    await user.click(screen.getByRole("button", { name: "Send" }));

    // The SSE stream carries prices only — cash and positions have to be re-fetched.
    await waitFor(() => expect(mocks.getPortfolio).toHaveBeenCalled());
    await waitFor(() => expect(mocks.getWatchlist).toHaveBeenCalled());
  });

  it("reports a failed request in the log rather than losing the message", async () => {
    const user = userEvent.setup();
    const { ApiError } = await import("@/lib/api");
    mocks.sendChat.mockRejectedValue(new ApiError("LLM_ERROR", "The model is unreachable.", 503));

    renderWithProviders(<ChatPanel />, { chatEntries: [] });

    await user.type(screen.getByLabelText("Message FinAlly"), "hello");
    await user.click(screen.getByRole("button", { name: "Send" }));

    expect(await screen.findByText("The model is unreachable.")).toBeInTheDocument();
  });
});
