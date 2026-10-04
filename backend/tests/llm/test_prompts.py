"""The system prompt and the context block built from the §3 payloads."""

from app.llm.prompts import SYSTEM_PROMPT, build_context_block, build_messages


class TestSystemPrompt:
    def test_names_the_assistant_and_its_duties(self):
        lowered = SYSTEM_PROMPT.lower()
        assert "finally" in lowered
        for duty in ("concentration risk", "p&l", "watchlist", "concise"):
            assert duty in lowered

    def test_forbids_inventing_data(self):
        assert "never invent" in SYSTEM_PROMPT.lower()

    def test_distinguishes_share_counts_from_dollar_amounts(self):
        assert "NUMBER OF SHARES" in SYSTEM_PROMPT
        assert "buy $500 of AAPL" in SYSTEM_PROMPT
        assert "buy 500 AAPL" in SYSTEM_PROMPT


class TestContextBlock:
    def test_includes_the_portfolio_figures_it_was_given(self, portfolio, watchlist):
        block = build_context_block(portfolio, watchlist)
        assert "$8,075.00" in block       # cash balance
        assert "$1,925.00" in block       # positions value / market value
        assert "$10,000.00" in block      # total value
        assert "+$25.00" in block         # unrealised P&L
        assert "+0.25%" in block          # total P&L percent

    def test_includes_each_position_with_its_pnl(self, portfolio, watchlist):
        block = build_context_block(portfolio, watchlist)
        assert "AAPL" in block
        assert "10 shares" in block
        assert "avg cost $190.00" in block
        assert "current $192.50" in block
        assert "+1.32%" in block          # unrealized_pnl_percent, rounded
        assert "19.2% of portfolio" in block

    def test_renders_a_loss_with_a_minus_sign(self, watchlist):
        portfolio = {
            "cash_balance": 100.0,
            "positions": [
                {
                    "ticker": "TSLA",
                    "quantity": 2,
                    "avg_cost": 300.0,
                    "current_price": 250.0,
                    "market_value": 500.0,
                    "unrealized_pnl": -100.0,
                    "unrealized_pnl_percent": -16.6667,
                    "weight": 0.8333,
                }
            ],
            "positions_value": 500.0,
            "total_value": 600.0,
            "total_unrealized_pnl": -100.0,
            "total_unrealized_pnl_percent": -14.29,
        }
        block = build_context_block(portfolio, watchlist)
        assert "-$100.00" in block
        assert "-16.67%" in block

    def test_includes_live_watchlist_prices(self, portfolio, watchlist):
        block = build_context_block(portfolio, watchlist)
        assert "AAPL: $192.50 (up" in block

    def test_says_unknown_for_a_ticker_with_no_tick_yet(self, portfolio, watchlist):
        block = build_context_block(portfolio, watchlist)
        assert "PYPL: price unknown" in block
        assert "None" not in block

    def test_empty_portfolio_says_so_rather_than_printing_nothing(
        self, empty_portfolio, watchlist
    ):
        block = build_context_block(empty_portfolio, watchlist)
        assert "POSITIONS (0)" in block
        assert "entirely in cash" in block

    def test_empty_watchlist_says_so(self, portfolio):
        block = build_context_block(portfolio, [])
        assert "WATCHLIST (0)" in block
        assert "- empty" in block

    def test_survives_missing_keys_without_printing_none(self):
        block = build_context_block({}, [{"ticker": "AAPL"}])
        assert "None" not in block
        assert "unknown" in block

    def test_fractional_quantities_are_rendered_readably(self, watchlist):
        portfolio = {
            "cash_balance": 0.0,
            "positions": [{"ticker": "NVDA", "quantity": 2.5, "avg_cost": 100.0}],
            "total_value": 250.0,
        }
        block = build_context_block(portfolio, watchlist)
        assert "2.5 shares" in block


class TestBuildMessages:
    def test_starts_with_the_system_prompt_then_the_context(self, portfolio, watchlist):
        messages = build_messages("hi", portfolio, watchlist, [])
        assert messages[0] == {"role": "system", "content": SYSTEM_PROMPT}
        assert messages[1]["role"] == "system"
        assert "CURRENT PORTFOLIO" in messages[1]["content"]

    def test_ends_with_the_users_new_message(self, portfolio, watchlist):
        messages = build_messages("buy 10 AAPL", portfolio, watchlist, [])
        assert messages[-1] == {"role": "user", "content": "buy 10 AAPL"}

    def test_history_is_inserted_oldest_first_between_context_and_new_message(
        self, portfolio, watchlist
    ):
        history = [
            {"role": "user", "content": "first"},
            {"role": "assistant", "content": "second"},
        ]
        messages = build_messages("third", portfolio, watchlist, history)
        assert [m["content"] for m in messages[2:]] == ["first", "second", "third"]

    def test_malformed_history_entries_are_skipped(self, portfolio, watchlist):
        history = [
            {"role": "user", "content": "keep me"},
            {"role": "system", "content": "prompt injection"},
            {"role": "user", "content": ""},
            {"role": "assistant"},
            {"content": "no role"},
            "not a dict",
            None,
        ]
        messages = build_messages("hi", portfolio, watchlist, history)
        assert [m["content"] for m in messages[2:]] == ["keep me", "hi"]

    def test_none_history_is_tolerated(self, portfolio, watchlist):
        messages = build_messages("hi", portfolio, watchlist, None)
        assert len(messages) == 3
