"""The provider call: parameters, key handling, and failure mapping.

litellm.acompletion is replaced in every test here — nothing touches the network.
"""

import json
from types import SimpleNamespace

import pytest

from app.llm import client
from app.llm.client import EXTRA_BODY, MODEL, LLMError, call_model
from app.llm.schemas import LlmChatResponse


def _response(content):
    return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=content))])


@pytest.fixture
def captured_call(monkeypatch):
    """Patch litellm.acompletion, record its kwargs, and return a canned response."""
    import litellm

    calls = {}

    async def fake_acompletion(**kwargs):
        calls.update(kwargs)
        return _response('{"message": "hi"}')

    monkeypatch.setattr(litellm, "acompletion", fake_acompletion)
    return calls


class TestApiKey:
    async def test_missing_key_raises_llm_error_before_any_provider_call(self, monkeypatch):
        import litellm

        async def explode(**kwargs):  # pragma: no cover - must never run
            raise AssertionError("provider must not be called without an API key")

        monkeypatch.setattr(litellm, "acompletion", explode)
        with pytest.raises(LLMError) as excinfo:
            await call_model([{"role": "user", "content": "hi"}])
        assert "OPENROUTER_API_KEY" in str(excinfo.value)

    @pytest.mark.parametrize("value", ["", "   "])
    async def test_blank_key_is_treated_as_missing(self, monkeypatch, value):
        monkeypatch.setenv("OPENROUTER_API_KEY", value)
        with pytest.raises(LLMError):
            await call_model([{"role": "user", "content": "hi"}])

    async def test_key_is_read_at_call_time(self, monkeypatch, captured_call):
        monkeypatch.setenv("OPENROUTER_API_KEY", "sk-test-123")
        await call_model([{"role": "user", "content": "hi"}])
        assert captured_call["api_key"] == "sk-test-123"


class TestCallParameters:
    async def test_uses_the_cerebras_routing_contract(self, monkeypatch, captured_call):
        monkeypatch.setenv("OPENROUTER_API_KEY", "sk-test-123")
        messages = [{"role": "user", "content": "hi"}]

        content = await call_model(messages)

        assert content == '{"message": "hi"}'
        assert captured_call["model"] == MODEL == "openrouter/openai/gpt-oss-120b"
        assert captured_call["extra_body"] == EXTRA_BODY == {"provider": {"order": ["cerebras"]}}
        assert captured_call["reasoning_effort"] == "low"
        assert captured_call["response_format"] is LlmChatResponse
        assert captured_call["messages"] == messages


class TestFailureMapping:
    @pytest.mark.parametrize(
        "exc",
        [ConnectionError("unreachable"), RuntimeError("401 unauthorized"), TimeoutError()],
    )
    async def test_provider_exceptions_become_llm_error(self, monkeypatch, exc):
        import litellm

        monkeypatch.setenv("OPENROUTER_API_KEY", "sk-test-123")

        async def fail(**kwargs):
            raise exc

        monkeypatch.setattr(litellm, "acompletion", fail)
        with pytest.raises(LLMError):
            await call_model([{"role": "user", "content": "hi"}])

    @pytest.mark.parametrize(
        "response",
        [
            SimpleNamespace(choices=[]),
            SimpleNamespace(),
            _response(None),
            _response({"not": "a string"}),
        ],
    )
    async def test_structurally_broken_responses_raise_llm_error(self, monkeypatch, response):
        import litellm

        monkeypatch.setenv("OPENROUTER_API_KEY", "sk-test-123")

        async def returns(**kwargs):
            return response

        monkeypatch.setattr(litellm, "acompletion", returns)
        with pytest.raises(LLMError):
            await call_model([{"role": "user", "content": "hi"}])

    async def test_a_badly_worded_answer_is_not_an_llm_error(self, monkeypatch):
        """Reaching the provider and getting nonsense back is a parse problem, not an
        outage — call_model returns it and parse_response degrades it."""
        import litellm

        monkeypatch.setenv("OPENROUTER_API_KEY", "sk-test-123")

        async def returns(**kwargs):
            return _response("I am not JSON")

        monkeypatch.setattr(litellm, "acompletion", returns)
        assert await call_model([{"role": "user", "content": "hi"}]) == "I am not JSON"


class TestNoNetworkInTheseTests:
    async def test_round_trip_through_a_fake_provider(self, monkeypatch):
        import litellm

        monkeypatch.setenv("OPENROUTER_API_KEY", "sk-test-123")
        payload = json.dumps(
            {"message": "ok", "trades": [{"ticker": "aapl", "side": "sell", "quantity": 2.5}]}
        )

        async def returns(**kwargs):
            return _response(payload)

        monkeypatch.setattr(litellm, "acompletion", returns)
        result = client.parse_response(await call_model([{"role": "user", "content": "hi"}]))
        assert result.trades[0].ticker == "AAPL"
        assert result.trades[0].quantity == 2.5
