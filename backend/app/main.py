"""FastAPI application assembly — CONTRACTS.md §6, §7.

Lifespan startup order (§7), all performed here rather than at module import
time so `cache`/`source` exist before anything that depends on them (notably
`create_stream_router`, which needs the live `PriceCache` instance):

    1. init_db()
    2. cache = PriceCache()
    3. source = create_market_data_source(cache)
    4. await source.start(tickers)
    5. start the 30s snapshot task
    6. include routers, then create_stream_router(cache), then mount static

Shutdown cancels the snapshot task and stops the market data source.
`PriceCache` and the source live on `app.state`, reached via `app.api.deps`
— no module-level globals.
"""

from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.api.chat import router as chat_router
from app.api.health import router as health_router
from app.api.portfolio import router as portfolio_router
from app.api.watchlist import router as watchlist_router
from app.config import load_environment
from app.db.repositories import init_db, list_watchlist
from app.market import PriceCache, create_market_data_source, create_stream_router
from app.market.massive_client import MassiveDataSource
from app.services.snapshots import start_snapshot_task, stop_snapshot_task

logger = logging.getLogger(__name__)

# backend/app/main.py -> backend/app -> backend; Docker copies the frontend
# static export to <backend-root>/static (CONTRACTS.md §6). FINALLY_STATIC_DIR
# overrides this — same shape as FINALLY_DB_PATH — so a local `uv run uvicorn`
# can serve a `frontend/out` export directly when Docker isn't available.
# Resolved at lifespan time (not import time) so tests can set it per-run.
DEFAULT_STATIC_DIR = Path(__file__).resolve().parent.parent / "static"


def resolve_static_dir() -> Path:
    """Resolve the static directory: FINALLY_STATIC_DIR env var, else the default."""
    override = os.environ.get("FINALLY_STATIC_DIR", "").strip()
    return Path(override) if override else DEFAULT_STATIC_DIR


@asynccontextmanager
async def lifespan(app: FastAPI):
    load_environment()
    init_db()

    cache = PriceCache()
    source = create_market_data_source(cache)
    app.state.price_cache = cache
    app.state.market_source = source
    app.state.market_source_name = "massive" if isinstance(source, MassiveDataSource) else "simulator"

    tickers = [row.ticker for row in list_watchlist()]
    await source.start(tickers)

    snapshot_task = start_snapshot_task(cache)
    app.state.snapshot_task = snapshot_task

    app.include_router(health_router)
    app.include_router(portfolio_router)
    app.include_router(watchlist_router)
    app.include_router(chat_router)
    app.include_router(create_stream_router(cache))

    static_dir = resolve_static_dir()
    if static_dir.is_dir():
        app.mount("/", StaticFiles(directory=str(static_dir), html=True), name="static")
        logger.info("Serving static frontend from %s", static_dir)
    else:
        logger.warning(
            "Static directory not found at %s; skipping static mount (backend-only dev mode).",
            static_dir,
        )

    try:
        yield
    finally:
        await stop_snapshot_task(snapshot_task)
        await source.stop()


def create_app() -> FastAPI:
    return FastAPI(title="FinAlly", lifespan=lifespan)


app = create_app()
