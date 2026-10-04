"""POST /api/chat and GET /api/chat/history — CONTRACTS.md §3.

This is the one place orchestration lives: load context, ask the LLM layer
what it wants to do, then execute each proposed trade / watchlist change
through the exact same service calls the manual endpoints use, catching
failures per-item so one bad action never sinks the whole response. A failed
trade or watchlist change is reported inline (`status: "failed"`, `error`) —
it is NOT an HTTP error; the chat response is 200 either way. The only HTTP
error this endpoint raises is LLM_ERROR, when the provider itself could not
be reached.

`app.llm.service` is imported lazily, inside `_call_llm`, rather than at
module level. That keeps this module importable (and its orchestration
testable via monkeypatching `_call_llm`) independent of whether the LLM
layer has landed yet.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.api.deps import get_market_source, get_price_cache
from app.api.errors import trade_error_code_and_message, watchlist_error_code_and_message
from app.api.watchlist import add_watchlist_entry, remove_watchlist_entry, watchlist_tickers_payload
from app.db import repositories as repo
from app.db.errors import DuplicateTickerError, RepositoryError, TickerNotFoundError
from app.market.cache import PriceCache
from app.market.interface import MarketDataSource
from app.services import portfolio as portfolio_service
from app.services.portfolio import UnknownTickerError

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/chat", tags=["chat"])

# How much prior conversation is handed to the LLM as context. Not specified
# by CONTRACTS.md §5 (which only requires "trimmed history, oldest first,
# caller-trimmed"); 20 messages (~10 turns) is a reasonable bound that keeps
# prompts small without losing recent context.
CHAT_HISTORY_LIMIT = 20

_TRADE_EXCEPTIONS = (UnknownTickerError, ValueError, RepositoryError)
_WATCHLIST_EXCEPTIONS = (DuplicateTickerError, TickerNotFoundError, ValueError)


class ChatRequest(BaseModel):
    message: str


class TradeActionOut(BaseModel):
    ticker: str
    side: str
    quantity: float
    status: str
    price: float | None = None
    error: str | None = None


class WatchlistActionOut(BaseModel):
    ticker: str
    action: str
    status: str
    error: str | None = None


class ActionsOut(BaseModel):
    trades: list[TradeActionOut]
    watchlist_changes: list[WatchlistActionOut]


class ChatResponse(BaseModel):
    id: str
    message: str
    actions: ActionsOut
    created_at: str


class ChatMessageOut(BaseModel):
    id: str
    role: str
    content: str
    actions: dict | None
    created_at: str


class ChatHistoryOut(BaseModel):
    messages: list[ChatMessageOut]


async def _call_llm(user_message: str, portfolio: dict, watchlist: list[dict], history: list[dict]):
    """Seam to `app.llm.service.generate_chat_response` — see module docstring.

    Tests monkeypatch this function directly (`app.api.chat._call_llm`) to
    exercise the orchestration below without depending on the LLM layer.
    """
    from app.llm.service import generate_chat_response

    return await generate_chat_response(user_message, portfolio, watchlist, history)


def _execute_trade_action(
    cache: PriceCache, ticker: str, side: str, quantity: float
) -> TradeActionOut:
    ticker = ticker.strip().upper()
    try:
        result = portfolio_service.execute_trade(cache, ticker, side, quantity)
    except _TRADE_EXCEPTIONS as exc:
        _, message = trade_error_code_and_message(exc)
        return TradeActionOut(
            ticker=ticker, side=side, quantity=quantity, status="failed", price=None, error=message
        )
    return TradeActionOut(
        ticker=ticker,
        side=side,
        quantity=quantity,
        status="executed",
        price=result["trade"]["price"],
        error=None,
    )


async def _execute_watchlist_action(
    cache: PriceCache, source: MarketDataSource, ticker: str, action: str
) -> WatchlistActionOut:
    ticker = ticker.strip().upper()
    try:
        if action == "add":
            await add_watchlist_entry(ticker, cache, source)
        elif action == "remove":
            await remove_watchlist_entry(ticker, source)
        else:
            raise ValueError(f"Unknown watchlist action: {action!r}")
    except _WATCHLIST_EXCEPTIONS as exc:
        if isinstance(exc, (DuplicateTickerError, TickerNotFoundError)):
            _, message = watchlist_error_code_and_message(exc)
        else:
            message = str(exc)
        return WatchlistActionOut(ticker=ticker, action=action, status="failed", error=message)
    return WatchlistActionOut(ticker=ticker, action=action, status="executed", error=None)


@router.post("", response_model=ChatResponse)
async def post_chat(
    body: ChatRequest,
    cache: PriceCache = Depends(get_price_cache),
    source: MarketDataSource = Depends(get_market_source),
) -> ChatResponse:
    portfolio = portfolio_service.get_portfolio(cache)
    watchlist = watchlist_tickers_payload(cache)
    history_rows = repo.list_chat_messages(limit=CHAT_HISTORY_LIMIT)
    history = [{"role": row.role, "content": row.content} for row in history_rows]

    repo.record_chat_message(role="user", content=body.message)

    try:
        result = await _call_llm(body.message, portfolio, watchlist, history)
    except Exception as exc:
        logger.exception("LLM call failed")
        raise HTTPException(
            status_code=502, detail={"code": "LLM_ERROR", "message": str(exc)}
        ) from exc

    trade_actions = [
        _execute_trade_action(cache, trade.ticker, trade.side, trade.quantity)
        for trade in result.trades
    ]
    watchlist_actions = [
        await _execute_watchlist_action(cache, source, change.ticker, change.action)
        for change in result.watchlist_changes
    ]

    actions = ActionsOut(trades=trade_actions, watchlist_changes=watchlist_actions)
    assistant_row = repo.record_chat_message(
        role="assistant",
        content=result.message,
        actions=actions.model_dump(),
    )

    return ChatResponse(
        id=assistant_row.id,
        message=result.message,
        actions=actions,
        created_at=assistant_row.created_at,
    )


@router.get("/history", response_model=ChatHistoryOut)
def get_chat_history(limit: int = 50) -> ChatHistoryOut:
    rows = repo.list_chat_messages(limit=limit)
    return ChatHistoryOut(
        messages=[
            ChatMessageOut(
                id=row.id, role=row.role, content=row.content, actions=row.actions,
                created_at=row.created_at,
            )
            for row in rows
        ]
    )
