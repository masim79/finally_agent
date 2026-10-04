"use client";

import { useEffect, useRef, useState } from "react";
import { ChatMessage } from "@/components/ChatMessage";
import { Panel } from "@/components/Panel";
import { useChat } from "@/state/ChatProvider";

const SUGGESTIONS = [
  "How concentrated is my portfolio?",
  "Buy 10 shares of NVDA",
  "Add PYPL to my watchlist",
];

export function ChatPanel() {
  const { entries, sending, historyLoading, send } = useChat();
  const [draft, setDraft] = useState("");
  const scrollRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    const element = scrollRef.current;
    if (element) element.scrollTop = element.scrollHeight;
  }, [entries, sending]);

  async function submit() {
    const text = draft.trim();
    if (!text || sending) return;
    setDraft("");
    await send(text);
  }

  return (
    <Panel
      title="FinAlly copilot"
      meta={
        <span className="label leading-none">
          {sending ? "Thinking" : historyLoading ? "Loading" : "Ready"}
        </span>
      }
      className="bg-rail"
      bodyClassName="flex flex-col min-h-0 bg-rail"
    >
      <div ref={scrollRef} className="min-h-0 flex-1 overflow-y-auto" data-testid="chat-log">
        {entries.length === 0 && !historyLoading ? (
          <div className="flex h-full flex-col justify-end gap-3 p-3">
            <div className="flex flex-col gap-1.5">
              <p className="label text-ink-2">Ask about your book</p>
              <p className="max-w-[34ch] text-tiny leading-snug text-ink-3">
                FinAlly sees your cash, positions, P&amp;L and watchlist, and can trade on your
                say-so.
              </p>
            </div>
            <div className="flex flex-col gap-1">
              {SUGGESTIONS.map((suggestion) => (
                <button
                  key={suggestion}
                  type="button"
                  onClick={() => {
                    setDraft(suggestion);
                    inputRef.current?.focus();
                  }}
                  className="cursor-pointer border border-line bg-surface/40 px-2 py-1.5 text-left text-tiny text-ink-2 transition-colors hover:border-blue hover:text-ink"
                >
                  {suggestion}
                </button>
              ))}
            </div>
          </div>
        ) : (
          <div className="flex flex-col gap-2.5 p-2.5">
            {entries.map((entry) => (
              <ChatMessage key={entry.id} entry={entry} />
            ))}
            {sending ? (
              <div
                className="flex items-center gap-2 border-l-2 border-accent/40 py-1.5 pl-2.5"
                role="status"
                aria-live="polite"
              >
                <span className="label leading-none text-accent">FinAlly</span>
                <span className="relative h-[2px] w-16 overflow-hidden bg-line">
                  <span
                    aria-hidden
                    className="absolute inset-y-0 left-0 w-1/4 bg-accent"
                    style={{ animation: "thinking-bar 1.1s ease-in-out infinite" }}
                  />
                </span>
                <span className="text-tiny text-ink-3">Thinking…</span>
              </div>
            ) : null}
          </div>
        )}
      </div>

      <form
        onSubmit={(event) => {
          event.preventDefault();
          void submit();
        }}
        className="flex shrink-0 flex-col gap-1.5 border-t border-line bg-rail-2 p-2"
      >
        <label htmlFor="chat-input" className="sr-only">
          Message FinAlly
        </label>
        <textarea
          id="chat-input"
          ref={inputRef}
          value={draft}
          rows={2}
          onChange={(event) => setDraft(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === "Enter" && !event.shiftKey) {
              event.preventDefault();
              void submit();
            }
          }}
          placeholder="Ask, analyse, or instruct a trade…"
          className="resize-none border border-line bg-surface px-2 py-1.5 text-data leading-snug text-ink placeholder:text-ink-3 focus:border-blue focus:outline-none"
        />
        <div className="flex items-center gap-2">
          <span className="label">↵ send · ⇧↵ newline</span>
          <button
            type="submit"
            disabled={sending || draft.trim().length === 0}
            className="ml-auto cursor-pointer border border-purple bg-purple/40 px-4 py-1 text-tiny font-semibold tracking-[0.1em] text-ink uppercase transition-colors hover:bg-purple/70 disabled:cursor-not-allowed disabled:border-line disabled:bg-transparent disabled:text-ink-3"
          >
            {sending ? "Sending" : "Send"}
          </button>
        </div>
      </form>
    </Panel>
  );
}
