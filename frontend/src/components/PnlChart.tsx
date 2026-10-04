"use client";

import { useEffect, useMemo, useRef } from "react";
import { AreaSeries, createChart } from "lightweight-charts";
import type { IChartApi, ISeriesApi, LineData, UTCTimestamp } from "lightweight-charts";
import { EmptyState, Panel } from "@/components/Panel";
import { baseChartOptions } from "@/lib/chartTheme";
import { moneyCompact, signedMoney, signedPercent } from "@/lib/format";
import type { Snapshot } from "@/lib/types";
import { useWorkstation } from "@/state/WorkstationProvider";

function toSeries(snapshots: Snapshot[]): LineData<UTCTimestamp>[] {
  const data: LineData<UTCTimestamp>[] = [];
  for (const snapshot of snapshots) {
    // REST timestamps are ISO-8601 strings; Lightweight Charts wants Unix seconds.
    const parsed = Date.parse(snapshot.recorded_at);
    if (Number.isNaN(parsed)) continue;
    const time = Math.floor(parsed / 1000) as UTCTimestamp;
    const last = data[data.length - 1];
    if (last && last.time === time) last.value = snapshot.total_value;
    else data.push({ time, value: snapshot.total_value });
  }
  return data;
}

export function PnlChart() {
  const { snapshots } = useWorkstation();
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const seriesRef = useRef<ISeriesApi<"Area"> | null>(null);

  const data = useMemo(() => toSeries(snapshots), [snapshots]);
  const first = data[0]?.value ?? null;
  const last = data[data.length - 1]?.value ?? null;
  const delta = first != null && last != null ? last - first : null;
  const deltaPercent = first ? ((last as number) - first) / first * 100 : null;
  const positive = (delta ?? 0) >= 0;

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    const options = baseChartOptions();
    const chart = createChart(container, {
      ...options,
      grid: { vertLines: { visible: false }, horzLines: { color: "#161d27" } },
      rightPriceScale: { ...options.rightPriceScale, scaleMargins: { top: 0.18, bottom: 0.1 } },
      timeScale: { ...options.timeScale, secondsVisible: false },
    });

    seriesRef.current = chart.addSeries(AreaSeries, { lineWidth: 2 });
    chartRef.current = chart;

    return () => {
      chart.remove();
      chartRef.current = null;
      seriesRef.current = null;
    };
  }, []);

  useEffect(() => {
    const series = seriesRef.current;
    if (!series) return;
    series.applyOptions({
      lineColor: positive ? "#3fd18b" : "#ff5c66",
      topColor: positive ? "rgba(63, 209, 139, 0.24)" : "rgba(255, 92, 102, 0.24)",
      bottomColor: "rgba(13, 17, 23, 0)",
    });
    series.setData(data);
    chartRef.current?.timeScale().fitContent();
  }, [data, positive]);

  return (
    <Panel
      title="Portfolio value"
      meta={
        delta == null ? null : (
          <span className={`num text-tiny ${positive ? "text-up" : "text-down"}`}>
            {signedMoney(delta)} {signedPercent(deltaPercent)}
          </span>
        )
      }
      bodyClassName="relative"
    >
      <div ref={containerRef} className="absolute inset-0" data-testid="pnl-chart" />
      {data.length > 0 ? (
        <div className="pointer-events-none absolute top-1.5 left-2 z-10 flex gap-3">
          <span className="num text-micro text-ink-3">open {moneyCompact(first)}</span>
          <span className="num text-micro text-ink-2">last {moneyCompact(last)}</span>
        </div>
      ) : null}
      {data.length === 0 ? (
        <div className="absolute inset-0 z-10 flex items-center justify-center bg-surface/85">
          <EmptyState
            headline="No snapshots yet"
            hint="Portfolio value is recorded every 30 seconds and after every trade."
          />
        </div>
      ) : null}
    </Panel>
  );
}
