"""Fixtures shared by the LLM tests.

Every test in this package runs with the network unavailable by construction: the
provider call is always monkeypatched, and `no_llm_env` clears both LLM_MOCK and
OPENROUTER_API_KEY so a stray value in the developer's shell cannot change a result.
"""

import pytest


@pytest.fixture(autouse=True)
def no_llm_env(monkeypatch):
    """Start every test from a clean, keyless, non-mock environment."""
    monkeypatch.delenv("LLM_MOCK", raising=False)
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)


@pytest.fixture
def portfolio():
    """The CONTRACTS.md §3 GET /api/portfolio payload, with one position."""
    return {
        "cash_balance": 8075.00,
        "positions": [
            {
                "ticker": "AAPL",
                "quantity": 10.0,
                "avg_cost": 190.00,
                "current_price": 192.50,
                "market_value": 1925.00,
                "unrealized_pnl": 25.00,
                "unrealized_pnl_percent": 1.3158,
                "weight": 0.1924,
            }
        ],
        "positions_value": 1925.00,
        "total_value": 10000.00,
        "total_unrealized_pnl": 25.00,
        "total_unrealized_pnl_percent": 0.25,
    }


@pytest.fixture
def empty_portfolio():
    return {
        "cash_balance": 10000.0,
        "positions": [],
        "positions_value": 0.0,
        "total_value": 10000.0,
        "total_unrealized_pnl": 0.0,
        "total_unrealized_pnl_percent": 0.0,
    }


@pytest.fixture
def watchlist():
    """GET /api/watchlist's "tickers" — one priced, one awaiting its first tick."""
    return [
        {
            "ticker": "AAPL",
            "added_at": "2026-10-01T14:00:00.000Z",
            "price": 192.50,
            "previous_price": 192.48,
            "change": 0.02,
            "change_percent": 0.0104,
            "direction": "up",
        },
        {
            "ticker": "PYPL",
            "added_at": "2026-10-01T14:05:00.000Z",
            "price": None,
            "previous_price": None,
            "change": None,
            "change_percent": None,
            "direction": None,
        },
    ]
