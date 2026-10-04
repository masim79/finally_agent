"""Data access layer for FinAlly — CONTRACTS.md §4, implemented signature-for-signature.

Every function opens its own connection and closes it before returning (see
`app.db.connection.get_connection`). `apply_trade` is the sole exception that
spans multiple tables in one transaction; everything else is a single
statement (or a tiny read-then-write pair) committed immediately.

`apply_trade` is also the only function that should ever change cash,
positions, or trades together when executing a trade. `upsert_position`,
`delete_position`, and `record_trade` remain as independent primitives on
this module's public surface (used by `apply_trade` is not required — it
inlines its own SQL so the whole trade commits as one transaction — but they
exist for lower-level/administrative use); callers executing an actual trade
must go through `apply_trade`, not compose these themselves, or cash and
positions can drift out of sync with the trade log.
"""

from __future__ import annotations

import json
import uuid

from app.db.connection import get_connection, init_db  # noqa: F401  (re-exported, see below)
from app.db.errors import (
    DuplicateTickerError,
    InsufficientCashError,
    InsufficientSharesError,
    InvalidQuantityError,
    TickerNotFoundError,
)
from app.db.models import (
    ChatRow,
    PositionRow,
    SnapshotRow,
    TradeRow,
    WatchlistRow,
    utc_now_iso,
)

# Float tolerance for quantity/cash comparisons — fractional shares and
# repeated arithmetic mean exact equality isn't safe to rely on.
_EPSILON = 1e-9

__all__ = [
    "init_db",
    "get_cash_balance",
    "set_cash_balance",
    "list_watchlist",
    "add_watchlist_ticker",
    "remove_watchlist_ticker",
    "list_positions",
    "get_position",
    "upsert_position",
    "delete_position",
    "record_trade",
    "list_trades",
    "record_snapshot",
    "list_snapshots",
    "record_chat_message",
    "list_chat_messages",
    "apply_trade",
]


# ---------------------------------------------------------------------------
# Profile
# ---------------------------------------------------------------------------


def get_cash_balance(user_id: str = "default") -> float:
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT cash_balance FROM users_profile WHERE id = ?", (user_id,)
        ).fetchone()
        return row["cash_balance"] if row else 0.0
    finally:
        conn.close()


def set_cash_balance(amount: float, user_id: str = "default") -> None:
    conn = get_connection()
    try:
        cur = conn.execute(
            "UPDATE users_profile SET cash_balance = ? WHERE id = ?", (amount, user_id)
        )
        if cur.rowcount == 0:
            conn.execute(
                "INSERT INTO users_profile (id, cash_balance, created_at) VALUES (?, ?, ?)",
                (user_id, amount, utc_now_iso()),
            )
        conn.commit()
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Watchlist
# ---------------------------------------------------------------------------


def list_watchlist(user_id: str = "default") -> list[WatchlistRow]:
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT * FROM watchlist WHERE user_id = ? ORDER BY added_at ASC, rowid ASC",
            (user_id,),
        ).fetchall()
        return [WatchlistRow.from_row(r) for r in rows]
    finally:
        conn.close()


def add_watchlist_ticker(ticker: str, user_id: str = "default") -> WatchlistRow:
    conn = get_connection()
    try:
        existing = conn.execute(
            "SELECT 1 FROM watchlist WHERE user_id = ? AND ticker = ?", (user_id, ticker)
        ).fetchone()
        if existing:
            raise DuplicateTickerError(ticker)
        row_id = str(uuid.uuid4())
        now = utc_now_iso()
        conn.execute(
            "INSERT INTO watchlist (id, user_id, ticker, added_at) VALUES (?, ?, ?, ?)",
            (row_id, user_id, ticker, now),
        )
        conn.commit()
        return WatchlistRow(id=row_id, user_id=user_id, ticker=ticker, added_at=now)
    finally:
        conn.close()


def remove_watchlist_ticker(ticker: str, user_id: str = "default") -> None:
    conn = get_connection()
    try:
        cur = conn.execute(
            "DELETE FROM watchlist WHERE user_id = ? AND ticker = ?", (user_id, ticker)
        )
        if cur.rowcount == 0:
            raise TickerNotFoundError(ticker)
        conn.commit()
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Positions
# ---------------------------------------------------------------------------


def list_positions(user_id: str = "default") -> list[PositionRow]:
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT * FROM positions WHERE user_id = ? ORDER BY ticker ASC", (user_id,)
        ).fetchall()
        return [PositionRow.from_row(r) for r in rows]
    finally:
        conn.close()


