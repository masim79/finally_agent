import http from "node:http";
import type { Socket } from "node:net";

/**
 * A tiny transparent HTTP reverse proxy, used ONLY by 06-sse-resilience.spec.ts, to produce a
 * REAL TCP-level connection drop instead of relying on Chrome's `context.setOffline()`.
 *
 * Why this exists: `context.setOffline()` (CDP `Network.emulateNetworkConditions`) reliably
 * blocks NEW requests — confirmed directly: a `fetch()` issued while "offline" throws
 * `Failed to fetch` — but it does NOT sever an already-open long-lived connection. An
 * `EventSource` that connected before `setOffline(true)` kept reporting `data-status="live"`
 * for the full duration of a 10s offline window in manual testing; its socket just kept
 * receiving bytes. This is a known limitation of CDP network emulation for streaming
 * connections (SSE/WebSocket), not a frontend bug — nothing in `priceStore.ts`'s reconnect
 * logic was ever actually exercised by that approach, so a passing OR failing assertion built
 * on it would both be meaningless.
 *
 * This proxy sits between the page and the real backend. Everything passes through unchanged
 * until `dropConnections()` is called, which destroys every currently-open proxied socket
 * (a real RST, not a browser-side fiction) and refuses new connections until `restore()`.
 * `EventSource` has no way to not notice a destroyed socket, so this genuinely exercises the
 * retry path the server's `retry: 1000` directive (CONTRACTS.md §2) is counting on.
 */
export interface NetworkProxy {
  url: string;
  dropConnections(): void;
  restore(): void;
  close(): Promise<void>;
}

export async function startNetworkProxy(upstreamUrl: string): Promise<NetworkProxy> {
  const upstream = new URL(upstreamUrl);
  let down = false;
  const sockets = new Set<Socket>();

  const server = http.createServer((req, res) => {
    if (down) {
      req.socket.destroy();
      return;
    }

    const proxyReq = http.request(
      {
        host: upstream.hostname,
        port: upstream.port,
        path: req.url,
        method: req.method,
        headers: req.headers,
      },
      (proxyRes) => {
        if (down) {
          proxyRes.destroy();
          return;
        }
        res.writeHead(proxyRes.statusCode ?? 502, proxyRes.headers);
        proxyRes.pipe(res);
      },
    );
    req.pipe(proxyReq);
    proxyReq.on("error", () => res.destroy());
    res.on("close", () => proxyReq.destroy());
  });

  server.on("connection", (socket) => {
    sockets.add(socket);
    socket.on("close", () => sockets.delete(socket));
  });

  await new Promise<void>((resolve) => server.listen(0, "127.0.0.1", resolve));
  const address = server.address();
  if (address == null || typeof address === "string") {
    throw new Error("network proxy failed to bind a port");
  }

  return {
    url: `http://127.0.0.1:${address.port}`,
    dropConnections() {
      down = true;
      for (const socket of sockets) socket.destroy();
    },
    restore() {
      down = false;
    },
    close() {
      for (const socket of sockets) socket.destroy();
      return new Promise<void>((resolve) => server.close(() => resolve()));
    },
  };
}
