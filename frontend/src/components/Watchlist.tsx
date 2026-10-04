"use client";

import { useCallback, useState } from "react";
import { EmptyState, Panel } from "@/components/Panel";
import { WatchlistRow } from "@/components/WatchlistRow";
import { normalizeTicker } from "@/lib/format";
import { useWorkstation } from "@/state/WorkstationProvider";

export function Watchlist() {
  const { watchlist, selected, select, addTicker, removeTicker, loading } = useWorkstation();
  const [draft, setDraft] = useState("");
  const [busy, setBusy] = useState(false);

  const handleRemove = useCallback(
    (ticker: string) => {
      void removeTicker(ticker);
    },
    [removeTicker],
  );

  async function handleAdd(event: React.FormEvent) {
    event.preventDefault();
    const ticker = normalizeTicker(draft);
    if (!ticker || busy) return;
    setBusy(true);
    const ok = await addTicker(ticker);
    setBusy(false);
    if (ok) setDraft("");
  }

  return (
    <Panel
      title="Watchlist"
      meta={<span className="num text-micro text-ink-3">{watchlist.length}</span>}
      bodyClassName="flex flex-col min-h-0"
    >
      <div
        className="grid h-5 shrink-0 grid-cols-[2.75rem_minmax(0,1fr)_3.5rem_64px] items-center gap-2 border-b border-line bg-surface-2/60 pr-2 pl-2.5"
        role="row"
      >
        <span className="label">Sym</span>
        <span className="label justify-self-end">Last</span>
        <span className="label justify-self-end">Sess %</span>
        <span className="label justify-self-end">Trend</span>
      </div>

      {/* The rows end where the data ends, so the add control stays attached to the list it
          adds to instead of being pushed to the panel floor with a void between them. Any
          slack falls below the form as inert background. An empty watchlist is the one case
          that still grows, so its EmptyState has a box to centre itself in. */}
      <div
        role="rowgroup"
        className={`min-h-0 overflow-y-auto ${watchlist.length === 0 ? "flex-1" : ""}`}
      >
        {watchlist.length === 0 ? (
          <EmptyState
            headline={loading ? "Loading watchlist" : "Watchlist is empty"}
            hint={loading ? undefined : "Add a symbol below to start streaming its price."}
          />
        ) : (
          watchlist.map((entry) => (
            <WatchlistRow
              key={entry.ticker}
              entry={entry}
              selected={entry.ticker === selected}
              onSelect={select}
              onRemove={handleRemove}
            />
          ))
        )}
      </div>

      <form
        onSubmit={handleAdd}
        className="flex h-8 shrink-0 items-center gap-1.5 border-t border-line bg-surface-2 px-2"
      >
        <label htmlFor="add-ticker" className="label">
          Add
        </label>
        <input
          id="add-ticker"
          value={draft}
          onChange={(event) => setDraft(normalizeTicker(event.target.value))}
          placeholder="PYPL"
          maxLength={8}
          autoComplete="off"
          className="num min-w-0 flex-1 border border-line bg-surface px-1.5 py-0.5 text-data tracking-tight text-ink placeholder:text-ink-3 focus:border-blue focus:outline-none"
        />
        <button
          type="submit"
          disabled={busy || draft.length === 0}
          className="cursor-pointer border border-purple/70 bg-purple/25 px-2 py-0.5 text-micro font-semibold tracking-[0.12em] text-ink uppercase transition-colors hover:bg-purple/45 disabled:cursor-not-allowed disabled:opacity-40"
        >
          {busy ? "…" : "Add"}
        </button>
      </form>
    </Panel>
  );
}
