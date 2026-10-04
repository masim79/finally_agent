"use client";

import { memo } from "react";
import { EMPTY, clockFromUnixSeconds, price as formatPrice, signedMoney, signedPercent } from "@/lib/format";
import { flashToken } from "@/lib/priceStore";
import { useTick } from "@/state/PriceStreamProvider";

/**
 * The live numbers for one symbol, isolated in its own component so a tick repaints these few
 * characters instead of re-rendering the chart panel around them.
 */
function TickerReadoutImpl({ ticker }: { ticker: string }) {
  const tick = useTick(ticker);
  const tone =
    tick == null || tick.dailyChange === 0 ? "flat" : tick.dailyChange > 0 ? "up" : "down";

  return (
    <div className="flex items-baseline gap-3">
      <span
        data-testid={`readout-price-${ticker}`}
        data-flash={flashToken(tick)}
        className="num px-1 text-[1.0625rem] leading-none font-medium text-ink"
      >
        {tick ? formatPrice(tick.price) : EMPTY}
      </span>
      <span
        className={`num text-tiny ${
          tone === "up" ? "text-up" : tone === "down" ? "text-down" : "text-ink-3"
        }`}
      >
        {tick ? `${signedMoney(tick.dailyChange)}  ${signedPercent(tick.dailyChangePercent)}` : EMPTY}
      </span>
      <span className="num text-micro text-ink-3">
        {tick ? clockFromUnixSeconds(tick.timestamp) : "––:––:––"}
      </span>
    </div>
  );
}

export const TickerReadout = memo(TickerReadoutImpl);
