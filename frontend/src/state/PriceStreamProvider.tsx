"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useSyncExternalStore } from "react";
import type { ReactNode } from "react";
import { PriceStore, STREAM_PATH } from "@/lib/priceStore";
import type { ConnectionStatus, PricePoint, TickerTick } from "@/lib/priceStore";

const PriceStoreContext = createContext<PriceStore | null>(null);

interface Props {
  children: ReactNode;
  /** Tests inject a store that is already populated, or one that should not connect. */
  store?: PriceStore;
  /** Set false in tests so no component tries to open a real EventSource. */
  connect?: boolean;
  path?: string;
}

/**
 * Owns the app's only SSE connection. Mounted once, at the root — never per component.
 */
export function PriceStreamProvider({ children, store, connect = true, path = STREAM_PATH }: Props) {
  const instance = useMemo(() => store ?? new PriceStore(), [store]);

  useEffect(() => {
    if (!connect) return;
    return instance.connect(path);
  }, [instance, connect, path]);

  return <PriceStoreContext.Provider value={instance}>{children}</PriceStoreContext.Provider>;
}

export function usePriceStore(): PriceStore {
  const store = useContext(PriceStoreContext);
  if (!store) throw new Error("usePriceStore must be used inside <PriceStreamProvider>");
  return store;
}

/** Subscribes to one ticker only. A tick in another symbol does not re-render the caller. */
export function useTick(ticker: string): TickerTick | null {
  const store = usePriceStore();
  const subscribe = useMemo(() => store.subscribeTicker(ticker), [store, ticker]);
  const snapshot = useCallback(() => store.getTick(ticker), [store, ticker]);
  return useSyncExternalStore(subscribe, snapshot, snapshot);
}

/** The accumulated sparkline series for one ticker. Empty until the first tick lands. */
export function useSeries(ticker: string): readonly PricePoint[] {
  const store = usePriceStore();
  const subscribe = useMemo(() => store.subscribeTicker(ticker), [store, ticker]);
  const snapshot = useCallback(() => store.getSeries(ticker), [store, ticker]);
  return useSyncExternalStore(subscribe, snapshot, snapshot);
}

/**
 * Re-renders on every ingested event. Only for consumers that aggregate across all symbols;
 * per-row components must use `useTick` instead.
 */
export function useStreamVersion(): number {
  const store = usePriceStore();
  return useSyncExternalStore(store.subscribeAll, store.getVersion, store.getVersion);
}

export function useConnectionStatus(): ConnectionStatus {
  const store = usePriceStore();
  return useSyncExternalStore(store.subscribeStatus, store.getStatus, store.getStatus);
}
