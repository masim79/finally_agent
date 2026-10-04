"use client";

import { useEffect, useRef, useState } from "react";
import { EMPTY, money, normalizeTicker } from "@/lib/format";
import { useTick } from "@/state/PriceStreamProvider";
import { useWorkstation } from "@/state/WorkstationProvider";
import type { Side } from "@/lib/types";

/**
 * The command line. A trading terminal is a keyboard before it is a mouse, so the trade
 * surface sits on the bottom edge of the screen as one monospaced input line: `/` jumps to it,
 * Enter buys, and the running notional updates against the live bid as you type.
 */
export function TradeBar() {
  const { selected, executeTrade, notice } = useWorkstation();
  const [ticker, setTicker] = useState(selected ?? "");
  const [quantity, setQuantity] = useState("");
  const [busy, setBusy] = useState(false);
  const [lastSelected, setLastSelected] = useState(selected);
  const tickerRef = useRef<HTMLInputElement>(null);

  // Selecting a symbol anywhere on the terminal arms the command line with it. Adjusting
  // during render rather than in an effect avoids a second pass with the stale symbol.
  if (selected !== lastSelected) {
    setLastSelected(selected);
    if (selected) setTicker(selected);
  }

  useEffect(() => {
    function onKeyDown(event: KeyboardEvent) {
      const target = event.target as HTMLElement | null;
      const typing =
        target instanceof HTMLInputElement || target instanceof HTMLTextAreaElement;
      if (event.key === "/" && !typing) {
        event.preventDefault();
        tickerRef.current?.focus();
        tickerRef.current?.select();
      }
      if (event.key === "Escape" && typing) target?.blur();
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, []);

  const tick = useTick(ticker);
  const parsedQuantity = Number.parseFloat(quantity);
  const validQuantity = Number.isFinite(parsedQuantity) && parsedQuantity > 0;
  const notional = tick && validQuantity ? tick.price * parsedQuantity : null;
  const ready = ticker.length > 0 && validQuantity && !busy;

  async function submit(side: Side) {
    if (!ready) return;
    setBusy(true);
    const ok = await executeTrade(ticker, parsedQuantity, side);
    setBusy(false);
    if (ok) setQuantity("");
  }

  return (
    <form
      onSubmit={(event) => {
        event.preventDefault();
        void submit("buy");
      }}
      aria-label="Trade command line"
      className="flex h-[34px] shrink-0 items-center gap-2 border-t border-line bg-surface-2 px-2.5"
    >
      <span aria-hidden className="num text-data leading-none text-accent">
        ▸<span className="caret">_</span>
      </span>

      <label htmlFor="trade-ticker" className="label">
        Sym
      </label>
      <input
        id="trade-ticker"
        ref={tickerRef}
        value={ticker}
        onChange={(event) => setTicker(normalizeTicker(event.target.value))}
        placeholder="AAPL"
        maxLength={8}
        autoComplete="off"
        className="num w-[5.5rem] border border-line bg-surface px-1.5 py-1 text-data tracking-tight text-accent uppercase placeholder:text-ink-3 focus:border-accent focus:outline-none"
      />

      <label htmlFor="trade-qty" className="label">
        Qty
      </label>
      <input
        id="trade-qty"
        value={quantity}
        onChange={(event) => setQuantity(event.target.value.replace(/[^0-9.]/g, ""))}
        placeholder="0"
        inputMode="decimal"
        autoComplete="off"
        className="num w-[5.5rem] border border-line bg-surface px-1.5 py-1 text-right text-data text-ink placeholder:text-ink-3 focus:border-accent focus:outline-none"
      />

      <span className="num text-tiny text-ink-2" data-testid="trade-notional">
        @ {tick ? money(tick.price) : EMPTY}
        <span className="mx-1.5 text-ink-3">=</span>
        <span className="text-ink">{notional == null ? EMPTY : money(notional)}</span>
      </span>

      <button
        type="button"
        onClick={() => void submit("buy")}
        disabled={!ready}
        className="cursor-pointer border border-up/60 bg-up/15 px-3.5 py-1 text-tiny font-semibold tracking-[0.1em] text-up uppercase transition-colors hover:bg-up/30 disabled:cursor-not-allowed disabled:border-line disabled:bg-transparent disabled:text-ink-3"
      >
        Buy
      </button>
      <button
        type="button"
        onClick={() => void submit("sell")}
        disabled={!ready}
        className="cursor-pointer border border-down/60 bg-down/15 px-3.5 py-1 text-tiny font-semibold tracking-[0.1em] text-down uppercase transition-colors hover:bg-down/30 disabled:cursor-not-allowed disabled:border-line disabled:bg-transparent disabled:text-ink-3"
      >
        Sell
      </button>

      <span className="label hidden shrink-0 xl:inline">/ focus · ↵ buys · market order</span>

      <output
        key={notice?.key}
        aria-live="polite"
        className={`num ml-auto truncate pl-3 text-tiny ${
          notice?.tone === "error" ? "text-down" : "text-up"
        }`}
      >
        {busy ? "Working…" : (notice?.text ?? "")}
      </output>
    </form>
  );
}
