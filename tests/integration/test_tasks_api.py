"""Testes de integração dos endpoints de tarefas."""

import json

import pytest
from fastapi.testclient import TestClient

from app.schemas.task import PRIORITY_FALLBACK_NOTICE, PrioritySource, TaskPriority
from app.services.priority_classifier import PriorityResult


def criar(client: TestClient, **corpo: str) -> dict:
    resposta = client.post("/tasks", json={"title": "Tarefa", **corpo})
    assert resposta.status_code == 201
    return resposta.json()


def test_ciclo_completo(client: TestClient, classifier) -> None:
    tarefa = criar(client, title="Escrever relatório", description="rascunho")
    assert tarefa["status"] == "pendente"
    assert tarefa["priority"] == "alta"
    assert tarefa["priority_source"] == "jev"
    assert tarefa["priority_notice"] is None
    assert classifier.calls == [("Escrever relatório", "rascunho")]
    tarefa_id = tarefa["id"]

    assert client.get(f"/tasks/{tarefa_id}").json() == tarefa
    assert [t["id"] for t in client.get("/tasks").json()] == [tarefa_id]

    editada = client.patch(f"/tasks/{tarefa_id}", json={"priority": "baixa"}).json()
    assert editada["priority"] == "baixa"
    assert editada["priority_source"] == "manual"

    concluida = client.patch(f"/tasks/{tarefa_id}/complete").json()
    assert concluida["status"] == "concluida"
    assert client.get("/tasks", params={"status": "pendente"}).json() == []
    assert len(client.get("/tasks", params={"status": "concluida"}).json()) == 1

    assert client.delete(f"/tasks/{tarefa_id}").status_code == 204
    assert client.get(f"/tasks/{tarefa_id}").status_code == 404
    assert client.get("/tasks").json() == []


def test_lista_vem_ordenada_por_id(client: TestClient) -> None:
    ids = [criar(client, title=f"t{i}")["id"] for i in range(3)]
    assert [t["id"] for t in client.get("/tasks").json()] == ids


def test_fallback_devolve_aviso_amigavel(client: TestClient, classifier) -> None:
    classifier.result = PriorityResult(TaskPriority.MEDIA, PrioritySource.FALLBACK)
    tarefa = criar(client)
    assert tarefa["priority_source"] == "fallback"
    assert tarefa["priority_notice"] == PRIORITY_FALLBACK_NOTICE


def test_prioridade_manual_nao_e_sobrescrita_ao_editar_o_titulo(
    client: TestClient, classifier
) -> None:
    tarefa_id = criar(client)["id"]
    client.patch(f"/tasks/{tarefa_id}", json={"priority": "baixa"})
    editada = client.patch(f"/tasks/{tarefa_id}", json={"title": "Outro título"}).json()
    assert editada["title"] == "Outro título"
    assert editada["priority"] == "baixa"
    assert editada["priority_source"] == "manual"
    assert len(classifier.calls) == 1


def test_editar_prioridade_para_o_mesmo_valor_marca_manual(client: TestClient) -> None:
    tarefa_id = criar(client)["id"]
    editada = client.patch(f"/tasks/{tarefa_id}", json={"priority": "alta"}).json()
    assert editada["priority_source"] == "manual"


def test_concluir_duas_vezes_nao_gera_erro(client: TestClient) -> None:
    tarefa_id = criar(client)["id"]
    assert client.patch(f"/tasks/{tarefa_id}/complete").status_code == 200
    assert client.patch(f"/tasks/{tarefa_id}/complete").status_code == 200


def test_remover_duas_vezes_devolve_404_na_segunda(client: TestClient) -> None:
    tarefa_id = criar(client)["id"]
    assert client.delete(f"/tasks/{tarefa_id}").status_code == 204
    assert client.delete(f"/tasks/{tarefa_id}").status_code == 404


@pytest.mark.parametrize(
    ("metodo", "url", "corpo"),
    [
        ("get", "/tasks/999", None),
        ("patch", "/tasks/999", {"title": "x"}),
        ("patch", "/tasks/999/complete", None),
        ("delete", "/tasks/999", None),
    ],
)
def test_id_inexistente_devolve_404_amigavel(
    client: TestClient, metodo: str, url: str, corpo: dict | None
) -> None:
    resposta = getattr(client, metodo)(url, **({"json": corpo} if corpo else {}))
    assert resposta.status_code == 404
    erro = resposta.json()["erro"]
    assert erro["codigo"] == "TAREFA_NAO_ENCONTRADA"
    assert erro["mensagem"] == "Não encontramos essa tarefa. Ela pode ter sido removida."


@pytest.mark.parametrize(
    ("metodo", "url", "corpo", "trecho"),
    [
        ("post", "/tasks", {}, "O título é obrigatório."),
        ("post", "/tasks", {"title": "   "}, "não pode ficar em branco"),
        ("post", "/tasks", {"title": "x", "priority": "alta"}, "não pode ser enviado"),
        ("patch", "/tasks/1", {"priority": "urgentissima"}, "Prioridade inválida"),
        ("patch", "/tasks/1", {"priority": None}, "Informe ao menos um campo"),
        ("patch", "/tasks/1", {"description": "a" * 501}, "500"),
        ("patch", "/tasks/1", {}, "Informe ao menos um campo"),
    ],
)
def test_corpo_invalido_devolve_422_amigavel(
    client: TestClient, metodo: str, url: str, corpo: dict, trecho: str
) -> None:
    resposta = getattr(client, metodo)(url, json=corpo)
    assert resposta.status_code == 422
    assert resposta.json()["erro"]["codigo"] == "DADOS_INVALIDOS"
    assert trecho in json.dumps(resposta.json(), ensure_ascii=False)


def test_json_malformado_devolve_422_amigavel(client: TestClient) -> None:
    resposta = client.post(
        "/tasks", content=b'{"title": ', headers={"content-type": "application/json"}
    )
    assert resposta.status_code == 422
    assert resposta.json()["erro"]["codigo"] == "DADOS_INVALIDOS"


def test_status_na_query_com_maiusculas_lista_as_opcoes(client: TestClient) -> None:
    resposta = client.get("/tasks", params={"status": "Pendente"})
    assert resposta.status_code == 422
    assert "Status inválido. Use: pendente ou concluida." in resposta.text


@pytest.mark.parametrize("task_id", ["abc", "0", "-5", "99999999999999999999"])
def test_id_invalido_nunca_gera_500(client: TestClient, task_id: str) -> None:
    for metodo in ("get", "delete"):
        resposta = getattr(client, metodo)(f"/tasks/{task_id}")
        assert resposta.status_code == 422
        assert resposta.json()["erro"]["codigo"] == "DADOS_INVALIDOS"


def test_falha_do_banco_devolve_503_sem_vazar_detalhes(
    client_banco_quebrado: TestClient,
) -> None:
    resposta = client_banco_quebrado.get("/tasks")
    assert resposta.status_code == 503
    erro = resposta.json()["erro"]
    assert erro["codigo"] == "BANCO_INDISPONIVEL"
    assert "pasta-inexistente" not in resposta.text
    assert "sqlite" not in resposta.text.lower()
    assert client_banco_quebrado.get("/tasks").status_code == 503


def test_documentacao_openapi_esta_disponivel(client: TestClient) -> None:
    assert client.get("/docs").status_code == 200
    esquema = client.get("/openapi.json").json()
    assert set(esquema["paths"]) == {"/tasks", "/tasks/{task_id}", "/tasks/{task_id}/complete"}
