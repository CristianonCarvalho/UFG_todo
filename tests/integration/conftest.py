"""Fixtures para testes de integração da API."""

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

import app.models  # noqa: F401
from app.db import Base, build_session_factory, get_db
from app.dependencies import get_classifier
from app.main import create_app
from app.schemas.task import PrioritySource, TaskPriority
from app.services.priority_classifier import PriorityResult


class FakeClassifier:
    """Classificador falso configurável que registra as chamadas recebidas."""

    def __init__(self) -> None:
        """Inicializa uma prioridade padrão e o histórico de chamadas."""
        self.result = PriorityResult(TaskPriority.ALTA, PrioritySource.JEV)
        self.calls: list[tuple[str, str | None]] = []

    def classify(self, title: str, description: str | None) -> PriorityResult:
        """Registra os dados classificados e devolve o resultado configurado."""
        self.calls.append((title, description))
        return self.result


def _client(factory: sessionmaker[Session], classifier: FakeClassifier) -> TestClient:
    def override_db() -> Iterator[Session]:
        session = factory()
        try:
            yield session
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    api = create_app()
    api.dependency_overrides[get_db] = override_db
    api.dependency_overrides[get_classifier] = lambda: classifier
    return TestClient(api, raise_server_exceptions=False)


@pytest.fixture
def classifier() -> FakeClassifier:
    """Fornece um classificador falso configurável."""
    return FakeClassifier()


@pytest.fixture
def client(tmp_path: Path, classifier: FakeClassifier) -> Iterator[TestClient]:
    """Fornece um cliente conectado a um banco SQLite temporário."""
    engine = create_engine(
        f"sqlite:///{tmp_path / 'api.db'}", connect_args={"check_same_thread": False}
    )
    Base.metadata.create_all(engine)
    yield _client(build_session_factory(engine), classifier)
    engine.dispose()


@pytest.fixture
def client_banco_quebrado(tmp_path: Path, classifier: FakeClassifier) -> Iterator[TestClient]:
    """Fornece um cliente cujo banco não pode ser aberto."""
    caminho = tmp_path / "pasta-inexistente" / "api.db"
    engine = create_engine(f"sqlite:///{caminho}", connect_args={"check_same_thread": False})
    yield _client(build_session_factory(engine), classifier)
    engine.dispose()
