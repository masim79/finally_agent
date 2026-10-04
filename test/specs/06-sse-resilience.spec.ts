import { test, expect } from "@playwright/test";
import { startNetworkProxy } from "../fixtures/network-proxy";

/**
 * PLAN.md §12: "SSE resilience: disconnect and verify reconnection."
 *
 * Routes this ONE test through a tiny local reverse proxy (fixtures/network-proxy.ts) instead
 * of `context.setOffline()`. That was the first approach tried, and it was wrong: verified
 * directly (a throwaway diagnostic against this same backend) that `setOffline(true)` blocks
 * NEW fetches to the app's origin (a `fetch()` issued while "offline" throws `Failed to fetch`)
 * but never touches the already-open EventSource — its `data-status` stayed "live" for a full
 * 10s offline window. That's a documented CDP limitation for long-lived streaming connections,
 * not a frontend bug, and it means a test built on it would prove nothing either way. The proxy
 * produces a real destroyed TCP socket, which `EventSource` cannot fail to notice, so this
 * actually exercises the server's `retry: 1000` directive (CONTRACTS.md §2) and the frontend's
 * reconnect handling in priceStore.ts.
 *
 * Read-only otherwise: no trades, no watchlist edits, so this file has no ordering dependency on
 * anything else and touches no ticker another spec owns.
 */

test.describe("SSE resilience", () => {
  test("drops and reconnects, and prices resume streaming", async ({ page, baseURL }) => {
    const proxy = await startNetworkProxy(baseURL ?? "http://127.0.0.1:8000");
    try {
      await page.goto(proxy.url);

      const status = page.getByTestId("connection-status");
      await expect(status).toHaveAttribute("data-status", "live");

      proxy.dropConnections();

      // EventSource reports CONNECTING while retrying and CLOSED only if it truly gives up;
      // either reading is an honest "not live" signal while the connection is down.
      await expect(status).toHaveAttribute("data-status", /reconnecting|offline/, {
        timeout: 10_000,
      });

      proxy.restore();

      await expect(status).toHaveAttribute("data-status", "live", { timeout: 10_000 });

      // Prove the stream actually resumed carrying data, not just that the dot turned green:
      // capture a price and require it to change again within a bounded window post-reconnect.
      const price = page.getByTestId("price-NVDA");
      const afterReconnect = await price.textContent();
      await expect
        .poll(async () => price.textContent(), {
          message: "expected NVDA's price to tick again after the connection recovered",
          timeout: 8_000,
          intervals: [250, 250, 500, 500, 1_000],
        })
        .not.toBe(afterReconnect);
    } finally {
      await proxy.close();
    }
  });
});
