"""Classificador automático de prioridade: Jev (OpenRouter) com fallback local."""

import logging
from dataclasses import dataclass
from typing import Any, Protocol

import httpx

from app.core.config import Settings
from app.schemas.task import PrioritySource, TaskPriority

logger = logging.getLogger(__name__)

HIGH_KEYWORDS = ("urgente", "bloqueio", "produção", "prazo hoje", "incidente")
LOW_KEYWORDS = ("quando possível", "opcional", "ideia")

QUESTION_KEY = "priority"
CRITERIA = {
    TaskPriority.BAIXA.value: "Pode esperar; sem prazo ou impacto imediato.",
    TaskPriority.MEDIA.value: "Importante, mas sem urgência imediata.",
    TaskPriority.ALTA.value: "Urgente ou com impacto crítico; deve ser feita primeiro.",
}


@dataclass(frozen=True)
class PriorityResult:
    """Prioridade classificada e a origem dela (nunca `manual`)."""

    priority: TaskPriority
    source: PrioritySource


class PriorityClassifier(Protocol):
    """Contrato de um classificador de prioridade."""

    def classify(self, title: str, description: str | None) -> PriorityResult:
        """Classifica a prioridade de uma tarefa sem levantar exceção."""
        ...


class _JevFailure(Exception):
    """Falha ao obter uma resposta válida e confiável do Jev."""


def heuristic_priority(title: str, description: str | None) -> TaskPriority:
    """Estima a prioridade por palavras-chave, sem rede."""
    texto = f"{title} {description or ''}".casefold()
    if any(palavra in texto for palavra in HIGH_KEYWORDS):
        return TaskPriority.ALTA
    if any(palavra in texto for palavra in LOW_KEYWORDS):
        return TaskPriority.BAIXA
    return TaskPriority.MEDIA


class JevPriorityClassifier:
    """Classifica a prioridade com o Jev (API System One) e recorre ao fallback local."""

    def __init__(self, settings: Settings, client: httpx.Client | None = None) -> None:
        """Cria o classificador com as configurações e, opcionalmente, um cliente HTTP."""
        self._settings = settings
        self._client = client or httpx.Client()

    def classify(self, title: str, description: str | None) -> PriorityResult:
        """Devolve a prioridade do Jev ou, em qualquer falha, a do fallback local."""
        try:
            return PriorityResult(self._ask_jev(title, description), PrioritySource.JEV)
        except Exception as exc:  # noqa: BLE001 - classify nunca pode levantar exceção
            logger.warning("Falha no classificador Jev: %s", type(exc).__name__)
            return PriorityResult(self._fallback(title, description), PrioritySource.FALLBACK)

    def _fallback(self, title: str, description: str | None) -> TaskPriority:
        try:
            return heuristic_priority(title, description)
        except Exception:  # noqa: BLE001
            return TaskPriority.MEDIA

    def _ask_jev(self, title: str, description: str | None) -> TaskPriority:
        chave = self._settings.openrouter_api_key
        if chave is None or not chave.get_secret_value():
            raise _JevFailure("chave ausente")

        url = f"{self._settings.openrouter_base_url.rstrip('/')}/v1/systemone"
        headers = {"Authorization": f"Bearer {chave.get_secret_value()}"}
        payload = {
            "model": self._settings.jev_model,
            "state": {"title": title, "description": description or ""},
            "questions": {
                QUESTION_KEY: {
                    "type": "choice",
                    "instructions": "Qual a prioridade desta tarefa?",
                    "criteria": CRITERIA,
                }
            },
        }

        ultima_falha: Exception = _JevFailure("sem tentativas")
        for _ in range(self._settings.classifier_max_retries + 1):
            try:
                response = self._client.post(
                    url,
                    json=payload,
                    headers=headers,
                    timeout=self._settings.classifier_timeout_seconds,
                )
            except httpx.TransportError as exc:
                ultima_falha = exc
                continue
            if response.status_code >= 500 or response.status_code == 429:
                ultima_falha = _JevFailure(f"http {response.status_code}")
                continue
            if not response.is_success:
                raise _JevFailure(f"http {response.status_code}")
            return self._parse(response.json())
        raise ultima_falha

    def _parse(self, data: Any) -> TaskPriority:
        resposta = data["answers"][QUESTION_KEY]
        probabilidades = resposta.get("probabilities")
        if isinstance(probabilidades, dict) and probabilidades:
            escolha = max(probabilidades, key=lambda opcao: probabilidades[opcao])
        else:
            escolha = resposta["choice"]
        prioridade = TaskPriority(escolha)
        confianca = float(resposta["confidence"])
        if confianca < self._settings.jev_min_confidence:
            raise _JevFailure("confiança baixa")
        return prioridade
