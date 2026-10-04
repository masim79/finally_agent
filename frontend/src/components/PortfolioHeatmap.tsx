"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { EmptyState, Panel } from "@/components/Panel";
import { money, signedPercent } from "@/lib/format";
import { squarify } from "@/lib/treemap";
import { useWorkstation } from "@/state/WorkstationProvider";

/** Saturation saturates at ±5%, so ordinary moves stay readable and outliers still shout. */
const CLAMP = 5;

/**
 * Direction and magnitude as a tinted surface, not as paint.
 *
 * The ceiling is deliberately low. One position routinely owns most of this panel — a single
 * 290×374 tile — and an alpha tuned for a 60px chip turns that tile into a fluorescent slab
 * that outshouts every other instrument on the terminal. Full-strength colour lives in the 2px
 * edge rail and in the P&L figure, both of which stay the same size whatever the tile does;
 * the fill only has to rank tiles against each other.
 *
 * NOTE: test/fixtures/api.ts mirrors this in `expectedTileColor()` for the E2E heatmap spec.
 * Change one, change the other.
 */
function tileColor(pnlPercent: number): string {
  const magnitude = Math.min(Math.abs(pnlPercent) / CLAMP, 1);
  const alpha = 0.12 + magnitude * 0.26;
  if (Math.abs(pnlPercent) < 0.0001) return "rgba(93, 106, 124, 0.18)";
  return pnlPercent > 0
    ? `rgba(63, 209, 139, ${alpha.toFixed(3)})`
    : `rgba(255, 92, 102, ${alpha.toFixed(3)})`;
}

export type Tier = "bare" | "strip" | "block" | "rich";

/**
 * A treemap tile's shape is decided by the data, not by the designer, so the label treatment has
 * to follow it. Four tiers, measured in DRAWN px (after the 2px gutter) against what actually
 * fits at 11px mono:
 *   bare  — a sliver; the rail and the fill are the whole message
 *   strip — a band too short to stack anything; ticker and P&L share one baseline
 *   block — room for a stacked label group, pinned together at the top
 *   rich  — room for a footer rule as well, so value and weight get a home of their own
 */
export function tierFor(w: number, h: number): Tier {
  if (w < 26 || h < 16) return "bare";
  if (h < 56) return "strip";
  if (h >= 104 && w >= 150) return "rich";
  return "block";
}

/**
 * Ceiling on a single tile, in px². Past roughly this a position stops reading as a tile in a
 * field and starts reading as a wall with a label on it. Tuned so the desktop rail's panel only
 * just needs it — the field then sits inset by ~20px, which reads as margin rather than as a
 * cluster stranded in a void — while the wider tablet panel gets pulled back harder.
 */
export const MAX_TILE_AREA = 28_000;

/**
 * Floor on how far the ceiling may shrink the field, as a fraction of the container's linear
 * size. A fixed area ceiling cannot serve a 294×226 rail panel and a 508×376 tablet panel at
 * once: honoured literally on the wide one it leaves a small cluster marooned in a lot of empty
 * panel, which looks worse than the big tile it was avoiding. At 0.72 the inset never exceeds a
 * seventh of the panel per side, so what is left always reads as margin. The desktop rail never
 * reaches the floor — only the oversized tablet panel does.
 */
const MIN_FIELD_SCALE = 0.72;

export interface Field {
  width: number;
  height: number;
  offsetX: number;
  offsetY: number;
}

/**
 * `squarify` fills whatever box it is handed, so a two-position book in a tall panel yields one
 * enormous rectangle rather than a treemap. The packing is right — the box is wrong. Scale the
 * box down uniformly (which scales every tile by the same factor, leaving the proportions and
 * the near-square aspect the algorithm works for untouched) until the largest tile fits under
 * the ceiling, then centre what is left. A full book needs no scaling and still runs full-bleed.
 */
export function fitField(values: number[], width: number, height: number): Field {
  const whole: Field = { width, height, offsetX: 0, offsetY: 0 };
  if (width <= 0 || height <= 0) return whole;

  const positive = values.filter((value) => value > 0);
  const total = positive.reduce((sum, value) => sum + value, 0);
  if (total <= 0) return whole;

  const largest = (Math.max(...positive) / total) * width * height;
  if (largest <= MAX_TILE_AREA) return whole;

  const scale = Math.max(MIN_FIELD_SCALE, Math.sqrt(MAX_TILE_AREA / largest));
  const scaled = { width: width * scale, height: height * scale };
  return {
    ...scaled,
    offsetX: (width - scaled.width) / 2,
    offsetY: (height - scaled.height) / 2,
  };
}

