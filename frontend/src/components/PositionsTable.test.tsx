import { act, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { PositionsTable } from "@/components/PositionsTable";
import { PriceStore } from "@/lib/priceStore";
import {
  emptyPortfolioFixture,
  portfolioFixture,
  priceUpdate,
  watchlistFixture,
} from "@/test/fixtures";
import { renderWithProviders } from "@/test/harness";

describe("PositionsTable", () => {
  it("renders the figures from the portfolio payload", () => {
    renderWithProviders(<PositionsTable />, { portfolio: portfolioFixture });

    const row = screen.getByRole("button", { name: /AAPL/ });
    expect(within(row).getByText("10")).toBeInTheDocument();
    expect(within(row).getByText("190.00")).toBeInTheDocument();
    expect(within(row).getByText("$1,925.00")).toBeInTheDocument();
    expect(within(row).getByText("+$25.00")).toBeInTheDocument();
    expect(within(row).getByText("+1.32%")).toBeInTheDocument();
    expect(within(row).getByText("19.2%")).toBeInTheDocument();
  });

  it("shows a loss in the down tone", () => {
    renderWithProviders(<PositionsTable />, { portfolio: portfolioFixture });
    const row = screen.getByRole("button", { name: /NVDA/ });
    expect(within(row).getByText("−$34.40")).toBeInTheDocument();
    expect(within(row).getByText("−6.62%")).toBeInTheDocument();
  });

  it("marks positions to market as prices stream in", () => {
    const store = new PriceStore();
    renderWithProviders(<PositionsTable />, { portfolio: portfolioFixture, store });

    act(() => {
      store.ingest({ AAPL: priceUpdate("AAPL", 200, 192.5) });
    });

    const row = screen.getByRole("button", { name: /AAPL/ });
    expect(within(row).getByTestId("position-price-AAPL")).toHaveTextContent("200.00");
    expect(within(row).getByText("$2,000.00")).toBeInTheDocument();
    expect(within(row).getByText("+$100.00")).toBeInTheDocument();
  });

  it("keeps the column order identical whether or not a row is selected", () => {
    // The selection marker is a pseudo-element rather than an extra <span> on purpose: the E2E
    // suite reads columns positionally, and a conditional node would shift them under it.
    renderWithProviders(<PositionsTable />, {
      portfolio: portfolioFixture,
      watchlist: watchlistFixture,
    });

    for (const ticker of ["AAPL", "NVDA"]) {
      const spans = screen.getByRole("button", { name: new RegExp(ticker) }).querySelectorAll("span");
      expect(spans[0]).toHaveTextContent(ticker);
      expect(spans[1]).toHaveTextContent(ticker === "AAPL" ? "10" : "4");
    }
  });

  it("treats an empty portfolio as a designed state, not a blank table", () => {
    renderWithProviders(<PositionsTable />, { portfolio: emptyPortfolioFixture });

    expect(screen.getByText("Flat — no open positions")).toBeInTheDocument();
    expect(
      screen.getByText("Every dollar is in cash. Use the command line to open one."),
    ).toBeInTheDocument();
  });
});
