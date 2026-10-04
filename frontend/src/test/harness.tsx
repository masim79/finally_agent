import { render } from "@testing-library/react";
import type { ReactElement } from "react";
import { PriceStore } from "@/lib/priceStore";
import { ChatProvider } from "@/state/ChatProvider";
import type { ChatEntry } from "@/state/ChatProvider";
import { PriceStreamProvider } from "@/state/PriceStreamProvider";
import { WorkstationProvider } from "@/state/WorkstationProvider";
import type { Portfolio, Snapshot, WatchlistEntry } from "@/lib/types";

interface Options {
  store?: PriceStore;
  portfolio?: Portfolio | null;
  watchlist?: WatchlistEntry[];
  snapshots?: Snapshot[];
  chatEntries?: ChatEntry[];
}

/**
 * Mounts a component inside the real providers with data already in place and no network:
  * `connect={false}` keeps any component from opening an EventSource, and `autoLoad={false}`
 * keeps the providers from fetching.
 */
export function renderWithProviders(ui: ReactElement, options: Options = {}) {
  const store = options.store ?? new PriceStore();
  const result = render(
    <PriceStreamProvider store={store} connect={false}>
      <WorkstationProvider
        autoLoad={false}
        initialPortfolio={options.portfolio ?? null}
        initialWatchlist={options.watchlist ?? []}
        initialSnapshots={options.snapshots ?? []}
      >
        <ChatProvider loadHistory={false} initialEntries={options.chatEntries ?? []}>
          {ui}
        </ChatProvider>
      </WorkstationProvider>
    </PriceStreamProvider>,
  );
  return { ...result, store };
}