def get_position(ticker: str, user_id: str = "default") -> PositionRow | None:
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT * FROM positions WHERE user_id = ? AND ticker = ?", (user_id, ticker)
        ).fetchone()
        return PositionRow.from_row(row) if row else None
    finally:
        conn.close()


def upsert_position(
    ticker: str, quantity: float, avg_cost: float, user_id: str = "default"
) -> PositionRow:
    conn = get_connection()
    try:
        existing = conn.execute(
            "SELECT id FROM positions WHERE user_id = ? AND ticker = ?", (user_id, ticker)
        ).fetchone()
        now = utc_now_iso()
        if existing:
            pos_id = existing["id"]
            conn.execute(
                "UPDATE positions SET quantity = ?, avg_cost = ?, updated_at = ? WHERE id = ?",
                (quantity, avg_cost, now, pos_id),
            )
        else:
            pos_id = str(uuid.uuid4())
            conn.execute(
                "INSERT INTO positions (id, user_id, ticker, quantity, avg_cost, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (pos_id, user_id, ticker, quantity, avg_cost, now),
            )
        conn.commit()
        return PositionRow(
            id=pos_id,
            user_id=user_id,
            ticker=ticker,
            quantity=quantity,
            avg_cost=avg_cost,
            updated_at=now,
        )
    finally:
        conn.close()


def delete_position(ticker: str, user_id: str = "default") -> None:
    conn = get_connection()
    try:
        conn.execute("DELETE FROM positions WHERE user_id = ? AND ticker = ?", (user_id, ticker))
        conn.commit()
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Trades
# ---------------------------------------------------------------------------


def record_trade(
    ticker: str, side: str, quantity: float, price: float, user_id: str = "default"
) -> TradeRow:
    conn = get_connection()
    try:
        trade_id = str(uuid.uuid4())
        now = utc_now_iso()
        conn.execute(
            "INSERT INTO trades (id, user_id, ticker, side, quantity, price, executed_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (trade_id, user_id, ticker, side, quantity, price, now),
        )
        conn.commit()
        return TradeRow(
            id=trade_id,
            user_id=user_id,
            ticker=ticker,
            side=side,
            quantity=quantity,
            price=price,
            executed_at=now,
        )
    finally:
        conn.close()


def list_trades(limit: int = 100, user_id: str = "default") -> list[TradeRow]:
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT * FROM trades WHERE user_id = ? "
            "ORDER BY executed_at DESC, rowid DESC LIMIT ?",
            (user_id, limit),
        ).fetchall()
        return [TradeRow.from_row(r) for r in rows]
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Snapshots
# ---------------------------------------------------------------------------


def record_snapshot(total_value: float, user_id: str = "default") -> None:
    conn = get_connection()
    try:
        conn.execute(
            "INSERT INTO portfolio_snapshots (id, user_id, total_value, recorded_at) "
            "VALUES (?, ?, ?, ?)",
            (str(uuid.uuid4()), user_id, total_value, utc_now_iso()),
        )
        conn.commit()
    finally:
        conn.close()


def list_snapshots(limit: int = 500, user_id: str = "default") -> list[SnapshotRow]:
    """Most recent `limit` snapshots, returned oldest first."""
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT * FROM portfolio_snapshots WHERE user_id = ? "
            "ORDER BY recorded_at DESC, rowid DESC LIMIT ?",
            (user_id, limit),
        ).fetchall()
        return [SnapshotRow.from_row(r) for r in reversed(rows)]
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Chat
# ---------------------------------------------------------------------------


def record_chat_message(
    role: str, content: str, actions: dict | None = None, user_id: str = "default"
) -> ChatRow:
    conn = get_connection()
    try:
        msg_id = str(uuid.uuid4())
        now = utc_now_iso()
        actions_json = json.dumps(actions) if actions is not None else None
        conn.execute(
            "INSERT INTO chat_messages (id, user_id, role, content, actions, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (msg_id, user_id, role, content, actions_json, now),
        )
        conn.commit()
        return ChatRow(
            id=msg_id, user_id=user_id, role=role, content=content, actions=actions,
            created_at=now,
        )
    finally:
        conn.close()


def list_chat_messages(limit: int = 50, user_id: str = "default") -> list[ChatRow]:
    """Most recent `limit` messages, returned oldest first; `actions` JSON-decoded."""
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT * FROM chat_messages WHERE user_id = ? "
            "ORDER BY created_at DESC, rowid DESC LIMIT ?",
            (user_id, limit),
        ).fetchall()
        return [ChatRow.from_row(r) for r in reversed(rows)]
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Atomic trade application — the ONE write path for cash, positions, and trades
# ---------------------------------------------------------------------------


