"""The FinAlly system prompt and the portfolio/watchlist context builder.

Everything here is pure string work over the CONTRACTS.md §3 REST payloads, so it
is trivially testable and never touches the network or the database. The context
block is written as formatted figures rather than a raw JSON dump: the model reads
dollar amounts and percentages more reliably than it reads nested objects, and it
lets us say "unknown" for a price the cache has not seen yet instead of leaking a
bare ``None``.
"""

from __future__ import annotations

SYSTEM_PROMPT = """You are FinAlly, an AI trading assistant embedded in a simulated \
trading workstation. The user trades a virtual $10,000 portfolio; there is no real money \
at stake, but you behave like a serious, numerate analyst.

What you do:
- Analyse portfolio composition, concentration risk, and unrealised P&L.
- Suggest trades, and always give the reasoning behind them in one or two sentences.
- Execute trades when the user asks for them or agrees to a suggestion you made.
- Manage the watchlist proactively: add tickers you are discussing or recommending, and
  suggest removing ones the user has lost interest in.

How you answer:
- Be concise and data-driven. Lead with the number that matters. No filler, no
  disclaimers about not being a financial advisor, no markdown headings.
- Cite only figures from the CURRENT PORTFOLIO and WATCHLIST blocks below. Never invent
  or estimate a price, a position, a quantity, or a cash balance. If a price is listed as
  unknown, say so and do not trade that ticker.
- If the user asks about something not in the data you were given, say you do not have it.

Trades — read this carefully:
- `quantity` is always a NUMBER OF SHARES, never a dollar amount. "buy 500 AAPL" means
  five hundred shares. "buy $500 of AAPL" means five hundred dollars' worth: divide 500 by
  AAPL's current price yourself, put the resulting share count in `quantity`, and state in
  your message both the share count and the dollar amount so the user can check you.
- Fractional share quantities are allowed. Quantities must be greater than zero.
- `side` is exactly "buy" or "sell". Only propose a sell for a ticker the user actually
  holds, and never for more shares than they hold.
- A buy must be affordable from the cash balance shown below.
- Only put a trade in `trades` when the user has asked for it or agreed to it. If you are
  merely suggesting an idea, describe it in `message` and leave `trades` empty.

Watchlist:
- `action` is exactly "add" or "remove". Do not add a ticker that is already on the
  watchlist, and do not remove one that is not on it.

Always reply with JSON matching the required schema: `message` (your conversational reply
to the user), `trades`, and `watchlist_changes`. Use empty arrays when there is nothing to
do — that is the normal case for a question."""

_UNKNOWN = "unknown"


def _money(value: object) -> str:
    """Format a dollar amount, or say so when the figure is missing."""
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        return _UNKNOWN
    return f"${value:,.2f}"


def _signed_money(value: object) -> str:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        return _UNKNOWN
    return f"{'+' if value >= 0 else '-'}${abs(value):,.2f}"


def _signed_pct(value: object) -> str:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        return _UNKNOWN
    return f"{value:+.2f}%"


def _qty(value: object) -> str:
    """Render a share count without a pointless trailing .0."""
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        return _UNKNOWN
    text = f"{float(value):.4f}".rstrip("0").rstrip(".")
    return text or "0"


def _weight_pct(value: object) -> str:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        return _UNKNOWN
    return f"{value * 100:.1f}%"


def _position_line(position: dict) -> str:
    return (
        f"- {position.get('ticker', _UNKNOWN)}: {_qty(position.get('quantity'))} shares, "
        f"avg cost {_money(position.get('avg_cost'))}, "
        f"current {_money(position.get('current_price'))}, "
        f"market value {_money(position.get('market_value'))}, "
        f"unrealised P&L {_signed_money(position.get('unrealized_pnl'))} "
        f"({_signed_pct(position.get('unrealized_pnl_percent'))}), "
        f"{_weight_pct(position.get('weight'))} of portfolio"
    )


def _watchlist_line(entry: dict) -> str:
    ticker = entry.get("ticker", _UNKNOWN)
    price = entry.get("price")
    if not isinstance(price, (int, float)) or isinstance(price, bool):
        return f"- {ticker}: price unknown (no market tick received yet; do not trade it)"
    direction = entry.get("direction") or "flat"
    return (
        f"- {ticker}: {_money(price)} ({direction}, "
        f"last tick {_signed_money(entry.get('change'))})"
    )


def build_context_block(portfolio: dict, watchlist: list[dict]) -> str:
    """Render the §3 portfolio payload and watchlist entries as readable figures."""
    portfolio = portfolio or {}
    positions = portfolio.get("positions") or []

    lines = [
        "CURRENT PORTFOLIO",
        f"Cash balance: {_money(portfolio.get('cash_balance'))}",
        f"Positions market value: {_money(portfolio.get('positions_value'))}",
        f"Total portfolio value: {_money(portfolio.get('total_value'))}",
        (
            "Total unrealised P&L: "
            f"{_signed_money(portfolio.get('total_unrealized_pnl'))} "
            f"({_signed_pct(portfolio.get('total_unrealized_pnl_percent'))})"
        ),
        "",
    ]

    if positions:
        lines.append(f"POSITIONS ({len(positions)})")
        lines.extend(_position_line(p) for p in positions)
    else:
        lines.append("POSITIONS (0)")
        lines.append("- none; the portfolio is entirely in cash")
    lines.append("")

    entries = watchlist or []
    lines.append(f"WATCHLIST ({len(entries)})")
    if entries:
        lines.extend(_watchlist_line(e) for e in entries)
    else:
        lines.append("- empty")

    return "\n".join(lines)


def build_messages(
    user_message: str,
    portfolio: dict,
    watchlist: list[dict],
    history: list[dict],
) -> list[dict]:
    """Assemble the full chat payload: system prompt + live context + history + the ask.

    The context block is its own system message placed after the standing instructions
    so that it stays adjacent to the conversation it describes, and so a long history
    cannot push the live figures out of the model's attention.
    """
    messages: list[dict] = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "system", "content": build_context_block(portfolio, watchlist)},
    ]

    for entry in history or []:
        if not isinstance(entry, dict):
            continue
        role = entry.get("role")
        content = entry.get("content")
        if role in ("user", "assistant") and isinstance(content, str) and content:
            messages.append({"role": role, "content": content})

    messages.append({"role": "user", "content": user_message})
    return messages
