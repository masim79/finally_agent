"""/api/watchlist* routes — CONTRACTS.md §3.

`add_watchlist_entry` / `remove_watchlist_entry` / `watchlist_tickers_payload`
are exported so `api/chat.py` can apply the LLM's watchlist changes through
the exact same repo-write + market-source-call path these routes use,
instead of re-implementing it.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Response
from pydantic import BaseModel, field_validator

from app.api.deps import get_market_source, get_price_cache
from app.api.errors import translate_watchlist_error
from app.db import repositories as repo
from app.db.errors import DuplicateTickerError, TickerNotFoundError
from app.db.models import WatchlistRow
from app.market.cache import PriceCache
from app.market.interface import MarketDataSource

router = APIRouter(prefix="/api/watchlist", tags=["watchlist"])


class WatchlistEntryOut(BaseModel):
    ticker: str
    added_at: str
    price: float | None
    previous_price: float | None
    change: float | None
    change_percent: float | None
    direction: str | None


class WatchlistOut(BaseModel):
    tickers: list[WatchlistEntryOut]


class AddTickerRequest(BaseModel):
    ticker: str

    @field_validator("ticker")
    @classmethod
    def _upper(cls, value: str) -> str:
        return value.strip().upper()


def _entry_view(row: WatchlistRow, cache: PriceCache) -> dict:
    update = cache.get(row.ticker)
    if update is None:
        return {
            "ticker": row.ticker,
            "added_at": row.added_at,
            "price": None,
            "previous_price": None,
            "change": None,
            "change_percent": None,
            "direction": None,
        }
    return {
        "ticker": row.ticker,
        "added_at": row.added_at,
        "price": update.price,
        "previous_price": update.previous_price,
        "change": update.change,
        "change_percent": update.change_percent,
        "direction": update.direction,
    }


def watchlist_tickers_payload(cache: PriceCache) -> list[dict]:
    """The `tickers` array for GET /api/watchlist, ordered by added_at ASC."""
    return [_entry_view(row, cache) for row in repo.list_watchlist()]


async def add_watchlist_entry(ticker: str, cache: PriceCache, source: MarketDataSource) -> dict:
    """Add a ticker to the watchlist and start the source generating it.

    Raises DuplicateTickerError if already present.
    """
    ticker = ticker.strip().upper()
    row = repo.add_watchlist_ticker(ticker)
    await source.add_ticker(ticker)
    return _entry_view(row, cache)


async def remove_watchlist_entry(ticker: str, source: MarketDataSource) -> None:
    """Remove a ticker from the watchlist and stop the source generating it.

    Raises TickerNotFoundError if absent. Does not touch an open position.
    """
    ticker = ticker.strip().upper()
    repo.remove_watchlist_ticker(ticker)
    await source.remove_ticker(ticker)


@router.get("", response_model=WatchlistOut)
def get_watchlist(cache: PriceCache = Depends(get_price_cache)) -> WatchlistOut:
    return WatchlistOut(tickers=watchlist_tickers_payload(cache))


@router.post("", response_model=WatchlistEntryOut, status_code=201)
async def add_ticker(
    body: AddTickerRequest,
    cache: PriceCache = Depends(get_price_cache),
    source: MarketDataSource = Depends(get_market_source),
) -> WatchlistEntryOut:
    try:
        entry = await add_watchlist_entry(body.ticker, cache, source)
    except DuplicateTickerError as exc:
        raise translate_watchlist_error(exc) from exc
    return WatchlistEntryOut(**entry)


@router.delete("/{ticker}", status_code=204)
async def remove_ticker(
    ticker: str, source: MarketDataSource = Depends(get_market_source)
) -> Response:
    try:
        await remove_watchlist_entry(ticker, source)
    except TickerNotFoundError as exc:
        raise translate_watchlist_error(exc) from exc
    return Response(status_code=204)
