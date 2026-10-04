"""The public entry point: the §5 signature, mock routing, and error boundaries."""

import inspect
import json
from types import SimpleNamespace

import pytest

from app.llm.schemas import MALFORMED_RESPONSE_MESSAGE
from app.llm.service import ChatResult, LLMError, generate_chat_response


def _response(content):
    return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=content))])


@pytest.fixture
def provider(monkeypatch):
    """Let a test set the provider's reply (or raise) without touching the network."""
    import litellm

    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-test-123")
    state = {"content": '{"message": "ok"}', "error": None, "calls": []}

    async def fake_acompletion(**kwargs):
        state["calls"].append(kwargs)
        if state["error"] is not None:
            raise state["error"]
        return _response(state["content"])

    monkeypatch.setattr(litellm, "acompletion", fake_acompletion)
    return state


class TestSignature:
    def test_matches_contracts_section_5(self):
        assert inspect.iscoroutinefunction(generate_chat_response)
        params = list(inspect.signature(generate_chat_response).parameters)
        assert params == ["user_message", "portfolio", "watchlist", "history"]

    def test_module_exposes_nothing_wider(self):
        from app.llm import service

        assert service.__all__ == [
            "ChatResult",
            "LLMError",
            "ProposedChange",
            "ProposedTrade",
            "generate_chat_response",
        ]


class TestLiveMode:
    async def test_parses_a_clean_structured_response(self, provider, portfolio, watchlist):
        provider["content"] = json.dumps(
            {
                "message": "Bought 10 AAPL at $192.50.",
                "trades": [{"ticker": "aapl", "side": "buy", "quantity": 10}],
                "watchlist_changes": [{"ticker": "pypl", "action": "add"}],
            }
        )
        result = await generate_chat_response("buy 10 apple", portfolio, watchlist, [])

        assert isinstance(result, ChatResult)
        assert result.message == "Bought 10 AAPL at $192.50."
        assert (result.trades[0].ticker, result.trades[0].side) == ("AAPL", "buy")
        assert result.watchlist_changes[0].action == "add"

    async def test_sends_the_portfolio_context_to_the_provider(
        self, provider, portfolio, watchlist
    ):
        await generate_chat_response("how am I doing?", portfolio, watchlist, [])
        sent = provider["calls"][0]["messages"]
        assert "$8,075.00" in sent[1]["content"]
        assert sent[-1]["content"] == "how am I doing?"

    async def test_malformed_response_degrades_instead_of_raising(
        self, provider, portfolio, watchlist
    ):
        provider["content"] = "```\nI forgot to answer in JSON\n```"
        result = await generate_chat_response("hi", portfolio, watchlist, [])
        assert result.message == MALFORMED_RESPONSE_MESSAGE
        assert result.trades == []
        assert result.watchlist_changes == []

    async def test_provider_failure_raises_llm_error(self, provider, portfolio, watchlist):
        provider["error"] = ConnectionError("openrouter unreachable")
        with pytest.raises(LLMError):
            await generate_chat_response("hi", portfolio, watchlist, [])

    async def test_missing_api_key_raises_llm_error(self, monkeypatch, portfolio, watchlist):
        monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
        with pytest.raises(LLMError) as excinfo:
            await generate_chat_response("hi", portfolio, watchlist, [])
        assert "OPENROUTER_API_KEY" in str(excinfo.value)


class TestMockRouting:
    async def test_mock_mode_short_circuits_the_provider(
        self, monkeypatch, provider, portfolio, watchlist
    ):
        monkeypatch.setenv("LLM_MOCK", "true")
        result = await generate_chat_response("buy 10 AAPL", portfolio, watchlist, [])
        assert provider["calls"] == []
        assert result.trades[0].ticker == "AAPL"

    async def test_mock_mode_works_with_no_api_key_at_all(
        self, monkeypatch, portfolio, watchlist
    ):
        monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
        monkeypatch.setenv("LLM_MOCK", "true")
        result = await generate_chat_response("hello", portfolio, watchlist, [])
        assert "$10,000.00" in result.message

    async def test_flag_is_checked_per_call(self, monkeypatch, provider, portfolio, watchlist):
        monkeypatch.setenv("LLM_MOCK", "true")
        await generate_chat_response("hi", portfolio, watchlist, [])
        assert provider["calls"] == []

        monkeypatch.setenv("LLM_MOCK", "false")
        await generate_chat_response("hi", portfolio, watchlist, [])
        assert len(provider["calls"]) == 1
