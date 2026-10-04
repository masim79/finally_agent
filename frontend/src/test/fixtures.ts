/** Fixtures shaped exactly like CONTRACTS.md §2 and §3. */

import type {
  ChatHistoryResponse,
  Portfolio,
  PriceStreamEvent,
  Snapshot,
  WatchlistEntry,
} from "@/lib/types";

export function priceUpdate(
  ticker: string,
  price: number,
  previous: number,
  timestamp = 1759325531.482,
): PriceStreamEvent[string] {
  const change = price - previous;
  return {
    ticker,
    price,
    previous_price: previous,
    timestamp,
    change,
    change_percent: previous === 0 ? 0 : (change / previous) * 100,
    direction: change > 0 ? "up" : change < 0 ? "down" : "flat",
  };
}

export const watchlistFixture: WatchlistEntry[] = [
  {
    ticker: "AAPL",
    added_at: "2026-10-01T14:00:00.000Z",
    price: 192.5,
    previous_price: 192.48,
    change: 0.02,
    change_percent: 0.0104,
    direction: "up",
  },
  {
    ticker: "NVDA",
    added_at: "2026-10-01T14:00:01.000Z",
    price: 121.4,
    previous_price: 121.5,
    change: -0.1,
    change_percent: -0.0823,
    direction: "down",
  },
  // Cold cache: every price field is null until the first tick for this symbol.
  {
    ticker: "JPM",
    added_at: "2026-10-01T14:00:02.000Z",
    price: null,
    previous_price: null,
    change: null,
    change_percent: null,
    direction: null,
  },
];

export const portfolioFixture: Portfolio = {
  cash_balance: 8075,
  positions: [
    {
      ticker: "AAPL",
      quantity: 10,
      avg_cost: 190,
      current_price: 192.5,
      market_value: 1925,
      unrealized_pnl: 25,
      unrealized_pnl_percent: 1.3158,
      weight: 0.1924,
    },
    {
      ticker: "NVDA",
      quantity: 4,
      avg_cost: 130,
      current_price: 121.4,
      market_value: 485.6,
      unrealized_pnl: -34.4,
      unrealized_pnl_percent: -6.6154,
      weight: 0.0485,
    },
  ],
  positions_value: 2410.6,
  total_value: 10485.6,
  total_unrealized_pnl: -9.4,
  total_unrealized_pnl_percent: -0.09,
};

export const emptyPortfolioFixture: Portfolio = {
  cash_balance: 10000,
  positions: [],
  positions_value: 0,
  total_value: 10000,
  total_unrealized_pnl: 0,
  total_unrealized_pnl_percent: 0,
};

export const snapshotsFixture: Snapshot[] = [
  { total_value: 10000, recorded_at: "2026-10-01T14:30:00.000Z" },
  { total_value: 10120.5, recorded_at: "2026-10-01T14:30:30.000Z" },
  { total_value: 10485.6, recorded_at: "2026-10-01T14:31:00.000Z" },
];

export const chatHistoryFixture: ChatHistoryResponse = {
  messages: [
    {
      id: "m1",
      role: "user",
      content: "buy me 10 apple shares",
      actions: null,
      created_at: "2026-10-01T14:32:10.000Z",
    },
    {
      id: "m2",
      role: "assistant",
      content: "Bought 10 AAPL at $192.50. That's 19% of your portfolio.",
      actions: {
        trades: [
          {
            ticker: "AAPL",
            side: "buy",
            quantity: 10,
            status: "executed",
            price: 192.5,
            error: null,
          },
          {
            ticker: "TSLA",
            side: "buy",
            quantity: 100,
            status: "failed",
            price: null,
            error: "Need $24500.00, have $8075.00",
          },
        ],
        watchlist_changes: [
          { ticker: "PYPL", action: "add", status: "executed", error: null },
        ],
      },
      created_at: "2026-10-01T14:32:11.482Z",
    },
  ],
};
