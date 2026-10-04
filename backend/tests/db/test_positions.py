"""Standalone position primitives: upsert_position, delete_position, get/list."""

from __future__ import annotations

from app.db import repositories as repo


def test_upsert_position_inserts_when_absent(initialized_db):
    position = repo.upsert_position("AAPL", 5.0, 100.0)

    assert position.ticker == "AAPL"
    assert position.quantity == 5.0
    assert position.avg_cost == 100.0
    assert repo.get_position("AAPL") == position


def test_upsert_position_updates_when_present(initialized_db):
    repo.upsert_position("AAPL", 5.0, 100.0)

    updated = repo.upsert_position("AAPL", 8.0, 120.0)

    assert updated.quantity == 8.0
    assert updated.avg_cost == 120.0
    assert len(repo.list_positions()) == 1  # updated in place, not duplicated


def test_delete_position_removes_it(initialized_db):
    repo.upsert_position("AAPL", 5.0, 100.0)

    repo.delete_position("AAPL")

    assert repo.get_position("AAPL") is None


def test_delete_missing_position_is_a_noop(initialized_db):
    repo.delete_position("NOPE")  # must not raise

    assert repo.get_position("NOPE") is None


def test_get_position_returns_none_when_absent(initialized_db):
    assert repo.get_position("AAPL") is None


def test_list_positions_scoped_per_user(initialized_db):
    repo.upsert_position("AAPL", 1.0, 100.0, user_id="alice")

    assert repo.list_positions() == []
    assert len(repo.list_positions(user_id="alice")) == 1
