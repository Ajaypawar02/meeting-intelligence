"""LLM provider: real LangChain chat model when keyed, else deterministic mock."""

from __future__ import annotations

from typing import Any, Protocol

from app.config import get_settings
from app.llm.mock_llm import MockLLM


class LLMLike(Protocol):
    def invoke(self, prompt: str | list | dict, **kwargs: Any) -> Any: ...


def get_llm() -> LLMLike:
    settings = get_settings()
    if settings.use_mock_llm:
        return MockLLM()

    try:
        from langchain_openai import ChatOpenAI
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError(
            "llm provider set to openai but langchain-openai is not installed. "
            "pip install 'meeting-intelligence[llm]' or set LLM_PROVIDER=mock."
        ) from exc

    return ChatOpenAI(
        model=settings.openai_model,
        api_key=settings.openai_api_key,
        temperature=0,
    )


def get_extractor() -> MockLLM:
    """Extraction always available via mock rules; real LLM can refine later."""
    return MockLLM()
