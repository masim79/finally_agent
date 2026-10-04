"""Regression test for a lost-update race in apply_trade.

apply_trade reads cash_balance (and the position row) and later writes the
updated values. If those reads run outside a write-locking transaction, two
concurrent calls can both read the same starting cash, each validate against
it, and the second write clobbers the first — the final balance reflects only
one trade even though both committed and both trade rows exist. This is not
contrived: a manual trade-bar click and an LLM auto-executed trade can land
in apply_trade at the same moment since FastAPI runs sync handlers in a
threadpool.

The fix is to open the transaction in IMMEDIATE mode (acquire the write lock
before any read), which serializes concurrent callers. To actually exercise
that race (or its absence) we need both threads to have completed their
*read* of cash_balance before either reaches its *write* — plain thread
scheduling is too fast and unreliable to hit that window on its own, so we
pause each caller with a barrier immediately after its cash_balance read
completes. If a second caller never arrives at that point within the timeout
(exactly what IMMEDIATE-mode locking causes once the fix is applied — the
second caller blocks *before* its SELECT even runs, waiting on the lock), the
wait degrades to a no-op rather than hanging, so this test is safe to run
both before and after the fix.
"""

from __future__ import annotations

import threading

import pytest

from app.db import repositories as repo

_BARRIER_TIMEOUT = 2.0


class _FetchedRow:
    """A cursor-alike wrapping an already-fetched row, for execute() to return."""

    def __init__(self, row):
        self._row = row

    def fetchone(self):
        return self._row


class _BarrierAfterCashReadConnection:
    """Wraps a real connection; pauses right after the cash_balance SELECT
    actually fetches its row, so two concurrent apply_trade calls are each
    guaranteed to have read cash_balance before either one writes it back.
    """

    def __init__(self, conn, barrier):
        self._conn = conn
        self._barrier = barrier

    def execute(self, sql, params=()):
        cur = self._conn.execute(sql, params)
        if sql.strip().upper().startswith("SELECT CASH_BALANCE FROM USERS_PROFILE"):
            row = cur.fetchone()  # perform the real read now, before pausing
            try:
                self._barrier.wait(timeout=_BARRIER_TIMEOUT)
            except threading.BrokenBarrierError:
                pass  # no concurrent partner showed up (e.g. the fix serialized us) — proceed
            return _FetchedRow(row)
        return cur

    def __getattr__(self, name):
        return getattr(self._conn, name)


def test_concurrent_buys_do_not_lose_a_cash_update(initialized_db):
    """Two concurrent buys (different tickers, same user) must both be
    reflected in the final cash balance — not just whichever wrote last."""
    starting_cash = repo.get_cash_balance()
    barrier = threading.Barrier(2)
    original_get_connection = repo.get_connection

    def patched_get_connection(*args, **kwargs):
        return _BarrierAfterCashReadConnection(original_get_connection(*args, **kwargs), barrier)

    errors: list[Exception] = []

    def worker(ticker: str, quantity: float, price: float) -> None:
        try:
            repo.apply_trade(ticker, "buy", quantity, price)
        except Exception as exc:  # noqa: BLE001 — collected and reported below
            errors.append(exc)

    repo.get_connection = patched_get_connection
    try:
        t1 = threading.Thread(target=worker, args=("AAPL", 5.0, 100.0))
        t2 = threading.Thread(target=worker, args=("GOOGL", 5.0, 100.0))
        t1.start()
        t2.start()
        t1.join(timeout=5)
        t2.join(timeout=5)
    finally:
        repo.get_connection = original_get_connection  # restore before asserting

    assert not errors, f"apply_trade raised under concurrency: {errors}"
    assert len(repo.list_trades()) == 2  # both trades were logged

    expected_cash = starting_cash - 500.0 - 500.0  # 5 shares * $100 each, twice
    assert repo.get_cash_balance() == pytest.approx(expected_cash)


def test_concurrent_buys_of_the_same_ticker_combine_instead_of_clobbering(initialized_db):
    """Two concurrent buys of the SAME ticker must both land in the position —
    not just whichever write happened last — covering the position side of
    the same lost-update window the cash-balance test above covers."""
    starting_cash = repo.get_cash_balance()
    barrier = threading.Barrier(2)
    original_get_connection = repo.get_connection

    def patched_get_connection(*args, **kwargs):
        return _BarrierAfterCashReadConnection(original_get_connection(*args, **kwargs), barrier)

    errors: list[Exception] = []

    def worker(quantity: float, price: float) -> None:
        try:
            repo.apply_trade("AAPL", "buy", quantity, price)
        except Exception as exc:  # noqa: BLE001 — collected and reported below
            errors.append(exc)

    repo.get_connection = patched_get_connection
    try:
        t1 = threading.Thread(target=worker, args=(5.0, 100.0))
        t2 = threading.Thread(target=worker, args=(10.0, 200.0))
        t1.start()
        t2.start()
        t1.join(timeout=5)
        t2.join(timeout=5)
    finally:
        repo.get_connection = original_get_connection  # restore before asserting

    assert not errors, f"apply_trade raised under concurrency: {errors}"
    assert len(repo.list_trades()) == 2  # both trades were logged

    position = repo.get_position("AAPL")
    assert position is not None
    assert position.quantity == pytest.approx(15.0)  # 5 + 10, not just one of them
    # Weighted average over BOTH fills: (5*100 + 10*200) / 15 = 166.67
    assert position.avg_cost == pytest.approx((5.0 * 100.0 + 10.0 * 200.0) / 15.0)

    expected_cash = starting_cash - (5.0 * 100.0) - (10.0 * 200.0)
    assert repo.get_cash_balance() == pytest.approx(expected_cash)
