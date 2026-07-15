from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


ROOT = Path(__file__).resolve().parents[1]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    llm_provider: str = "mock"  # mock | openai
    openai_api_key: str | None = None
    openai_model: str = "gpt-4o-mini"
    confidence_threshold: float = 0.75
    data_dir: Path = ROOT / "data"
    output_dir: Path = ROOT / "artifacts" / "runs"
    checkpoint_db: Path = ROOT / "artifacts" / "checkpoints.sqlite"
    default_audience_role: str = "general"

    @property
    def use_mock_llm(self) -> bool:
        if self.llm_provider.lower() == "mock":
            return True
        if not self.openai_api_key:
            return True
        return False


@lru_cache
def get_settings() -> Settings:
    return Settings()
