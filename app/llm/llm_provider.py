"""LLM provider: mock | ollama | openai | groq | openrouter."""

from __future__ import annotations

from typing import Any, Protocol

from app.config import get_settings
from app.llm.extractor import HybridExtractor
from app.llm.mock_llm import MockLLM

# Providers that talk OpenAI-compatible HTTP APIs
_OPENAI_COMPAT = frozenset({"openai", "groq", "openrouter"})


class LLMLike(Protocol):
    def invoke(self, prompt: str | list | dict, **kwargs: Any) -> Any: ...


def get_llm() -> LLMLike:
    """Return a chat model for the configured provider, else MockLLM."""
    settings = get_settings()
    provider = settings.provider

    if provider == "mock":
        return MockLLM()

    if provider == "ollama":
        try:
            return _build_ollama(settings)
        except Exception:
            return MockLLM()

    if provider in _OPENAI_COMPAT:
        if not settings.api_key_for_provider():
            return MockLLM()
        try:
            return _build_openai_compatible(settings)
        except Exception:
            return MockLLM()

    return MockLLM()


def get_extractor() -> HybridExtractor:
    """Extractor used by classify/extract nodes.

    Chat providers run JSON extraction; MockLLM is used when the key/package
    is missing or the model call fails.
    """
    settings = get_settings()
    provider = settings.provider

    if provider == "mock":
        return HybridExtractor(None, backend_name="mock")

    if provider == "ollama":
        try:
            return HybridExtractor(_build_ollama(settings), backend_name="ollama")
        except Exception:
            return HybridExtractor(None, backend_name="ollama->mock_unavailable")

    if provider in _OPENAI_COMPAT:
        if not settings.api_key_for_provider():
            return HybridExtractor(None, backend_name=f"{provider}->mock_no_key")
        try:
            return HybridExtractor(
                _build_openai_compatible(settings),
                backend_name=provider,
            )
        except Exception:
            return HybridExtractor(None, backend_name=f"{provider}->mock_unavailable")

    return HybridExtractor(None, backend_name="mock")


def active_llm_label() -> str:
    """Short label for CLI/API health (does not call the model)."""
    settings = get_settings()
    provider = settings.provider

    if provider == "mock":
        return "mock"
    if provider == "ollama":
        return f"ollama:{settings.ollama_model}"
    if provider == "groq":
        if not settings.api_key_for_provider():
            return "mock (groq key missing)"
        return f"groq:{settings.groq_model}"
    if provider == "openrouter":
        if not settings.api_key_for_provider():
            return "mock (openrouter key missing)"
        return f"openrouter:{settings.openrouter_model}"
    if provider == "openai":
        if not settings.openai_api_key:
            return "mock (openai key missing)"
        base = settings.openai_base_url or "api.openai.com"
        return f"openai:{settings.openai_model}@{base}"
    return "mock"


def _build_ollama(settings: Any) -> LLMLike:
    try:
        from langchain_ollama import ChatOllama
    except ImportError as exc:
        raise RuntimeError(
            "LLM_PROVIDER=ollama requires langchain-ollama. "
            "Install with: pip install 'meeting-intelligence[ollama]'"
        ) from exc

    return ChatOllama(
        model=settings.ollama_model,
        base_url=settings.ollama_base_url,
        temperature=0,
    )


def _build_openai_compatible(settings: Any) -> LLMLike:
    """OpenAI, Groq, OpenRouter, or any OpenAI-compatible free API."""
    try:
        from langchain_openai import ChatOpenAI
    except ImportError as exc:
        raise RuntimeError(
            f"LLM_PROVIDER={settings.provider} requires langchain-openai. "
            "Install with: pip install 'meeting-intelligence[llm]'"
        ) from exc

    provider = settings.provider
    if provider == "groq":
        model = settings.groq_model
        api_key = settings.api_key_for_provider()
        base_url = settings.groq_base_url
    elif provider == "openrouter":
        model = settings.openrouter_model
        api_key = settings.api_key_for_provider()
        base_url = settings.openrouter_base_url
    else:
        model = settings.openai_model
        api_key = settings.openai_api_key
        base_url = settings.openai_base_url

    kwargs: dict[str, Any] = {
        "model": model,
        "api_key": api_key,
        "temperature": 0,
    }
    if base_url:
        kwargs["base_url"] = base_url

    # OpenRouter recommends these headers for rankings / free tier
    if provider == "openrouter":
        kwargs["default_headers"] = {
            "HTTP-Referer": "https://github.com/meeting-intelligence",
            "X-Title": "Meeting Intelligence",
        }

    return ChatOpenAI(**kwargs)
