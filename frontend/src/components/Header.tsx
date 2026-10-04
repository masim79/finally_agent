"use client";

import { clockFromUnixSeconds, money, signedMoney, signedPercent } from "@/lib/format";
import { usePriceStore, useConnectionStatus, useStreamVersion } from "@/state/PriceStreamProvider";
import { useWorkstation } from "@/state/WorkstationProvider";
import type { ConnectionStatus } from "@/lib/priceStore";

const STATUS: Record<ConnectionStatus, { color: string; label: string; pulse: boolean }> = {
  connecting: { color: "bg-accent", label: "Connecting", pulse: true },
  live: { color: "bg-up", label: "Live", pulse: false },
  reconnecting: { color: "bg-accent", label: "Reconnecting", pulse: true },
  offline: { color: "bg-down", label: "Disconnected", pulse: false },
};

function Stat({
  label,
  value,
  tone = "text-ink",
  size = "text-data",
}: {
  label: string;
  value: string;
  tone?: string;
  size?: string;
}) {
  return (
    <div className="flex flex-col justify-center gap-0.5">
      <span className="label leading-none">{label}</span>
      <span className={`num leading-none ${size} ${tone}`}>{value}</span>
    </div>
  );
}

export function Header() {
  const { portfolio } = useWorkstation();
  const store = usePriceStore();
  const status = useConnectionStatus();
  // Net liquidation value has to aggregate every held symbol, so this is the one place that
  // re-renders on every event rather than per ticker.
  useStreamVersion();

  const positions = portfolio?.positions ?? [];
  const cash = portfolio?.cash_balance ?? null;

  let positionsValue = 0;
  let unrealized = 0;
  let cost = 0;
  for (const position of positions) {
    const livePrice = store.getTick(position.ticker)?.price ?? position.current_price;
    positionsValue += livePrice * position.quantity;
    unrealized += (livePrice - position.avg_cost) * position.quantity;
    cost += position.avg_cost * position.quantity;
  }
  const netLiq = cash == null ? null : cash + positionsValue;
  const unrealizedPercent = cost === 0 ? 0 : (unrealized / cost) * 100;
  const tone = unrealized > 0 ? "text-up" : unrealized < 0 ? "text-down" : "text-ink-2";
  const dot = STATUS[status];
  const lastEvent = store.getLastEventAt();

  return (
    <header className="flex h-12 shrink-0 items-stretch gap-5 border-b border-line bg-surface px-3">
      <div className="flex items-center gap-2.5">
        <span aria-hidden className="h-6 w-[3px] bg-accent" />
        <div className="flex flex-col gap-0.5">
          <span className="text-[0.9375rem] leading-none font-bold tracking-[0.2em] text-ink">
            FINALLY
          </span>
          <span className="label leading-none">AI trading workstation</span>
        </div>
      </div>

      <div aria-hidden className="my-2 w-px bg-line" />

      <Stat
        label="Net liquidation"
        value={netLiq == null ? "––" : money(netLiq)}
        size="text-[1.125rem] font-medium"
      />

      <Stat
        label="Unrealized P&L"
        value={`${signedMoney(unrealized)}  ${signedPercent(unrealizedPercent)}`}
        tone={tone}
      />

      <Stat label="Cash" value={cash == null ? "––" : money(cash)} tone="text-ink-2" />

      <Stat
        label="Positions"
        value={positions.length === 0 ? "flat" : money(positionsValue)}
        tone="text-ink-2"
      />

      <div className="ml-auto flex items-center gap-4">
        <div className="flex flex-col items-end gap-0.5">
          <span className="label leading-none">Last tick</span>
          <span className="num text-data leading-none text-ink-2">
            {lastEvent == null ? "––:––:––" : clockFromUnixSeconds(lastEvent)}
          </span>
        </div>
        <div
          className="flex items-center gap-1.5 border border-line bg-surface-2 px-2 py-1"
          role="status"
          aria-live="polite"
          data-testid="connection-status"
          data-status={status}
        >
          <span
            aria-hidden
            className={`h-1.5 w-1.5 rounded-full ${dot.color}`}
            style={dot.pulse ? { animation: "pulse-dot 1.1s ease-in-out infinite" } : undefined}
          />
          <span className="label leading-none">{dot.label}</span>
        </div>
      </div>
    </header>
  );
}
