"use client";

import { useEffect, useRef, useState } from "react";
import { AreaSeries, createChart } from "lightweight-charts";
import type { IChartApi, ISeriesApi, LineData, UTCTimestamp } from "lightweight-charts";
import { EmptyState, Panel } from "@/components/Panel";
import { TickerReadout } from "@/components/TickerReadout";
import { baseChartOptions } from "@/lib/chartTheme";
import type { PricePoint } from "@/lib/priceStore";
import { usePriceStore } from "@/state/PriceStreamProvider";
import { useWorkstation } from "@/state/WorkstationProvider";

/**
 * Lightweight Charts renders to canvas and is driven imperatively here: ticks go straight from
 * the price store into `series.update()` without a React render in between. The component
 * itself only re-renders when the selected symbol changes.
 */
function toChartData(points: readonly PricePoint[]): LineData<UTCTimestamp>[] {
  // The series resolution is one second; the stream runs at ~500ms, so two samples can share a
  // second. Lightweight Charts requires strictly ascending times, so the later one wins.
  const data: LineData<UTCTimestamp>[] = [];
  for (const point of points) {
    const time = Math.floor(point.time) as UTCTimestamp;
    const last = data[data.length - 1];
    if (last && last.time === time) last.value = point.value;
    else data.push({ time, value: point.value });
  }
  return data;
}

export function MainChart() {
  const store = usePriceStore();
  const { selected } = useWorkstation();
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const seriesRef = useRef<ISeriesApi<"Area"> | null>(null);
  const [hasData, setHasData] = useState(false);

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    const options = baseChartOptions();
    const chart = createChart(container, {
      ...options,
      grid: { vertLines: { color: "#161d27" }, horzLines: { color: "#161d27" } },
      rightPriceScale: { ...options.rightPriceScale, scaleMargins: { top: 0.12, bottom: 0.08 } },
      timeScale: { ...options.timeScale, secondsVisible: true },
    });

    const series = chart.addSeries(AreaSeries, {
      lineColor: "#209dd7",
      topColor: "rgba(32, 157, 215, 0.28)",
      bottomColor: "rgba(32, 157, 215, 0.01)",
      lineWidth: 2,
      priceLineColor: "#ecad0a",
      priceLineStyle: 2,
      lastValueVisible: true,
    });

    chartRef.current = chart;
    seriesRef.current = series;

    return () => {
      chart.remove();
      chartRef.current = null;
      seriesRef.current = null;
    };
  }, []);

  useEffect(() => {
    const series = seriesRef.current;
    if (!series || !selected) {
      setHasData(false);
      return;
    }

    const paint = () => {
      const data = toChartData(store.getSeries(selected));
      setHasData(data.length > 0);
      series.setData(data);
    };

    paint();
    chartRef.current?.timeScale().fitContent();

    return store.subscribeTicker(selected)(() => {
      const points = store.getSeries(selected);
      const last = points[points.length - 1];
      if (!last) return;
      setHasData(true);
      series.update({ time: Math.floor(last.time) as UTCTimestamp, value: last.value });
      // History accumulates from zero, so keep refitting until there is enough of it to fill
      // the width; after that the chart scrolls on its own.
      if (points.length < 150) chartRef.current?.timeScale().fitContent();
    });
  }, [selected, store]);

  return (
    <Panel
      title="Chart"
      meta={
        selected ? (
          <>
            <span className="num text-data font-semibold tracking-tight text-accent">{selected}</span>
            <TickerReadout ticker={selected} />
          </>
        ) : null
      }
      bodyClassName="relative"
    >
      <div ref={containerRef} className="absolute inset-0" data-testid="main-chart" />
      {!hasData ? (
        <div className="absolute inset-0 z-10 flex items-center justify-center bg-surface/85">
          <EmptyState
            headline={selected ? `Waiting for ${selected}` : "No symbol selected"}
            hint={
              selected
                ? "Price history builds from the live stream — the chart fills in as ticks arrive."
                : "Pick a symbol in the watchlist to chart it."
            }
          />
        </div>
      ) : null}
    </Panel>
  );
}
