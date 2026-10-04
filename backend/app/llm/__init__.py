"""FinAlly LLM integration: structured chat responses via OpenRouter → Cerebras."""

from app.llm.client import LLMError
from app.llm.schemas import ChatResult, ProposedChange, ProposedTrade
from app.llm.service import generate_chat_response

__all__ = [
    "ChatResult",
    "LLMError",
    "ProposedChange",
    "ProposedTrade",
    "generate_chat_response",
]
