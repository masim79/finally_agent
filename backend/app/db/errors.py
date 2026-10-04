"""Exceptions raised by app.db.repositories.

All subclass RepositoryError so callers can catch broadly when they just need
to know "something about this data operation was invalid," or narrowly when
they need to map to a specific CONTRACTS.md §3 error code.
"""

from __future__ import annotations


class RepositoryError(Exception):
    """Base class for every exception raised by the repository layer."""


class DuplicateTickerError(RepositoryError):
    """A ticker already exists in the watchlist for this user. Maps to DUPLICATE_TICKER."""

    def __init__(self, ticker: str):
        self.ticker = ticker
        super().__init__(f"Ticker already in watchlist: {ticker}")


class TickerNotFoundError(RepositoryError):
    """A ticker is not present in the watchlist. Maps to TICKER_NOT_IN_WATCHLIST."""

    def __init__(self, ticker: str):
        self.ticker = ticker
        super().__init__(f"Ticker not in watchlist: {ticker}")


class InsufficientCashError(RepositoryError):
    """A buy would require more cash than the user's balance. Maps to INSUFFICIENT_CASH."""

    def __init__(self, required: float, available: float):
        self.required = required
        self.available = available
        super().__init__(f"Need ${required:.2f}, have ${available:.2f}")


class InsufficientSharesError(RepositoryError):
    """A sell exceeds the held quantity. Maps to INSUFFICIENT_SHARES."""

    def __init__(self, ticker: str, requested: float, held: float):
        self.ticker = ticker
        self.requested = requested
        self.held = held
        super().__init__(f"Cannot sell {requested} {ticker}, only hold {held}")


class InvalidQuantityError(RepositoryError):
    """A trade quantity is zero or negative. Maps to INVALID_QUANTITY."""

    def __init__(self, quantity: float):
        self.quantity = quantity
        super().__init__(f"Quantity must be positive, got {quantity}")
