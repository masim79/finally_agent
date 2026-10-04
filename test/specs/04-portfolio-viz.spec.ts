import { test, expect, type Page } from "@playwright/test";
import { api, expectedTileColor } from "../fixtures/api";
import { panel } from "../fixtures/ui";

/**
 * PLAN.md §12: "Portfolio visualization: heatmap renders with correct colors, P&L chart has
 * data points."
 *
 * Seeds its own position through the API (AAPL, a ticker 03-trading never touches) rather than
 * relying on state left behind by another spec — this file isn't testing the trade bar, so
 * driving a trade through it would only add flake surface for no coverage gained (brief's own
 * seeding guidance). That also makes this file independent of execution order.
 *
 * The heatmap tile color is asserted against the REAL `unrealized_pnl_percent` the frontend's
 * own GET /api/portfolio call returned (captured via page.waitForResponse, not a second,
 * possibly-skewed API call afterward) — see expectedTileColor() in fixtures/api.ts, which
 * mirrors PortfolioHeatmap.tsx's tileColor() formula. That's the only way to assert "renders
 * with P&L-appropriate colors" without gambling on which way a live, randomly-walking price
 * happens to move on a given run.
 */

function parseRgba(value: string): { r: number; g: number; b: number; a: number } {
  const match = value.match(/rgba?\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*(?:,\s*([\d.]+)\s*)?\)/);
  if (!match) throw new Error(`Not an rgb(a) color: ${JSON.stringify(value)}`);
  return {
    r: Number(match[1]),
    g: Number(match[2]),
    b: Number(match[3]),
    a: match[4] === undefined ? 1 : Number(match[4]),
  };
}

test.describe("portfolio visualization", () => {
  test("heatmap renders a P&L-colored tile and the P&L chart gets a data point after a trade", async ({
    page,
  }: {
    page: Page;
  }) => {
    await api.trade("AAPL", 3, "buy");

    const portfolioResponse = page.waitForResponse(
      (response) => response.url().includes("/api/portfolio") && !response.url().includes("history") && response.request().method() === "GET",
    );
    await page.goto("/");
    const portfolio = (await (await portfolioResponse).json()) as {
      positions: Array<{ ticker: string; unrealized_pnl_percent: number }>;
    };
    const aapl = portfolio.positions.find((p) => p.ticker === "AAPL");
    expect(aapl, "seeded AAPL position should be in the portfolio the page just loaded").toBeTruthy();

    // --- Heatmap ---
    const heatmap = page.getByTestId("heatmap");
    const tile = heatmap.getByRole("button", { name: /^AAPL/ });
    await expect(tile).toBeVisible();

    const box = await tile.boundingBox();
    expect(box?.width).toBeGreaterThan(10);
    expect(box?.height).toBeGreaterThan(10);

    const actualColor = await tile.evaluate((el) => (el as HTMLElement).style.backgroundColor);
    const actual = parseRgba(actualColor);
    const expected = parseRgba(expectedTileColor(aapl!.unrealized_pnl_percent));
    expect(actual.r).toBe(expected.r);
    expect(actual.g).toBe(expected.g);
    expect(actual.b).toBe(expected.b);
    expect(actual.a).toBeCloseTo(expected.a, 2);

    // --- P&L chart ---
    // Every trade writes a portfolio_snapshots row immediately (CONTRACTS.md §3), so the chart
    // already has data by the time this page loads — no need to wait out the 30s background
    // snapshot timer.
    await expect(panel(page, "Portfolio value").getByText("No snapshots yet")).toHaveCount(0);
    await expect(page.getByText(/^open /)).toBeVisible();
    await expect(page.getByTestId("pnl-chart")).toBeVisible();

    // Positions table reflects the same seeded position.
    await expect(panel(page, "Positions").getByText("AAPL", { exact: true })).toBeVisible();
  });
});
