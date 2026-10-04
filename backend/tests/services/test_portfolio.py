"""Unit tests for app.services.portfolio — valuation and trade execution."""

from __future__ import annotations

import pytest

from app.db import repositories as repo
from app.db.errors import InsufficientCashError, InsufficientSharesError, InvalidQuantityError
from app.services import portfolio as svc


def test_get_portfolio_empty(price_cache):
    result = svc.get_portfolio(price_cache)
    assert result == {
        "cash_balance": 10000.0,
        "positions": [],
        "positions_value": 0.0,
        "total_value": 10000.0,
        "total_unrealized_pnl": 0.0,
        "total_unrealized_pnl_percent": 0.0,
    }


def test_get_portfolio_with_cached_price(price_cache):
    price_cache.update("AAPL", 192.50)
    repo.upsert_position("AAPL", quantity=10.0, avg_cost=190.0)

    result = svc.get_portfolio(price_cache)
    assert result["cash_balance"] == 10000.0
    assert len(result["positions"]) == 1
    pos = result["positions"][0]
    assert pos["current_price"] == 192.50
    assert pos["market_value"] == 1925.0
    assert pos["unrealized_pnl"] == 25.0
    assert pos["unrealized_pnl_percent"] == round(25.0 / 1900.0 * 100, 4)
    assert result["positions_value"] == 1925.0
    assert result["total_value"] == 10000.0 + 1925.0
    assert result["total_unrealized_pnl"] == 25.0


def test_get_portfolio_falls_back_to_avg_cost_when_uncached(price_cache):
    repo.upsert_position("GOOGL", quantity=5.0, avg_cost=100.0)
    result = svc.get_portfolio(price_cache)
    pos = result["positions"][0]
    assert pos["current_price"] == 100.0
    assert pos["unrealized_pnl"] == 0.0
    assert pos["unrealized_pnl_percent"] == 0.0


def test_get_portfolio_zero_avg_cost_never_divides_by_zero(price_cache):
    repo.upsert_position("FREE", quantity=5.0, avg_cost=0.0)
    result = svc.get_portfolio(price_cache)
    pos = result["positions"][0]
    assert pos["unrealized_pnl_percent"] == 0.0  # guarded, not NaN/inf


def test_execute_trade_buy_creates_position(price_cache):
    price_cache.update("AAPL", 192.50)
    result = svc.execute_trade(price_cache, "aapl", "buy", 10)

    assert result["trade"]["ticker"] == "AAPL"
    assert result["trade"]["price"] == 192.50
    assert result["cash_balance"] == 10000.0 - 1925.0
    assert result["position"]["quantity"] == 10.0
    assert result["position"]["avg_cost"] == 192.50


def test_execute_trade_weighted_average_on_second_buy(price_cache):
    price_cache.update("AAPL", 190.0)
    svc.execute_trade(price_cache, "AAPL", "buy", 10)
    price_cache.update("AAPL", 200.0)
    result = svc.execute_trade(price_cache, "AAPL", "buy", 10)
    assert result["position"]["avg_cost"] == 195.0


def test_execute_trade_sell_never_changes_avg_cost_and_closes_at_zero(price_cache):
    price_cache.update("AAPL", 190.0)
    svc.execute_trade(price_cache, "AAPL", "buy", 10)
    price_cache.update("AAPL", 250.0)

    partial = svc.execute_trade(price_cache, "AAPL", "sell", 4)
    assert partial["position"]["avg_cost"] == 190.0
    assert partial["position"]["quantity"] == 6.0

    full = svc.execute_trade(price_cache, "AAPL", "sell", 6)
    assert full["position"] is None


def test_execute_trade_sell_more_than_held_raises(price_cache):
    price_cache.update("AAPL", 190.0)
    svc.execute_trade(price_cache, "AAPL", "buy", 5)
    with pytest.raises(InsufficientSharesError):
        svc.execute_trade(price_cache, "AAPL", "sell", 10)


def test_execute_trade_buy_beyond_cash_raises(price_cache):
    price_cache.update("AAPL", 190.0)
    with pytest.raises(InsufficientCashError):
        svc.execute_trade(price_cache, "AAPL", "buy", 1000)


def test_execute_trade_invalid_quantity_raises(price_cache):
    price_cache.update("AAPL", 190.0)
    with pytest.raises(InvalidQuantityError):
        svc.execute_trade(price_cache, "AAPL", "buy", 0)


def test_execute_trade_unknown_ticker_raises(price_cache):
    with pytest.raises(svc.UnknownTickerError):
        svc.execute_trade(price_cache, "ZZZZ", "buy", 1)


def test_execute_trade_writes_snapshot_immediately(price_cache):
    price_cache.update("AAPL", 190.0)
    svc.execute_trade(price_cache, "AAPL", "buy", 10)
    snapshots = repo.list_snapshots()
    assert len(snapshots) == 1
    assert snapshots[0].total_value == 10000.0


def test_compute_total_value_matches_portfolio_total(price_cache):
    price_cache.update("AAPL", 190.0)
    svc.execute_trade(price_cache, "AAPL", "buy", 10)
    assert svc.compute_total_value(price_cache) == svc.get_portfolio(price_cache)["total_value"]


def test_get_history_oldest_first_and_limit(price_cache):
    price_cache.update("AAPL", 190.0)
    for _ in range(3):
        svc.execute_trade(price_cache, "AAPL", "buy", 1)

    history = svc.get_history()
    assert len(history) == 3
    assert [s["recorded_at"] for s in history] == sorted(s["recorded_at"] for s in history)

    limited = svc.get_history(limit=2)
    assert len(limited) == 2
    assert limited == history[-2:]
