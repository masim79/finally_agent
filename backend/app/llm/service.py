"""Public entry point for the LLM layer — CONTRACTS.md §5.

The whole layer exposes exactly one function. It decides; it executes nothing. The
backend loops over the returned trades and watchlist changes and applies them
through the same services the trade bar uses, which keeps trade validation in one
place and keeps everything here testable with no database and no network.
"""

from __future__ import annotations

from app.llm.client import LLMError, call_model, parse_response
from app.llm.mock import is_mock_enabled, mock_chat_response
from app.llm.prompts import build_messages
from app.llm.schemas import ChatResult, ProposedChange, ProposedTrade

__all__ = [
    "ChatResult",
    "LLMError",
    "ProposedChange",
    "ProposedTrade",
    "generate_chat_response",
]


async def generate_chat_response(
    user_message: str,
    portfolio: dict,
    watchlist: list[dict],
    history: list[dict],
) -> ChatResult:
    """Call the LLM and return its parsed intent. Executes NOTHING.

    Args:
        user_message: The user's new message.
        portfolio: Exactly the ``GET /api/portfolio`` payload (CONTRACTS.md §3).
        watchlist: Exactly ``GET /api/watchlist``'s ``tickers`` array.
        history: ``[{"role", "content"}]``, oldest first, already trimmed by the caller.

    Returns:
        A ChatResult. A malformed or truncated model response never raises — it
        degrades to a ChatResult whose message explains the trouble and whose
        action lists are empty.

    Raises:
        LLMError: only when the provider is unreachable, unauthenticated, or its
            API key is absent. The backend surfaces this as the §3 ``LLM_ERROR``.
    """
    if is_mock_enabled():
        return mock_chat_response(user_message, portfolio, watchlist)

    messages = build_messages(user_message, portfolio, watchlist, history)
    raw = await call_model(messages)
    return parse_response(raw)
