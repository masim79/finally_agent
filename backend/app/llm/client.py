"""The LiteLLM → OpenRouter → Cerebras call, and the parser that survives its output.

Two responsibilities, split by what the backend should do about them:

* ``call_model`` raises :class:`LLMError` and nothing else. An LLMError means the
  provider is unreachable, unauthenticated, or missing its key — conditions the
  backend surfaces as the §3 ``LLM_ERROR`` code.
* ``parse_response`` never raises. Whatever the model emitted, it returns a
  ``ChatResult``: salvaged where possible, degraded to an apology where not. A
  truncated or schema-violating response is a bad answer, not an outage, and must
  not turn a chat turn into a 500.
"""

from __future__ import annotations

import json
import logging
import os
import re

from pydantic import ValidationError

from app.llm.schemas import (
    ChatResult,
    LlmTrade,
    LlmWatchlistChange,
    ProposedChange,
    ProposedTrade,
    degraded_result,
)

logger = logging.getLogger(__name__)

MODEL = "openrouter/openai/gpt-oss-120b"
EXTRA_BODY = {"provider": {"order": ["cerebras"]}}
REASONING_EFFORT = "low"

_FENCE_RE = re.compile(r"^\s*```(?:json|JSON)?\s*\n?(?P<body>.*?)\n?\s*```\s*$", re.DOTALL)


class LLMError(Exception):
    """The provider could not be reached or would not authenticate us.

    Reserved for infrastructure failures. A model that answers badly is handled by
    degrading the result, not by raising this.
    """


def _api_key() -> str:
    """Read OPENROUTER_API_KEY at call time, so tests and mock mode can toggle it."""
    key = (os.environ.get("OPENROUTER_API_KEY") or "").strip()
    if not key:
        raise LLMError(
            "OPENROUTER_API_KEY is not set. Set it in the environment (or .env) to enable "
            "live chat, or set LLM_MOCK=true to use deterministic mock responses."
        )
    return key


async def call_model(messages: list[dict]) -> str:
    """Send ``messages`` to Cerebras via OpenRouter and return the raw content string.

    Raises:
        LLMError: no API key, or the provider call failed for any reason.
    """
    # Imported lazily: litellm is a heavy import, and mock mode must never pay for it.
    import litellm

    from app.llm.schemas import LlmChatResponse

    api_key = _api_key()

    try:
        response = await litellm.acompletion(
            model=MODEL,
            messages=messages,
            response_format=LlmChatResponse,
            reasoning_effort=REASONING_EFFORT,
            extra_body=EXTRA_BODY,
            api_key=api_key,
        )
    except Exception as exc:  # noqa: BLE001 - every provider failure is one LLMError
        raise LLMError(f"LLM provider call failed: {exc}") from exc

    content = _extract_content(response)
    if content is None:
        raise LLMError("LLM provider returned a response with no message content")
    return content


def _extract_content(response: object) -> str | None:
    """Pull ``choices[0].message.content`` out of a response without trusting its shape."""
    try:
        choices = response.choices  # type: ignore[attr-defined]
        content = choices[0].message.content
    except (AttributeError, IndexError, KeyError, TypeError):
        return None
    return content if isinstance(content, str) else None


def _strip_fences(text: str) -> str:
    """Unwrap a ```json ... ``` block if the model wrapped its JSON in one."""
    match = _FENCE_RE.match(text)
    return match.group("body") if match else text.strip()


def _load_json(text: str) -> dict | None:
    """Parse a JSON object out of ``text``, tolerating fences and surrounding prose."""
    candidate = _strip_fences(text)
    try:
        parsed = json.loads(candidate)
    except (json.JSONDecodeError, ValueError):
        # Last resort: the model may have added a sentence either side of the object.
        start, end = candidate.find("{"), candidate.rfind("}")
        if start == -1 or end <= start:
            return None
        try:
            parsed = json.loads(candidate[start : end + 1])
        except (json.JSONDecodeError, ValueError):
            return None
    return parsed if isinstance(parsed, dict) else None


def _parse_trades(raw: object) -> list[ProposedTrade]:
    """Validate trades one at a time so one bad entry does not discard the good ones."""
    if not isinstance(raw, list):
        return []
    trades: list[ProposedTrade] = []
    for item in raw:
        if not isinstance(item, dict):
            logger.warning("Discarding non-object trade entry from LLM response: %r", item)
            continue
        try:
            validated = LlmTrade.model_validate(item)
        except ValidationError as exc:
            logger.warning("Discarding invalid trade from LLM response: %r (%s)", item, exc)
            continue
        trades.append(
            ProposedTrade(
                ticker=validated.ticker, side=validated.side, quantity=validated.quantity
            )
        )
    return trades


def _parse_watchlist_changes(raw: object) -> list[ProposedChange]:
    if not isinstance(raw, list):
        return []
    changes: list[ProposedChange] = []
    for item in raw:
        if not isinstance(item, dict):
            logger.warning("Discarding non-object watchlist entry from LLM response: %r", item)
            continue
        try:
            validated = LlmWatchlistChange.model_validate(item)
        except ValidationError as exc:
            logger.warning(
                "Discarding invalid watchlist change from LLM response: %r (%s)", item, exc
            )
            continue
        changes.append(ProposedChange(ticker=validated.ticker, action=validated.action))
    return changes


def parse_response(raw: str | None) -> ChatResult:
    """Turn the model's raw content into a ChatResult. Never raises.

    A response is salvaged as far as it can be: a usable ``message`` is kept even when
    the action arrays are junk, and a junk entry inside an otherwise good array is
    dropped on its own. Only the loss of ``message`` itself — unparseable JSON, a
    missing field, an empty string — degrades the whole turn.
    """
    if not isinstance(raw, str) or not raw.strip():
        logger.warning("LLM returned empty content; degrading response")
        return degraded_result()

    payload = _load_json(raw)
    if payload is None:
        logger.warning("LLM content was not a JSON object; degrading response")
        return degraded_result()

    message = payload.get("message")
    if not isinstance(message, str) or not message.strip():
        logger.warning("LLM response had no usable 'message' field; degrading response")
        return degraded_result()

    return ChatResult(
        message=message.strip(),
        trades=_parse_trades(payload.get("trades")),
        watchlist_changes=_parse_watchlist_changes(payload.get("watchlist_changes")),
    )
