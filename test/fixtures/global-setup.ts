import type { FullConfig } from "@playwright/test";

/**
 * Blocks the suite until GET /api/health answers {status:"ok"}. Both run paths race their own
 * startup against this: docker-compose.test.yml also has a Docker-level healthcheck gate, and
 * run-against-uvicorn.mjs polls the same endpoint before invoking Playwright at all — but a
 * slow container build or a slow `uv run` first-import can still leave a gap, and failing spec 1
 * with a connection-refused error is a worse signal than waiting here.
 */
async function waitForHealth(baseURL: string, timeoutMs = 60_000): Promise<void> {
  const deadline = Date.now() + timeoutMs;
  let lastError: unknown;

  while (Date.now() < deadline) {
    try {
      const response = await fetch(`${baseURL}/api/health`);
      if (response.ok) {
        const body = (await response.json()) as { status?: string };
        if (body.status === "ok") return;
        lastError = new Error(`/api/health returned status=${String(body.status)}`);
      } else {
        lastError = new Error(`/api/health responded ${response.status}`);
      }
    } catch (error) {
      lastError = error;
    }
    await new Promise((resolve) => setTimeout(resolve, 500));
  }

  throw new Error(
    `App never became healthy at ${baseURL}/api/health within ${timeoutMs}ms. Last error: ${String(lastError)}`,
  );
}

export default async function globalSetup(config: FullConfig): Promise<void> {
  const baseURL =
    config.projects[0]?.use?.baseURL ?? process.env.BASE_URL ?? "http://127.0.0.1:8000";
  await waitForHealth(baseURL);
}
