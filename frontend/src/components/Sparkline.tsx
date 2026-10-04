"use client";

import { memo, useEffect, useRef } from "react";
import type { PricePoint } from "@/lib/priceStore";

interface Props {
  series: readonly PricePoint[];
  width?: number;
  height?: number;
  /** Colour follows the session trend, not the last tick, so the line doesn't strobe. */
  tone?: "up" | "down" | "flat";
  label?: string;
}

const TONE = {
  up: "#3fd18b",
  down: "#ff5c66",
  flat: "#5d6a7c",
} as const;

/**
 * Hand-rolled canvas sparkline. Ten of these redraw twice a second, so this avoids both a
 * charting-library instance per row and any SVG node churn — one `clearRect` and one path.
 */
function SparklineImpl({ series, width = 64, height = 20, tone = "flat", label }: Props) {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const context = canvas.getContext("2d");
    if (!context) return;

    const ratio = typeof window === "undefined" ? 1 : window.devicePixelRatio || 1;
    if (canvas.width !== width * ratio || canvas.height !== height * ratio) {
      canvas.width = width * ratio;
      canvas.height = height * ratio;
    }
    context.setTransform(ratio, 0, 0, ratio, 0, 0);
    context.clearRect(0, 0, width, height);

    if (series.length < 2) {
      // Pre-first-tick: a dashed rule reads as "no data yet" rather than as a flat price.
      context.strokeStyle = "#232c38";
      context.lineWidth = 1;
      context.setLineDash([2, 3]);
      context.beginPath();
      context.moveTo(0, height / 2 + 0.5);
      context.lineTo(width, height / 2 + 0.5);
      context.stroke();
      context.setLineDash([]);
      return;
    }

    let min = Infinity;
    let max = -Infinity;
    for (const point of series) {
      if (point.value < min) min = point.value;
      if (point.value > max) max = point.value;
    }
    const span = max - min || 1;
    const padding = 2;
    const usable = height - padding * 2;
    const step = width / (series.length - 1);
    const y = (value: number) => padding + usable - ((value - min) / span) * usable;

    const colour = TONE[tone];

    context.beginPath();
    context.moveTo(0, y(series[0].value));
    for (let i = 1; i < series.length; i += 1) context.lineTo(i * step, y(series[i].value));

    // Faint fill under the line gives the row visual weight without adding another colour.
    context.save();
    context.lineTo(width, height);
    context.lineTo(0, height);
    context.closePath();
    context.globalAlpha = 0.12;
    context.fillStyle = colour;
    context.fill();
    context.restore();

    context.beginPath();
    context.moveTo(0, y(series[0].value));
    for (let i = 1; i < series.length; i += 1) context.lineTo(i * step, y(series[i].value));
    context.strokeStyle = colour;
    context.lineWidth = 1;
    context.lineJoin = "round";
    context.stroke();

    context.beginPath();
    context.arc(width - 1, y(series[series.length - 1].value), 1.5, 0, Math.PI * 2);
    context.fillStyle = colour;
    context.fill();
  }, [series, width, height, tone]);

  return (
    <canvas
      ref={canvasRef}
      role="img"
      aria-label={
        label ?? (series.length < 2 ? "Sparkline, waiting for price data" : "Price sparkline")
      }
      data-points={series.length}
      style={{ width, height }}
      className="block"
    />
  );
}

export const Sparkline = memo(SparklineImpl);
