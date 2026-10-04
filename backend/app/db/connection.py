"""SQLite connection management and lazy schema initialization.

Connections are per-call (opened and closed within a single repository
function) rather than pooled or held open — SQLite serializes writes anyway,
and FastAPI runs sync handlers in a threadpool, so `check_same_thread=False`
plus WAL journaling is enough for correctness without any shared connection
state.
"""

from __future__ import annotations

import os
import sqlite3
from pathlib import Path

DEFAULT_DB_PATH = "db/finally.db"


def resolve_db_path(db_path: str | None = None) -> str:
    """Resolve the database path: argument > FINALLY_DB_PATH env var > default."""
    if db_path:
        return db_path
    return os.environ.get("FINALLY_DB_PATH", DEFAULT_DB_PATH)


def get_connection(db_path: str | None = None) -> sqlite3.Connection:
    """Open a new connection to the SQLite database.

    Creates the parent directory of the resolved path if it doesn't exist.
    Configures WAL journaling, foreign-key enforcement, and dict-like row
    access (`sqlite3.Row`). Callers are responsible for closing what they
    open (typically in a `try`/`finally`).
    """
    path = resolve_db_path(db_path)
    if path != ":memory:":
        parent = Path(path).parent
        if str(parent) not in ("", "."):
            parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA busy_timeout=5000")
    return conn


def init_db(db_path: str | None = None) -> None:
    """Create tables if absent and seed defaults if empty. Idempotent.

    Path resolution: argument > FINALLY_DB_PATH env var > 'db/finally.db'.

    Note: that resolution order governs only the connection this call itself
    opens. Every other function in `app.db.repositories` takes no `db_path`
    parameter and resolves its own connection the same way (env var, else
    default) on each call. So passing an explicit `db_path` here initializes
    that file, but it will not be the file subsequent repository calls use
    unless FINALLY_DB_PATH is also set to it (or it already equals the
    default). Production startup (CONTRACTS.md §7) calls `init_db()` with no
    argument for exactly this reason — FINALLY_DB_PATH is the one knob that
    keeps every call site consistent.
    """
    from app.db import seed  # local import: avoids a module import cycle

    conn = get_connection(db_path)
    try:
        schema_path = Path(__file__).parent / "schema.sql"
        conn.executescript(schema_path.read_text(encoding="utf-8"))
        conn.commit()
        seed.seed_if_empty(conn)
        conn.commit()
    finally:
        conn.close()
