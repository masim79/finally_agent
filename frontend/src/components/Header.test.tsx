import { act, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { Header } from "@/components/Header";
import { PriceStore } from "@/lib/priceStore";
import { emptyPortfolioFixture, portfolioFixture, priceUpdate } from "@/test/fixtures";
import { renderWithProviders } from "@/test/harness";

describe("Header", () => {
  it("shows net liquidation value and cash from the portfolio payload", () => {
    renderWithProviders(<Header />, { portfolio: portfolioFixture });

    expect(screen.getByText("$10,485.60")).toBeInTheDocument();
    expect(screen.getByText("$8,075.00")).toBeInTheDocument();
  });

  it("revalues the book as prices stream in", () => {
    const store = new PriceStore();
    renderWithProviders(<Header />, { portfolio: portfolioFixture, store });

    act(() => {
      store.ingest({ AAPL: priceUpdate("AAPL", 202.5, 192.5) });
    });

    // 8075 cash + 10 AAPL at 202.50 + 4 NVDA still at its last REST price of 121.40.
    expect(screen.getByText("$10,585.60")).toBeInTheDocument();
  });

  it("reads flat rather than $0.00 when nothing is held", () => {
    renderWithProviders(<Header />, { portfolio: emptyPortfolioFixture });
    expect(screen.getByText("flat")).toBeInTheDocument();
  });

  it("surfaces the stream state through the status indicator", () => {
    const store = new PriceStore();
    renderWithProviders(<Header />, { portfolio: portfolioFixture, store });

    const indicator = screen.getByTestId("connection-status");
    expect(indicator).toHaveAttribute("data-status", "connecting");

    act(() => {
      store.disconnect();
    });

    expect(indicator).toHaveAttribute("data-status", "offline");
    expect(screen.getByText("Disconnected")).toBeInTheDocument();
  });

  it("holds the clock blank until the first event rather than showing 1970", () => {
    const store = new PriceStore();
    renderWithProviders(<Header />, { portfolio: portfolioFixture, store });
    expect(screen.getByText("––:––:––")).toBeInTheDocument();

    act(() => {
      // Unix SECONDS, as the stream sends them: 2025-10-01T13:32:11Z.
      store.ingest({ AAPL: priceUpdate("AAPL", 193, 192.5, 1759325531.482) });
    });

    expect(screen.queryByText("––:––:––")).not.toBeInTheDocument();
    expect(screen.getByText(/^\d{2}:\d{2}:\d{2}$/)).toBeInTheDocument();
  });
});
