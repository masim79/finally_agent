"""Trade execution, portfolio valuation, and P&L — CONTRACTS.md §3.

This module owns fill-price resolution and the arithmetic that turns raw
rows into the GET /api/portfolio and POST /api/portfolio/trade shapes. The
one write path for cash, positions, and trades is `app.db.repositories.
apply_trade`, which is atomic and self-validating (insufficient cash/shares,
invalid quantity); this module never re-implements that validation, it only
resolves the price apply_trade needs and translates what comes back.

Valuation rules (CONTRACTS.md §3), enforced everywhere a price or a
percentage is computed below:
  - A position whose ticker has no cached price falls back to `avg_cost` as
    `current_price`, so its P&L reads exactly 0 rather than crashing.
  - Every division is guarded: a zero `total_value` or zero cost basis
    (`avg_cost * quantity`) yields 0.0, never an exception or NaN.
"""

from __future__ import annotations

from app.db import repositories as repo
from app.market.cache import PriceCache


class UnknownTickerError(Exception):
    """No cached price exists for a ticker being traded. Maps to UNKNOWN_TICKER."""

    def __init__(self, ticker: str):
        self.ticker = ticker
        super().__init__(f"No price available for {ticker}")


def _resolve_price(cache: PriceCache, ticker: str, avg_cost: float) -> float:
    """Current cached price for a held position, falling back to avg_cost."""
    price = cache.get_price(ticker)
    return price if price is not None else avg_cost


def _position_view(
    ticker: str, quantity: float, avg_cost: float, current_price: float, total_value: float
) -> dict:
    """Build one `positions[]` / `position` entry per CONTRACTS.md §3."""
    market_value = quantity * current_price
    unrealized_pnl = (current_price - avg_cost) * quantity
    cost_basis = avg_cost * quantity
    unrealized_pnl_percent = round((unrealized_pnl / cost_basis) * 100, 4) if cost_basis else 0.0
    weight = round(market_value / total_value, 4) if total_value else 0.0
    return {
        "ticker": ticker,
        "quantity": quantity,
        "avg_cost": round(avg_cost, 2),
        "current_price": round(current_price, 2),
        "market_value": round(market_value, 2),
        "unrealized_pnl": round(unrealized_pnl, 2),
        "unrealized_pnl_percent": unrealized_pnl_percent,
        "weight": weight,
    }


def _positions_value(cache: PriceCache, positions: list) -> float:
    return sum(pos.quantity * _resolve_price(cache, pos.ticker, pos.avg_cost) for pos in positions)


def compute_total_value(cache: PriceCache) -> float:
    """Cash balance plus the current market value of every open position.

    Used by the 30s snapshot background task, which needs only the total.
    """
    cash = repo.get_cash_balance()
    positions = repo.list_positions()
    return cash + _positions_value(cache, positions)


def get_portfolio(cache: PriceCache) -> dict:
    """Assemble the GET /api/portfolio payload. Empty portfolio -> positions: []."""
    cash = repo.get_cash_balance()
    positions = repo.list_positions()
    positions_value = _positions_value(cache, positions)
    total_value = cash + positions_value

    position_views = [
        _position_view(
            pos.ticker,
            pos.quantity,
            pos.avg_cost,
            _resolve_price(cache, pos.ticker, pos.avg_cost),
            total_value,
        )
        for pos in positions
    ]
    total_unrealized_pnl = sum(v["unrealized_pnl"] for v in position_views)
    total_unrealized_pnl_percent = (
        round((total_unrealized_pnl / total_value) * 100, 4) if total_value else 0.0
    )

    return {
        "cash_balance": round(cash, 2),
        "positions": position_views,
        "positions_value": round(positions_value, 2),
        "total_value": round(total_value, 2),
        "total_unrealized_pnl": round(total_unrealized_pnl, 2),
        "total_unrealized_pnl_percent": total_unrealized_pnl_percent,
    }


def execute_trade(cache: PriceCache, ticker: str, side: str, quantity: float) -> dict:
    """Resolve the fill price, delegate the atomic write, then snapshot.

    This is the ONE trade-execution path — the trade bar's POST /api/portfolio/trade
    and the chat orchestration's auto-executed trades both call this, so validation
    and the post-trade snapshot happen in exactly one place.

    Raises:
        UnknownTickerError: the price cache has no price for `ticker`.
        app.db.errors.InsufficientCashError / InsufficientSharesError /
            InvalidQuantityError: from `apply_trade`; callers translate these
            to the CONTRACTS.md §3 error codes.
        ValueError: `side` is neither "buy" nor "sell".
    """
    ticker = ticker.strip().upper()
    price = cache.get_price(ticker)
    if price is None:
        raise UnknownTickerError(ticker)

    trade_row, position_row, new_cash = repo.apply_trade(ticker, side, quantity, price)

    # Snapshot immediately after every successful trade (CONTRACTS.md §3).
    # Re-read positions rather than patch the in-memory view, since apply_trade
    # may have inserted, updated, or deleted the traded position.
    total_value = new_cash + _positions_value(cache, repo.list_positions())
    repo.record_snapshot(round(total_value, 2))

    position_view = None
    if position_row is not None:
        position_view = _position_view(
            position_row.ticker,
            position_row.quantity,
            position_row.avg_cost,
            _resolve_price(cache, position_row.ticker, position_row.avg_cost),
            total_value,
        )

    return {
        "trade": {
            "id": trade_row.id,
            "ticker": trade_row.ticker,
            "side": trade_row.side,
            "quantity": trade_row.quantity,
            "price": trade_row.price,
            "executed_at": trade_row.executed_at,
        },
        "cash_balance": round(new_cash, 2),
        "position": position_view,
    }


def get_history(limit: int = 500) -> list[dict]:
    """GET /api/portfolio/history payload body: oldest-first snapshots."""
    snapshots = repo.list_snapshots(limit=limit)
    return [{"total_value": s.total_value, "recorded_at": s.recorded_at} for s in snapshots]
