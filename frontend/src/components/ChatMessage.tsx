"use client";

import { clockFromIso, money, quantity as formatQuantity } from "@/lib/format";
import type { ChatActions } from "@/lib/types";
import type { ChatEntry } from "@/state/ChatProvider";

function ActionRow({
  ok,
  text,
  detail,
}: {
  ok: boolean;
  text: string;
  detail?: string | null;
}) {
  return (
    <li
      className={`border-l-2 bg-black/20 py-1 pr-2 pl-2 ${ok ? "border-up" : "border-down"}`}
      data-status={ok ? "executed" : "failed"}
    >
      <span className={`num text-tiny ${ok ? "text-up" : "text-down"}`}>{text}</span>
      {detail ? <p className="mt-0.5 text-micro leading-snug text-ink-2">{detail}</p> : null}
    </li>
  );
}

/**
 * Actions the assistant actually ran, rendered as receipts under its message — failures
 * included, because a refused trade is information the user needs as much as a filled one.
 */
function Actions({ actions }: { actions: ChatActions }) {
  const total = actions.trades.length + actions.watchlist_changes.length;
  if (total === 0) return null;

  return (
    <ul className="mt-1.5 flex flex-col gap-1" aria-label="Executed actions">
      {actions.trades.map((trade, index) => {
        const ok = trade.status === "executed";
        const verb = trade.side === "buy" ? "Bought" : "Sold";
        const price = trade.price == null ? "" : ` at ${money(trade.price)}`;
        return (
          <ActionRow
            key={`trade-${trade.ticker}-${index}`}
            ok={ok}
            text={
              ok
                ? `${verb} ${formatQuantity(trade.quantity)} ${trade.ticker}${price}`
                : `${trade.side === "buy" ? "Buy" : "Sell"} ${formatQuantity(trade.quantity)} ${trade.ticker} rejected`
            }
            detail={trade.error}
          />
        );
      })}
      {actions.watchlist_changes.map((change, index) => {
        const ok = change.status === "executed";
        const verb = change.action === "add" ? "Added" : "Removed";
        return (
          <ActionRow
            key={`watch-${change.ticker}-${index}`}
            ok={ok}
            text={
              ok
                ? `${verb} ${change.ticker} ${change.action === "add" ? "to" : "from"} the watchlist`
                : `${change.action === "add" ? "Add" : "Remove"} ${change.ticker} failed`
            }
            detail={change.error}
          />
        );
      })}
    </ul>
  );
}

export function ChatMessage({ entry }: { entry: ChatEntry }) {
  const isUser = entry.role === "user";
  const isSystem = entry.role === "system";

  return (
    <article
      data-role={entry.role}
      className={`flex flex-col gap-1 border-l-2 py-1.5 pr-1 pl-2.5 ${
        isUser
          ? "border-blue/70"
          : isSystem
            ? "border-down/70"
            : "border-accent/70"
      }`}
    >
      <div className="flex items-baseline gap-2">
        <span
          className={`label leading-none ${
            isUser ? "text-blue" : isSystem ? "text-down" : "text-accent"
          }`}
        >
          {isUser ? "You" : isSystem ? "System" : "FinAlly"}
        </span>
        <span className="num text-micro text-ink-3">{clockFromIso(entry.created_at)}</span>
      </div>
      <p className="text-data leading-[1.45] whitespace-pre-wrap text-ink">{entry.content}</p>
      {entry.actions ? <Actions actions={entry.actions} /> : null}
    </article>
  );
}
