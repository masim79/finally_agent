"""Tests for GET /api/health."""

from __future__ import annotations


def test_health_reports_ok_and_tracked_tickers(client, market_source):
    resp = client.get("/api/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["market_source"] == "simulator"
    assert body["db"] == "ok"
    assert isinstance(body["tracked_tickers"], int)
    assert body["tracked_tickers"] == len(market_source.get_tickers())


def test_health_does_not_crash_without_db_initialized(app, client, monkeypatch):
    """The Docker healthcheck must succeed even if the DB layer errors."""

    def _boom(*args, **kwargs):
        raise RuntimeError("db not ready")

    monkeypatch.setattr("app.db.repositories.get_cash_balance", _boom)
    resp = client.get("/api/health")
    assert resp.status_code == 200
    assert resp.json()["db"] == "error"
