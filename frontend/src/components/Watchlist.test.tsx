import { act, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { Watchlist } from "@/components/Watchlist";
import { PriceStore } from "@/lib/priceStore";
import { priceUpdate, portfolioFixture, watchlistFixture } from "@/test/fixtures";
import { renderWithProviders } from "@/test/harness";

const mocks = vi.hoisted(() => ({
  getPortfolio: vi.fn(),
  getWatchlist: vi.fn(),
  getPortfolioHistory: vi.fn(),
  addTicker: vi.fn(),
  removeTicker: vi.fn(),
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

describe("Watchlist", () => {
  it("renders the cold-cache state rather than a fabricated zero", () => {
    renderWithProviders(<Watchlist />, { watchlist: watchlistFixture });

    // JPM has every price field null in the fixture, exactly as a cold cache returns it.
    expect(screen.getByTestId("price-JPM")).toHaveTextContent("––");
    expect(screen.getByTestId("change-JPM")).toHaveTextContent("––");
  });

  it("starts every sparkline empty and fills it in from the stream", () => {
    const store = new PriceStore();
    renderWithProviders(<Watchlist />, { watchlist: watchlistFixture, store });

    const sparkline = screen.getByLabelText("AAPL sparkline, waiting for price data");
    expect(sparkline).toHaveAttribute("data-points", "0");

    act(() => {
      store.ingest({ AAPL: priceUpdate("AAPL", 192.5, 192.48) });
      store.ingest({ AAPL: priceUpdate("AAPL", 192.6, 192.5) });
    });

    expect(screen.getByLabelText("AAPL price trend")).toHaveAttribute("data-points", "2");
  });

  it("flashes the price cell on a change, with a token that alternates each tick", () => {
    const store = new PriceStore();
    renderWithProviders(<Watchlist />, { watchlist: watchlistFixture, store });

    const cell = screen.getByTestId("price-AAPL");
    expect(cell).not.toHaveAttribute("data-flash");

    act(() => {
      store.ingest({ AAPL: priceUpdate("AAPL", 193.1, 192.5) });
    });
    const firstFlash = cell.getAttribute("data-flash");
    expect(firstFlash).toMatch(/^up-/);
    expect(cell).toHaveTextContent("193.10");

    act(() => {
      store.ingest({ AAPL: priceUpdate("AAPL", 192.2, 193.1) });
    });
    const secondFlash = cell.getAttribute("data-flash");
    expect(secondFlash).toMatch(/^down-/);
    expect(secondFlash).not.toBe(firstFlash);

    act(() => {
      store.ingest({ AAPL: priceUpdate("AAPL", 191.0, 192.2) });
    });
    // Same direction twice running still changes the token, or the animation would not re-fire.
    expect(cell.getAttribute("data-flash")).not.toBe(secondFlash);
  });

  it("shows the session change, not the stream's tick-over-tick percentage", () => {
    const store = new PriceStore();
    renderWithProviders(<Watchlist />, { watchlist: watchlistFixture, store });

    act(() => {
      store.ingest({ AAPL: priceUpdate("AAPL", 100, 99.99) });
    });
    act(() => {
      store.ingest({ AAPL: priceUpdate("AAPL", 102, 101.99) });
    });

    expect(screen.getByTestId("change-AAPL")).toHaveTextContent("+2.00%");
  });

  it("adds a ticker and clears the field", async () => {
    const user = userEvent.setup();
    mocks.addTicker.mockResolvedValue({
      ticker: "PYPL",
      added_at: "2026-10-01T15:00:00.000Z",
      price: null,
      previous_price: null,
      change: null,
      change_percent: null,
      direction: null,
    });

    renderWithProviders(<Watchlist />, { watchlist: watchlistFixture });

    const input = screen.getByLabelText("Add");
    await user.type(input, "pypl");
    // The field normalises as you type, so the request always carries a clean symbol.
    expect(input).toHaveValue("PYPL");

    await user.click(screen.getByRole("button", { name: "Add" }));

    await waitFor(() => expect(mocks.addTicker).toHaveBeenCalledWith("PYPL"));
    await waitFor(() => expect(input).toHaveValue(""));
  });

  it("removes a ticker", async () => {
    const user = userEvent.setup();
    mocks.removeTicker.mockResolvedValue(undefined);

    renderWithProviders(<Watchlist />, { watchlist: watchlistFixture });

    await user.click(screen.getByRole("button", { name: "Remove NVDA from the watchlist" }));

    await waitFor(() => expect(mocks.removeTicker).toHaveBeenCalledWith("NVDA"));
    // Removing is server state the price stream never reports, so the panel re-reads it.
    await waitFor(() => expect(mocks.getWatchlist).toHaveBeenCalled());
  });

  it("invites the first symbol when the watchlist is empty", () => {
    renderWithProviders(<Watchlist />, { watchlist: [] });
    expect(screen.getByText("Watchlist is empty")).toBeInTheDocument();
  });

  it("keeps the add control against the last row, and only grows the list when it is empty", () => {
    // The rows must not stretch: a stretched list pushes the add form to the panel floor and
    // opens a void between the two. The empty state is the one case that needs the whole box.
    const { unmount } = renderWithProviders(<Watchlist />, { watchlist: watchlistFixture });
    expect(screen.getByRole("rowgroup")).not.toHaveClass("flex-1");
    unmount();

    renderWithProviders(<Watchlist />, { watchlist: [] });
    expect(screen.getByRole("rowgroup")).toHaveClass("flex-1");
  });
});
