"""Trade log and snapshot ordering, record_trade/record_snapshot primitives."""

from __future__ import annotations

from app.db import repositories as repo


def test_record_trade_returns_row(initialized_db):
    trade = repo.record_trade("AAPL", "buy", 10.0, 100.0)

    assert trade.ticker == "AAPL"
    assert trade.side == "buy"
    assert trade.quantity == 10.0
    assert trade.price == 100.0
    assert trade.executed_at


def test_list_trades_newest_first(initialized_db):
    first = repo.record_trade("AAPL", "buy", 1.0, 100.0)
    second = repo.record_trade("GOOGL", "buy", 1.0, 100.0)
    third = repo.record_trade("MSFT", "buy", 1.0, 100.0)

    trades = repo.list_trades()

    assert [t.id for t in trades] == [third.id, second.id, first.id]


def test_list_trades_respects_limit(initialized_db):
    for i in range(5):
        repo.record_trade("AAPL", "buy", 1.0, 100.0 + i)

    trades = repo.list_trades(limit=2)

    assert len(trades) == 2
    assert trades[0].price == 104.0  # most recent first
    assert trades[1].price == 103.0


def test_list_trades_scoped_per_user(initialized_db):
    repo.record_trade("AAPL", "buy", 1.0, 100.0, user_id="alice")

    assert repo.list_trades() == []
    assert len(repo.list_trades(user_id="alice")) == 1


def test_record_snapshot_and_list_oldest_first(initialized_db):
    repo.record_snapshot(10000.0)
    repo.record_snapshot(10500.0)
    repo.record_snapshot(9800.0)

    snapshots = repo.list_snapshots()

    assert [s.total_value for s in snapshots] == [10000.0, 10500.0, 9800.0]


def test_list_snapshots_limit_keeps_most_recent_but_still_oldest_first(initialized_db):
    for value in (1.0, 2.0, 3.0, 4.0, 5.0):
        repo.record_snapshot(value)

    snapshots = repo.list_snapshots(limit=2)

    # Most recent 2 values (4.0, 5.0), still returned oldest-first.
    assert [s.total_value for s in snapshots] == [4.0, 5.0]


def test_list_snapshots_scoped_per_user(initialized_db):
    repo.record_snapshot(100.0, user_id="alice")

    assert repo.list_snapshots() == []
    assert len(repo.list_snapshots(user_id="alice")) == 1