def apply_trade(
    ticker: str, side: str, quantity: float, price: float, user_id: str = "default"
) -> tuple[TradeRow, PositionRow | None, float]:
    """Validate, then atomically update cash, the position, and the trade log.

    Returns (trade, position_or_None, new_cash_balance). `position` is None
    when a sell fully closes the position. Raises InvalidQuantityError before
    touching the database if quantity isn't positive; raises
    InsufficientCashError / InsufficientSharesError after reading current
    state but before any write. If a write fails partway through, the whole
    transaction is rolled back so nothing partially applies.

    The transaction is opened in IMMEDIATE mode, acquiring the write lock
    before the cash/position reads rather than at the first write. Python's
    sqlite3 otherwise runs plain SELECTs in autocommit (a DEFERRED
    transaction only begins at the first DML statement), which would let two
    concurrent calls both read the same starting cash and each validate
    against it — a lost update where the second writer's commit silently
    overwrites the first's. A manual trade-bar click and an LLM
    auto-executed trade are exactly the kind of pair that can land in this
    function at the same moment, since FastAPI runs sync handlers in a
    threadpool. BEGIN IMMEDIATE makes a concurrent caller block at the start
    of apply_trade (for up to the busy_timeout set in get_connection) rather
    than race the read, so every call here sees a consistent, already-locked
    view of cash and the position.
    """
    if side not in ("buy", "sell"):
        raise ValueError(f"side must be 'buy' or 'sell', got {side!r}")
    if quantity <= 0:
        raise InvalidQuantityError(quantity)

    conn = get_connection()
    try:
        conn.execute("BEGIN IMMEDIATE")
        cash_row = conn.execute(
            "SELECT cash_balance FROM users_profile WHERE id = ?", (user_id,)
        ).fetchone()
        cash_balance = cash_row["cash_balance"] if cash_row else 0.0

        pos_row = conn.execute(
            "SELECT * FROM positions WHERE user_id = ? AND ticker = ?", (user_id, ticker)
        ).fetchone()
        held = pos_row["quantity"] if pos_row else 0.0
        avg_cost = pos_row["avg_cost"] if pos_row else 0.0

        cost = quantity * price

        if side == "buy":
            if cost > cash_balance + _EPSILON:
                raise InsufficientCashError(cost, cash_balance)
            new_cash = cash_balance - cost
            new_qty = held + quantity
            new_avg_cost = ((held * avg_cost) + (quantity * price)) / new_qty
        else:
            if quantity > held + _EPSILON:
                raise InsufficientSharesError(ticker, quantity, held)
            new_cash = cash_balance + cost
            new_qty = held - quantity
            new_avg_cost = avg_cost  # sells never change avg_cost

        now = utc_now_iso()

        if cash_row:
            conn.execute(
                "UPDATE users_profile SET cash_balance = ? WHERE id = ?", (new_cash, user_id)
            )
        else:
            conn.execute(
                "INSERT INTO users_profile (id, cash_balance, created_at) VALUES (?, ?, ?)",
                (user_id, new_cash, now),
            )

        position: PositionRow | None
        if new_qty <= _EPSILON:
            conn.execute(
                "DELETE FROM positions WHERE user_id = ? AND ticker = ?", (user_id, ticker)
            )
            position = None
        else:
            if pos_row:
                pos_id = pos_row["id"]
                conn.execute(
                    "UPDATE positions SET quantity = ?, avg_cost = ?, updated_at = ? "
                    "WHERE id = ?",
                    (new_qty, new_avg_cost, now, pos_id),
                )
            else:
                pos_id = str(uuid.uuid4())
                conn.execute(
                    "INSERT INTO positions "
                    "(id, user_id, ticker, quantity, avg_cost, updated_at) "
                    "VALUES (?, ?, ?, ?, ?, ?)",
                    (pos_id, user_id, ticker, new_qty, new_avg_cost, now),
                )
            position = PositionRow(
                id=pos_id,
                user_id=user_id,
                ticker=ticker,
                quantity=new_qty,
                avg_cost=new_avg_cost,
                updated_at=now,
            )

        trade_id = str(uuid.uuid4())
        conn.execute(
            "INSERT INTO trades (id, user_id, ticker, side, quantity, price, executed_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (trade_id, user_id, ticker, side, quantity, price, now),
        )
        trade = TradeRow(
            id=trade_id,
            user_id=user_id,
            ticker=ticker,
            side=side,
            quantity=quantity,
            price=price,
            executed_at=now,
        )

        conn.commit()
        return trade, position, new_cash
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