export function PortfolioHeatmap() {
  const { portfolio, select, selected } = useWorkstation();
  const containerRef = useRef<HTMLDivElement>(null);
  const [size, setSize] = useState({ width: 0, height: 0 });

  useEffect(() => {
    const element = containerRef.current;
    if (!element || typeof ResizeObserver === "undefined") return;
    const observer = new ResizeObserver(([entry]) => {
      const { width, height } = entry.contentRect;
      setSize({ width, height });
    });
    observer.observe(element);
    return () => observer.disconnect();
  }, []);

  const positions = useMemo(() => portfolio?.positions ?? [], [portfolio]);

  const field = useMemo(
    () =>
      fitField(
        positions.map((position) => position.market_value),
        size.width,
        size.height,
      ),
    [positions, size.width, size.height],
  );

  const tiles = useMemo(
    () =>
      squarify(
        positions.map((position) => ({ key: position.ticker, value: position.market_value })),
        field.width,
        field.height,
      ),
    [positions, field.width, field.height],
  );

  const byTicker = useMemo(
    () => new Map(positions.map((position) => [position.ticker, position])),
    [positions],
  );

  /* The tiles divide the invested dollar, so AAPL can own 87% of this panel while the Positions
     table calls it 37% of the book — the difference is cash, which has no tile. Rather than let
     two numbers contradict each other one panel apart, every tile prints the same net-liq weight
     the table prints, and this rail states the frame of reference the areas are drawn in. */
  const investedPercent =
    portfolio && portfolio.total_value > 0
      ? (portfolio.positions_value / portfolio.total_value) * 100
      : 0;

  return (
    <Panel
      title="Allocation"
      meta={
        positions.length > 0 ? (
          <span className="num text-micro text-ink-3">{positions.length} pos</span>
        ) : null
      }
      bodyClassName="flex min-h-0 flex-col"
    >
      <div className="relative min-h-0 flex-1">
        <div ref={containerRef} className="absolute inset-0 p-px" data-testid="heatmap">
          {positions.length === 0 ? (
            <EmptyState
              headline="No positions"
              hint="Buy a symbol from the command line below and it appears here, sized by weight."
            />
          ) : (
            tiles.map((tile) => {
              const position = byTicker.get(tile.key);
              if (!position) return null;
              const w = Math.max(tile.w - 2, 0);
              const h = Math.max(tile.h - 2, 0);
              const tier = tierFor(w, h);
              const pnlPercent = position.unrealized_pnl_percent;
              const weight = `${(position.weight * 100).toFixed(1)}%`;
              const isSelected = tile.key === selected;
              const rail =
                pnlPercent > 0.0001 ? "bg-up" : pnlPercent < -0.0001 ? "bg-down" : "bg-ink-3";

              return (
                <button
                  type="button"
                  key={tile.key}
                  onClick={() => select(tile.key)}
                  title={`${tile.key} · ${money(position.market_value)} · ${signedPercent(pnlPercent)} · ${weight} of book`}
                  style={{
                    left: field.offsetX + tile.x,
                    top: field.offsetY + tile.y,
                    width: w,
                    height: h,
                    backgroundColor: tileColor(pnlPercent),
                  }}
                  /* Every figure hangs off the same left axis as the rail — a tile can be 437px
                     wide or 38px tall, and pushing the pair to opposite edges stops them reading
                     as one label the moment the tile grows. */
                  className={`absolute flex overflow-hidden border border-white/10 text-left transition-[outline-color] ${
                    tier === "strip" ? "items-center gap-2" : "flex-col justify-between"
                  } ${
                    isSelected
                      ? "outline outline-accent"
                      : "outline outline-transparent hover:outline-ink-3"
                  }`}
                >
                  {/* The one place colour runs at full strength. It is 2px wide whatever the tile
                      does, so a 54px sliver at +0.17% — where the fill is all but transparent —
                      still reads as a tile, and still says which way it is going. */}
                  <span aria-hidden className={`absolute inset-y-0 left-0 w-[2px] ${rail}`} />

                  {tier === "bare" ? null : tier === "strip" ? (
                    <>
                      <span className="num pl-2 text-tiny leading-none font-semibold text-ink">
                        {tile.key}
                      </span>
                      {w >= 96 ? (
                        <span className="num text-micro leading-none text-ink/75">
                          {signedPercent(pnlPercent)}
                        </span>
                      ) : null}
                    </>
                  ) : (
                    <>
                      <span className="flex flex-col gap-0.5 py-1.5 pr-1.5 pl-2">
                        <span className="num text-tiny leading-none font-semibold text-ink">
                          {tile.key}
                        </span>
                        {/* A narrow column fits a four-letter symbol and nothing else; half a
                            percentage clipped by `overflow-hidden` is worse than none. */}
                        {w >= 56 ? (
                          <span className="num text-micro leading-none text-ink/75">
                            {signedPercent(pnlPercent)}
                          </span>
                        ) : null}
                      </span>
                      {tier === "rich" ? (
                        <span className="flex items-baseline gap-2.5 border-t border-white/10 py-1.5 pr-1.5 pl-2">
                          <span className="num text-micro leading-none text-ink/70">
                            {money(position.market_value)}
                          </span>
                          <span className="flex items-baseline gap-1">
                            <span className="label">Wgt</span>
                            <span className="num text-micro leading-none text-ink-2">{weight}</span>
                          </span>
                        </span>
                      ) : null}
                    </>
                  )}
                </button>
              );
            })
          )}
        </div>
      </div>

      {positions.length > 0 ? (
        <div
          data-testid="exposure-rail"
          className="relative flex h-[18px] shrink-0 items-center justify-between overflow-hidden border-t border-line bg-surface-2/70 px-2"
        >
          <span
            aria-hidden
            className="absolute inset-y-0 left-0 bg-blue/15"
            style={{ width: `${investedPercent.toFixed(1)}%` }}
          />
          <span className="relative flex items-baseline gap-1">
            <span className="label">Invested</span>
            <span className="num text-micro text-ink-2">{investedPercent.toFixed(1)}%</span>
          </span>
          <span className="relative flex items-baseline gap-1">
            <span className="num text-micro text-ink-2">
              {(100 - investedPercent).toFixed(1)}%
            </span>
            <span className="label">Cash</span>
          </span>
        </div>
      ) : null}
    </Panel>
  );
}
