from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


ROOT = Path(__file__).resolve().parents[1]

# Built-in free / freemium OpenAI-compatible endpoints
GROQ_DEFAULT_BASE_URL = "https://api.groq.com/openai/v1"
OPENROUTER_DEFAULT_BASE_URL = "https://openrouter.ai/api/v1"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # mock | ollama | openai | groq | openrouter
    llm_provider: str = "mock"

    openai_api_key: str | None = None
    openai_model: str = "gpt-4o-mini"
    # Generic OpenAI-compatible base URL (also used when provider=openai)
    openai_base_url: str | None = None

    # Groq free-tier API (https://console.groq.com)
    groq_api_key: str | None = None
    groq_model: str = "llama-3.1-8b-instant"
    groq_base_url: str = GROQ_DEFAULT_BASE_URL

    # OpenRouter (free models available; https://openrouter.ai)
    openrouter_api_key: str | None = None
    openrouter_model: str = "meta-llama/llama-3.2-3b-instruct:free"
    openrouter_base_url: str = OPENROUTER_DEFAULT_BASE_URL

    ollama_model: str = "llama3.2"
    ollama_base_url: str = "http://127.0.0.1:11434"

    confidence_threshold: float = 0.75
    data_dir: Path = ROOT / "data"
    output_dir: Path = ROOT / "artifacts" / "runs"
    checkpoint_db: Path = ROOT / "artifacts" / "checkpoints.sqlite"
    default_audience_role: str = "general"

    @property
    def provider(self) -> str:
        return self.llm_provider.lower().strip()

    def api_key_for_provider(self) -> str | None:
        if self.provider == "groq":
            return self.groq_api_key or self.openai_api_key
        if self.provider == "openrouter":
            return self.openrouter_api_key or self.openai_api_key
        if self.provider == "openai":
            return self.openai_api_key
        return None

    @property
    def use_mock_llm(self) -> bool:
        """True when we should not attempt a remote/local chat model."""
        if self.provider == "mock":
            return True
        if self.provider == "ollama":
            return False
        if self.provider in {"openai", "groq", "openrouter"}:
            return not bool(self.api_key_for_provider())
        return True


@lru_cache
def get_settings() -> Settings:
    return Settings()
