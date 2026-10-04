"""Shared FastAPI dependencies.

`PriceCache` and the market data source live on `app.state` (set during
lifespan startup, CONTRACTS.md §7) rather than as module-level globals, so
route handlers reach them through these `Depends` functions instead of
importing a shared instance directly.
"""

from __future__ import annotations

from fastapi import Request

from app.market.cache import PriceCache
from app.market.interface import MarketDataSource


def get_price_cache(request: Request) -> PriceCache:
    return request.app.state.price_cache


def get_market_source(request: Request) -> MarketDataSource:
    return request.app.state.market_source
