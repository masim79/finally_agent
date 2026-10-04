"use client";

import { ChatPanel } from "@/components/ChatPanel";
import { Header } from "@/components/Header";
import { MainChart } from "@/components/MainChart";
import { PnlChart } from "@/components/PnlChart";
import { PortfolioHeatmap } from "@/components/PortfolioHeatmap";
import { PositionsTable } from "@/components/PositionsTable";
import { TradeBar } from "@/components/TradeBar";
import { Watchlist } from "@/components/Watchlist";
import { useWorkstation } from "@/state/WorkstationProvider";

/**
 * Desktop is the design target: one viewport, no page scroll, every panel scrolling inside its
 * own frame. The left rail is the book — what you watch, and what you hold — the centre is the
 * tape, and the copilot gets a full-height rail of its own with the command line beneath the
 * market region. Below 1280px the same panels stack into one scrolling column so the terminal
 * degrades to a tablet rather than collapsing into unreadable columns.
 */
export function Workstation() {
  const { loadError } = useWorkstation();

  return (
    <div className="flex h-dvh flex-col bg-void">
      <Header />

      {loadError ? (
        <div
          role="alert"
          className="flex h-6 shrink-0 items-center gap-2 border-b border-down/50 bg-down/10 px-3 text-tiny text-down"
        >
          <span className="label text-down">Backend</span>
          {loadError}
        </div>
      ) : null}

      <div className="flex min-h-0 flex-1 flex-col overflow-y-auto xl:flex-row xl:overflow-hidden">
        <div className="flex min-w-0 flex-col xl:min-h-0 xl:flex-1">
          <div className="flex flex-col xl:min-h-0 xl:flex-1 xl:flex-row">
            <div className="flex shrink-0 flex-col md:flex-row xl:h-auto xl:min-h-0 xl:w-[296px] xl:flex-col">
              {/* Allocation is a fixed compact block: giving a treemap more room only makes its
                  biggest rectangle bigger, never more informative. The watchlist takes the rest
                  of the rail — its rows end where the data ends, the add control follows them
                  immediately, and the slack falls below that control as plain panel background. */}
              <div className="h-[376px] shrink-0 md:flex-1 xl:h-auto xl:min-h-0 xl:flex-1">
                <Watchlist />
              </div>
              <div className="h-[212px] shrink-0 md:h-[376px] md:flex-1 xl:h-[200px] xl:flex-none">
                <PortfolioHeatmap />
              </div>
            </div>

            <div className="flex min-w-0 flex-col xl:min-h-0 xl:flex-1">
              <div className="h-[340px] shrink-0 xl:h-auto xl:min-h-0 xl:flex-[1.6]">
                <MainChart />
              </div>
              <div className="h-[260px] shrink-0 xl:h-auto xl:min-h-0 xl:flex-1">
                <PnlChart />
              </div>
              <div className="h-[260px] shrink-0 xl:h-auto xl:min-h-0 xl:flex-[1.05]">
                <PositionsTable />
              </div>
            </div>
          </div>

          <TradeBar />
        </div>

        <div className="h-[460px] shrink-0 xl:h-auto xl:w-[364px]">
          <ChatPanel />
        </div>
      </div>
    </div>
  );
}
