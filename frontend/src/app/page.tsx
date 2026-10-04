"use client";

import { Workstation } from "@/components/Workstation";
import { ChatProvider } from "@/state/ChatProvider";
import { PriceStreamProvider } from "@/state/PriceStreamProvider";
import { WorkstationProvider } from "@/state/WorkstationProvider";

export default function Page() {
  return (
    <PriceStreamProvider>
      <WorkstationProvider>
        <ChatProvider>
          <Workstation />
        </ChatProvider>
      </WorkstationProvider>
    </PriceStreamProvider>
  );
}
