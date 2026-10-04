"""GET /api/health — CONTRACTS.md §3.

The Docker healthcheck hits this endpoint, so it must always return 200 even
if the database isn't warm yet or app.state hasn't been fully populated
(e.g. a request racing startup) — it reports what it can rather than raising.
"""

from __future__ import annotations

from fastapi import APIRouter, Request
from pydantic import BaseModel

router = APIRouter(prefix="/api", tags=["health"])


class HealthOut(BaseModel):
    status: str
    market_source: str
    tracked_tickers: int
    db: str


@router.get("/health", response_model=HealthOut)
def health(request: Request) -> HealthOut:
    market_source_name = getattr(request.app.state, "market_source_name", "simulator")

    source = getattr(request.app.state, "market_source", None)
    tracked_tickers = len(source.get_tickers()) if source is not None else 0

    db_status = "ok"
    try:
        from app.db.repositories import get_cash_balance

        get_cash_balance()
    except Exception:
        db_status = "error"

    return HealthOut(
        status="ok",
        market_source=market_source_name,
        tracked_tickers=tracked_tickers,
        db=db_status,
    )
