from pydantic import SecretStr

from app.core.config import Settings


def test_valores_padrao() -> None:
    settings = Settings(_env_file=None, openrouter_api_key=None)
    assert settings.openrouter_api_key is None
    assert settings.openrouter_base_url == "https://openrouter.ai/api"
    assert settings.jev_model == "typesafe/jev-1.13"
    assert settings.classifier_timeout_seconds == 5.0
    assert settings.classifier_max_retries == 1
    assert settings.jev_min_confidence == 0.5


def test_le_variaveis_de_ambiente(monkeypatch) -> None:
    monkeypatch.setenv("OPENROUTER_API_KEY", "chave-teste")
    monkeypatch.setenv("JEV_MODEL", "typesafe/jev-latest")
    settings = Settings(_env_file=None)
    assert isinstance(settings.openrouter_api_key, SecretStr)
    assert settings.openrouter_api_key.get_secret_value() == "chave-teste"
    assert settings.jev_model == "typesafe/jev-latest"


def test_chave_nao_aparece_na_representacao() -> None:
    settings = Settings(_env_file=None, openrouter_api_key="chave-teste")
    assert "chave-teste" not in repr(settings)


def test_database_url_padrao_e_sobrescrita(monkeypatch) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)
    assert Settings(_env_file=None).database_url == "sqlite:///./tasks.db"
    monkeypatch.setenv("DATABASE_URL", "sqlite:///./outro.db")
    assert Settings(_env_file=None).database_url == "sqlite:///./outro.db"
