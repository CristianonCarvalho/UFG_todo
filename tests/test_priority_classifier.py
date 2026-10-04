import json
import logging

import httpx
import pytest

from app.core.config import Settings
from app.schemas.task import PrioritySource, TaskPriority
from app.services.priority_classifier import (
    JevPriorityClassifier,
    PriorityResult,
    heuristic_priority,
)

OPCOES = ("baixa", "media", "alta")
NEUTRO = "Organizar a documentação"


def resposta_jev(escolha: str = "alta", confianca: float = 0.9) -> httpx.Response:
    probabilidades = {opcao: 0.05 for opcao in OPCOES}
    probabilidades[escolha] = 0.9
    corpo = {
        "answers": {
            "priority": {
                "type": "choice",
                "choice": escolha,
                "confidence": confianca,
                "probabilities": probabilidades,
            }
        }
    }
    return httpx.Response(200, json=corpo)


def criar(handler, api_key: str | None = "chave-teste", **ajustes) -> JevPriorityClassifier:
    settings = Settings(_env_file=None, openrouter_api_key=api_key, **ajustes)
    client = httpx.Client(transport=httpx.MockTransport(handler))
    return JevPriorityClassifier(settings, client)


def test_sucesso_usa_jev() -> None:
    classificador = criar(lambda request: resposta_jev("alta"))
    resultado = classificador.classify(NEUTRO, None)
    assert resultado == PriorityResult(TaskPriority.ALTA, PrioritySource.JEV)


def test_requisicao_tem_formato_esperado_e_so_titulo_e_descricao() -> None:
    capturadas: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        capturadas.append(request)
        return resposta_jev("media")

    criar(handler).classify("Meu título", "Minha descrição")
    request = capturadas[0]
    corpo = json.loads(request.content)
    assert request.url == "https://openrouter.ai/api/v1/systemone"
    assert request.headers["authorization"] == "Bearer chave-teste"
    assert corpo["model"] == "typesafe/jev-1.13"
    assert corpo["state"] == {"title": "Meu título", "description": "Minha descrição"}
    pergunta = corpo["questions"]["priority"]
    assert pergunta["type"] == "choice"
    assert set(pergunta["criteria"]) == set(OPCOES)


def test_timeout_usa_fallback() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("lento")

    resultado = criar(handler).classify(NEUTRO, None)
    assert resultado == PriorityResult(TaskPriority.MEDIA, PrioritySource.FALLBACK)


def test_http_500_e_depois_200_faz_retry() -> None:
    chamadas: list[int] = []

    def handler(request: httpx.Request) -> httpx.Response:
        chamadas.append(1)
        if len(chamadas) == 1:
            return httpx.Response(500)
        return resposta_jev("alta")

    resultado = criar(handler).classify(NEUTRO, None)
    assert resultado.source is PrioritySource.JEV
    assert len(chamadas) == 2


def test_http_500_em_todas_as_tentativas_usa_fallback() -> None:
    chamadas: list[int] = []

    def handler(request: httpx.Request) -> httpx.Response:
        chamadas.append(1)
        return httpx.Response(500)

    resultado = criar(handler).classify(NEUTRO, None)
    assert resultado.source is PrioritySource.FALLBACK
    assert len(chamadas) == 2


def test_http_429_faz_retry() -> None:
    chamadas: list[int] = []

    def handler(request: httpx.Request) -> httpx.Response:
        chamadas.append(1)
        return httpx.Response(429) if len(chamadas) == 1 else resposta_jev("baixa")

    resultado = criar(handler).classify(NEUTRO, None)
    assert resultado == PriorityResult(TaskPriority.BAIXA, PrioritySource.JEV)


def test_http_401_usa_fallback_sem_retry() -> None:
    chamadas: list[int] = []

    def handler(request: httpx.Request) -> httpx.Response:
        chamadas.append(1)
        return httpx.Response(401)

    resultado = criar(handler).classify(NEUTRO, None)
    assert resultado.source is PrioritySource.FALLBACK
    assert len(chamadas) == 1


def test_json_invalido_usa_fallback() -> None:
    resultado = criar(lambda request: httpx.Response(200, content=b"isto nao e json")).classify(
        NEUTRO, None
    )
    assert resultado.source is PrioritySource.FALLBACK


def test_resposta_sem_answers_priority_usa_fallback() -> None:
    for corpo in ({}, {"answers": {}}, {"answers": {"outra": {}}}, [], "texto"):
        resultado = criar(lambda request, c=corpo: httpx.Response(200, json=c)).classify(
            NEUTRO, None
        )
        assert resultado.source is PrioritySource.FALLBACK


def test_opcao_fora_das_permitidas_usa_fallback() -> None:
    corpo = {
        "answers": {
            "priority": {
                "type": "choice",
                "choice": "critica",
                "confidence": 0.9,
                "probabilities": {"critica": 0.9, "baixa": 0.1},
            }
        }
    }
    resultado = criar(lambda request: httpx.Response(200, json=corpo)).classify(NEUTRO, None)
    assert resultado.source is PrioritySource.FALLBACK


def test_confianca_abaixo_do_minimo_usa_fallback() -> None:
    resultado = criar(lambda request: resposta_jev("alta", confianca=0.3)).classify(NEUTRO, None)
    assert resultado == PriorityResult(TaskPriority.MEDIA, PrioritySource.FALLBACK)


@pytest.mark.parametrize("chave", [None, ""])
def test_chave_ausente_ou_vazia_nao_envia_requisicao(chave: str | None) -> None:
    chamadas: list[int] = []

    def handler(request: httpx.Request) -> httpx.Response:
        chamadas.append(1)
        return resposta_jev()

    resultado = criar(handler, api_key=chave).classify(NEUTRO, None)
    assert resultado.source is PrioritySource.FALLBACK
    assert chamadas == []


def test_heuristica_urgente_e_alta() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("sem rede")

    resultado = criar(handler).classify("Corrigir bug urgente", None)
    assert resultado == PriorityResult(TaskPriority.ALTA, PrioritySource.FALLBACK)


@pytest.mark.parametrize(
    ("titulo", "descricao", "esperado"),
    [
        ("URGENTE: ligar para o cliente", None, TaskPriority.ALTA),
        ("Erro em PRODUÇÃO", None, TaskPriority.ALTA),
        ("Revisar texto", "há um incidente aberto", TaskPriority.ALTA),
        ("Atualizar ícone", "fazer quando possível", TaskPriority.BAIXA),
        ("Uma ideia legal", None, TaskPriority.BAIXA),
        ("Organizar a documentação", None, TaskPriority.MEDIA),
    ],
)
def test_heuristica_por_palavras_chave(
    titulo: str, descricao: str | None, esperado: TaskPriority
) -> None:
    assert heuristic_priority(titulo, descricao) is esperado


def test_classify_nunca_levanta_excecao() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise RuntimeError("erro inesperado no transporte")

    resultado = criar(handler).classify(NEUTRO, None)
    assert resultado.source is PrioritySource.FALLBACK


def test_log_nao_expoe_chave_titulo_nem_descricao(caplog: pytest.LogCaptureFixture) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("lento")

    with caplog.at_level(logging.WARNING):
        criar(handler, api_key="chave-super-secreta").classify("TituloSigiloso", "DescSigilosa")
    assert caplog.records
    for proibido in ("chave-super-secreta", "TituloSigiloso", "DescSigilosa"):
        assert proibido not in caplog.text
