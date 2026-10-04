"""Configurações da aplicação lidas de variáveis de ambiente e do arquivo `.env`."""

from functools import lru_cache

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configurações do classificador de prioridade."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    openrouter_api_key: SecretStr | None = None
    openrouter_base_url: str = "https://openrouter.ai/api"
    jev_model: str = "typesafe/jev-1.13"
    classifier_timeout_seconds: float = 5.0
    classifier_max_retries: int = 1
    jev_min_confidence: float = 0.5


@lru_cache
def get_settings() -> Settings:
    """Devolve as configurações, lidas uma única vez por processo."""
    return Settings()
