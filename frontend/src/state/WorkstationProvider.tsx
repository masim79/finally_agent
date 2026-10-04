"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import type { ReactNode } from "react";
import { ApiError, api } from "@/lib/api";
import type { Portfolio, Side, Snapshot, WatchlistEntry } from "@/lib/types";
import { usePriceStore } from "./PriceStreamProvider";

export interface Notice {
  tone: "ok" | "error";
  text: string;
  /** Monotonic, so an identical message twice in a row still re-announces. */
  key: number;
}

interface WorkstationValue {
  portfolio: Portfolio | null;
  watchlist: WatchlistEntry[];
  snapshots: Snapshot[];
  loading: boolean;
  /** Set when the first load fails outright — the panels show it instead of a false zero. */
  loadError: string | null;
  notice: Notice | null;
  selected: string | null;
  select: (ticker: string) => void;
  refresh: () => Promise<void>;
  executeTrade: (ticker: string, quantity: number, side: Side) => Promise<boolean>;
  addTicker: (ticker: string) => Promise<boolean>;
  removeTicker: (ticker: string) => Promise<boolean>;
}

const WorkstationContext = createContext<WorkstationValue | null>(null);

function describe(error: unknown): string {
  if (error instanceof ApiError) return error.message;
  return "Something went wrong. Try again.";
}

interface Props {
  children: ReactNode;
  /** Tests mount with data already in place and no network. */
  initialPortfolio?: Portfolio | null;
  initialWatchlist?: WatchlistEntry[];
  initialSnapshots?: Snapshot[];
  autoLoad?: boolean;
}

export function WorkstationProvider({
  children,
  initialPortfolio = null,
  initialWatchlist = [],
  initialSnapshots = [],
  autoLoad = true,
}: Props) {
  const priceStore = usePriceStore();
  const [portfolio, setPortfolio] = useState<Portfolio | null>(initialPortfolio);
  const [watchlist, setWatchlist] = useState<WatchlistEntry[]>(initialWatchlist);
  const [snapshots, setSnapshots] = useState<Snapshot[]>(initialSnapshots);
  const [loading, setLoading] = useState(autoLoad);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [notice, setNotice] = useState<Notice | null>(null);
  const [selected, setSelected] = useState<string | null>(initialWatchlist[0]?.ticker ?? null);
  const noticeKey = useRef(0);

  const announce = useCallback((tone: Notice["tone"], text: string) => {
    noticeKey.current += 1;
    setNotice({ tone, text, key: noticeKey.current });
  }, []);

  const applyWatchlist = useCallback(
    (entries: WatchlistEntry[]) => {
      // The REST price is the first price the page has seen for a symbol, so it becomes the
      // session baseline the daily-change column measures against.
      entries.forEach((entry) => priceStore.seedBaseline(entry.ticker, entry.price));
      priceStore.prune(entries.map((entry) => entry.ticker));
      setWatchlist(entries);
      setSelected((current) => {
        if (current && entries.some((entry) => entry.ticker === current)) return current;
        return entries[0]?.ticker ?? null;
      });
    },
    [priceStore],
  );

  const refresh = useCallback(async () => {
    try {
      const [nextPortfolio, nextWatchlist, history] = await Promise.all([
        api.getPortfolio(),
        api.getWatchlist(),
        api.getPortfolioHistory(),
      ]);
      setPortfolio(nextPortfolio);
      applyWatchlist(nextWatchlist.tickers);
      setSnapshots(history.snapshots);
      setLoadError(null);
    } catch (error) {
      setLoadError(describe(error));
    } finally {
      setLoading(false);
    }
  }, [applyWatchlist]);

  useEffect(() => {
    if (!autoLoad) return;
    let cancelled = false;
    void (async () => {
      if (!cancelled) await refresh();
    })();
    return () => {
      cancelled = true;
    };
  }, [autoLoad, refresh]);

  const executeTrade = useCallback(
    async (ticker: string, quantity: number, side: Side) => {
      try {
        const result = await api.trade(ticker, quantity, side);
        announce(
          "ok",
          `${side === "buy" ? "Bought" : "Sold"} ${result.trade.quantity} ${result.trade.ticker} at $${result.trade.price.toFixed(2)}`,
        );
        // The SSE stream carries prices only, so positions and cash have to be re-read.
        await refresh();
        return true;
      } catch (error) {
        announce("error", describe(error));
        return false;
      }
    },
    [announce, refresh],
  );

  const addTicker = useCallback(
    async (ticker: string) => {
      try {
        const entry = await api.addTicker(ticker);
        priceStore.seedBaseline(entry.ticker, entry.price);
        announce("ok", `Added ${entry.ticker} to the watchlist`);
        await refresh();
        setSelected(entry.ticker);
        return true;
      } catch (error) {
        announce("error", describe(error));
        return false;
      }
    },
    [announce, priceStore, refresh],
  );

  const removeTicker = useCallback(
    async (ticker: string) => {
      try {
        await api.removeTicker(ticker);
        announce("ok", `Removed ${ticker} from the watchlist`);
        await refresh();
        return true;
      } catch (error) {
        announce("error", describe(error));
        return false;
      }
    },
    [announce, refresh],
  );

  const value = useMemo<WorkstationValue>(
    () => ({
      portfolio,
      watchlist,
      snapshots,
      loading,
      loadError,
      notice,
      selected,
      select: setSelected,
      refresh,
      executeTrade,
      addTicker,
      removeTicker,
    }),
    [
      portfolio,
      watchlist,
      snapshots,
      loading,
      loadError,
      notice,
      selected,
      refresh,
      executeTrade,
      addTicker,
      removeTicker,
    ],
  );

  return <WorkstationContext.Provider value={value}>{children}</WorkstationContext.Provider>;
}

export function useWorkstation(): WorkstationValue {
  const value = useContext(WorkstationContext);
  if (!value) throw new Error("useWorkstation must be used inside <WorkstationProvider>");
  return value;
}
