"""Provider selection for free APIs (groq / openrouter)."""

from __future__ import annotations

from app.config import Settings, get_settings
from app.llm.llm_provider import active_llm_label, get_extractor


def test_groq_settings_resolve_key_and_defaults():
    s = Settings(
        llm_provider="groq",
        groq_api_key="gsk-test",
        groq_model="llama-3.1-8b-instant",
    )
    assert s.api_key_for_provider() == "gsk-test"
    assert s.use_mock_llm is False
    assert "groq.com" in s.groq_base_url


def test_openrouter_free_model_defaults():
    s = Settings(
        llm_provider="openrouter",
        openrouter_api_key="sk-or-test",
    )
    assert "llama" in s.openrouter_model
    assert s.api_key_for_provider() == "sk-or-test"
    assert s.use_mock_llm is False


def test_groq_without_key_falls_back_to_mock_extractor(monkeypatch):
    get_settings.cache_clear()
    monkeypatch.setenv("LLM_PROVIDER", "groq")
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    get_settings.cache_clear()
    try:
        ext = get_extractor()
        assert ext.backend_name == "groq->mock_no_key"
        assert "groq" in active_llm_label() or "mock" in active_llm_label()
    finally:
        get_settings.cache_clear()


def test_openai_compatible_generic_still_supported():
    s = Settings(
        llm_provider="openai",
        openai_api_key="sk-test",
        openai_base_url="https://example-free-api.test/v1",
        openai_model="free-model",
    )
    assert s.use_mock_llm is False
    assert s.openai_base_url.endswith("/v1")
