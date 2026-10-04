"""Structured-output models and the public result types for the LLM layer.

Two families of types live here, deliberately kept apart:

* The ``Llm*`` Pydantic models describe the JSON the model is asked to emit. They
  are what gets handed to LiteLLM as ``response_format``, and they are where
  validation happens (ticker upper-casing, positive quantities, literal sides).
* ``ChatResult`` / ``ProposedTrade`` / ``ProposedChange`` are the frozen
  dataclasses the backend consumes (CONTRACTS.md Â§5). They carry no validation
  of their own because nothing reaches them unvalidated.

The JSON Schema sent to the provider is kept deliberately plain â€” no ``pattern``,
no ``exclusiveMinimum`` â€” because strict structured-output modes support only a
narrow keyword subset. All the real constraints are enforced by validators, which
run after the model has answered and emit nothing into the schema.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Literal

from pydantic import BaseModel, field_validator

#: Shown to the user when the model's answer cannot be salvaged at all.
MALFORMED_RESPONSE_MESSAGE = (
    "I had trouble reading my own analysis just now â€” the response came back "
    "garbled, so I haven't taken any action. Could you ask me again?"
)

_TICKER_CHARS = set("ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789.-")


def _clean_ticker(value: str) -> str:
    """Upper-case, strip, and sanity-check a ticker. Non-strings never get here --
    Pydantic rejects them before this after-validator runs."""
    value = value.strip().upper()
    if not value:
        raise ValueError("ticker must not be empty")
    if len(value) > 10:
        raise ValueError("ticker is implausibly long")
    if not set(value) <= _TICKER_CHARS:
        raise ValueError(f"ticker contains unexpected characters: {value!r}")
    return value


class LlmTrade(BaseModel):
    """A trade to execute. `quantity` is a number of SHARES, never a dollar amount."""

    ticker: str
    side: Literal["buy", "sell"]
    quantity: float

    @field_validator("ticker")
    @classmethod
    def _validate_ticker(cls, value: str) -> str:
        return _clean_ticker(value)

    @field_validator("quantity")
    @classmethod
    def _validate_quantity(cls, value: float) -> float:
        if not math.isfinite(value):
            raise ValueError("quantity must be a finite number")
        if value <= 0:
            raise ValueError(f"quantity must be positive, got {value}")
        return value


class LlmWatchlistChange(BaseModel):
    """One watchlist modification the model wants applied."""

    ticker: str
    action: Literal["add", "remove"]

    @field_validator("ticker")
    @classmethod
    def _validate_ticker(cls, value: str) -> str:
        return _clean_ticker(value)


# Every field is declared required and carries no default. Strict structured output
# marks all properties required regardless, and a leftover ``"default": []`` is one more
# keyword for a strict validator to object to. Absent fields are handled by the parser --
# nothing inbound is validated through LlmChatResponse itself.
#
# Note that these docstrings travel to the model as JSON Schema descriptions, so they are
# written for the model to read.
class LlmChatResponse(BaseModel):
    """FinAlly's reply: a conversational message plus any actions to apply."""

    message: str
    trades: list[LlmTrade]
    watchlist_changes: list[LlmWatchlistChange]


@dataclass(frozen=True)
class ProposedTrade:
    """A trade the LLM decided on. The backend executes it; this layer never does."""

    ticker: str
    side: str
    quantity: float


@dataclass(frozen=True)
class ProposedChange:
    """A watchlist change the LLM decided on."""

    ticker: str
    action: str


@dataclass(frozen=True)
class ChatResult:
    """CONTRACTS.md Â§5 return type. Action lists are always lists, never None."""

    message: str
    trades: list[ProposedTrade] = field(default_factory=list)
    watchlist_changes: list[ProposedChange] = field(default_factory=list)


def degraded_result(message: str = MALFORMED_RESPONSE_MESSAGE) -> ChatResult:
    """A result that says something useful to the user and asks for nothing."""
    return ChatResult(message=message, trades=[], watchlist_changes=[])
