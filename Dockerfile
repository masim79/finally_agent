# syntax=docker/dockerfile:1

# ---------------------------------------------------------------------------
# Stage 1: frontend build — Next.js static export (node:20-slim)
# ---------------------------------------------------------------------------
FROM node:20-slim AS frontend-builder
WORKDIR /app/frontend

# Manifests first so `npm ci`/`npm install` is cached independently of source.
COPY frontend/package.json frontend/package-lock.json* ./
RUN if [ -f package-lock.json ]; then npm ci; else npm install; fi

COPY frontend/ ./
RUN npm run build

# ---------------------------------------------------------------------------
# Stage 2: backend runtime — FastAPI served by uvicorn (python:3.12-slim)
# ---------------------------------------------------------------------------
FROM python:3.12-slim AS backend

# curl is needed for the HEALTHCHECK below; python:3.12-slim doesn't ship it.
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Grab the uv binary straight from its official image rather than a pip/curl
# install step — fastest and most reproducible way to get it into the image.
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /usr/local/bin/

WORKDIR /app

# Dependency manifests (+ README, which hatchling's build needs for project
# metadata) copied before source so `uv sync` is cached across source-only
# rebuilds. --no-install-project here installs only third-party deps; the
# local package itself is installed in the second `uv sync` below, after the
# source is in place.
COPY backend/pyproject.toml backend/uv.lock backend/README.md ./
RUN uv sync --frozen --no-install-project --no-dev

COPY backend/app ./app
RUN uv sync --frozen --no-dev

# Frontend static export, served by FastAPI at "/" (see CONTRACTS.md §6).
COPY --from=frontend-builder /app/frontend/out ./static

# Non-root runtime user. The SQLite file lives under /app/db, backed by a
# named volume at runtime — that directory (and everything else under /app)
# must be owned by this user *before* uvicorn starts. A root-owned mount
# point makes sqlite3.connect() fail in a way that looks like an app bug.
RUN useradd --create-home --uid 1000 appuser \
    && mkdir -p /app/db \
    && chown -R appuser:appuser /app

ENV PATH="/app/.venv/bin:${PATH}" \
    PYTHONUNBUFFERED=1 \
    FINALLY_DB_PATH=/app/db/finally.db

USER appuser

VOLUME ["/app/db"]
EXPOSE 8000

# /api/health deliberately works without a warm database, so it's safe to
# poll from the first second after the container starts.
HEALTHCHECK --interval=10s --timeout=3s --start-period=5s --retries=5 \
    CMD curl -fsS http://localhost:8000/api/health || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
