"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import type { ReactNode } from "react";
import { ApiError, api } from "@/lib/api";
import type { ChatActions, ChatHistoryMessage } from "@/lib/types";
import { useWorkstation } from "./WorkstationProvider";

export interface ChatEntry {
  id: string;
  role: "user" | "assistant" | "system";
  content: string;
  actions: ChatActions | null;
  created_at: string;
}

interface ChatValue {
  entries: ChatEntry[];
  /** True for the whole round trip — responses arrive complete, not token by token. */
  sending: boolean;
  historyLoading: boolean;
  send: (message: string) => Promise<void>;
}

const ChatContext = createContext<ChatValue | null>(null);

function hasExecutedAction(actions: ChatActions | null): boolean {
  if (!actions) return false;
  return (
    actions.trades.some((trade) => trade.status === "executed") ||
    actions.watchlist_changes.some((change) => change.status === "executed")
  );
}

interface Props {
  children: ReactNode;
  initialEntries?: ChatEntry[];
  loadHistory?: boolean;
}

export function ChatProvider({ children, initialEntries = [], loadHistory = true }: Props) {
  const { refresh } = useWorkstation();
  const [entries, setEntries] = useState<ChatEntry[]>(initialEntries);
  const [sending, setSending] = useState(false);
  const [historyLoading, setHistoryLoading] = useState(loadHistory);

  useEffect(() => {
    if (!loadHistory) return;
    let cancelled = false;
    api
      .getChatHistory()
      .then((response) => {
        if (cancelled) return;
        setEntries(response.messages.map((message: ChatHistoryMessage) => ({ ...message })));
      })
      .catch(() => {
        // An unreachable history endpoint shouldn't block a new conversation.
      })
      .finally(() => {
        if (!cancelled) setHistoryLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [loadHistory]);

  const send = useCallback(
    async (message: string) => {
      const text = message.trim();
      if (!text || sending) return;

      const localId = `local-${Date.now()}`;
      setEntries((current) => [
        ...current,
        {
          id: localId,
          role: "user",
          content: text,
          actions: null,
          created_at: new Date().toISOString(),
        },
      ]);
      setSending(true);

      try {
        const response = await api.sendChat(text);
        setEntries((current) => [
          ...current,
          {
            id: response.id,
            role: "assistant",
            content: response.message,
            actions: response.actions,
            created_at: response.created_at,
          },
        ]);
        // Trades and watchlist edits the assistant ran are server state the stream never carries.
        if (hasExecutedAction(response.actions)) await refresh();
      } catch (error) {
        setEntries((current) => [
          ...current,
          {
            id: `error-${Date.now()}`,
            role: "system",
            content:
              error instanceof ApiError
                ? error.message
                : "The assistant didn't respond. Try again.",
            actions: null,
            created_at: new Date().toISOString(),
          },
        ]);
      } finally {
        setSending(false);
      }
    },
    [refresh, sending],
  );

  const value = useMemo<ChatValue>(
    () => ({ entries, sending, historyLoading, send }),
    [entries, sending, historyLoading, send],
  );

  return <ChatContext.Provider value={value}>{children}</ChatContext.Provider>;
}

export function useChat(): ChatValue {
  const value = useContext(ChatContext);
  if (!value) throw new Error("useChat must be used inside <ChatProvider>");
  return value;
}
