"""/api/portfolio* routes — CONTRACTS.md §3."""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, field_validator

from app.api.deps import get_price_cache
from app.api.errors import translate_trade_error
from app.db.errors import RepositoryError
from app.market.cache import PriceCache
from app.services import portfolio as portfolio_service
from app.services.portfolio import UnknownTickerError

router = APIRouter(prefix="/api/portfolio", tags=["portfolio"])

# Exceptions execute_trade can raise that map to a known §3 error code:
# UnknownTickerError (this module), ValueError (bad side — defensive, since
# the Pydantic Literal below already rejects it at 422), and the
# RepositoryError family from apply_trade (insufficient cash/shares, invalid
# quantity).
_TRADE_EXCEPTIONS = (UnknownTickerError, ValueError, RepositoryError)


class PositionOut(BaseModel):
    ticker: str
    quantity: float
    avg_cost: float
    current_price: float
    market_value: float
    unrealized_pnl: float
    unrealized_pnl_percent: float
    weight: float


class PortfolioOut(BaseModel):
    cash_balance: float
    positions: list[PositionOut]
    positions_value: float
    total_value: float
    total_unrealized_pnl: float
    total_unrealized_pnl_percent: float


class TradeRequest(BaseModel):
    ticker: str
    quantity: float
    side: Literal["buy", "sell"]

    @field_validator("ticker")
    @classmethod
    def _upper(cls, value: str) -> str:
        return value.strip().upper()


class TradeOut(BaseModel):
    id: str
    ticker: str
    side: str
    quantity: float
    price: float
    executed_at: str


class TradeResponse(BaseModel):
    trade: TradeOut
    cash_balance: float
    position: PositionOut | None


class SnapshotOut(BaseModel):
    total_value: float
    recorded_at: str


class HistoryResponse(BaseModel):
    snapshots: list[SnapshotOut]


@router.get("", response_model=PortfolioOut)
def get_portfolio(cache: PriceCache = Depends(get_price_cache)) -> PortfolioOut:
    return PortfolioOut(**portfolio_service.get_portfolio(cache))


@router.post("/trade", response_model=TradeResponse)
def post_trade(body: TradeRequest, cache: PriceCache = Depends(get_price_cache)) -> TradeResponse:
    try:
        result = portfolio_service.execute_trade(cache, body.ticker, body.side, body.quantity)
    except _TRADE_EXCEPTIONS as exc:
        raise translate_trade_error(exc) from exc
    return TradeResponse(**result)


@router.get("/history", response_model=HistoryResponse)
def get_history(limit: int = Query(default=500, ge=1, le=5000)) -> HistoryResponse:
    return HistoryResponse(snapshots=portfolio_service.get_history(limit=limit))
