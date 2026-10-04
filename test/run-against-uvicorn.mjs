#!/usr/bin/env node
/**
 * Second run path (no Docker daemon required): starts the real backend with `uv run uvicorn`
 * directly on the host, pointed at `frontend/out/` via the `FINALLY_STATIC_DIR` override
 * (app/main.py resolves it if set and non-empty, else falls back to the container's
 * `backend/static` default — so this override is additive and the container path is
 * unaffected). Waits for the server to report healthy, then runs the identical Playwright suite
 * against it with BASE_URL pointed at that process. Once Docker is available again,
 * `npm run test:docker` runs the SAME spec files unchanged against the real container — this
 * script is a stand-in for that, not a separate test surface.
 *
 * Responsible for exactly what docker-compose.test.yml gets for free from a fresh container:
 *   - a clean database for this run (delete the scratch file before starting, not after)
 *   - a real static export to serve (fail loudly before starting the server if it's missing,
 *     rather than producing twelve identical "element not found" UI failures)
 *   - LLM_MOCK=true, no API keys
 *   - the server actually answering /api/health before tests start (playwright.config.ts's
 *     globalSetup polls this too, belt-and-suspenders against a slow first `uv run` import)
 *   - tearing the server down afterwards, success or failure
 */

import { spawn, spawnSync } from "node:child_process";
import { createWriteStream, existsSync, mkdirSync, rmSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = dirname(fileURLToPath(import.meta.url));
const repoRoot = join(__dirname, "..");
const backendDir = join(repoRoot, "backend");
const staticDir = join(repoRoot, "frontend", "out");
const scratchDir = join(__dirname, ".tmp");
const dbPath = join(scratchDir, "finally_e2e.db");
const port = process.env.TEST_APP_PORT ?? "8000";
const host = "127.0.0.1";
const baseURL = `http://${host}:${port}`;

function assertStaticExportExists() {
  const indexPath = join(staticDir, "index.html");
  if (!existsSync(indexPath)) {
    throw new Error(
      `No frontend export at ${indexPath}. Build it first (cd frontend && npm run build) — ` +
        `the backend has nothing to serve at "/" without it, and every UI spec will fail the ` +
        `same way (element not found) regardless of what's actually broken.`,
    );
  }
}

function deleteScratchDb() {
  for (const suffix of ["", "-wal", "-shm", "-journal"]) {
    const path = dbPath + suffix;
    if (existsSync(path)) rmSync(path);
  }
}

async function waitForHealth(timeoutMs = 45_000) {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    try {
      const response = await fetch(`${baseURL}/api/health`);
      if (response.ok) {
        const body = await response.json();
        if (body.status === "ok") return;
      }
    } catch {
      // backend not listening yet — keep polling
    }
    await new Promise((resolve) => setTimeout(resolve, 500));
  }
  throw new Error(`uvicorn never answered ${baseURL}/api/health within ${timeoutMs}ms`);
}

function killTree(pid) {
  if (pid == null) return;
  if (process.platform === "win32") {
    // `uv run` spawns uvicorn as a child process; /T recurses the kill to it.
    spawnSync("taskkill", ["/PID", String(pid), "/T", "/F"], { stdio: "ignore" });
  } else {
    try {
      process.kill(-pid, "SIGTERM");
    } catch {
      try {
        process.kill(pid, "SIGTERM");
      } catch {
        // already gone
      }
    }
  }
}

async function main() {
  try {
    assertStaticExportExists();
  } catch (error) {
    console.error(`[run-against-uvicorn] ${error.message}`);
    process.exit(1);
  }

  mkdirSync(scratchDir, { recursive: true });
  deleteScratchDb();

  const logPath = join(scratchDir, "uvicorn.log");
  const log = createWriteStream(logPath, { flags: "w" });

  console.log(`[run-against-uvicorn] starting backend on ${baseURL} (db: ${dbPath})`);
  console.log(`[run-against-uvicorn] serving static export from: ${staticDir}`);
  console.log(`[run-against-uvicorn] backend log: ${logPath}`);

  const appProcess = spawn(
    "uv",
    ["run", "uvicorn", "app.main:app", "--host", host, "--port", String(port)],
    {
      cwd: backendDir,
      env: {
        ...process.env,
        LLM_MOCK: "true",
        FINALLY_DB_PATH: dbPath,
        FINALLY_STATIC_DIR: staticDir,
        OPENROUTER_API_KEY: "",
        MASSIVE_API_KEY: "",
      },
      shell: process.platform === "win32",
      detached: process.platform !== "win32",
      stdio: ["ignore", "pipe", "pipe"],
    },
  );
  appProcess.stdout.pipe(log);
  appProcess.stderr.pipe(log);

  let playwrightExitCode = 1;
  try {
    await waitForHealth();
    console.log("[run-against-uvicorn] backend healthy — running Playwright suite");

    const extraArgs = process.argv.slice(2);
    playwrightExitCode = await new Promise((resolve) => {
      const pw = spawn("npx", ["playwright", "test", ...extraArgs], {
        cwd: __dirname,
        env: { ...process.env, BASE_URL: baseURL },
        stdio: "inherit",
        shell: process.platform === "win32",
      });
      pw.on("exit", (code) => resolve(code ?? 1));
    });
  } catch (error) {
    console.error(`[run-against-uvicorn] ${error.message ?? error}`);
    console.error(`[run-against-uvicorn] see ${logPath} for backend output`);
    playwrightExitCode = 1;
  } finally {
    console.log("[run-against-uvicorn] stopping backend");
    killTree(appProcess.pid);
    log.close();
  }

  process.exit(playwrightExitCode);
}

main();
