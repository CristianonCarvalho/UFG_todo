import logging
import re
import uuid
from datetime import datetime
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.exc import SQLAlchemyError

from app.core.errors import TaskNotFoundError, register_exception_handlers
from app.schemas.task import PRIORITY_FALLBACK_NOTICE, TaskCreate, TaskOut, TaskUpdate

MENSAGENS_EM_INGLES = (
    "Field required",
    "Not Found",
    "Method Not Allowed",
    "Internal Server Error",
    "Input should",
    "Extra inputs",
    "String should",
)


@pytest.fixture
def client() -> TestClient:
    app = FastAPI()
    register_exception_handlers(app)

    @app.post("/criar")
    def criar(body: TaskCreate) -> dict[str, bool]:
        return {"ok": True}

    @app.patch("/editar")
    def editar(body: TaskUpdate) -> dict[str, bool]:
        return {"ok": True}

    @app.get("/nao-encontrada")
    def nao_encontrada() -> None:
        raise TaskNotFoundError()

    @app.get("/banco")
    def banco() -> None:
        raise SQLAlchemyError("select * from tabela_secreta")

    @app.get("/boom")
    def boom() -> None:
        raise RuntimeError("segredo-interno")

    return TestClient(app, raise_server_exceptions=False)


def verifica_formato(response) -> dict:
    corpo = response.json()
    assert list(corpo) == ["erro"]
    erro = corpo["erro"]
    uuid.UUID(erro["id_requisicao"])
    assert erro["codigo"] and erro["mensagem"]
    for texto in MENSAGENS_EM_INGLES:
        assert texto not in response.text
    return erro


def test_titulo_ausente(client: TestClient) -> None:
    response = client.post("/criar", json={})
    erro = verifica_formato(response)
    assert response.status_code == 422
    assert erro["codigo"] == "DADOS_INVALIDOS"
    assert {"campo": "title", "mensagem": "O título é obrigatório."} in erro["detalhes"]


def test_titulo_em_branco(client: TestClient) -> None:
    response = client.post("/criar", json={"title": "   "})
    erro = verifica_formato(response)
    assert response.status_code == 422
    assert erro["detalhes"][0]["mensagem"] == "O título não pode ficar em branco."


def test_titulo_com_101_caracteres(client: TestClient) -> None:
    response = client.post("/criar", json={"title": "a" * 101})
    erro = verifica_formato(response)
    assert response.status_code == 422
    assert "100" in erro["detalhes"][0]["mensagem"]


def test_prioridade_invalida(client: TestClient) -> None:
    response = client.patch("/editar", json={"priority": "urgentissima"})
    erro = verifica_formato(response)
    mensagem = erro["detalhes"][0]["mensagem"]
    assert mensagem == "Prioridade inválida. Use: baixa, media ou alta."


def test_campo_extra(client: TestClient) -> None:
    response = client.post("/criar", json={"title": "x", "priority": "alta"})
    erro = verifica_formato(response)
    assert response.status_code == 422
    assert "priority" in erro["detalhes"][0]["mensagem"]
    assert "não" in erro["detalhes"][0]["mensagem"]


def test_atualizacao_sem_campos(client: TestClient) -> None:
    response = client.patch("/editar", json={})
    erro = verifica_formato(response)
    assert response.status_code == 422
    assert "Informe ao menos um campo" in erro["detalhes"][0]["mensagem"]


def test_json_malformado_retorna_422_amigavel(client: TestClient) -> None:
    response = client.post(
        "/criar", content=b'{"title": ', headers={"content-type": "application/json"}
    )
    erro = verifica_formato(response)
    assert response.status_code == 422
    assert erro["codigo"] == "DADOS_INVALIDOS"


def test_tarefa_nao_encontrada(client: TestClient) -> None:
    response = client.get("/nao-encontrada")
    erro = verifica_formato(response)
    assert response.status_code == 404
    assert erro["codigo"] == "TAREFA_NAO_ENCONTRADA"
    assert erro["mensagem"] == "Não encontramos essa tarefa. Ela pode ter sido removida."
    assert "detalhes" not in erro


def test_rota_inexistente(client: TestClient) -> None:
    response = client.get("/nao-existe")
    erro = verifica_formato(response)
    assert response.status_code == 404
    assert erro["mensagem"] == "Não encontramos o que você procurou."


def test_metodo_errado(client: TestClient) -> None:
    response = client.get("/criar")
    erro = verifica_formato(response)
    assert response.status_code == 405
    assert erro["mensagem"] == "Esta ação não é permitida aqui."


def test_erro_de_banco(client: TestClient, caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.ERROR, logger="app.errors"):
        response = client.get("/banco")
    erro = verifica_formato(response)
    assert response.status_code == 503
    assert erro["codigo"] == "BANCO_INDISPONIVEL"
    assert "tabela_secreta" not in response.text
    assert erro["id_requisicao"] in caplog.text


def test_erro_inesperado_nao_vaza_detalhes(
    client: TestClient, caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level(logging.ERROR, logger="app.errors"):
        response = client.get("/boom")
    erro = verifica_formato(response)
    assert response.status_code == 500
    assert erro["codigo"] == "ERRO_INTERNO"
    for proibido in ("segredo-interno", "Traceback", "RuntimeError"):
        assert proibido not in response.text
    assert erro["id_requisicao"] in caplog.text
    assert "segredo-interno" in caplog.text


def test_id_requisicao_muda_a_cada_requisicao(client: TestClient) -> None:
    ids = {client.get("/nao-existe").json()["erro"]["id_requisicao"] for _ in range(3)}
    assert len(ids) == 3


def _tarefa(source: str) -> SimpleNamespace:
    return SimpleNamespace(
        id=1,
        title="t",
        description=None,
        status="pendente",
        priority="media",
        priority_source=source,
        created_at=datetime(2026, 10, 4),
    )


@pytest.mark.parametrize(
    ("source", "esperado"),
    [("fallback", PRIORITY_FALLBACK_NOTICE), ("jev", None), ("manual", None)],
)
def test_priority_notice(source: str, esperado: str | None) -> None:
    assert TaskOut.model_validate(_tarefa(source)).priority_notice == esperado


def test_mensagens_em_portugues_nao_usam_ingles() -> None:
    assert re.search(r"required|invalid", PRIORITY_FALLBACK_NOTICE) is None
