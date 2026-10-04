"""Uniform error envelope for CONTRACTS.md §3: `{"detail": {"code", "message"}}`.

Shared by `api/portfolio.py`, `api/watchlist.py`, and `api/chat.py` so a trade
or watchlist failure maps to the same code and message whether it came from
the trade bar, the watchlist panel, or the LLM's auto-executed actions.
"""

from __future__ import annotations

from fastapi import HTTPException

from app.db.errors import (
    DuplicateTickerError,
    InsufficientCashError,
    InsufficientSharesError,
    InvalidQuantityError,
    TickerNotFoundError,
)
from app.services.portfolio import UnknownTickerError


def api_error(status_code: int, code: str, message: str) -> HTTPException:
    return HTTPException(status_code=status_code, detail={"code": code, "message": message})


def trade_error_code_and_message(exc: Exception) -> tuple[str, str]:
    """Map a trade-attempt exception to its CONTRACTS.md §3 code and a message.

    Used both to raise an HTTPException (manual trades) and to fill the
    inline `error` field of a failed chat-driven trade, which is never an
    HTTP error itself.
    """
    if isinstance(exc, UnknownTickerError):
        return "UNKNOWN_TICKER", f"No price available for {exc.ticker}"
    if isinstance(exc, InsufficientCashError):
        return "INSUFFICIENT_CASH", str(exc)
    if isinstance(exc, InsufficientSharesError):
        return "INSUFFICIENT_SHARES", str(exc)
    if isinstance(exc, (InvalidQuantityError, ValueError)):
        return "INVALID_QUANTITY", str(exc)
    return "INTERNAL_ERROR", str(exc)


def translate_trade_error(exc: Exception) -> HTTPException:
    code, message = trade_error_code_and_message(exc)
    status_code = 500 if code == "INTERNAL_ERROR" else 400
    return api_error(status_code, code, message)


def watchlist_error_code_and_message(exc: Exception) -> tuple[str, str]:
    if isinstance(exc, DuplicateTickerError):
        return "DUPLICATE_TICKER", str(exc)
    if isinstance(exc, TickerNotFoundError):
        return "TICKER_NOT_IN_WATCHLIST", str(exc)
    return "INTERNAL_ERROR", str(exc)


def translate_watchlist_error(exc: Exception) -> HTTPException:
    code, message = watchlist_error_code_and_message(exc)
    status_code = {"DUPLICATE_TICKER": 409, "TICKER_NOT_IN_WATCHLIST": 404}.get(code, 500)
    return api_error(status_code, code, message)
