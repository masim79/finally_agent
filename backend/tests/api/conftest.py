"""Shared fixtures for API tests.

Builds a FastAPI app wired the way `main.lifespan` wires one (routers against
a PriceCache and a market data source on `app.state`), but without going
through the real lifespan: a fresh temp-file SQLite database per test (via
FINALLY_DB_PATH, matching `tests/db/conftest.py`'s pattern) and a
pre-populated `PriceCache` instead of a live GBM simulator, so assertions
don't race a background price feed. `FakeMarketDataSource` stands in for the
real simulator/Massive source, just recording start/add/remove calls.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.chat import router as chat_router
from app.api.health import router as health_router
from app.api.portfolio import router as portfolio_router
from app.api.watchlist import router as watchlist_router
from app.db import repositories as repo
from app.market.cache import PriceCache

# A handful of the 10 default-seeded tickers get a known price; the rest are
# deliberately left uncached so tests can exercise the "no price yet" /
# avg_cost-fallback paths.
DEFAULT_PRICES = {
    "AAPL": 192.50,
    "GOOGL": 175.00,
    "MSFT": 420.00,
    "TSLA": 250.00,
}


@dataclass
class FakeMarketDataSource:
    """Test double for `app.market.interface.MarketDataSource`."""

    started_with: list[str] = field(default_factory=list)
    added: list[str] = field(default_factory=list)
    removed: list[str] = field(default_factory=list)
    _tickers: list[str] = field(default_factory=list)

    async def start(self, tickers: list[str]) -> None:
        self.started_with = list(tickers)
        self._tickers = list(tickers)

    async def stop(self) -> None:
        pass

    async def add_ticker(self, ticker: str) -> None:
        self.added.append(ticker)
        if ticker not in self._tickers:
            self._tickers.append(ticker)

    async def remove_ticker(self, ticker: str) -> None:
        self.removed.append(ticker)
        if ticker in self._tickers:
            self._tickers.remove(ticker)

    def get_tickers(self) -> list[str]:
        return list(self._tickers)


@pytest.fixture
def db_path(tmp_path, monkeypatch):
    """Point FINALLY_DB_PATH at a fresh per-test file and enable LLM_MOCK."""
    path = tmp_path / "finally.db"
    monkeypatch.setenv("FINALLY_DB_PATH", str(path))
    monkeypatch.setenv("LLM_MOCK", "true")
    return str(path)


@pytest.fixture
def initialized_db(db_path):
    """A freshly created and seeded database: $10,000 cash, 10 default tickers."""
    repo.init_db()
    return db_path


@pytest.fixture
def price_cache(initialized_db) -> PriceCache:
    cache = PriceCache()
    for ticker, price in DEFAULT_PRICES.items():
        cache.update(ticker, price)
    return cache


@pytest.fixture
def market_source() -> FakeMarketDataSource:
    return FakeMarketDataSource()


@pytest.fixture
def app(price_cache: PriceCache, market_source: FakeMarketDataSource) -> FastAPI:
    fastapi_app = FastAPI(title="FinAlly-test")
    fastapi_app.state.price_cache = price_cache
    fastapi_app.state.market_source = market_source
    fastapi_app.state.market_source_name = "simulator"

    fastapi_app.include_router(health_router)
    fastapi_app.include_router(portfolio_router)
    fastapi_app.include_router(watchlist_router)
    fastapi_app.include_router(chat_router)
    return fastapi_app


@pytest.fixture
def client(app: FastAPI) -> TestClient:
    return TestClient(app)
