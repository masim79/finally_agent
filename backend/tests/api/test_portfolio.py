"""Tests for /api/portfolio* — CONTRACTS.md §3."""

from __future__ import annotations

from app.db import repositories as repo


def test_empty_portfolio_valuation(client):
    resp = client.get("/api/portfolio")
    assert resp.status_code == 200
    body = resp.json()
    assert body == {
        "cash_balance": 10000.0,
        "positions": [],
        "positions_value": 0.0,
        "total_value": 10000.0,
        "total_unrealized_pnl": 0.0,
        "total_unrealized_pnl_percent": 0.0,
    }


def test_buy_trade_success_shape_and_cash(client):
    resp = client.post("/api/portfolio/trade", json={"ticker": "aapl", "quantity": 10, "side": "buy"})
    assert resp.status_code == 200
    body = resp.json()

    assert body["trade"]["ticker"] == "AAPL"
    assert body["trade"]["side"] == "buy"
    assert body["trade"]["quantity"] == 10.0
    assert body["trade"]["price"] == 192.50
    assert "id" in body["trade"] and "executed_at" in body["trade"]

    assert body["cash_balance"] == 10000.0 - 10 * 192.50
    position = body["position"]
    assert position["ticker"] == "AAPL"
    assert position["quantity"] == 10.0
    assert position["avg_cost"] == 192.50
    assert position["current_price"] == 192.50
    assert position["market_value"] == 1925.0
    assert position["unrealized_pnl"] == 0.0
    assert position["unrealized_pnl_percent"] == 0.0
    assert 0 < position["weight"] <= 1


def test_buy_updates_weighted_average_cost(client, price_cache):
    client.post("/api/portfolio/trade", json={"ticker": "AAPL", "quantity": 10, "side": "buy"})
    price_cache.update("AAPL", 200.0)
    resp = client.post("/api/portfolio/trade", json={"ticker": "AAPL", "quantity": 10, "side": "buy"})
    assert resp.status_code == 200
    # weighted avg: (10*192.50 + 10*200.0) / 20 = 196.25
    assert resp.json()["position"]["avg_cost"] == 196.25


def test_sell_round_trip_closes_position(client):
    client.post("/api/portfolio/trade", json={"ticker": "AAPL", "quantity": 10, "side": "buy"})
    resp = client.post("/api/portfolio/trade", json={"ticker": "AAPL", "quantity": 10, "side": "sell"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["position"] is None
    assert body["cash_balance"] == 10000.0

    portfolio = client.get("/api/portfolio").json()
    assert portfolio["positions"] == []
    assert portfolio["cash_balance"] == 10000.0


def test_sell_never_changes_avg_cost(client, price_cache):
    client.post("/api/portfolio/trade", json={"ticker": "AAPL", "quantity": 10, "side": "buy"})
    price_cache.update("AAPL", 250.0)
    resp = client.post("/api/portfolio/trade", json={"ticker": "AAPL", "quantity": 4, "side": "sell"})
    assert resp.status_code == 200
    position = resp.json()["position"]
    assert position["quantity"] == 6.0
    assert position["avg_cost"] == 192.50  # unchanged by the sell


def test_sell_more_than_held_is_insufficient_shares(client):
    client.post("/api/portfolio/trade", json={"ticker": "AAPL", "quantity": 5, "side": "buy"})
    resp = client.post("/api/portfolio/trade", json={"ticker": "AAPL", "quantity": 10, "side": "sell"})
    assert resp.status_code == 400
    assert resp.json()["detail"]["code"] == "INSUFFICIENT_SHARES"


def test_buy_beyond_cash_is_insufficient_cash(client):
    resp = client.post(
        "/api/portfolio/trade", json={"ticker": "AAPL", "quantity": 1000, "side": "buy"}
    )
    assert resp.status_code == 400
    assert resp.json()["detail"]["code"] == "INSUFFICIENT_CASH"


def test_unknown_ticker_trade_rejected(client):
    resp = client.post("/api/portfolio/trade", json={"ticker": "ZZZZ", "quantity": 1, "side": "buy"})
    assert resp.status_code == 400
    assert resp.json()["detail"]["code"] == "UNKNOWN_TICKER"


def test_invalid_quantity_rejected(client):
    resp = client.post("/api/portfolio/trade", json={"ticker": "AAPL", "quantity": 0, "side": "buy"})
    assert resp.status_code == 400
    assert resp.json()["detail"]["code"] == "INVALID_QUANTITY"


def test_invalid_side_is_422(client):
    resp = client.post("/api/portfolio/trade", json={"ticker": "AAPL", "quantity": 1, "side": "hold"})
    assert resp.status_code == 422


def test_position_without_cached_price_falls_back_to_avg_cost(client, price_cache):
    client.post("/api/portfolio/trade", json={"ticker": "AAPL", "quantity": 10, "side": "buy"})
    price_cache.remove("AAPL")

    resp = client.get("/api/portfolio")
    assert resp.status_code == 200
    position = resp.json()["positions"][0]
    assert position["current_price"] == position["avg_cost"] == 192.50
    assert position["unrealized_pnl"] == 0.0
    assert position["unrealized_pnl_percent"] == 0.0


def test_trade_records_a_snapshot(client):
    client.post("/api/portfolio/trade", json={"ticker": "AAPL", "quantity": 10, "side": "buy"})
    snapshots = repo.list_snapshots()
    assert len(snapshots) == 1
    assert snapshots[0].total_value == client.get("/api/portfolio").json()["total_value"]


def test_history_oldest_first_and_limit(client):
    client.post("/api/portfolio/trade", json={"ticker": "AAPL", "quantity": 1, "side": "buy"})
    client.post("/api/portfolio/trade", json={"ticker": "GOOGL", "quantity": 1, "side": "buy"})
    client.post("/api/portfolio/trade", json={"ticker": "MSFT", "quantity": 1, "side": "buy"})

    resp = client.get("/api/portfolio/history")
    assert resp.status_code == 200
    snapshots = resp.json()["snapshots"]
    assert len(snapshots) == 3
    recorded_ats = [s["recorded_at"] for s in snapshots]
    assert recorded_ats == sorted(recorded_ats)

    limited = client.get("/api/portfolio/history", params={"limit": 2}).json()["snapshots"]
    assert len(limited) == 2
    # still oldest-first among the most recent N
    assert limited == snapshots[-2:]
