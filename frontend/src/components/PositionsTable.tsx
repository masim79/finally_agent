"use client";

import { memo } from "react";
import { EmptyState, Panel } from "@/components/Panel";
import {
  money,
  price as formatPrice,
  quantity as formatQuantity,
  signedMoney,
  signedPercent,
} from "@/lib/format";
import { flashToken } from "@/lib/priceStore";
import type { Position } from "@/lib/types";
import { usePriceStore, useStreamVersion, useTick } from "@/state/PriceStreamProvider";
import { useWorkstation } from "@/state/WorkstationProvider";

/** Selection marker as a pseudo-element: an extra conditional <span> would shift the column
 *  order of every row depending on whether it happens to be selected. */
const MARK =
  "before:absolute before:inset-y-0 before:left-0 before:w-[2px] before:bg-accent before:content-['']";

const GRID =
  "grid grid-cols-[3.5rem_minmax(0,1fr)_minmax(0,1fr)_minmax(0,1fr)_minmax(0,1.1fr)_minmax(0,1.1fr)_4.5rem_3.5rem] items-center gap-2 px-2.5";

interface RowProps {
  position: Position;
  selected: boolean;
  onSelect: (ticker: string) => void;
}

/**
 * Marked to market from the live stream rather than from the last `/api/portfolio` read, so
 * P&L moves with the tape. Falls back to the REST figures before the first tick for a symbol.
 */
function PositionRowImpl({ position, selected, onSelect }: RowProps) {
  const tick = useTick(position.ticker);
  const livePrice = tick?.price ?? position.current_price;
  const marketValue = livePrice * position.quantity;
  const pnl = (livePrice - position.avg_cost) * position.quantity;
  const pnlPercent = position.avg_cost === 0 ? 0 : (livePrice / position.avg_cost - 1) * 100;
  const tone = pnl > 0 ? "text-up" : pnl < 0 ? "text-down" : "text-ink-2";

  return (
    <button
      type="button"
      onClick={() => onSelect(position.ticker)}
      className={`${GRID} relative h-7 w-full border-b border-line-soft text-left text-data transition-colors ${
        selected ? `bg-surface-3 ${MARK}` : "hover:bg-surface-2"
      }`}
    >
      <span className={`num font-medium ${selected ? "text-accent" : "text-ink"}`}>
        {position.ticker}
      </span>
      <span className="num text-right text-ink-2">{formatQuantity(position.quantity)}</span>
      <span className="num text-right text-ink-2">{formatPrice(position.avg_cost)}</span>
      <span
        data-testid={`position-price-${position.ticker}`}
        data-flash={flashToken(tick)}
        className="num px-1 text-right text-ink"
      >
        {formatPrice(livePrice)}
      </span>
      <span className="num text-right text-ink">{money(marketValue)}</span>
      <span className={`num text-right ${tone}`}>{signedMoney(pnl)}</span>
      <span className={`num text-right ${tone}`}>{signedPercent(pnlPercent)}</span>
      <span className="num text-right text-ink-3">{(position.weight * 100).toFixed(1)}%</span>
    </button>
  );
}

const PositionRow = memo(PositionRowImpl);

/**
 * The book's total, marked to the same live prices as the rows. Isolated so the aggregate
 * subscription repaints this readout and not the table underneath it.
 */
function LiveTotal({ positions }: { positions: Position[] }) {
  const store = usePriceStore();
  useStreamVersion();

  let pnl = 0;
  let cost = 0;
  for (const position of positions) {
    const livePrice = store.getTick(position.ticker)?.price ?? position.current_price;
    pnl += (livePrice - position.avg_cost) * position.quantity;
    cost += position.avg_cost * position.quantity;
  }
  const percent = cost === 0 ? 0 : (pnl / cost) * 100;

  return (
    <span className={`num text-tiny ${pnl >= 0 ? "text-up" : "text-down"}`}>
      {signedMoney(pnl)} {signedPercent(percent)}
    </span>
  );
}

export function PositionsTable() {
  const { portfolio, selected, select, loading } = useWorkstation();
  const positions = portfolio?.positions ?? [];

  return (
    <Panel
      title="Positions"
      meta={positions.length > 0 ? <LiveTotal positions={positions} /> : null}
      bodyClassName="flex flex-col min-h-0"
    >
      <div className={`${GRID} h-5 shrink-0 border-b border-line bg-surface-2/60`}>
        <span className="label">Sym</span>
        <span className="label text-right">Qty</span>
        <span className="label text-right">Avg</span>
        <span className="label text-right">Last</span>
        <span className="label text-right">Value</span>
        <span className="label text-right">P&amp;L</span>
        <span className="label text-right">P&amp;L %</span>
        <span className="label text-right">Wgt</span>
      </div>
      <div className="min-h-0 flex-1 overflow-y-auto">
        {positions.length === 0 ? (
          <EmptyState
            headline={loading ? "Loading positions" : "Flat — no open positions"}
            hint={loading ? undefined : "Every dollar is in cash. Use the command line to open one."}
          />
        ) : (
          positions.map((position) => (
            <PositionRow
              key={position.ticker}
              position={position}
              selected={position.ticker === selected}
              onSelect={select}
            />
          ))
        )}
      </div>
    </Panel>
  );
}
