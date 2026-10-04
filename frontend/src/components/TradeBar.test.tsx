import { act, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { TradeBar } from "@/components/TradeBar";
import { PriceStore } from "@/lib/priceStore";
import { portfolioFixture, priceUpdate, watchlistFixture } from "@/test/fixtures";
import { renderWithProviders } from "@/test/harness";

const mocks = vi.hoisted(() => ({
  trade: vi.fn(),
  getPortfolio: vi.fn(),
  getWatchlist: vi.fn(),
  getPortfolioHistory: vi.fn(),
}));

vi.mock("@/lib/api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/api")>();
  return { ...actual, api: { ...actual.api, ...mocks } };
});

beforeEach(() => {
  Object.values(mocks).forEach((mock) => mock.mockReset());
  mocks.getPortfolio.mockResolvedValue(portfolioFixture);
  mocks.getWatchlist.mockResolvedValue({ tickers: watchlistFixture });
  mocks.getPortfolioHistory.mockResolvedValue({ snapshots: [] });
});

describe("TradeBar", () => {
  it("arms itself with the symbol selected elsewhere on the terminal", () => {
    renderWithProviders(<TradeBar />, { watchlist: watchlistFixture });
    expect(screen.getByLabelText("Sym")).toHaveValue("AAPL");
  });

  it("keeps both sides disabled until there is a symbol and a positive quantity", async () => {
    const user = userEvent.setup();
    renderWithProviders(<TradeBar />, { watchlist: watchlistFixture });

    expect(screen.getByRole("button", { name: "Buy" })).toBeDisabled();

    await user.type(screen.getByLabelText("Qty"), "10");
    expect(screen.getByRole("button", { name: "Buy" })).toBeEnabled();
    expect(screen.getByRole("button", { name: "Sell" })).toBeEnabled();
  });

  it("prices the order against the live tick as you type", async () => {
    const user = userEvent.setup();
    const store = new PriceStore();
    renderWithProviders(<TradeBar />, { watchlist: watchlistFixture, store });

    act(() => {
      store.ingest({ AAPL: priceUpdate("AAPL", 192.5, 192.48) });
    });
    await user.type(screen.getByLabelText("Qty"), "10");

    expect(screen.getByTestId("trade-notional")).toHaveTextContent("$1,925.00");
  });

  it("executes a buy and re-reads portfolio state afterwards", async () => {
    const user = userEvent.setup();
    mocks.trade.mockResolvedValue({
      trade: {
        id: "t1",
        ticker: "AAPL",
        side: "buy",
        quantity: 10,
        price: 192.5,
        executed_at: "2026-10-01T14:32:11.482Z",
      },
      cash_balance: 8075,
      position: portfolioFixture.positions[0],
    });

    renderWithProviders(<TradeBar />, { watchlist: watchlistFixture });

    await user.type(screen.getByLabelText("Qty"), "10");
    await user.click(screen.getByRole("button", { name: "Buy" }));

    await waitFor(() => expect(mocks.trade).toHaveBeenCalledWith("AAPL", 10, "buy"));
    await waitFor(() => expect(mocks.getPortfolio).toHaveBeenCalled());
    expect(await screen.findByText("Bought 10 AAPL at $192.50")).toBeInTheDocument();
    expect(screen.getByLabelText("Qty")).toHaveValue("");
  });

  it("reports a rejected order in the readout and keeps the quantity", async () => {
    const user = userEvent.setup();
    const { ApiError } = await import("@/lib/api");
    mocks.trade.mockRejectedValue(
      new ApiError("INSUFFICIENT_CASH", "Need $1925.00, have $100.00", 400),
    );

    renderWithProviders(<TradeBar />, { watchlist: watchlistFixture });

    await user.type(screen.getByLabelText("Qty"), "10");
    await user.click(screen.getByRole("button", { name: "Buy" }));

    expect(await screen.findByText("Need $1925.00, have $100.00")).toBeInTheDocument();
    expect(screen.getByLabelText("Qty")).toHaveValue("10");
  });

  it("sends a sell with the sell side", async () => {
    const user = userEvent.setup();
    mocks.trade.mockResolvedValue({
      trade: {
        id: "t2",
        ticker: "AAPL",
        side: "sell",
        quantity: 4,
        price: 192.5,
        executed_at: "2026-10-01T14:33:00.000Z",
      },
      cash_balance: 8845,
      position: null,
    });

    renderWithProviders(<TradeBar />, { watchlist: watchlistFixture });

    await user.type(screen.getByLabelText("Qty"), "4");
    await user.click(screen.getByRole("button", { name: "Sell" }));

    await waitFor(() => expect(mocks.trade).toHaveBeenCalledWith("AAPL", 4, "sell"));
  });
});
