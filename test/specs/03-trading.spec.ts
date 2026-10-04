import { test, expect } from "@playwright/test";
import { headerStat, panel, parseMoney, tradeBarOutput } from "../fixtures/ui";

/**
 * PLAN.md §12: "Buy: cash falls, position appears, portfolio total updates" and
 * "Sell: cash rises, position reduces or disappears."
 *
 * Trades through the trade bar UI (this file IS testing the trade bar), using JPM — a default
 * watchlist ticker so a price is guaranteed to be cached, and one no other spec trades. Cash
 * deltas are computed from the fill price Printed in the trade confirmation, never assumed —
 * the price at click time is not the price at fill (PLAN.md's own warning: prices move every
 * 500ms). Three sequential trades build on each other (buy 10, sell 4 -> reduces, sell the
 * remaining 6 -> disappears) via `test.describe.configure({ mode: "serial" })`, covering both
 * "reduces" and "disappears" without over-fitting to one order of the market.
 */

test.describe("trading", () => {
  test.describe.configure({ mode: "serial" });

  async function submitTrade(page: import("@playwright/test").Page, side: "buy" | "sell", qty: number) {
    await page.locator("#trade-ticker").fill("JPM");
    await page.locator("#trade-qty").fill(String(qty));
    // Playwright's `exact: true` is case-SENSITIVE whole-string matching, not just
    // whole-string — `name: side` (lowercase "buy"/"sell") against the button's actual text
    // ("Buy"/"Sell") never matched anything, so this locator waited the full test timeout for
    // a match that could never happen. Scoped to the trade bar's own form (there's exactly one
    // "Buy" and one "Sell" button there) with correct casing and no `exact`, matching the
    // pattern already used for the watchlist's "Add" button in 02-watchlist.spec.ts.
    const label = side === "buy" ? "Buy" : "Sell";
    await page
      .locator('form[aria-label="Trade command line"]')
      .getByRole("button", { name: label })
      .click();
  }

  test("buy: cash falls by the fill cost, position appears, portfolio total updates", async ({
    page,
  }) => {
    await page.goto("/");

    // WorkstationProvider loads cash/positions/history asynchronously after mount; reading
    // textContent() immediately races that fetch and can still see the "––" placeholder. Wait
    // for a real value first (a web-first assertion, so this waits rather than guessing a delay).
    await expect(headerStat(page, "Cash")).not.toHaveText("––");
    const cashBeforeText = (await headerStat(page, "Cash").textContent()) ?? "";
    const cashBefore = parseMoney(cashBeforeText);
    const netLiqBefore = parseMoney((await headerStat(page, "Net liquidation").textContent()) ?? "");

    await submitTrade(page, "buy", 10);

    const notice = tradeBarOutput(page);
    await expect(notice).toHaveText(/^Bought 10 JPM at \$[\d,]+\.\d{2}$/);
    const fillPrice = parseMoney((await notice.textContent()) ?? "");

    // executeTrade() re-fetches the whole portfolio after the fill; wait for that round trip to
    // land (the header's Cash figure to actually change) rather than reading it immediately.
    await expect
      .poll(async () => headerStat(page, "Cash").textContent())
      .not.toBe(cashBeforeText);
    const cashAfter = parseMoney((await headerStat(page, "Cash").textContent()) ?? "");
    expect(cashAfter).toBeCloseTo(cashBefore - fillPrice * 10, 2);

    // Net liquidation (cash + positions value) is unchanged by a fill at the fill price itself
    // (cash down, position value up by the same amount) — it only drifts afterward as the price
    // ticks, so check it stayed close rather than asserting an exact figure.
    const netLiqAfter = parseMoney((await headerStat(page, "Net liquidation").textContent()) ?? "");
    expect(Math.abs(netLiqAfter - netLiqBefore)).toBeLessThan(fillPrice * 10 * 0.05);

    const positions = panel(page, "Positions");
    await expect(positions.getByText("JPM", { exact: true })).toBeVisible();
    await expect(page.getByTestId("position-price-JPM")).toBeVisible();
  });

  test("sell (partial): cash rises by the fill proceeds, position reduces", async ({ page }) => {
    await page.goto("/");

    await expect(headerStat(page, "Cash")).not.toHaveText("––");
    const cashBeforeText = (await headerStat(page, "Cash").textContent()) ?? "";
    const cashBefore = parseMoney(cashBeforeText);

    await submitTrade(page, "sell", 4);

    const notice = tradeBarOutput(page);
    await expect(notice).toHaveText(/^Sold 4 JPM at \$[\d,]+\.\d{2}$/);
    const fillPrice = parseMoney((await notice.textContent()) ?? "");

    await expect
      .poll(async () => headerStat(page, "Cash").textContent())
      .not.toBe(cashBeforeText);
    const cashAfter = parseMoney((await headerStat(page, "Cash").textContent()) ?? "");
    expect(cashAfter).toBeCloseTo(cashBefore + fillPrice * 4, 2);

    // Position reduces (10 -> 6) rather than disappearing. The row's second <span> is the
    // quantity column (ticker, qty, avg, last, value, P&L, P&L%, weight, in that order in
    // PositionsTable.tsx) — targeted directly so this doesn't pass by coincidentally matching a
    // "6" digit inside the price or P&L columns instead.
    await expect(panel(page, "Positions").getByText("JPM", { exact: true })).toBeVisible();
    const row = panel(page, "Positions").locator("button", { hasText: "JPM" });
    await expect(row.locator("span").nth(1)).toHaveText("6");
  });

  test("sell (full): closing the remaining shares removes the position", async ({ page }) => {
    await page.goto("/");

    await submitTrade(page, "sell", 6);

    await expect(tradeBarOutput(page)).toHaveText(/^Sold 6 JPM at \$[\d,]+\.\d{2}$/);

    await expect(page.getByTestId("position-price-JPM")).toHaveCount(0);
    await expect(panel(page, "Positions").getByText("Flat — no open positions")).toBeVisible();
  });
});
