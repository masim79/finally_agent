import { test, expect } from "@playwright/test";
import { headerStat, panel } from "../fixtures/ui";

/**
 * PLAN.md §12: "Fresh start: ten default tickers, $10,000 cash, prices visibly streaming."
 *
 * This file MUST run first (hence the numeric prefix — Playwright runs spec files in the order
 * they're discovered, and the suite is pinned to a single worker in playwright.config.ts). Every
 * assertion here depends on a truly untouched database: $10,000 cash and ten rows only hold if
 * no earlier spec has traded or edited the watchlist. Later specs either seed their own state
 * through the API or claim tickers (DIS, PLTR/JPM, PYPL, TSLA, NFLX-removal) chosen so they don't
 * fight this file for the same symbols.
 */

const DEFAULT_TICKERS = [
  "AAPL",
  "GOOGL",
  "MSFT",
  "AMZN",
  "TSLA",
  "NVDA",
  "META",
  "JPM",
  "V",
  "NFLX",
] as const;

test.describe("fresh start", () => {
  test("shows the ten default tickers, $10,000 cash, and a live connection", async ({ page }) => {
    await page.goto("/");

    // $10,000 starting cash, formatted as USD in the header.
    await expect(headerStat(page, "Cash")).toHaveText("$10,000.00");

    // Exactly ten rows in the watchlist body (the header row is its own [role="row"], excluded
    // by scoping to the rowgroup).
    await expect(page.locator('[role="rowgroup"] [role="row"]')).toHaveCount(10);

    for (const ticker of DEFAULT_TICKERS) {
      await expect(page.getByTestId(`price-${ticker}`)).toBeVisible();
    }

    // Flat — no trades have happened yet.
    await expect(panel(page, "Positions").getByText("Flat — no open positions")).toBeVisible();
  });

  test("prices are visibly streaming", async ({ page }) => {
    await page.goto("/");

    // Every row resolves a real numeric price (not the "––" placeholder) once the cache has
    // ticked — a web-first assertion, so this waits rather than racing the first SSE event.
    for (const ticker of DEFAULT_TICKERS) {
      await expect(page.getByTestId(`price-${ticker}`)).not.toHaveText("––");
    }

    // Prove it's actually streaming, not a static snapshot: capture one tick and require a
    // different one inside a bounded window. NVDA is used because it sits near $800/share, so a
    // GBM step is very likely to move the displayed 2-decimal value tick to tick — a cheap stock
    // can round to the same cent for several ticks in a row and make this assertion flaky for no
    // real reason.
    const nvdaPrice = page.getByTestId("price-NVDA");
    const initial = await nvdaPrice.textContent();
    await expect
      .poll(async () => nvdaPrice.textContent(), {
        message: "expected NVDA's displayed price to change within the streaming window",
        timeout: 8_000,
        intervals: [250, 250, 500, 500, 1_000],
      })
      .not.toBe(initial);

    // The connection dot agrees: it's live, not connecting/reconnecting/offline.
    await expect(page.getByTestId("connection-status")).toHaveAttribute("data-status", "live");
  });
});
