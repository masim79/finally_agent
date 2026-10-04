"""Tests for /api/watchlist* — CONTRACTS.md §3."""

from __future__ import annotations

from app.db.seed import DEFAULT_TICKERS


def test_get_watchlist_default_tickers_ordered_with_known_prices(client):
    resp = client.get("/api/watchlist")
    assert resp.status_code == 200
    entries = resp.json()["tickers"]
    assert [e["ticker"] for e in entries] == DEFAULT_TICKERS  # added_at ASC == seed order

    aapl = next(e for e in entries if e["ticker"] == "AAPL")
    assert aapl["price"] == 192.50
    assert aapl["direction"] == "flat"  # first update for the ticker

    unpriced = next(e for e in entries if e["ticker"] == "JPM")
    assert unpriced["price"] is None
    assert unpriced["previous_price"] is None
    assert unpriced["change"] is None
    assert unpriced["direction"] is None


def test_add_ticker_success_notifies_market_source(client, market_source):
    resp = client.post("/api/watchlist", json={"ticker": "pypl"})
    assert resp.status_code == 201
    body = resp.json()
    assert body["ticker"] == "PYPL"
    assert body["price"] is None
    assert "PYPL" in market_source.added

    tickers = [e["ticker"] for e in client.get("/api/watchlist").json()["tickers"]]
    assert "PYPL" in tickers


def test_add_duplicate_ticker_is_409(client):
    resp = client.post("/api/watchlist", json={"ticker": "AAPL"})
    assert resp.status_code == 409
    assert resp.json()["detail"]["code"] == "DUPLICATE_TICKER"


def test_remove_ticker_success_notifies_market_source(client, market_source):
    resp = client.delete("/api/watchlist/AAPL")
    assert resp.status_code == 204
    assert resp.content == b""
    assert "AAPL" in market_source.removed

    tickers = [e["ticker"] for e in client.get("/api/watchlist").json()["tickers"]]
    assert "AAPL" not in tickers


def test_remove_unknown_ticker_is_404(client):
    resp = client.delete("/api/watchlist/ZZZZ")
    assert resp.status_code == 404
    assert resp.json()["detail"]["code"] == "TICKER_NOT_IN_WATCHLIST"


def test_removing_ticker_does_not_touch_open_position(client):
    client.post("/api/portfolio/trade", json={"ticker": "AAPL", "quantity": 5, "side": "buy"})
    resp = client.delete("/api/watchlist/AAPL")
    assert resp.status_code == 204

    watchlist_tickers = [e["ticker"] for e in client.get("/api/watchlist").json()["tickers"]]
    assert "AAPL" not in watchlist_tickers

    positions = client.get("/api/portfolio").json()["positions"]
    assert any(p["ticker"] == "AAPL" and p["quantity"] == 5.0 for p in positions)
