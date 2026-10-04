"""init_db: fresh-init seeding and idempotency against seeded / partial DBs."""

from __future__ import annotations

import sqlite3

from app.db import repositories as repo
from app.db.connection import get_connection
from app.db.seed import DEFAULT_CASH_BALANCE, DEFAULT_TICKERS


def test_fresh_init_seeds_default_user_and_watchlist(db_path):
    repo.init_db()

    assert repo.get_cash_balance() == DEFAULT_CASH_BALANCE

    tickers = [w.ticker for w in repo.list_watchlist()]
    assert tickers == DEFAULT_TICKERS


def test_reinit_against_already_seeded_db_is_a_noop(db_path):
    repo.init_db()
    repo.set_cash_balance(1234.56)
    repo.add_watchlist_ticker("PYPL")

    repo.init_db()  # second call must not reset or duplicate anything

    assert repo.get_cash_balance() == 1234.56
    tickers = [w.ticker for w in repo.list_watchlist()]
    assert tickers == DEFAULT_TICKERS + ["PYPL"]


def test_reinit_against_partially_populated_db_fills_only_missing_table(db_path):
    # Simulate a DB where the schema exists and the profile was seeded, but the
    # watchlist seeding step never ran (e.g. a crash between the two inserts).
    repo.init_db()
    conn = get_connection()
    try:
        conn.execute("DELETE FROM watchlist")
        conn.commit()
    finally:
        conn.close()

    repo.set_cash_balance(500.0)  # prove the existing profile is left alone

    repo.init_db()

    assert repo.get_cash_balance() == 500.0  # untouched, not reset to the default
    tickers = [w.ticker for w in repo.list_watchlist()]
    assert tickers == DEFAULT_TICKERS  # the missing table got seeded


def test_init_creates_parent_directory(tmp_path, monkeypatch):
    nested = tmp_path / "nested" / "dir" / "finally.db"
    monkeypatch.setenv("FINALLY_DB_PATH", str(nested))

    repo.init_db()

    assert nested.exists()


def test_init_never_drops_tables_with_data(initialized_db):
    repo.record_trade("AAPL", "buy", 1.0, 100.0)

    repo.init_db()
    repo.init_db()

    assert len(repo.list_trades()) == 1


def test_tables_created_with_expected_columns(initialized_db):
    conn = get_connection()
    try:
        conn.row_factory = sqlite3.Row
        names = {
            row["name"]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            ).fetchall()
        }
    finally:
        conn.close()

    for table in (
        "users_profile",
        "watchlist",
        "positions",
        "trades",
        "portfolio_snapshots",
        "chat_messages",
    ):
        assert table in names
