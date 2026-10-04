"""parse_response must never raise, and must salvage whatever it can.

These cases are the ones the happy path hides: valid JSON that violates the schema,
a missing message, markdown fences, one good trade beside one malformed one.
"""

import json

import pytest

from app.llm.client import parse_response
from app.llm.schemas import MALFORMED_RESPONSE_MESSAGE, ProposedChange, ProposedTrade

CLEAN = json.dumps(
    {
        "message": "Bought 10 AAPL at $192.50.",
        "trades": [{"ticker": "AAPL", "side": "buy", "quantity": 10}],
        "watchlist_changes": [{"ticker": "PYPL", "action": "add"}],
    }
)


class TestCleanResponse:
    def test_parses_message_trades_and_watchlist_changes(self):
        result = parse_response(CLEAN)
        assert result.message == "Bought 10 AAPL at $192.50."
        assert result.trades == [ProposedTrade(ticker="AAPL", side="buy", quantity=10.0)]
        assert result.watchlist_changes == [ProposedChange(ticker="PYPL", action="add")]

    def test_message_only_response_yields_empty_action_lists(self):
        result = parse_response('{"message": "Your portfolio looks balanced."}')
        assert result.message == "Your portfolio looks balanced."
        assert result.trades == []
        assert result.watchlist_changes == []

    def test_uppercases_tickers_from_the_model(self):
        raw = json.dumps(
            {
                "message": "ok",
                "trades": [{"ticker": "aapl", "side": "buy", "quantity": 1}],
                "watchlist_changes": [{"ticker": "pypl", "action": "remove"}],
            }
        )
        result = parse_response(raw)
        assert result.trades[0].ticker == "AAPL"
        assert result.watchlist_changes[0].ticker == "PYPL"


class TestDegradation:
    """Whole-turn degradation: the message itself could not be recovered."""

    @pytest.mark.parametrize(
        "raw",
        [
            pytest.param('{"message": "truncated", "trades": [{"ticker": "AA', id="truncated"),
            pytest.param("not json at all", id="prose"),
            pytest.param("", id="empty-string"),
            pytest.param("   ", id="whitespace"),
            pytest.param(None, id="none"),
            pytest.param("[1, 2, 3]", id="json-array-not-object"),
            pytest.param('"just a string"', id="json-string-not-object"),
            pytest.param('{"trades": []}', id="message-field-missing"),
            pytest.param('{"message": ""}', id="empty-message"),
            pytest.param('{"message": "   "}', id="whitespace-message"),
            pytest.param('{"message": 42}', id="message-wrong-type"),
            pytest.param('{"message": null}', id="message-null"),
        ],
    )
    def test_unrecoverable_responses_degrade_without_raising(self, raw):
        result = parse_response(raw)
        assert result.message == MALFORMED_RESPONSE_MESSAGE
        assert result.trades == []
        assert result.watchlist_changes == []


class TestSalvage:
    """A usable message survives junk alongside it; junk entries are dropped alone."""

    def test_markdown_fenced_json_is_unwrapped(self):
        result = parse_response(f"```json\n{CLEAN}\n```")
        assert result.message == "Bought 10 AAPL at $192.50."
        assert result.trades[0].ticker == "AAPL"

    def test_bare_fences_are_unwrapped(self):
        result = parse_response(f"```\n{CLEAN}\n```")
        assert result.trades[0].quantity == 10.0

    def test_prose_around_the_object_is_discarded(self):
        result = parse_response(f"Sure, here you go:\n{CLEAN}\nHope that helps!")
        assert result.message == "Bought 10 AAPL at $192.50."

    def test_one_good_trade_survives_one_malformed_trade(self):
        raw = json.dumps(
            {
                "message": "Buying Apple.",
                "trades": [
                    {"ticker": "AAPL", "side": "buy", "quantity": 10},
                    {"ticker": "MSFT", "side": "buy", "quantity": "ten"},
                ],
            }
        )
        result = parse_response(raw)
        assert result.trades == [ProposedTrade(ticker="AAPL", side="buy", quantity=10.0)]

    @pytest.mark.parametrize(
        "bad_trade",
        [
            {"ticker": "MSFT", "side": "buy", "quantity": -5},
            {"ticker": "MSFT", "side": "buy", "quantity": 0},
            {"ticker": "MSFT", "side": "short", "quantity": 5},
            {"ticker": "", "side": "buy", "quantity": 5},
            {"side": "buy", "quantity": 5},
            {"ticker": "MSFT", "quantity": 5},
            "MSFT",
            None,
        ],
    )
    def test_each_kind_of_malformed_trade_is_dropped(self, bad_trade):
        raw = json.dumps(
            {
                "message": "ok",
                "trades": [{"ticker": "AAPL", "side": "buy", "quantity": 1}, bad_trade],
            }
        )
        result = parse_response(raw)
        assert [t.ticker for t in result.trades] == ["AAPL"]
        assert result.message == "ok"

    def test_malformed_watchlist_change_is_dropped(self):
        raw = json.dumps(
            {
                "message": "ok",
                "watchlist_changes": [
                    {"ticker": "PYPL", "action": "add"},
                    {"ticker": "SHOP", "action": "subscribe"},
                ],
            }
        )
        result = parse_response(raw)
        assert result.watchlist_changes == [ProposedChange(ticker="PYPL", action="add")]

    @pytest.mark.parametrize("junk", ["nonsense", 42, {"ticker": "AAPL"}, None])
    def test_action_field_of_the_wrong_type_becomes_an_empty_list(self, junk):
        raw = json.dumps({"message": "ok", "trades": junk, "watchlist_changes": junk})
        result = parse_response(raw)
        assert result.message == "ok"
        assert result.trades == []
        assert result.watchlist_changes == []

    def test_unknown_extra_fields_are_ignored(self):
        raw = json.dumps({"message": "ok", "confidence": 0.9, "notes": ["a"]})
        assert parse_response(raw).message == "ok"
