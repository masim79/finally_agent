"""Default seed data: one user profile + the 10 default watchlist tickers.

Both seeding steps are independently idempotent: each checks whether its own
table is empty before inserting, so a partially-populated database (e.g. a
profile row but no watchlist) gets only the missing piece filled in, and a
fully-seeded database is left untouched on every subsequent startup.
"""

from __future__ import annotations

import sqlite3
import uuid

from app.db.models import utc_now_iso

DEFAULT_USER_ID = "default"
DEFAULT_CASH_BALANCE = 10000.0
DEFAULT_TICKERS = ["AAPL", "GOOGL", "MSFT", "AMZN", "TSLA", "NVDA", "META", "JPM", "V", "NFLX"]


def seed_if_empty(conn: sqlite3.Connection) -> None:
    """Seed users_profile and watchlist, each only if currently empty.

    Does not commit; the caller (app.db.connection.init_db) controls the
    transaction boundary.
    """
    if conn.execute("SELECT COUNT(*) FROM users_profile").fetchone()[0] == 0:
        conn.execute(
            "INSERT INTO users_profile (id, cash_balance, created_at) VALUES (?, ?, ?)",
            (DEFAULT_USER_ID, DEFAULT_CASH_BALANCE, utc_now_iso()),
        )

    if conn.execute("SELECT COUNT(*) FROM watchlist").fetchone()[0] == 0:
        now = utc_now_iso()
        conn.executemany(
            "INSERT INTO watchlist (id, user_id, ticker, added_at) VALUES (?, ?, ?, ?)",
            [(str(uuid.uuid4()), DEFAULT_USER_ID, ticker, now) for ticker in DEFAULT_TICKERS],
        )
