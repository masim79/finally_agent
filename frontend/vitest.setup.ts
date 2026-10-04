import "@testing-library/jest-dom/vitest";
import { cleanup } from "@testing-library/react";
import { afterEach, vi } from "vitest";

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

// jsdom ships no EventSource; the price-stream store needs the constructor to exist.
if (!("EventSource" in globalThis)) {
  class MissingEventSource {
    constructor() {
      throw new Error("EventSource must be stubbed in tests that open a stream");
    }
  }
  Object.defineProperty(globalThis, "EventSource", {
    writable: true,
    configurable: true,
    value: MissingEventSource,
  });
}

// Charts and the heatmap measure their container, and jsdom reports 0x0 for everything.
// The stub reports a fixed desktop-ish box so layout-dependent components have something real
// to lay out against.
const OBSERVED_BOX = { width: 600, height: 300 };

Object.defineProperty(globalThis, "ResizeObserver", {
  writable: true,
  configurable: true,
  value: class {
    constructor(private readonly callback: ResizeObserverCallback) {}
    observe(target: Element) {
      this.callback(
        [{ target, contentRect: { ...OBSERVED_BOX } } as unknown as ResizeObserverEntry],
        this as unknown as ResizeObserver,
      );
    }
    unobserve() {}
    disconnect() {}
  },
});

Object.defineProperty(HTMLCanvasElement.prototype, "getContext", {
  writable: true,
  configurable: true,
  value: () => null,
});
