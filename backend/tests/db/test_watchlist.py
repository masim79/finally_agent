"""Watchlist repository functions: ordering, duplicate, and not-found errors."""

from __future__ import annotations

import pytest

from app.db import repositories as repo
from app.db.errors import DuplicateTickerError, RepositoryError, TickerNotFoundError


def test_list_watchlist_ordered_by_added_at_ascending(initialized_db):
    repo.remove_watchlist_ticker("AAPL")
    repo.remove_watchlist_ticker("GOOGL")
    repo.add_watchlist_ticker("ZZZ")
    repo.add_watchlist_ticker("AAA")

    tickers = [w.ticker for w in repo.list_watchlist()]
    # Original seed order preserved, with new additions appended in insertion order.
    assert tickers[-2:] == ["ZZZ", "AAA"]


def test_add_watchlist_ticker_returns_row(initialized_db):
    row = repo.add_watchlist_ticker("PYPL")

    assert row.ticker == "PYPL"
    assert row.user_id == "default"
    assert row.id
    assert row.added_at


def test_add_duplicate_ticker_raises(initialized_db):
    with pytest.raises(DuplicateTickerError) as exc_info:
        repo.add_watchlist_ticker("AAPL")

    assert exc_info.value.ticker == "AAPL"
    assert isinstance(exc_info.value, RepositoryError)


def test_remove_watchlist_ticker(initialized_db):
    repo.remove_watchlist_ticker("AAPL")

    tickers = [w.ticker for w in repo.list_watchlist()]
    assert "AAPL" not in tickers


def test_remove_missing_ticker_raises(initialized_db):
    with pytest.raises(TickerNotFoundError) as exc_info:
        repo.remove_watchlist_ticker("NOPE")

    assert exc_info.value.ticker == "NOPE"
    assert isinstance(exc_info.value, RepositoryError)


def test_watchlist_scoped_per_user(initialized_db):
    repo.add_watchlist_ticker("PYPL", user_id="alice")

    default_tickers = [w.ticker for w in repo.list_watchlist()]
    alice_tickers = [w.ticker for w in repo.list_watchlist(user_id="alice")]

    assert "PYPL" not in default_tickers
    assert alice_tickers == ["PYPL"]
