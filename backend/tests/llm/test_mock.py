"""Every row of the CONTRACTS.md §5 mock table, plus determinism and env handling.

The E2E suite asserts against these behaviours, so they are a contract.
"""

import pytest

from app.llm.mock import is_mock_enabled, mock_chat_response


class TestMockEnvFlag:
    def test_absent_variable_is_off(self):
        assert is_mock_enabled() is False

    @pytest.mark.parametrize("value", ["true", "TRUE", "True", "1", "yes", "on", " true "])
    def test_truthy_values_enable_mock(self, monkeypatch, value):
        monkeypatch.setenv("LLM_MOCK", value)
        assert is_mock_enabled() is True

    @pytest.mark.parametrize("value", ["false", "0", "no", "", "off", "maybe"])
    def test_everything_else_is_off(self, monkeypatch, value):
        monkeypatch.setenv("LLM_MOCK", value)
        assert is_mock_enabled() is False

    def test_is_read_at_call_time_not_import_time(self, monkeypatch):
        assert is_mock_enabled() is False
        monkeypatch.setenv("LLM_MOCK", "true")
        assert is_mock_enabled() is True
        monkeypatch.delenv("LLM_MOCK")
        assert is_mock_enabled() is False


class TestBuyRow:
    """buy + a ticker + a number -> that buy in trades, message naming both."""

    @pytest.mark.parametrize(
        "message,ticker,quantity",
        [
            ("buy 10 AAPL", "AAPL", 10.0),
            ("Buy 10 AAPL shares please", "AAPL", 10.0),
            ("I want to buy 2.5 NVDA", "NVDA", 2.5),
            ("buy 7 msft", "MSFT", 7.0),
            ("buying 3 TSLA now", "TSLA", 3.0),
        ],
    )
    def test_returns_the_buy(self, message, ticker, quantity, portfolio, watchlist):
        result = mock_chat_response(message, portfolio, watchlist)
        assert len(result.trades) == 1
        trade = result.trades[0]
        assert (trade.ticker, trade.side, trade.quantity) == (ticker, "buy", quantity)
        assert result.watchlist_changes == []

    def test_message_names_the_ticker_and_quantity(self, portfolio, watchlist):
        result = mock_chat_response("buy 10 AAPL", portfolio, watchlist)
        assert "AAPL" in result.message
        assert "10" in result.message
        assert "10.0" not in result.message


class TestSellRow:
    @pytest.mark.parametrize(
        "message,ticker,quantity",
        [
            ("sell 5 AAPL", "AAPL", 5.0),
            ("Sell 1.5 of my GOOGL", "GOOGL", 1.5),
            ("sell 20 nflx", "NFLX", 20.0),
        ],
    )
    def test_returns_the_sell(self, message, ticker, quantity, portfolio, watchlist):
        result = mock_chat_response(message, portfolio, watchlist)
        assert len(result.trades) == 1
        trade = result.trades[0]
        assert (trade.ticker, trade.side, trade.quantity) == (ticker, "sell", quantity)

    def test_message_names_the_ticker_and_quantity(self, portfolio, watchlist):
        result = mock_chat_response("sell 5 AAPL", portfolio, watchlist)
        assert "AAPL" in result.message and "5" in result.message


class TestAddRow:
    @pytest.mark.parametrize(
        "message,ticker",
        [
            ("add PYPL", "PYPL"),
            ("Add SHOP to my watchlist", "SHOP"),
            ("please add pypl", "PYPL"),
        ],
    )
    def test_returns_the_add(self, message, ticker, portfolio, watchlist):
        result = mock_chat_response(message, portfolio, watchlist)
        assert len(result.watchlist_changes) == 1
        change = result.watchlist_changes[0]
        assert (change.ticker, change.action) == (ticker, "add")
        assert result.trades == []
        assert ticker in result.message


class TestRemoveRow:
    @pytest.mark.parametrize(
        "message,ticker",
        [
            ("remove PYPL", "PYPL"),
            ("Remove TSLA from the watchlist", "TSLA"),
            ("remove nflx", "NFLX"),
        ],
    )
    def test_returns_the_remove(self, message, ticker, portfolio, watchlist):
        result = mock_chat_response(message, portfolio, watchlist)
        assert len(result.watchlist_changes) == 1
        change = result.watchlist_changes[0]
        assert (change.ticker, change.action) == (ticker, "remove")
        assert result.trades == []
        assert ticker in result.message


class TestFallbackRow:
    """anything else -> a fixed analysis string citing total_value, no actions."""

    @pytest.mark.parametrize(
        "message",
        [
            "How is my portfolio doing?",
            "What should I do?",
            "hello",
            "",
            "buy something",          # buy, but no ticker and no number
            "sell AAPL",              # sell with a ticker but no number
            "buy 10",                 # buy with a number but no ticker
        ],
    )
    def test_returns_analysis_with_no_actions(self, message, portfolio, watchlist):
        result = mock_chat_response(message, portfolio, watchlist)
        assert result.trades == []
        assert result.watchlist_changes == []
        assert "$10,000.00" in result.message

    def test_cites_the_total_value_it_was_given(self, empty_portfolio, watchlist):
        empty_portfolio["total_value"] = 12345.67
        result = mock_chat_response("hi", empty_portfolio, watchlist)
        assert "$12,345.67" in result.message

    def test_tolerates_a_portfolio_with_no_total_value(self, watchlist):
        result = mock_chat_response("hi", {}, watchlist)
        assert "$0.00" in result.message


class TestDeterminismAndPrecedence:
    def test_same_input_gives_the_same_output(self, portfolio, watchlist):
        first = mock_chat_response("buy 10 AAPL", portfolio, watchlist)
        second = mock_chat_response("buy 10 AAPL", portfolio, watchlist)
        assert first == second

    def test_buy_wins_over_add_when_both_words_appear(self, portfolio, watchlist):
        result = mock_chat_response("buy 10 AAPL and add it", portfolio, watchlist)
        assert result.trades[0].side == "buy"
        assert result.watchlist_changes == []

    def test_an_uppercase_ticker_is_preferred_over_a_lowercase_word(
        self, portfolio, watchlist
    ):
        result = mock_chat_response("please buy 4 shares of NVDA today", portfolio, watchlist)
        assert result.trades[0].ticker == "NVDA"
