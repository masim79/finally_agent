"""Tests for POST /api/chat and GET /api/chat/history — CONTRACTS.md §3.

`LLM_MOCK=true` is set by the `db_path` fixture (tests/api/conftest.py), so
these exercise the real `app.llm.service.generate_chat_response` in its
deterministic mock mode (CONTRACTS.md §5's keyword table) — not a stub —
giving genuine end-to-end coverage of the chat orchestration. The one
exception is the LLM_ERROR case, which monkeypatches `app.api.chat._call_llm`
directly, since mock mode by design never raises.
"""

from __future__ import annotations

import pytest


def test_chat_analysis_message_has_no_actions(client):
    resp = client.post("/api/chat", json={"message": "how am I doing?"})
    assert resp.status_code == 200
    body = resp.json()
    assert "10,000.00" in body["message"]
    assert body["actions"]["trades"] == []
    assert body["actions"]["watchlist_changes"] == []
    assert "id" in body and "created_at" in body


def test_chat_executes_a_buy_trade(client):
    resp = client.post("/api/chat", json={"message": "buy 10 aapl shares"})
    assert resp.status_code == 200
    body = resp.json()
    trades = body["actions"]["trades"]
    assert len(trades) == 1
    assert trades[0] == {
        "ticker": "AAPL", "side": "buy", "quantity": 10.0,
        "status": "executed", "price": 192.50, "error": None,
    }

    portfolio = client.get("/api/portfolio").json()
    assert portfolio["cash_balance"] == 10000.0 - 10 * 192.50


def test_chat_trade_failure_is_inline_not_http_error(client):
    """A trade that fails validation mid-conversation: 200 with status=failed."""
    first = client.post("/api/chat", json={"message": "buy 57 googl shares"})
    assert first.status_code == 200
    assert first.json()["actions"]["trades"][0]["status"] == "executed"

    # Remaining cash is 10000 - 57*175 = 25.00; AAPL at 192.50 can't be afforded.
    second = client.post("/api/chat", json={"message": "buy 1 aapl shares"})
    assert second.status_code == 200
    trade = second.json()["actions"]["trades"][0]
    assert trade["status"] == "failed"
    assert trade["price"] is None
    assert "INSUFFICIENT_CASH" in trade["error"] or "Need $" in trade["error"]
    assert second.json()["message"]  # assistant still produced a response


def test_chat_executes_watchlist_add(client, market_source):
    resp = client.post("/api/chat", json={"message": "add pypl to my watchlist"})
    assert resp.status_code == 200
    changes = resp.json()["actions"]["watchlist_changes"]
    assert changes == [{"ticker": "PYPL", "action": "add", "status": "executed", "error": None}]
    assert "PYPL" in market_source.added


def test_chat_watchlist_add_failure_is_inline(client):
    """AAPL is already on the default watchlist -> DUPLICATE_TICKER, inline."""
    resp = client.post("/api/chat", json={"message": "add aapl to my watchlist"})
    assert resp.status_code == 200
    change = resp.json()["actions"]["watchlist_changes"][0]
    assert change["status"] == "failed"
    assert change["error"]


def test_chat_executes_watchlist_remove(client, market_source):
    resp = client.post("/api/chat", json={"message": "remove jpm from my watchlist"})
    assert resp.status_code == 200
    changes = resp.json()["actions"]["watchlist_changes"]
    assert changes == [{"ticker": "JPM", "action": "remove", "status": "executed", "error": None}]
    assert "JPM" in market_source.removed


def test_chat_llm_error_is_502(client, monkeypatch):
    async def _boom(*args, **kwargs):
        raise RuntimeError("provider unreachable")

    monkeypatch.setattr("app.api.chat._call_llm", _boom)
    resp = client.post("/api/chat", json={"message": "hello"})
    assert resp.status_code == 502
    assert resp.json()["detail"]["code"] == "LLM_ERROR"


def test_chat_persists_user_and_assistant_messages(client):
    client.post("/api/chat", json={"message": "buy 1 aapl shares"})

    resp = client.get("/api/chat/history")
    assert resp.status_code == 200
    messages = resp.json()["messages"]
    assert len(messages) == 2

    user_msg, assistant_msg = messages
    assert user_msg["role"] == "user"
    assert user_msg["content"] == "buy 1 aapl shares"
    assert user_msg["actions"] is None

    assert assistant_msg["role"] == "assistant"
    assert assistant_msg["actions"]["trades"][0]["status"] == "executed"

    # oldest first
    assert user_msg["created_at"] <= assistant_msg["created_at"]


@pytest.fixture(autouse=True)
def _llm_mock_env(monkeypatch):
    """Belt-and-braces: ensure LLM_MOCK=true even if a test's fixture order changes."""
    monkeypatch.setenv("LLM_MOCK", "true")
