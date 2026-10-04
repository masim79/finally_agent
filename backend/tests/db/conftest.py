"""Fixtures for the database layer test suite.

Every test gets its own SQLite file under pytest's tmp_path, pointed to via
FINALLY_DB_PATH. Because every app.db.repositories function resolves its
connection through that env var on each call (see app.db.connection), setting
it once per test is enough to keep the whole repository API isolated and
consistent for the duration of the test.
"""

from __future__ import annotations

import pytest

from app.db import repositories as repo


@pytest.fixture
def db_path(tmp_path, monkeypatch):
    """Point FINALLY_DB_PATH at a fresh per-test file. Does not initialize it."""
    path = tmp_path / "finally.db"
    monkeypatch.setenv("FINALLY_DB_PATH", str(path))
    return str(path)


@pytest.fixture
def initialized_db(db_path):
    """A freshly created and seeded database."""
    repo.init_db()
    return db_path
