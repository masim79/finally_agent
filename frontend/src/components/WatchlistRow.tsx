"use client";

import { memo } from "react";
import { Sparkline } from "@/components/Sparkline";
import { EMPTY, price as formatPrice, signedPercent } from "@/lib/format";
import { flashToken } from "@/lib/priceStore";
import { useSeries, useTick } from "@/state/PriceStreamProvider";
import type { WatchlistEntry } from "@/lib/types";

interface Props {
  entry: WatchlistEntry;
  selected: boolean;
  onSelect: (ticker: string) => void;
  onRemove: (ticker: string) => void;
}

/**
 * One row, subscribed to one symbol. Memoised and reading the store directly, so a tick in
 * NVDA re-renders the NVDA row only — the other nine never see it.
 */
function WatchlistRowImpl({ entry, selected, onSelect, onRemove }: Props) {
  const tick = useTick(entry.ticker);
  const series = useSeries(entry.ticker);

  // Before the first tick the REST snapshot still has a price worth showing; if that is null
  // too (cold cache) the row renders its waiting state rather than a fabricated zero.
  const livePrice = tick?.price ?? entry.price;
  const dailyPercent = tick?.dailyChangePercent ?? null;
  const tone = dailyPercent == null || dailyPercent === 0 ? "flat" : dailyPercent > 0 ? "up" : "down";

  return (
    <div
      role="row"
      aria-selected={selected}
      className={`group relative grid h-[30px] grid-cols-[2.75rem_minmax(0,1fr)_3.5rem_64px] items-center gap-2 border-b border-line-soft pr-2 pl-2.5 text-data transition-colors ${
        selected
          ? "bg-surface-3 before:absolute before:inset-y-0 before:left-0 before:w-[2px] before:bg-accent before:content-['']"
          : "hover:bg-surface-2"
      }`}
    >
      <button
        type="button"
        onClick={() => onSelect(entry.ticker)}
        className={`num cursor-pointer text-left text-[0.8125rem] font-medium tracking-tight ${
          selected ? "text-accent" : "text-ink group-hover:text-blue"
        }`}
        aria-label={`Show ${entry.ticker} on the main chart`}
      >
        {entry.ticker}
      </button>

      <span
        data-testid={`price-${entry.ticker}`}
        data-flash={flashToken(tick)}
        className="num justify-self-end px-1 text-right text-ink"
      >
        {livePrice == null ? EMPTY : formatPrice(livePrice)}
      </span>

      <span
        data-testid={`change-${entry.ticker}`}
        className={`num text-right text-tiny ${
          tone === "up" ? "text-up" : tone === "down" ? "text-down" : "text-ink-3"
        }`}
        title="Change since this page loaded"
      >
        {dailyPercent == null ? EMPTY : signedPercent(dailyPercent)}
      </span>

      <span className="justify-self-end">
        <Sparkline
          series={series}
          tone={tone}
          label={
            series.length < 2
              ? `${entry.ticker} sparkline, waiting for price data`
              : `${entry.ticker} price trend`
          }
        />
      </span>

      <button
        type="button"
        onClick={() => onRemove(entry.ticker)}
        aria-label={`Remove ${entry.ticker} from the watchlist`}
        className="absolute top-1/2 right-0.5 hidden h-4 w-4 -translate-y-1/2 cursor-pointer items-center justify-center bg-surface-3 text-[0.65rem] leading-none text-ink-3 hover:text-down group-focus-within:flex group-hover:flex"
      >
        ×
      </button>
    </div>
  );
}

export const WatchlistRow = memo(WatchlistRowImpl);
