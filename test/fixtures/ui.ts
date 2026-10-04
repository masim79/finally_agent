import type { Page, Locator } from "@playwright/test";

/**
 * Small locator helpers shared across specs, built against the real selectors in
 * frontend/src/components/* (read directly, not guessed): Header's Stat rows have no
 * data-testid, but each is a label span followed by a value span, and Panel sections get an
 * implicit ARIA "region" role from their `aria-label={title}` — both are stable contracts of
 * the markup, not implementation details likely to shift under us.
 */

/** The value span next to a Header stat label ("Cash", "Net liquidation", "Positions", ...). */
export function headerStat(page: Page, label: string): Locator {
  return page
    .locator("header")
    .getByText(label, { exact: true })
    .locator("xpath=following-sibling::span[1]");
}

/** A <section aria-label="..."> panel (Watchlist, Positions, Allocation, Portfolio value, Chart, FinAlly copilot). */
export function panel(page: Page, title: string): Locator {
  return page.getByRole("region", { name: title });
}

/** The watchlist row containing a given ticker, scoped to the body rowgroup (not the header row). */
export function watchlistRow(page: Page, ticker: string): Locator {
  return page
    .locator('[role="rowgroup"] [role="row"]')
    .filter({ has: page.getByTestId(`price-${ticker}`) });
}

/** The trade bar's single-line status output — shared by trades, watchlist add/remove, via `notice`. */
export function tradeBarOutput(page: Page): Locator {
  return page.locator('form[aria-label="Trade command line"] output');
}

/** "$1,234.56" -> 1234.56. Throws if the text isn't money-shaped (e.g. still the "––" placeholder). */
export function parseMoney(text: string): number {
  const match = text.replace(/−/g, "-").match(/-?\$?([\d,]+\.\d{2})/);
  if (!match) throw new Error(`Not a money string: ${JSON.stringify(text)}`);
  const value = Number.parseFloat(match[1].replace(/,/g, ""));
  return text.trim().startsWith("-") || text.includes("−") ? -value : value;
}
