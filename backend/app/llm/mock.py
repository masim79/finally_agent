"""Deterministic, offline stand-in for the model, used when ``LLM_MOCK=true``.

This is a test contract, not a convenience: the Playwright E2E suite asserts
against the behaviours in CONTRACTS.md §5's mock table, so the keyword rules below
are as load-bearing as any API signature. No network, no API key, no randomness —
the same message always produces the same ChatResult.
"""

from __future__ import annotations

import os
import re

from app.llm.schemas import ChatResult, ProposedChange, ProposedTrade

_TRUTHY = {"1", "true", "yes", "on"}

#: Short words that look like tickers but are not. Tickers are matched as whole
#: words of 1-5 letters, which already filters out "shares", "watchlist", "please".
_STOPWORDS = {
    "A", "ADD", "ALL", "AN", "AND", "ANY", "ARE", "AT", "BUY", "CAN", "CASH", "D", "DO",
    "DOES", "EACH", "FOR", "FROM", "GET", "HALF", "HAS", "HAVE", "HOLD", "HOW", "I",
    "IN", "IS", "IT", "LET", "LIST", "ME", "MORE", "MUCH", "MY", "NO", "NOW", "OF",
    "OFF", "ON", "ONE", "OR", "OUT", "OWN", "PLS", "PUT",
    "RE", "S", "SELL", "SOME", "STOCK", "T", "TAKE", "THE", "THEN", "TO", "UP", "US",
    "VE", "WANT", "WHAT", "WHY", "WITH", "WORTH", "YES", "YOU", "YOUR",
}

_WORD_RE = re.compile(r"\b[A-Za-z]{1,5}\b")
_NUMBER_RE = re.compile(r"\d+(?:\.\d+)?")


def is_mock_enabled() -> bool:
    """Read ``LLM_MOCK`` from the environment *at call time* so tests can toggle it."""
    return (os.environ.get("LLM_MOCK") or "").strip().lower() in _TRUTHY


def _extract_ticker(text: str) -> str | None:
    """Find the ticker in a message, preferring an already-upper-cased word."""
    words = _WORD_RE.findall(text)
    candidates = [w for w in words if w.upper() not in _STOPWORDS]
    if not candidates:
        return None
    for word in candidates:
        if word.isupper():
            return word
    return candidates[0].upper()


def _extract_quantity(text: str) -> float | None:
    match = _NUMBER_RE.search(text)
    if not match:
        return None
    quantity = float(match.group())
    return quantity if quantity > 0 else None


def _format_quantity(quantity: float) -> str:
    text = f"{quantity:.4f}".rstrip("0").rstrip(".")
    return text or "0"


def _analysis(portfolio: dict) -> ChatResult:
    total = (portfolio or {}).get("total_value")
    if not isinstance(total, (int, float)) or isinstance(total, bool):
        total = 0.0
    return ChatResult(
        message=(
            f"Your portfolio is currently worth ${total:,.2f}. "
            "Ask me to buy or sell a ticker, or to add one to your watchlist, "
            "and I'll take care of it."
        ),
        trades=[],
        watchlist_changes=[],
    )


def mock_chat_response(
    user_message: str,
    portfolio: dict,
    watchlist: list[dict],
) -> ChatResult:
    """Return the fixed response for ``user_message`` per the CONTRACTS.md §5 table."""
    text = user_message or ""
    lowered = text.lower()
    ticker = _extract_ticker(text)
    quantity = _extract_quantity(text)

    if "buy" in lowered and ticker and quantity:
        return ChatResult(
            message=f"Buying {_format_quantity(quantity)} {ticker} at the current market price.",
            trades=[ProposedTrade(ticker=ticker, side="buy", quantity=quantity)],
            watchlist_changes=[],
        )

    if "sell" in lowered and ticker and quantity:
        return ChatResult(
            message=f"Selling {_format_quantity(quantity)} {ticker} at the current market price.",
            trades=[ProposedTrade(ticker=ticker, side="sell", quantity=quantity)],
            watchlist_changes=[],
        )

    if "add" in lowered and ticker:
        return ChatResult(
            message=f"Adding {ticker} to your watchlist.",
            trades=[],
            watchlist_changes=[ProposedChange(ticker=ticker, action="add")],
        )

    if "remove" in lowered and ticker:
        return ChatResult(
            message=f"Removing {ticker} from your watchlist.",
            trades=[],
            watchlist_changes=[ProposedChange(ticker=ticker, action="remove")],
        )

    return _analysis(portfolio)
