/**
 * Direct REST client for seeding state through the API instead of the UI, per CONTRACTS.md §3.
 * Used where the UI under test is not the thing being verified (e.g. "give me an existing
 * position before I screenshot the heatmap") — driving that through clicks would be slower and
 * would make the heatmap spec depend on the trade bar working. Specs that ARE testing the trade
 * bar, the watchlist form, or the chat panel still go through the UI.
 *
 * Reads BASE_URL directly (not Playwright's `request` fixture) so it also works from
 * run-against-uvicorn.mjs-style standalone scripts if ever needed, and because these calls are
 * fired from spec setup, not from a `page`/`request` fixture context.
 */

const BASE_URL = process.env.BASE_URL ?? "http://127.0.0.1:8000";

export interface Position {
  ticker: string;
  quantity: number;
  avg_cost: number;
  current_price: number;
  market_value: number;
  unrealized_pnl: number;
  unrealized_pnl_percent: number;
  weight: number;
}

export interface Portfolio {
  cash_balance: number;
  positions: Position[];
  positions_value: number;
  total_value: number;
  total_unrealized_pnl: number;
  total_unrealized_pnl_percent: number;
}

export interface TradeResponseBody {
  trade: { id: string; ticker: string; side: "buy" | "sell"; quantity: number; price: number; executed_at: string };
  cash_balance: number;
  position: Position | null;
}

export interface ApiErrorBody {
  detail: { code: string; message: string };
}

async function parseJson<T>(response: Response): Promise<T> {
  const text = await response.text();
  return text.length > 0 ? (JSON.parse(text) as T) : (undefined as T);
}

export const api = {
  baseURL: BASE_URL,

  async health(): Promise<{ status: string; market_source: string; tracked_tickers: number; db: string }> {
    const response = await fetch(`${BASE_URL}/api/health`);
    return parseJson(response);
  },

  async portfolio(): Promise<Portfolio> {
    const response = await fetch(`${BASE_URL}/api/portfolio`);
    if (!response.ok) throw new Error(`GET /api/portfolio -> ${response.status}`);
    return parseJson(response);
  },

  /** Throws with the §3 error body attached as `.body` when the trade is rejected. */
  async trade(ticker: string, quantity: number, side: "buy" | "sell"): Promise<TradeResponseBody> {
    const response = await fetch(`${BASE_URL}/api/portfolio/trade`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ ticker, quantity, side }),
    });
    const body = await parseJson<TradeResponseBody | ApiErrorBody>(response);
    if (!response.ok) {
      throw Object.assign(new Error(`POST /api/portfolio/trade -> ${response.status}`), { body });
    }
    return body as TradeResponseBody;
  },

  async addTicker(ticker: string): Promise<void> {
    const response = await fetch(`${BASE_URL}/api/watchlist`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ ticker }),
    });
    if (!response.ok && response.status !== 409) {
      throw new Error(`POST /api/watchlist -> ${response.status}`);
    }
  },

  async removeTicker(ticker: string): Promise<void> {
    const response = await fetch(`${BASE_URL}/api/watchlist/${encodeURIComponent(ticker)}`, {
      method: "DELETE",
    });
    if (!response.ok && response.status !== 404) {
      throw new Error(`DELETE /api/watchlist/${ticker} -> ${response.status}`);
    }
  },

  /** Polls until the price cache has a tick for `ticker` (e.g. right after adding it). */
  async waitForPrice(ticker: string, timeoutMs = 10_000): Promise<number> {
    const deadline = Date.now() + timeoutMs;
    while (Date.now() < deadline) {
      const response = await fetch(`${BASE_URL}/api/watchlist`);
      const body = (await parseJson<{ tickers: Array<{ ticker: string; price: number | null }> }>(
        response,
      ));
      const entry = body.tickers.find((t) => t.ticker === ticker);
      if (entry?.price != null) return entry.price;
      await new Promise((resolve) => setTimeout(resolve, 250));
    }
    throw new Error(`No cached price for ${ticker} after ${timeoutMs}ms`);
  },
};

/**
 * Mirrors PortfolioHeatmap.tsx's `tileColor()` exactly (frontend/src/components/PortfolioHeatmap.tsx)
 * so the heatmap spec can assert against the REAL pnl value the backend returns, instead of
 * guessing a sign and hoping the market cooperated. Kept here rather than imported across
 * packages — test/ has no build-time link to frontend/src, and the formula is simple and
 * commented at both ends so a change in one is easy to notice when the other goes stale.
 */
export function expectedTileColor(pnlPercent: number): string {
  const CLAMP = 5;
  const magnitude = Math.min(Math.abs(pnlPercent) / CLAMP, 1);
  const alpha = 0.12 + magnitude * 0.26;
  if (Math.abs(pnlPercent) < 0.0001) return "rgba(93, 106, 124, 0.18)";
  return pnlPercent > 0
    ? `rgba(63, 209, 139, ${alpha.toFixed(3)})`
    : `rgba(255, 92, 102, ${alpha.toFixed(3)})`;
}
