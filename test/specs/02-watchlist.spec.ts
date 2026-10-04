import { test, expect } from "@playwright/test";
import { tradeBarOutput, watchlistRow } from "../fixtures/ui";

/**
 * PLAN.md §12: "Add and remove a ticker from the watchlist."
 *
 * Uses DIS — not one of the ten seeded tickers and not touched by any other spec — so this file
 * is self-contained regardless of run order, and ends the run in the same state it started
 * (added, then removed), leaving no symbol behind for 03/04/05 to trip over.
 */

test.describe("watchlist add/remove", () => {
  test("adding a ticker streams its price; removing it drops the row", async ({ page }) => {
    await page.goto("/");

    await expect(page.getByTestId("price-DIS")).toHaveCount(0);

    // Scoped to the watchlist's own form: an unscoped, non-exact "Add" role lookup would also
    // match the chat panel's "Add PYPL to my watchlist" suggestion chip and throw a strict-mode
    // (ambiguous locator) error.
    const addForm = page.locator("form:has(#add-ticker)");
    await addForm.locator("#add-ticker").fill("dis");
    await addForm.getByRole("button", { name: "Add", exact: true }).click();

    // The row appears and the trade bar's shared status line confirms it — `announce()` in
    // WorkstationProvider is the one place add/remove/trade all report through.
    await expect(page.getByTestId("price-DIS")).toBeVisible();
    await expect(tradeBarOutput(page)).toHaveText("Added DIS to the watchlist");

    // The simulator starts generating it immediately (market_source.add_ticker()), so the price
    // cell resolves to a real number rather than staying on the "––" placeholder.
    await expect(page.getByTestId("price-DIS")).not.toHaveText("––");

    const row = watchlistRow(page, "DIS");
    await row.hover(); // the remove (×) button is only revealed on hover/focus
    await row.getByRole("button", { name: "Remove DIS from the watchlist" }).click();

    await expect(page.getByTestId("price-DIS")).toHaveCount(0);
    await expect(tradeBarOutput(page)).toHaveText("Removed DIS from the watchlist");
  });
});
