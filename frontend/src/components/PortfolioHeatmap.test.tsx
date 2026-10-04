import { screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import {
  MAX_TILE_AREA,
  PortfolioHeatmap,
  fitField,
  tierFor,
} from "@/components/PortfolioHeatmap";
import type { Portfolio } from "@/lib/types";
import { emptyPortfolioFixture, portfolioFixture } from "@/test/fixtures";
import { renderWithProviders } from "@/test/harness";

/**
 * An 80 / 18 / 2 book. Against the harness's 600×300 box the leading position blows past the
 * tile ceiling, so the field scales down and centres: the result is a mid-sized block, a narrow
 * column, and a 2% sliver — the three label treatments, from one fixture.
 */
const concentratedFixture: Portfolio = {
  cash_balance: 0,
  positions: [
    {
      ticker: "AAA",
      quantity: 100,
      avg_cost: 75,
      current_price: 80,
      market_value: 8000,
      unrealized_pnl: 500,
      unrealized_pnl_percent: 6.6667,
      weight: 0.8,
    },
    {
      ticker: "BBB",
      quantity: 20,
      avg_cost: 95,
      current_price: 90,
      market_value: 1800,
      unrealized_pnl: -100,
      unrealized_pnl_percent: -5.2632,
      weight: 0.18,
    },
    {
      ticker: "CCC",
      quantity: 10,
      avg_cost: 19,
      current_price: 20,
      market_value: 200,
      unrealized_pnl: 10,
      unrealized_pnl_percent: 5.2632,
      weight: 0.02,
    },
  ],
  positions_value: 10000,
  total_value: 10000,
  total_unrealized_pnl: 410,
  total_unrealized_pnl_percent: 4.1,
};

function alphaOf(backgroundColor: string): number {
  const match = /rgba?\([^)]*?,\s*([\d.]+)\s*\)/.exec(backgroundColor);
  return match ? Number(match[1]) : 1;
}

describe("PortfolioHeatmap", () => {
  it("lays out one tile per position", () => {
    renderWithProviders(<PortfolioHeatmap />, { portfolio: portfolioFixture });

    const tiles = screen.getAllByRole("button");
    expect(tiles).toHaveLength(2);
    expect(tiles[0]).toHaveAccessibleName(/AAPL/);
  });

  it("sizes tiles by market value, so the larger position takes more area", () => {
    renderWithProviders(<PortfolioHeatmap />, { portfolio: portfolioFixture });

    const apple = screen.getByTitle(/^AAPL/);
    const nvidia = screen.getByTitle(/^NVDA/);
    const area = (element: HTMLElement) =>
      Number.parseFloat(element.style.width) * Number.parseFloat(element.style.height);

    expect(area(apple)).toBeGreaterThan(area(nvidia));
  });

  it("colours a profit green and a loss red", () => {
    renderWithProviders(<PortfolioHeatmap />, { portfolio: portfolioFixture });

    expect(screen.getByTitle(/^AAPL/).style.backgroundColor).toMatch(/63, 209, 139/);
    expect(screen.getByTitle(/^NVDA/).style.backgroundColor).toMatch(/255, 92, 102/);
  });

  it("keeps the fill a tint rather than a slab, even on an outsized move", () => {
    // A tile routinely covers 100,000px² of this panel. Past roughly 0.4 the fill stops reading
    // as a data surface and becomes the loudest object on the terminal.
    renderWithProviders(<PortfolioHeatmap />, { portfolio: concentratedFixture });

    for (const ticker of ["AAA", "BBB", "CCC"]) {
      expect(alphaOf(screen.getByTitle(new RegExp(`^${ticker}`)).style.backgroundColor)).toBeLessThanOrEqual(
        0.4,
      );
    }
  });

  it("keeps the ticker and its P&L in one label group, with value and weight footed below", () => {
    renderWithProviders(<PortfolioHeatmap />, { portfolio: portfolioFixture });

    const apple = within(screen.getByTitle(/^AAPL/));
    const label = apple.getByText("AAPL").parentElement;
    expect(label).not.toBeNull();
    expect(within(label as HTMLElement).getByText("+1.32%")).toBeInTheDocument();

    // Weight is the net-liq figure the Positions table prints, not the tile's share of the panel.
    expect(apple.getByText("$1,925.00")).toBeInTheDocument();
    expect(apple.getByText("19.2%")).toBeInTheDocument();
  });

  it("drops the footer on a tile too narrow to hold it, but keeps the symbol", () => {
    renderWithProviders(<PortfolioHeatmap />, { portfolio: concentratedFixture });

    const column = within(screen.getByTitle(/^BBB/));
    expect(column.getByText("BBB")).toBeInTheDocument();
    expect(column.getByText("−5.26%")).toBeInTheDocument();
    expect(column.queryByText("Wgt")).not.toBeInTheDocument();
    expect(column.queryByText("$1,800.00")).not.toBeInTheDocument();
  });

  it("keeps a 2% band to its symbol rather than clipping a figure into it", () => {
    renderWithProviders(<PortfolioHeatmap />, { portfolio: concentratedFixture });

    const band = screen.getByTitle(/^CCC/);
    expect(within(band).getByText("CCC")).toBeInTheDocument();
    expect(within(band).queryByText("+5.26%")).not.toBeInTheDocument();
    // Still a tile: clickable, tooltipped, and carrying its direction in the edge rail.
    expect(band.querySelector(".bg-up")).not.toBeNull();
  });

  it("pulls a runaway position back off the panel edges instead of space-filling", () => {
    // The harness reports a 600×300 container, and AAA is 80% of the book — filling the box it
    // would be ~144,000px² of one colour. The field shrinks and centres, so it reads as tiles
    // with a margin rather than as a wall.
    renderWithProviders(<PortfolioHeatmap />, { portfolio: concentratedFixture });

    const biggest = screen.getByTitle(/^AAA/);
    const area =
      Number.parseFloat(biggest.style.width) * Number.parseFloat(biggest.style.height);
    expect(area).toBeLessThan(0.7 * 0.8 * 600 * 300);
    expect(Number.parseFloat(biggest.style.left)).toBeGreaterThan(0);
    expect(Number.parseFloat(biggest.style.top)).toBeGreaterThan(0);
  });

  it("states the invested/cash split the tile areas are drawn against", () => {
    renderWithProviders(<PortfolioHeatmap />, { portfolio: portfolioFixture });

    const rail = within(screen.getByTestId("exposure-rail"));
    expect(rail.getByText("23.0%")).toBeInTheDocument();
    expect(rail.getByText("77.0%")).toBeInTheDocument();
  });

  it("invites a first trade when the portfolio is empty", () => {
    renderWithProviders(<PortfolioHeatmap />, { portfolio: emptyPortfolioFixture });

    expect(screen.getByText("No positions")).toBeInTheDocument();
    expect(screen.queryAllByRole("button")).toHaveLength(0);
    expect(screen.queryByTestId("exposure-rail")).not.toBeInTheDocument();
  });
});

