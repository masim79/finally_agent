"""apply_trade: the single atomic write path for cash, positions, and trades."""

from __future__ import annotations

import pytest

from app.db import repositories as repo
from app.db.connection import get_connection as real_get_connection
from app.db.errors import (
    InsufficientCashError,
    InsufficientSharesError,
    InvalidQuantityError,
    RepositoryError,
)


def test_buy_updates_cash_and_creates_position(initialized_db):
    starting_cash = repo.get_cash_balance()

    trade, position, new_cash = repo.apply_trade("AAPL", "buy", 10.0, 100.0)

    assert trade.ticker == "AAPL"
    assert trade.side == "buy"
    assert trade.quantity == 10.0
    assert trade.price == 100.0
    assert position is not None
    assert position.quantity == 10.0
    assert position.avg_cost == 100.0
    assert new_cash == pytest.approx(starting_cash - 1000.0)
    assert repo.get_cash_balance() == pytest.approx(new_cash)


def test_weighted_average_cost_on_successive_buys(initialized_db):
    repo.apply_trade("AAPL", "buy", 10.0, 100.0)  # 10 @ 100
    _, position, _ = repo.apply_trade("AAPL", "buy", 10.0, 200.0)  # +10 @ 200

    # (10*100 + 10*200) / 20 = 150
    assert position.quantity == 20.0
    assert position.avg_cost == pytest.approx(150.0)


def test_sell_does_not_change_avg_cost(initialized_db):
    repo.apply_trade("AAPL", "buy", 10.0, 100.0)

    _, position, _ = repo.apply_trade("AAPL", "sell", 4.0, 150.0)

    assert position is not None
    assert position.quantity == pytest.approx(6.0)
    assert position.avg_cost == pytest.approx(100.0)  # unchanged despite the higher sell price


def test_sell_increases_cash_by_proceeds(initialized_db):
    repo.apply_trade("AAPL", "buy", 10.0, 100.0)
    cash_after_buy = repo.get_cash_balance()

    _, _, new_cash = repo.apply_trade("AAPL", "sell", 5.0, 120.0)

    assert new_cash == pytest.approx(cash_after_buy + 600.0)


def test_full_close_deletes_position(initialized_db):
    repo.apply_trade("AAPL", "buy", 10.0, 100.0)

    _, position, _ = repo.apply_trade("AAPL", "sell", 10.0, 120.0)

    assert position is None
    assert repo.get_position("AAPL") is None


def test_full_close_with_fractional_quantity_and_float_tolerance(initialized_db):
    repo.apply_trade("AAPL", "buy", 0.1, 100.0)
    repo.apply_trade("AAPL", "buy", 0.2, 100.0)  # held is now 0.1 + 0.2, not exactly 0.3 in float

    # Selling the full (imprecise) float amount must still fully close the position.
    held = repo.get_position("AAPL").quantity
    _, position, _ = repo.apply_trade("AAPL", "sell", held, 100.0)

    assert position is None
    assert repo.get_position("AAPL") is None


def test_partial_sell_leaves_remainder(initialized_db):
    repo.apply_trade("AAPL", "buy", 10.0, 100.0)

    _, position, _ = repo.apply_trade("AAPL", "sell", 3.0, 100.0)

    assert position is not None
    assert position.quantity == pytest.approx(7.0)


def test_insufficient_cash_raises_and_leaves_state_untouched(initialized_db):
    starting_cash = repo.get_cash_balance()

    with pytest.raises(InsufficientCashError) as exc_info:
        repo.apply_trade("AAPL", "buy", 1_000_000.0, 100.0)

    assert isinstance(exc_info.value, RepositoryError)
    assert repo.get_cash_balance() == starting_cash
    assert repo.get_position("AAPL") is None
    assert repo.list_trades() == []


def test_insufficient_shares_raises_and_leaves_state_untouched(initialized_db):
    repo.apply_trade("AAPL", "buy", 5.0, 100.0)
    cash_before = repo.get_cash_balance()

    with pytest.raises(InsufficientSharesError) as exc_info:
        repo.apply_trade("AAPL", "sell", 10.0, 100.0)

    assert isinstance(exc_info.value, RepositoryError)
    assert repo.get_cash_balance() == cash_before
    assert repo.get_position("AAPL").quantity == 5.0
    assert len(repo.list_trades()) == 1  # only the original buy


@pytest.mark.parametrize("quantity", [0.0, -1.0, -0.0001])
def test_invalid_quantity_raises_before_any_write(initialized_db, quantity):
    cash_before = repo.get_cash_balance()

    with pytest.raises(InvalidQuantityError):
        repo.apply_trade("AAPL", "buy", quantity, 100.0)

    assert repo.get_cash_balance() == cash_before
    assert repo.list_trades() == []


def test_invalid_side_raises_value_error(initialized_db):
    with pytest.raises(ValueError):
        repo.apply_trade("AAPL", "hold", 1.0, 100.0)


class _FailOnTradesInsertConnection:
    """Wraps a real sqlite3 connection and fails the trades insert only.

    Used to prove apply_trade's transaction rolls back everything it already
    wrote (cash, position) when a later statement in the same trade fails.
    """

    def __init__(self, conn):
        self._conn = conn

    def execute(self, sql, params=()):
        if sql.strip().upper().startswith("INSERT INTO TRADES"):
            raise RuntimeError("simulated failure writing the trade row")
        return self._conn.execute(sql, params)

    def __getattr__(self, name):
        return getattr(self._conn, name)


def test_apply_trade_rolls_back_on_mid_transaction_failure(initialized_db, monkeypatch):
    cash_before = repo.get_cash_balance()
    positions_before = repo.list_positions()
    trades_before = repo.list_trades()

    original_get_connection = repo.get_connection
    failing_conn = _FailOnTradesInsertConnection(real_get_connection())
    monkeypatch.setattr(repo, "get_connection", lambda *a, **k: failing_conn)

    with pytest.raises(RuntimeError):
        repo.apply_trade("AAPL", "buy", 10.0, 100.0)

    # Restore only get_connection (not the whole monkeypatch instance, which
    # also holds the initialized_db fixture's FINALLY_DB_PATH) to verify with
    # a clean connection against the same database file.
    monkeypatch.setattr(repo, "get_connection", original_get_connection)

    assert repo.get_cash_balance() == cash_before
    assert repo.list_positions() == positions_before
    assert repo.list_trades() == trades_before
    assert repo.get_position("AAPL") is None
