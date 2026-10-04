"""Fixtures for services-layer unit tests — no HTTP, direct function calls.

Mirrors tests/db/conftest.py's pattern: FINALLY_DB_PATH points at a fresh
per-test file, and every app.db.repositories call resolves its connection
through that env var, so setting it once per test isolates the whole
repository API for the duration of the test.
"""

from __future__ import annotations

import pytest

from app.db import repositories as repo
from app.market.cache import PriceCache


@pytest.fixture
def db_path(tmp_path, monkeypatch):
    path = tmp_path / "finally.db"
    monkeypatch.setenv("FINALLY_DB_PATH", str(path))
    return str(path)


@pytest.fixture
def initialized_db(db_path):
    repo.init_db()
    return db_path


@pytest.fixture
def price_cache(initialized_db) -> PriceCache:
    return PriceCache()