describe("fitField", () => {
  it("hands back the whole box when the biggest tile already fits", () => {
    const even = [100, 100, 100, 100, 100, 100, 100, 100];
    expect(fitField(even, 600, 300)).toEqual({
      width: 600,
      height: 300,
      offsetX: 0,
      offsetY: 0,
    });
  });

  it("scales uniformly and centres when one position would run away with the panel", () => {
    const field = fitField([9000, 1000], 290, 160);

    expect(field.width).toBeLessThan(290);
    expect(field.height).toBeLessThan(160);
    // Uniform: the container's aspect survives, so squarify still packs near-squares.
    expect(field.width / field.height).toBeCloseTo(290 / 160, 5);
    expect(field.offsetX).toBeCloseTo((290 - field.width) / 2, 5);
    expect(field.offsetY).toBeCloseTo((160 - field.height) / 2, 5);
    expect(0.9 * field.width * field.height).toBeCloseTo(MAX_TILE_AREA, 5);
  });

  it("stops shrinking before the field would be marooned in an oversized panel", () => {
    // Honouring the ceiling literally here would want a 0.30 scale — a chip in a lot of panel.
    const field = fitField([9000, 1000], 800, 600);

    expect(field.width).toBeCloseTo(576, 5);
    expect(field.height).toBeCloseTo(432, 5);
    expect(field.offsetX).toBeCloseTo(112, 5);
    expect(field.offsetY).toBeCloseTo(84, 5);
  });

  it("survives an unmeasured container and a book with nothing in it", () => {
    expect(fitField([100], 0, 0)).toEqual({ width: 0, height: 0, offsetX: 0, offsetY: 0 });
    expect(fitField([], 290, 220)).toEqual({
      width: 290,
      height: 220,
      offsetX: 0,
      offsetY: 0,
    });
    expect(fitField([0, 0], 290, 220)).toEqual({
      width: 290,
      height: 220,
      offsetX: 0,
      offsetY: 0,
    });
  });
});

describe("tierFor", () => {
  it("grades a tile by what can legibly sit inside it", () => {
    expect(tierFor(20, 120)).toBe("bare");
    expect(tierFor(120, 12)).toBe("bare");
    expect(tierFor(120, 40)).toBe("strip");
    expect(tierFor(120, 200)).toBe("block");
    expect(tierFor(200, 90)).toBe("block");
    expect(tierFor(200, 160)).toBe("rich");
  });
});
