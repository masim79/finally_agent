"""Validation rules on the structured-output models."""

import pytest
from pydantic import ValidationError

from app.llm.schemas import ChatResult, LlmChatResponse, LlmTrade, LlmWatchlistChange


class TestLlmTrade:
    def test_uppercases_ticker(self):
        assert LlmTrade(ticker="aapl", side="buy", quantity=10).ticker == "AAPL"

    def test_strips_whitespace_around_ticker(self):
        assert LlmTrade(ticker="  msft \n", side="sell", quantity=1).ticker == "MSFT"

    def test_allows_dotted_ticker(self):
        assert LlmTrade(ticker="brk.b", side="buy", quantity=1).ticker == "BRK.B"

    def test_allows_fractional_quantity(self):
        assert LlmTrade(ticker="AAPL", side="buy", quantity=0.5).quantity == 0.5

    def test_rejects_non_numeric_quantity(self):
        with pytest.raises(ValidationError):
            LlmTrade(ticker="AAPL", side="buy", quantity="ten")

    def test_coerces_numeric_string_quantity(self):
        assert LlmTrade(ticker="AAPL", side="buy", quantity="10").quantity == 10.0

    @pytest.mark.parametrize("quantity", [0, -5, float("nan"), float("inf")])
    def test_rejects_non_positive_or_non_finite_quantity(self, quantity):
        with pytest.raises(ValidationError):
            LlmTrade(ticker="AAPL", side="buy", quantity=quantity)

    def test_rejects_unknown_side(self):
        with pytest.raises(ValidationError):
            LlmTrade(ticker="AAPL", side="short", quantity=1)

    @pytest.mark.parametrize("ticker", ["", "   ", "TOOLONGTICKER", "AA PL", "AA$L", 42])
    def test_rejects_bad_tickers(self, ticker):
        with pytest.raises(ValidationError):
            LlmTrade(ticker=ticker, side="buy", quantity=1)


class TestLlmWatchlistChange:
    def test_uppercases_ticker(self):
        assert LlmWatchlistChange(ticker="pypl", action="add").ticker == "PYPL"

    def test_rejects_unknown_action(self):
        with pytest.raises(ValidationError):
            LlmWatchlistChange(ticker="PYPL", action="watch")


class TestLlmChatResponse:
    def test_all_three_fields_are_required_on_the_wire(self):
        """Strict structured output marks every property required anyway; declaring
        them so keeps a pointless "default" out of the schema we send."""
        schema = LlmChatResponse.model_json_schema()
        assert set(schema["required"]) == {"message", "trades", "watchlist_changes"}
        with pytest.raises(ValidationError):
            LlmChatResponse(message="hello")

    def test_json_schema_is_plain_enough_for_strict_structured_output(self):
        """Strict modes support only a narrow keyword subset, so the schema we send
        must carry no pattern/minimum/default keywords. The validators enforce those
        constraints on the way back instead."""
        schema = repr(LlmChatResponse.model_json_schema())
        for keyword in ("pattern", "exclusiveMinimum", "minimum", "maxLength", "default"):
            assert keyword not in schema


class TestChatResult:
    def test_action_lists_default_to_empty_and_are_not_shared(self):
        a, b = ChatResult(message="x"), ChatResult(message="y")
        assert a.trades == [] and a.watchlist_changes == []
        assert a.trades is not b.trades
