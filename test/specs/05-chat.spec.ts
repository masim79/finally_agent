import { test, expect } from "@playwright/test";
import { panel } from "../fixtures/ui";

/**
 * PLAN.md §12: "AI chat (mocked): send a message, receive a response, trade execution appears
 * inline."
 *
 * Runs with LLM_MOCK=true (CONTRACTS.md §5's mock table), which both run paths set — this spec
 * never touches a real model and is fully deterministic. The mock still executes real trades and
 * real watchlist changes through the normal service layer (only the "what should I do" decision
 * is mocked), so every assertion below checks an actual, persisted effect — not just chat copy.
 *
 * Uses TSLA (untouched by 03/04) for the trade pair and NFLX/PYPL (a default ticker's removal,
 * and the one CONTRACTS.md itself uses as its add example) for the watchlist pair.
 */

async function send(page: import("@playwright/test").Page, message: string) {
  const log = page.getByTestId("chat-log");
  // ChatProvider fetches GET /api/chat/history on mount and only then renders persisted
  // messages from earlier tests in this serial run; counting articles before that resolves
  // races the fetch (the panel header's meta text reads "Loading" until it does).
  await expect(page.getByText("Loading", { exact: true })).toHaveCount(0);
  const before = await log.locator("article").count();
  await page.locator("#chat-input").fill(message);
  await page.getByRole("button", { name: "Send" }).click();
  // Two new articles land: the optimistic user echo, then the assistant's reply.
  await expect(log.locator("article")).toHaveCount(before + 2);
  return log.locator('article[data-role="assistant"]').last();
}

test.describe("AI chat", () => {
  test.describe.configure({ mode: "serial" });

  test("buy via chat executes a real trade, shown inline", async ({ page }) => {
    await page.goto("/");

    const reply = await send(page, "buy 5 TSLA");
    await expect(reply).toBeVisible();
    await expect(reply.locator('li[data-status="executed"]')).toContainText(/Bought 5 TSLA at \$/);

    // The executed trade is real: it shows up in the positions table too (ChatProvider calls
    // refresh() whenever an action actually executed).
    await expect(page.getByTestId("position-price-TSLA")).toBeVisible();
  });

  test("sell via chat executes a real (partial) trade, shown inline", async ({ page }) => {
    await page.goto("/");

    const reply = await send(page, "sell 2 TSLA");
    await expect(reply.locator('li[data-status="executed"]')).toContainText(/Sold 2 TSLA at \$/);

    const row = panel(page, "Positions").locator("button", { hasText: "TSLA" });
    await expect(row.locator("span").nth(1)).toHaveText("3"); // 5 bought - 2 sold
  });

  test("watchlist changes via chat: remove, then add", async ({ page }) => {
    await page.goto("/");
    await expect(page.getByTestId("price-NFLX")).toBeVisible();

    const removeReply = await send(page, "remove NFLX from watchlist");
    await expect(removeReply.locator('li[data-status="executed"]')).toContainText(
      "Removed NFLX from the watchlist",
    );
    await expect(page.getByTestId("price-NFLX")).toHaveCount(0);

    const addReply = await send(page, "add PYPL to my watchlist");
    await expect(addReply.locator('li[data-status="executed"]')).toContainText(
      "Added PYPL to the watchlist",
    );
    await expect(page.getByTestId("price-PYPL")).toBeVisible();
  });

  test("a plain question gets an analysis reply with no actions", async ({ page }) => {
    await page.goto("/");

    const reply = await send(page, "How is my portfolio doing?");
    // Per CONTRACTS.md §5's mock table: "anything else" -> a fixed analysis string citing
    // total_value, with no trades and no watchlist changes.
    await expect(reply.locator("ul[aria-label='Executed actions']")).toHaveCount(0);
    await expect(reply).toContainText(/\$[\d,]+\.\d{2}/);
  });
});
